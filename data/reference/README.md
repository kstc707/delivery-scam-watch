# Reference data (public carrier facts)

| File | What | Source | Licence / terms |
|---|---|---|---|
| `tracking_number_data/*.json` | FedEx, UPS, USPS and DHL tracking-number formats, check-digit rules and test numbers | [jkeen/tracking_number_data](https://github.com/jkeen/tracking_number_data), copied 2026-11-02 | MIT (`tracking_number_data/LICENSE`) |
| `brand_dns.json` | Each carrier's SPF and DMARC records and the domains its DNS authorises to send DMARC reports | Public DNS via Google Public DNS over HTTPS; refresh with `python -m scamwatch reference` | Public DNS records |

Facts taken from FedEx's public Track API specification (developer.fedex.com, read 2026-11-02) are
cited in `scamwatch/synthetic/genuine.py`; the specification itself is not copied into this repository.
fedex.com's own Trust Center pages block automated access from cloud servers and were not used.
