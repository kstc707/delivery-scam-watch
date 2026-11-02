"""Carrier facts: tracking-number formats, carrier DNS, message triage, spec-based genuine messages."""

from __future__ import annotations

import json

from scamwatch.analysis import tracking
from scamwatch.analysis.official import official_domains, parse
from scamwatch.analysis.triage import triage
from scamwatch.collectors.dnscheck import classify
from scamwatch.synthetic.genuine import generate


def test_every_published_test_number_is_read_correctly():
    """The tracking_number_data project ships valid and invalid examples for each format."""
    checked = 0
    for code in tracking.CARRIERS:
        for fmt in json.loads((tracking.DATA / f"{code}.json").read_text())["tracking_numbers"]:
            for n in fmt.get("test_numbers", {}).get("valid", []):
                hit = [h for h in tracking.identify(n) if h["format"] == fmt["name"]]
                assert hit and hit[0]["check_digit_ok"] in (True, None), (fmt["name"], n)
                checked += 1
            for n in fmt.get("test_numbers", {}).get("invalid", []):
                hit = [h for h in tracking.identify(n) if h["format"] == fmt["name"]]
                assert not hit or hit[0]["check_digit_ok"] is False, (fmt["name"], n)
                checked += 1
    assert checked >= 130


def test_made_up_fedex_number_fails_and_generated_one_passes():
    assert tracking.find("FedEx: package 276022486774 is held")[0]["valid_for"] == []
    good = tracking.make_fedex_express("12345678901")
    assert tracking.identify(good)[0]["check_digit_ok"] is True
    assert tracking.find("Call +1 (202) 988-9294 now") == []  # phone numbers are not tracking numbers


def test_dns_parsing_and_owned_domains():
    info = parse(["v=spf1 include:x.example -all", "fedexfreight.com._report._dmarc.fedex.com", "other"])
    assert info["spf_strict"] and info["dmarc_report_domains"] == ["fedexfreight.com"]
    owned = official_domains()
    assert "fedex.com" in owned["FedEx"] and "usps.com" in owned["USPS"]
    assert classify({"Status": 3}) == "nxdomain" and classify({"Status": 0}) == "exists"


def test_triage_flags_a_real_scam_shape_and_passes_a_genuine_shape():
    owned = official_domains()
    scam = triage(
        "USPS: The package cannot be delivered due to incomplete address. Reply Y then open usps-help.top/x", owned
    )
    assert scam["verdict"] == "likely scam"
    assert any("do not own" in r for r in scam["reasons"]) and any("reply" in r for r in scam["reasons"])
    real = generate(4)
    for g in real:
        assert triage(g["text"], owned)["verdict"] == "looks genuine", g["text"]


def test_genuine_generator_uses_valid_numbers_and_all_four_events():
    msgs = generate(40)
    assert {m["event"] for m in msgs} == {"ON_TENDER", "ON_ESTIMATED_DELIVERY", "ON_EXCEPTION", "ON_DELIVERY"}
    for m in msgs:
        nums = tracking.find(m["text"])
        assert nums and "FedEx" in nums[0]["valid_for"]
