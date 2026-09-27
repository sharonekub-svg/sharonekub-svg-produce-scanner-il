"""Side-by-side of Phase-4 follow-up runs on identical test rows (docs/results.md)."""
import json
import sys
from pathlib import Path

def g(p, *ks):
    try:
        d = json.loads(Path(p).read_text())
        for k in ks:
            d = d[k]
        return d
    except (FileNotFoundError, KeyError, TypeError):
        return None

def recall(run, name):
    h = g(f"{run}/eval_test_look.json", "heads", "produce")
    if not h:
        return None
    return h.get("per_class", {}).get(name, {}).get("recall")

print(f"{'run':<34}{'top1':>7}{'mF1':>7}{'worst':>7}{'shown':>7}{'accOK':>7}{'lookAbst':>9}{'lookE':>7}{'warmF1':>8}{'warmOK':>8}")
for run in sys.argv[1:]:
    L = f"{run}/eval_test_look.json"; W = f"{run}/eval_test_warm.json"
    row = [g(L, "heads", "produce", "top1"), g(L, "heads", "produce", "macro_f1"), g(L, "heads", "produce", "worst_class_recall"),
           g(L, "decision", "in_dist_coverage_ok"), g(L, "decision", "in_dist_accuracy_when_ok"),
           g(L, "ood", "ood_abstention_rate"), g(L, "ood", "auroc", "energy"),
           g(W, "heads", "produce", "macro_f1"), g(W, "decision", "in_dist_accuracy_when_ok")]
    print(f"{'/'.join(Path(run).parts[-2:]):<34}" + "".join(f"{(f'{v:.3f}' if isinstance(v, float) else '-'):>8}" for v in row))
