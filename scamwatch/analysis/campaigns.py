"""Find domain campaigns automatically: many names stamped out from one template.

Scam kits register names like fedex-vipbtb.shop, fedex-vipdsf.shop, fedex-vipmvbf.shop: same brand,
same ending, same shape, random letters in between. To find these without a human spotting them:

1. Reduce each name to its *shape*: keep the brand and known words, replace each run of other
   letters with '*' and each run of digits with '#', keep the separators and the ending.
       fedex-vipbtb.shop -> fedex-*.shop        usps.com-trackdqf.top -> usps.com-track*.top
       kcldhl.cc         -> *dhl.cc             dhl-tracking.live     -> dhl-tracking.live
2. Group names with the same shape. A group of 3 or more is a candidate campaign.
3. Describe it: the longest prefix all members share ('fedex-vip'), how many names, which registrars
   (from RDAP), and over how many days they appeared.

A shape like 'fedex*.com' could in principle collect unrelated names; the registrar and timing
columns are what let an analyst judge whether a group is one operation.
"""

from __future__ import annotations

import os
import re
from collections import Counter

import pandas as pd

from .features import BRANDS, brand_token
from .texts import registered_domain

_extract_suffix = None

# words kept as they are in a shape: brands, plus delivery words of 4+ letters (shorter ones such as
# 'pay' turn up by chance inside random strings)
WORDS = [
    "tracking", "track", "delivery", "deliver", "parcel", "package", "postal", "post", "express", "update",
    "support", "service", "services", "verify", "secure", "login", "entrega", "paket", "logistics", "logistic",
    "customs", "redelivery", "label", "help",
]  # fmt: skip
WHOLE = {"com", "www", "net", "org"}  # kept only as a whole part ('usps.com-track...')


def _suffix(fqdn: str) -> str:
    global _extract_suffix
    if _extract_suffix is None:
        import tldextract

        _extract_suffix = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)
    return _extract_suffix(fqdn).suffix


def shape(fqdn: str) -> str:
    """The template a name was stamped from (see module doc)."""
    fqdn = fqdn.lower().rstrip(".")
    if fqdn.startswith("www."):
        fqdn = fqdn[4:]
    suffix = _suffix(fqdn)
    head = fqdn[: -len(suffix) - 1] if suffix and fqdn.endswith("." + suffix) else fqdn
    words = [b for b in BRANDS if b != "ups"] + WORDS
    if brand_token(fqdn) == "UPS":
        words.append("ups")
    word_re = re.compile("|".join(sorted(map(re.escape, words), key=len, reverse=True)))
    out = []
    for part in re.split(r"([.\-_])", head):
        if part in ".-_" or part in WHOLE:
            out.append(part)
            continue
        pos = 0
        for m in word_re.finditer(part):
            out.append(_fill(part[pos : m.start()]))
            out.append(m.group(0))
            pos = m.end()
        out.append(_fill(part[pos:]))
    return "".join(out) + ("." + suffix if suffix else "")


def _fill(s: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"[a-z]+", "*", s))


def _common_prefix(names: list[str]) -> str:
    p = os.path.commonprefix(names)
    return p.rstrip(".-") if len(p) >= 3 else ""


def mine(domains: pd.DataFrame, registrations: pd.DataFrame | None = None, min_size: int = 3) -> pd.DataFrame:
    """domains: columns fqdn and seen (a timestamp). registrations: registered_domain, registrar, created_at.

    Returns one row per campaign (shape with at least min_size distinct registered names)."""
    d = domains.copy()
    d["fqdn"] = d.fqdn.str.lower().str.replace(r"^www\.", "", regex=True)
    d = d.drop_duplicates("fqdn")
    d["registered_domain"] = d.fqdn.map(registered_domain)
    d["template"] = d.fqdn.map(shape)
    d = d[d["template"].str.contains(r"\*|#")]  # a shape with nothing random in it is one name, not a template
    if registrations is not None and len(registrations):
        d = d.merge(registrations, on="registered_domain", how="left")
    else:
        d["registrar"], d["created_at"] = None, pd.NaT
    rows = []
    for sh, g in d.groupby("template"):
        if g.registered_domain.nunique() < min_size:
            continue
        regs = Counter(r for r in g.registrar.dropna())
        rows.append(
            {
                "template": sh,
                "prefix": _common_prefix(sorted(g.fqdn)),
                "names": int(g.registered_domain.nunique()),
                "first_seen": g.seen.min(),
                "last_seen": g.seen.max(),
                "days": int((g.seen.max() - g.seen.min()).days) + 1 if g.seen.notna().any() else None,
                "registrars": dict(regs.most_common(3)),
                "with_registration_data": int(g.registrar.notna().sum()),
                "examples": sorted(g.fqdn)[:4],
                "members": sorted(g.fqdn),
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values("names", ascending=False).reset_index(drop=True) if len(out) else out
