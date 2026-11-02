"""Turn one suspicious message into the record a fraud analyst would want, with the reasons spelled out.

This is the extraction step a carrier's fraud team runs on messages customers forward to them: pull out
every link, tracking number and phone number, check each against what the real company uses, and
score the message with transparent rules. Each rule that fires adds a reason, so an analyst can see
why a message was flagged instead of trusting an opaque score.

  signal                                   points   why
  link to a domain the brand does not own     +3     genuine notifications link to the carrier's own site
  link domain matches a blocklisted template  +2     same kit as known scams (campaigns.py)
  tracking number fails its check digit       +2     a made-up number
  'reply Y' / copy-the-link trick             +2     switching on links the phone disabled
  names a carrier, quotes no valid number     +1     genuine notifications are built around one
  asks to fix an address or pay a fee         +1     the two lures real scams use most
  urgency ('within 24 hours', 'final notice') +1
  only official links and a valid number      -3     what a genuine notification looks like

  score >= 3: likely scam · 1-2: review · <= 0: looks genuine
"""

from __future__ import annotations

import re

from . import tracking
from .campaigns import shape
from .texts import (
    REPLY_TRICK,
    URGENCY,
    brand_in_text,
    extract_urls,
    host_of,
    lure_of,
    registered_domain,
)

PHONE = re.compile(r"(?:\+\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")


def triage(text: str, official: dict[str, set[str]], blocklist_templates: set[str] | None = None) -> dict:
    blocklist_templates = blocklist_templates or set()
    brand = brand_in_text(text)
    urls = extract_urls(text)
    hosts = [host_of(u) for u in urls]
    owned = set().union(*official.values()) if official else set()
    official_links = [h for h in hosts if registered_domain(h) in owned]
    foreign_links = [h for h in hosts if registered_domain(h) not in owned]
    numbers = tracking.find(text)
    number_digits = {n["number"] for n in numbers}
    phones = [p for p in (m.group(0) for m in PHONE.finditer(text)) if re.sub(r"\D", "", p) not in number_digits]
    valid_for = sorted({c for n in numbers for c in n["valid_for"]})
    # fails = fits a carrier format whose check digit is wrong; formats without a check digit can't fail
    failing = [n["number"] for n in numbers if n["fits"] and all(f["check_digit_ok"] is False for f in n["fits"])]
    lure = lure_of(text)

    reasons: list[tuple[str, int]] = []
    if foreign_links:
        reasons.append((f"links to a domain the carriers do not own ({len(foreign_links)})", 3))
    if any(shape(h) in blocklist_templates for h in foreign_links):
        reasons.append(("link matches a blocklisted scam template", 2))
    if failing:
        reasons.append(("tracking number fails its check digit", 2))
    if REPLY_TRICK.search(text):
        reasons.append(("asks to reply or copy the link", 2))
    if brand and brand not in valid_for:
        reasons.append((f"names {brand} but quotes no valid {brand} tracking number", 1))
    if lure in ("update address", "pay a fee"):
        reasons.append((f"lure: {lure}", 1))
    if URGENCY.search(text):
        reasons.append(("urgency", 1))
    if official_links and not foreign_links and valid_for:
        reasons.append(("only official links and a valid tracking number", -3))
    score = sum(p for _, p in reasons)
    return {
        "brand": brand,
        "links": hosts,
        "official_links": official_links,
        "tracking_numbers": numbers,
        "valid_tracking_for": valid_for,
        "phones": phones,
        "lure": lure,
        "score": score,
        "verdict": "likely scam" if score >= 3 else "review" if score >= 1 else "looks genuine",
        "reasons": [r for r, _ in reasons],
    }
