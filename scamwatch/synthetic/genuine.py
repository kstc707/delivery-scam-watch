"""Genuine-style FedEx notifications built from FedEx's published Track API specification.

What comes from FedEx's spec (developer.fedex.com, Track API, read 2026-11-02):
  - the four notification events: ON_TENDER, ON_ESTIMATED_DELIVERY, ON_EXCEPTION, ON_DELIVERY;
  - status codes (PU picked up, OC label created, DE delivery exception, HL hold at location, DL);
  - a genuine customs note exists (CLEARANCE_ENTRY_FEE_APPLIES), so real messages can mention fees;
  - every notification is about a tracking number (here FedEx Express 12-digit numbers with a correct
    check digit, see tracking.make_fedex_express).
What is assumed: the exact wording, and that links go to https://www.fedex.com/fedextrack/?trknbr=...
(the tracking path fedex.com's robots.txt lists). Real FedEx messages from a phone should replace or
extend these; until then this set is a labelled sanity check for false alarms, not ground truth.

Hard cases are included on purpose: genuine exceptions about an address problem and genuine customs
fees, because those are exactly the stories scams copy.
"""

from __future__ import annotations

import random
import string

from ..analysis.tracking import make_fedex_express

SEED = 20261102
LINK = "https://www.fedex.com/fedextrack/?trknbr={n}"

TEMPLATES = {
    "ON_TENDER": [
        "FedEx: Your package {n} was picked up and is on its way. Track: {link}",
        "FedEx: A label was created for your shipment {n}. We'll let you know when it's picked up. {link}",
    ],
    "ON_ESTIMATED_DELIVERY": [
        "FedEx: Your package {n} is scheduled for delivery {day} by end of day. Track: {link}",
        "FedEx: Delivery update for {n}. Estimated delivery {day} between {start} and {end}. {link}",
    ],
    "ON_EXCEPTION": [
        "FedEx: There's a delay with package {n}. New estimated delivery {day}. Details: {link}",
        "FedEx: Delivery exception for {n}: we couldn't access the delivery location. We'll try again {day}. {link}",
        # hard cases: real address problems and real customs fees
        "FedEx: Delivery exception for {n}: incorrect address. Review delivery options at {link}",
        "FedEx: Your international shipment {n} has duties and taxes due before release. Details: {link}",
    ],
    "ON_DELIVERY": [
        "FedEx: Your package {n} was delivered {day} at {start}. Proof of delivery: {link}",
        "FedEx: Delivered: {n}, left at front door. {link}",
    ],
}


def generate(n: int = 200, seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    days = ["today", "tomorrow", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    events = list(TEMPLATES)
    out = []
    for i in range(n):
        event = events[i % len(events)]
        number = make_fedex_express("".join(rng.choices(string.digits, k=11)))
        start = rng.randint(8, 16)
        text = rng.choice(TEMPLATES[event]).format(
            n=number, link=LINK.format(n=number), day=rng.choice(days), start=f"{start}:00", end=f"{start + 3}:00"
        )
        out.append({"text": text, "event": event, "label": "genuine (spec-based, wording assumed)"})
    return out
