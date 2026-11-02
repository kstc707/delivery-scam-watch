"""Which domains really belong to each carrier, from the carriers' own public DNS records.

A company's DNS says a lot about its legitimate email and web estate:
  - SPF (a TXT record starting 'v=spf1') lists the servers allowed to send its email;
  - DMARC (TXT at _dmarc.<domain>) says what receivers should do with email that fails those checks:
    p=reject means 'throw it away', which makes spoofing the real domain pointless and pushes
    scammers to lookalike domains and text messages instead;
  - '<other-domain>._report._dmarc.<domain>' records authorise another domain to send DMARC reports
    to this one. They are published only for domains the company runs or works with, so they are a
    data-driven list of related domains (for FedEx: fedexfreight.com, fedexdataworks.com, ...).

`refresh()` reads these records through Google's public DNS-over-HTTPS service and saves a dated
snapshot in data/reference/brand_dns.json; `official_domains()` merges the snapshot with the hand
allowlist in config/brands.yaml.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx

from ..config import PROJECT_ROOT, load_brands
from .texts import registered_domain

SNAPSHOT = PROJECT_ROOT / "data" / "reference" / "brand_dns.json"
APEX = {"FedEx": "fedex.com", "UPS": "ups.com", "USPS": "usps.com", "DHL": "dhl.com"}
DOH = "https://dns.google/resolve"


def _txt(client: httpx.Client, name: str) -> list[str]:
    r = client.get(DOH, params={"name": name, "type": "TXT"})
    r.raise_for_status()
    return [a["data"].strip('"') for a in r.json().get("Answer", []) if a.get("type") == 16]


def _dmarc(client: httpx.Client, domain: str, hops: int = 3) -> str | None:
    """DMARC record, following a CNAME-style alias (FedEx points _dmarc at infosec.fedex.com)."""
    name = f"_dmarc.{domain}"
    for _ in range(hops):
        r = client.get(DOH, params={"name": name, "type": "TXT"}).json()
        for a in r.get("Answer", []):
            if a.get("type") == 16 and a["data"].strip('"').lower().startswith("v=dmarc1"):
                return a["data"].strip('"')
        alias = [a["data"].rstrip(".") for a in r.get("Answer", []) if a.get("type") == 5]
        if not alias:
            return None
        name = alias[0]
    return None


def parse(records: list[str]) -> dict:
    spf = next((r for r in records if r.lower().startswith("v=spf1")), None)
    reporters = sorted({r.split("._report._dmarc")[0] for r in records if "._report._dmarc" in r})
    return {
        "spf": spf,
        "spf_strict": bool(spf and spf.rstrip().endswith("-all")),
        "dmarc_report_domains": reporters,
        "txt_records": len(records),
    }


def refresh(client: httpx.Client | None = None) -> dict:
    own = client is None
    client = client or httpx.Client(timeout=20)
    try:
        out = {"fetched_at": datetime.now(UTC).isoformat(timespec="seconds"), "source": DOH, "brands": {}}
        for brand, apex in APEX.items():
            info = parse(_txt(client, apex))
            info["apex"] = apex
            info["dmarc"] = _dmarc(client, apex)
            info["dmarc_policy"] = next(
                (p.split("=", 1)[1].strip() for p in (info["dmarc"] or "").split(";") if p.strip().startswith("p=")),
                None,
            )
            out["brands"][brand] = info
    finally:
        if own:
            client.close()
    SNAPSHOT.write_text(json.dumps(out, indent=2))
    return out


def official_domains() -> dict[str, set[str]]:
    """Registered domains each brand really owns: hand allowlist + DMARC report domains from DNS."""
    snap = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else {"brands": {}}
    out: dict[str, set[str]] = {}
    for b in load_brands():
        doms = {registered_domain(d) for d in b.allowlist}
        info = snap["brands"].get(b.name, {})
        doms |= {registered_domain(d) for d in info.get("dmarc_report_domains", [])}
        if info.get("apex"):
            doms.add(info["apex"])
        out[b.name] = doms
    return out
