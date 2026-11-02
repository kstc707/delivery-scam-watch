"""Statistics helpers and automatic domain-campaign mining."""

from __future__ import annotations

import pandas as pd

from scamwatch.analysis.campaigns import mine, shape
from scamwatch.analysis.stats import compare_mix, p_text, wilson


def test_wilson_interval_matches_known_values():
    w = wilson(35, 47)
    assert w["share"] == 0.745 and 0.60 < w["low"] < 0.61 and 0.84 < w["high"] < 0.85
    edge = wilson(22, 22)  # 100%: the interval must still say 'not certain'
    assert edge["high"] == 1.0 and edge["low"] < 0.9
    assert wilson(0, 0)["share"] is None


def test_compare_mix_detects_a_real_difference_and_not_a_fake_one():
    big = compare_mix(["a"] * 80 + ["b"] * 20, ["a"] * 20 + ["b"] * 80, ("x", "y"))
    assert big["test"] == "chi-square" and big["p_value"] < 0.001 and big["cramers_v"] > 0.5
    same = compare_mix(["a"] * 50 + ["b"] * 50, ["a"] * 50 + ["b"] * 50, ("x", "y"))
    assert same["p_value"] > 0.9
    small = compare_mix(["a"] * 3 + ["b"], ["b"] * 4, ("x", "y"))
    assert small["test"] == "Fisher exact"
    assert p_text(0.0001) == "p < 0.001" and p_text(None) == "not tested"


def test_shapes_keep_brand_words_and_ending():
    assert shape("fedex-vipbtb.shop") == "fedex-*.shop"
    assert shape("usps.com-trackdqf.top") == "usps.com-track*.top"
    assert shape("kcldhl.cc") == "*dhl.cc"
    assert shape("dhlzjw661.cfd") == "dhl*#.cfd"
    assert shape("www.uspss.org") == shape("uspss.org")
    assert shape("dhl-tracking.live") == "dhl-tracking.live"  # nothing random: a one-off name


def test_mining_rediscovers_the_series_we_first_spotted_by_eye():
    t = pd.Timestamp("2026-10-26", tz="UTC")
    names = ["fedex-vipbtb.shop", "fedex-vipdsf.shop", "fedex-vipmvbf.shop", "fedex-vipvujg.shop",
             "dhl-tracking.live", "fedexkfj.com", "fedexqwq.com", "imports-dhl.com"]  # fmt: skip
    regs = pd.DataFrame(
        {
            "registered_domain": ["fedex-vipbtb.shop", "fedex-vipdsf.shop"],
            "registrar": ["GNAME", "GNAME"],
            "created_at": [t, t],
        }  # fmt: skip
    )
    m = mine(pd.DataFrame({"fqdn": names, "seen": [t] * len(names)}), regs)
    assert list(m.template) == ["fedex-*.shop"]  # fedex*.com has only 2 names, below the minimum of 3
    row = m.iloc[0]
    assert row.prefix == "fedex-vip" and row.names == 4 and row.registrars == {"GNAME": 2}
