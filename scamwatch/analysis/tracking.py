"""Find tracking numbers in a message and check them against each carrier's real number formats.

Every FedEx, UPS, USPS and DHL tracking number follows a published format and most end in a check
digit computed from the other digits (the same idea as the last digit of a credit card number). A
genuine notification is built around a real tracking number; a scam text usually quotes none, or a
made-up one that fails the check digit.

The formats and check-digit rules come from the open-source tracking_number_data project (MIT
licence, copied into data/reference/tracking_number_data/ with its licence). Its own test numbers
are used in tests/test_fedex.py to prove this code reads them correctly.

Check-digit methods used by the carriers:
  mod10       weight the digits alternately (for example 3 and 1), add them up, and the check digit
              is what brings the total to the next multiple of 10
  weighted    multiply each digit by a fixed weight (FedEx Express: 3, 1, 7, 3, 1, 7, ...), add up,
              take the remainder after dividing by 11, then by 10
  mod7        the serial number's remainder after dividing by 7 (DHL Express)
"""

from __future__ import annotations

import json
import re
from functools import cache

from ..config import PROJECT_ROOT

DATA = PROJECT_ROOT / "data" / "reference" / "tracking_number_data"
CARRIERS = {"fedex": "FedEx", "ups": "UPS", "usps": "USPS", "dhl": "DHL"}

# long digit runs (spaces or dashes allowed between digits) and UPS's 1Z... numbers
CANDIDATE = re.compile(r"(?<![\w/.+])(1Z[0-9A-Z]{16}|\d(?:[ -]?\d){9,33})(?![\w/])", re.I)
PHONE_SHAPE = re.compile(r"^(?:\+?\d{1,3}[ -])?\(?\d{3}\)?[ -]?\d{3}[ -]?\d{4}$")


def _python_regex(r) -> re.Pattern:
    r = "".join(r) if isinstance(r, list) else r
    return re.compile("^" + re.sub(r"\(\?<(\w+)>", r"(?P<\1>", r) + "$")  # Ruby-style named groups -> Python


@cache
def formats() -> list[tuple[str, str, re.Pattern, dict]]:
    out = []
    for code in CARRIERS:
        for t in json.loads((DATA / f"{code}.json").read_text())["tracking_numbers"]:
            out.append((code, t["name"], _python_regex(t["regex"]), t.get("validation", {})))
    return out


def _mod10(seq: str, rule: dict) -> int:
    if rule.get("reverse"):
        seq = seq[::-1]
    total = 0
    for i, ch in enumerate(seq):
        x = int(ch) if ch.isdigit() else (ord(ch) - 3) % 10
        total += x * (rule["odds_multiplier"] if i % 2 == 1 else rule["evens_multiplier"])
    return (10 - total % 10) % 10


def check_digit_ok(validation: dict, serial: str, check: str) -> bool | None:
    rule = validation.get("checksum")
    if not rule or not serial or not check:
        return None  # this format has no check digit
    if rule["name"] == "mod10":
        return _mod10(serial, rule) == int(check)
    if rule["name"] == "mod7":
        return int(serial) % 7 == int(check)
    if rule["name"] == "sum_product_with_weightings_and_modulo":
        total = sum(int(c) * w for c, w in zip(serial, rule["weightings"], strict=False))
        return total % rule["modulo1"] % rule["modulo2"] == int(check)
    return None


def identify(number: str) -> list[dict]:
    """Every carrier format a number fits, and whether its check digit is right."""
    s = re.sub(r"[\s-]+", "", number).upper()
    hits = []
    for code, name, rx, validation in formats():
        m = rx.match(s)
        if not m:
            continue
        g = {k: re.sub(r"\s", "", v or "") for k, v in m.groupdict().items()}
        serial, check = g.get("SerialNumber", ""), g.get("CheckDigit", "")
        prepend = validation.get("serial_number_format", {}).get("prepend_if")
        if prepend and re.match(prepend["matches_regex"], serial):
            serial = prepend["content"] + serial
        hits.append(
            {"carrier": CARRIERS[code], "format": name, "check_digit_ok": check_digit_ok(validation, serial, check)}
        )
    return hits


def find(text: str) -> list[dict]:
    """Tracking-number candidates in a message. Phone-number shapes are skipped."""
    out = []
    for m in CANDIDATE.finditer(text or ""):
        raw = m.group(0)
        if PHONE_SHAPE.match(raw.strip()):
            continue
        hits = identify(raw)
        out.append(
            {
                "number": re.sub(r"[\s-]+", "", raw),
                "fits": hits,
                "valid_for": sorted({h["carrier"] for h in hits if h["check_digit_ok"]}),
            }
        )
    return out


def make_fedex_express(serial11: str) -> str:
    """A FedEx Express 12-digit number with a correct check digit (for spec-based test messages)."""
    weights = [3, 1, 7, 3, 1, 7, 3, 1, 7, 3, 1]
    total = sum(int(c) * w for c, w in zip(serial11, weights, strict=True))
    return serial11 + str(total % 11 % 10)
