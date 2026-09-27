#!/usr/bin/env python3
"""Keep a produce type's quality head only if it passed on HELD-OUT test photos.

  python scripts/gate_quality_heads.py runs/<run>/eval_test_all.json runs/<run>/supported_heads.json \
      --out runs/<run>/supported_heads_gated.json

Training decides which heads have enough labels (supported_heads.json); this decides which ones are
good enough to show a score (docs/research/quality-score.md). Thresholds are the product bar, fixed
before looking at results:
  coarse good-vs-bad (freshness / visual_spoilage): balanced accuracy >= 0.85 and AUROC >= 0.90,
      with >= 30 good and >= 30 bad test photos
  ripeness: exact stage >= 0.70 and within one stage >= 0.95, with >= 100 test photos
A head with too few test photos fails (no evidence = no score).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

COARSE_MIN = {"balanced_accuracy": 0.85, "auroc": 0.90, "n_each": 30}
RIPENESS_MIN = {"accuracy": 0.70, "within_one_stage": 0.95, "n": 100}


def gate(quality: dict, supported: dict[str, list[str]]) -> tuple[dict[str, list[str]], list[dict]]:
    kept: dict[str, list[str]] = {}
    report = []
    for prod, heads in supported.items():
        for h in heads:
            base = h.split("~")[0]
            m = quality.get(base, {}).get(prod)
            if base == "ripeness":
                ok = bool(m) and m["n"] >= RIPENESS_MIN["n"] and m["accuracy"] >= RIPENESS_MIN["accuracy"] \
                    and m["within_one_stage"] >= RIPENESS_MIN["within_one_stage"]
            else:
                ok = bool(m) and min(m["n_good"], m["n_bad"]) >= COARSE_MIN["n_each"] \
                    and m["balanced_accuracy"] >= COARSE_MIN["balanced_accuracy"] and m["auroc"] >= COARSE_MIN["auroc"]
            report.append({"produce": prod, "head": h, "passed": ok, "metrics": m})
            if ok:
                kept.setdefault(prod, []).append(h)
    return {k: sorted(v) for k, v in kept.items()}, report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("eval_json", type=Path)
    ap.add_argument("supported_json", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    q = json.loads(a.eval_json.read_text()).get("quality_heads", {})
    kept, report = gate(q, json.loads(a.supported_json.read_text()))
    a.out.write_text(json.dumps(kept, indent=2))
    a.out.with_name(a.out.stem + "_report.json").write_text(json.dumps(report, indent=2))
    for r in report:
        m = r["metrics"] or {}
        brief = {k: round(v, 3) if isinstance(v, float) else v for k, v in m.items()}
        print(f"{'PASS' if r['passed'] else 'fail'}  {r['produce']:<12} {r['head']:<24} {brief}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
