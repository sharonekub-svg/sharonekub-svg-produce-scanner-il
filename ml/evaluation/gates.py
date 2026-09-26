"""Acceptance gates: a model is not 'better' because its overall accuracy is higher.

Gate config (YAML `gates:` block) example:
  produce:
    min_macro_f1: 0.85
    min_class_recall: {default: 0.80, banana: 0.90, avocado: 0.90}
    max_ece: 0.05
"""
from __future__ import annotations


def check_gates(summary_by_head: dict[str, dict], gates: dict[str, dict]) -> list[str]:
    """Return a list of human-readable failures (empty = pass)."""
    failures = []
    for head, g in gates.items():
        s = summary_by_head.get(head)
        if s is None or s["n"] == 0:
            failures.append(f"{head}: no evaluable samples")
            continue
        if "min_macro_f1" in g and s["macro_f1"] < g["min_macro_f1"]:
            failures.append(f"{head}: macro_f1 {s['macro_f1']:.3f} < {g['min_macro_f1']}")
        if "max_ece" in g and s["ece"] > g["max_ece"]:
            failures.append(f"{head}: ece {s['ece']:.3f} > {g['max_ece']}")
        mcr = g.get("min_class_recall")
        if mcr:
            default = mcr.get("default")
            for cls, stats in s["per_class"].items():
                thr = mcr.get(cls, default)
                if thr is None or not stats["support"]:
                    continue
                if stats["recall"] < thr:
                    failures.append(f"{head}/{cls}: recall {stats['recall']:.3f} < {thr} (n={int(stats['support'])})")
    return failures
