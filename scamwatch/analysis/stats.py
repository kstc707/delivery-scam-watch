"""Statistics for the headline numbers: how sure we are, and whether a difference is real.

Two tools, both standard and easy to explain:

- Wilson interval for a share ("35 of 47 are likely scams"). It gives the range the true share
  probably lies in (95% confidence). Unlike the textbook "p +/- 1.96 * SE" interval it stays inside
  0-100% and behaves well for small samples and shares near 0% or 100%, which is exactly our case.
- Chi-square test of independence for "do these two groups have the same mix?" (real lures vs our
  assumed lures, text-message link endings vs blocklist endings). It gives a p-value: the chance of
  a difference at least this large if the two groups really had the same mix. Cramér's V says how
  big the difference is (0 = none, 1 = completely different), because with big samples even a tiny
  difference gets a small p-value. When a 2x2 table has small counts, Fisher's exact test is used
  instead, since chi-square's approximation breaks down there.
"""

from __future__ import annotations

import math
from collections import Counter

import numpy as np
from scipy.stats import chi2_contingency, fisher_exact


def wilson(k: int, n: int, z: float = 1.96) -> dict:
    """Share k/n with its 95% Wilson interval."""
    if n <= 0:
        return {"k": k, "n": n, "share": None, "low": None, "high": None}
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return {"k": int(k), "n": int(n), "share": round(p, 3), "low": round(max(0.0, centre - half), 3),
            "high": round(min(1.0, centre + half), 3)}  # fmt: skip


def _table(a: list, b: list, top: int | None = None) -> tuple[list[str], np.ndarray]:
    """Two lists of category labels -> (categories, 2 x K count table). Rare categories pooled as 'other'."""
    ca, cb = Counter(a), Counter(b)
    cats = [c for c, _ in (ca + cb).most_common()]
    if top is not None and len(cats) > top:
        keep = set(cats[:top])
        a = [x if x in keep else "other" for x in a]
        b = [x if x in keep else "other" for x in b]
        ca, cb = Counter(a), Counter(b)
        cats = [c for c, _ in (ca + cb).most_common()]
    return cats, np.array([[ca[c] for c in cats], [cb[c] for c in cats]])


def compare_mix(a: list, b: list, labels: tuple[str, str], top: int | None = 8) -> dict:
    """Do groups a and b have the same mix of categories?"""
    cats, t = _table(a, b, top)
    t = t[:, t.sum(axis=0) > 0]
    out = {
        "groups": {labels[0]: int(t[0].sum()), labels[1]: int(t[1].sum())},
        "categories": cats,
        "counts": {labels[0]: t[0].tolist(), labels[1]: t[1].tolist()},
    }
    if t.shape[1] < 2 or min(t.sum(axis=1)) == 0:
        return {**out, "test": None, "p_value": None, "note": "not enough data to test"}
    if t.shape[1] == 2 and (t < 5).any():
        _, p = fisher_exact(t)
        return {**out, "test": "Fisher exact", "p_value": float(p)}
    chi2, p, dof, expected = chi2_contingency(t)
    v = math.sqrt(chi2 / (t.sum() * (min(t.shape) - 1)))
    note = "some expected counts are below 5; treat the p-value as rough" if (expected < 5).any() else None
    return {**out, "test": "chi-square", "chi2": round(float(chi2), 2), "dof": int(dof), "p_value": float(p),
            "cramers_v": round(v, 3), "note": note}  # fmt: skip


def p_text(p: float | None) -> str:
    """Plain-language p-value for the page: 'p < 0.001' or 'p = 0.04'."""
    if p is None:
        return "not tested"
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}" if p < 0.01 else f"p = {p:.2f}"
