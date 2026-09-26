"""Inter-rater agreement for labelling QA (numpy only)."""
from __future__ import annotations

from collections import defaultdict
from typing import Sequence

import numpy as np


def cohen_kappa(a: Sequence[str], b: Sequence[str], categories: Sequence[str], weights: str | None = None) -> float:
    """Cohen's kappa. weights=None (nominal) or 'quadratic' (ordinal; categories in order)."""
    idx = {c: i for i, c in enumerate(categories)}
    k = len(categories)
    m = np.zeros((k, k))
    for x, y in zip(a, b):
        m[idx[x], idx[y]] += 1
    n = m.sum()
    if n == 0:
        return float("nan")
    if weights is None:
        w = 1 - np.eye(k)
    elif weights == "quadratic":
        i, j = np.meshgrid(np.arange(k), np.arange(k), indexing="ij")
        w = ((i - j) ** 2) / max(1, (k - 1) ** 2)
    else:
        raise ValueError(weights)
    expected = np.outer(m.sum(1), m.sum(0)) / n
    denom = (w * expected).sum()
    return float(1 - (w * m).sum() / denom) if denom else 1.0


def pairwise_from_rows(rows: list[dict], item_key: str, head: str, annotator_key: str = "annotator") -> tuple[list[str], list[str]]:
    """Collect (label_a, label_b) for items graded by >= 2 annotators (first two, sorted by name).
    Empty labels (unknown) are skipped."""
    by_item: dict[str, dict[str, str]] = defaultdict(dict)
    for r in rows:
        v = (r.get(head) or "").strip()
        if v and "|" not in v:
            by_item[r[item_key]][r[annotator_key]] = v
    a, b = [], []
    for grades in by_item.values():
        if len(grades) >= 2:
            names = sorted(grades)
            a.append(grades[names[0]])
            b.append(grades[names[1]])
    return a, b
