"""Build the static dashboard (dashboard/index.html) from outputs/results.json.

The page is one HTML file: dashboard/template.html with the numbers dropped in as a JSON object.
No database is needed, so the scheduled job can rebuild it right after `report`, and Vercel serves
whatever is committed.
"""

from __future__ import annotations

import json

from .config import PROJECT_ROOT

TEMPLATE = PROJECT_ROOT / "dashboard" / "template.html"
PAGE = PROJECT_ROOT / "dashboard" / "index.html"
RESULTS = PROJECT_ROOT / "outputs" / "results.json"

STREAM_KEYS = [
    "days_covered",
    "keyword_domains",
    "after_stage1_rule",
    "infrastructure_suppressed",
    "after_infrastructure_filter",
    "after_stage2_model",
    "model_threshold",
    "review_counts",
    "analyst_hours_per_month",
    "likely_scams_not_on_any_blocklist",
]


def page_data(res: dict) -> dict:
    """Reshape the report into what the page's script reads (short keys keep the page small)."""
    ex, st = res["experiment"], res["stream"]
    det = res["detector_brand_scope"]
    sources = {
        name: {"runs": s["runs"], "seen": s["items_scanned_or_matched"], "stored": s["stored"]}
        for name, s in res["collection"]["sources"].items()
        if name != "selftest"
    }
    if "rdap" in sources:
        sources["rdap"]["stored"] = res["registrations"].get("looked_up", 0)
    if "smishtank" in sources and res.get("texts"):
        sources["smishtank"]["stored"] = res["texts"]["messages"]
    return {
        "generated": res["generated_at"],
        "labelled": res["labelled"],
        "stream": {k: st[k] for k in STREAM_KEYS if k in st},
        "rows": [
            {
                "d": r["fqdn"],
                "b": r["brand"],
                "r": r["review"],
                "t": r["first_signal"],
                "s": r["score"],
                "c": r.get("campaign"),
            }
            for r in st["rows"]
        ],
        "patterns": ex["pattern_shares"],
        "endings": ex["endings"],
        "aucA": ex["real_vs_A_auc"],
        "aucB": ex["real_vs_B_auc"],
        "curve": [
            {"n": c["real_labels"], **{k: c[k]["recall_at_95_precision"] for k in ("real_only", "real+A", "real+B")}}
            for c in ex["curve"]
        ],
        "detector": {"lab": det["grouped_cv"]["gbm"], "lobo": det["leave_one_brand_out"]},
        "regs": res["registrations"],
        "sources": sources,
        "bExamples": ex["generator_B_examples"],
        "texts": res.get("texts") or None,
        "campaigns": res.get("campaigns"),
        "intervals": res.get("intervals"),
        "triage": res.get("triage"),
    }


def build() -> str:
    res = json.loads(RESULTS.read_text())
    data = json.dumps(page_data(res), separators=(",", ":")).replace("</", "<\\/")  # never closes the script tag
    html = TEMPLATE.read_text().replace("__DATA__", data, 1)
    PAGE.write_text(html)
    return str(PAGE)
