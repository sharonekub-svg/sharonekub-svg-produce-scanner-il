#!/usr/bin/env python3
"""Generate decision-parity fixtures: Python decide() outputs the TypeScript port must reproduce.

  python scripts/gen_decision_fixtures.py [--n 600]
  -> app/__tests__/fixtures/decision_cases.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.common.taxonomy import HEADS, load_taxonomy  # noqa: E402
from ml.inference.decision import DEFAULT_THRESHOLDS, decide  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=8)
    args = ap.parse_args()
    tax = load_taxonomy()
    rng = np.random.default_rng(args.seed)
    bundle = {"bundle_version": 1, "model_id": "fixture", "outputs": {h: list(tax.classes(h)) for h in HEADS},
              "produce_meta": tax.produce_meta, "label_he": tax.label_he, "temperatures": {},
              "thresholds": {**DEFAULT_THRESHOLDS, "ood_min_energy": 2.0,
                             "condition_abstain": {"apple": 0.9, "strawberry": 0.7, "orange": 0.8},
                             "condition_max_p": 0.86, "condition_max_p_graded": 0.744,
                             "condition_max_p_type": {"kiwi": 0.86}},
              "supported_heads": {"banana": ["freshness", "ripeness", "visual_spoilage"],
                                  "avocado": ["ripeness", "visual_spoilage~coarse"], "apple": ["freshness", "condition"],
                                  "orange": ["freshness~coarse", "visual_spoilage~coarse", "condition~graded"],
                                  "pomegranate": ["visual_spoilage~coarse"],
                                  "strawberry": ["freshness", "ripeness", "condition"],
                                  "kiwi": ["condition~graded"], "tomato": ["freshness~general", "condition~graded"]},
              "input": {"size": 224, "mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225],
                        "resize": "short_side_then_center_crop", "resize_ratio": 1.14}}
    focus = [tax.produce.index(p) for p in ("banana", "avocado", "apple", "tomato", "other", "kiwi", "orange", "pomegranate",
                                            "strawberry")]
    cases = []
    for k in range(args.n):
        probs = {}
        for h in HEADS:
            n = tax.num_classes(h)
            sharp = rng.uniform(0.2, 6.0)
            logits = rng.normal(0, 1, n) * sharp
            if h == "produce" and rng.random() < 0.8:
                logits[rng.choice(focus)] += rng.uniform(0, 8)
            e = np.exp(logits - logits.max())
            probs[h] = (e / e.sum()).round(6)
        # condition head v2: P(good condition) per produce; mostly confident, sometimes near 0.5
        cond = rng.uniform(0, 1, tax.num_classes("produce"))
        sharpen = rng.random() < 0.6
        probs["condition"] = (np.where(cond > 0.5, 1 - (1 - cond) ** 3, cond ** 3) if sharpen else cond).round(6)
        probs["condition_rot"] = rng.uniform(0, 1, tax.num_classes("produce")).round(6)
        quality = rng.choice([None] * 8 + ["too_dark", "blurry", "overexposed", "weird"])
        energy = round(float(rng.normal(3, 2)), 4) if rng.random() < 0.7 else None
        res = decide(tax, {h: v for h, v in probs.items()}, bundle["supported_heads"], quality_reason=quality,
                     energy_score=energy, thresholds=bundle["thresholds"])
        cases.append({"probs": {h: v.tolist() for h, v in probs.items()}, "quality_reason": quality,
                      "energy": energy, "expected": res.to_dict()})
    out = ROOT / "app" / "__tests__" / "fixtures" / "decision_cases.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"bundle": bundle, "cases": cases}, ensure_ascii=False), encoding="utf-8")
    statuses = {}
    for c in cases:
        s = c["expected"]["status"] + ("/" + c["expected"]["recommendation"] if c["expected"]["recommendation"] else "")
        statuses[s] = statuses.get(s, 0) + 1
    print(out, statuses)
    return 0


if __name__ == "__main__":
    sys.exit(main())
