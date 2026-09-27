"""Choose quality.DEFAULTS["min_laplacian_var"] from evidence: blur the test split at increasing
Gaussian radii, record each image's Laplacian variance (the gate's statistic) and whether the model
is still right, then report, per candidate threshold, the accuracy of what passes the gate and how
many sharp photos it would wrongly send back.

  python -m ml.evaluation.blur_sweep --ckpt runs/X/best.pt --processed data/processed_commercial \
      --exclude-source-regex '(^|/)(Lime|Red-Grapefruit|Zucchini|Potato|Passion-Fruit)/' --out runs/X/blur_sweep.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import torch
from PIL import ImageFilter

from ml.evaluation.evaluate import load_ckpt
from ml.inference import quality
from ml.preprocessing.image_io import load_rgb
from ml.training import augment, dataset

# Radius as a fraction of the long side, so the sweep means the same thing at any resolution.
LEVELS = (0.0, 0.002, 0.004, 0.006, 0.008, 0.011, 0.015, 0.02, 0.03)
THRESHOLDS = (0, 10, 20, 30, 40, 60, 80, 100, 130, 160, 200, 250, 300)


@torch.no_grad()
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--processed", type=Path, required=True)
    ap.add_argument("--exclude-source-regex")
    ap.add_argument("--max-rows", type=int, default=800)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    net, cfg, tax, _, _ = load_ckpt(args.ckpt)
    rows = [r for r in dataset.read_manifest(args.processed / "manifest.jsonl", {"test"})
            if isinstance(r["labels"]["produce"], str)
            and not (args.exclude_source_regex and re.search(args.exclude_source_regex, r["source_path"]))]
    if len(rows) > args.max_rows:
        rows = [rows[i] for i in sorted(np.random.default_rng(0).choice(len(rows), args.max_rows, replace=False))]
    tf = augment.build_eval_transform(cfg)
    y = np.array([tax.produce.index(r["labels"]["produce"]) for r in rows])
    lap = np.zeros((len(LEVELS), len(rows)))
    correct = np.zeros((len(LEVELS), len(rows)), dtype=bool)
    for i, r in enumerate(rows):
        img = load_rgb(args.processed / r["image"])
        batch, lv = [], []
        for frac in LEVELS:
            im = img.filter(ImageFilter.GaussianBlur(frac * max(img.size))) if frac else img
            lv.append(quality.assess(im).laplacian_var)
            batch.append(tf(im))
        pred = net(torch.stack(batch))["produce"].argmax(1).numpy()
        lap[:, i] = lv
        correct[:, i] = pred == y[i]
    per_level = [{"radius_frac": f, "accuracy": float(correct[j].mean()), "lapvar_median": float(np.median(lap[j]))}
                 for j, f in enumerate(LEVELS)]
    sharp = lap[0]
    per_thr = []
    for t in THRESHOLDS:
        passed = lap >= t
        per_thr.append({"min_laplacian_var": t,
                        "sharp_rejected": float((sharp < t).mean()),
                        "accuracy_of_passed_all_levels": float(correct[passed].mean()) if passed.any() else None,
                        "blurred_passed": {str(f): float(passed[j].mean()) for j, f in enumerate(LEVELS) if f}})
    res = {"ckpt": str(args.ckpt), "n": len(rows), "levels": per_level, "thresholds": per_thr,
           "current_default": quality.DEFAULTS["min_laplacian_var"]}
    out = args.out or args.ckpt.parent / "blur_sweep.json"
    out.write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
