#!/usr/bin/env python3
"""Package a v0.8+ SigLIP2 run for the server: vision.onnx + heads.npz + bundle.json.

  PYTHONPATH=. python scripts/release_siglip.py --run runs/siglip/v08 --onnx exports/siglip2/vision.onnx \
      --processed data/processed_commercial_v7 --version v0.8-dev --to server/model
The bundle keeps the v0.7 shape (outputs, temperatures, thresholds, supported_heads, produce_meta, label_he) so the
app's decision code and /v1/analyze are unchanged; `backbone: siglip2` tells the server which engine to load.
Photo-quality gate: only extreme cases ask for a retake (docs/results.md round 6: sharp, evenly lit fruit on a
white background was being rejected as "blurry"/"overexposed").
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ml.common.taxonomy import HEADS, load_taxonomy

QUALITY = {"min_mean_luma": 20.0, "max_mean_luma": 245.0, "min_laplacian_var": 8.0, "max_clipped_frac": 0.85,
           "analysis_size": 256}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--onnx", type=Path, required=True)
    ap.add_argument("--processed", type=Path, required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--to", type=Path, required=True)
    args = ap.parse_args()
    tax = load_taxonomy()
    rd = lambda n: json.loads((args.run / n).read_text())  # noqa: E731
    heads = (args.run / "heads.npz").read_bytes()
    digest = hashlib.sha256(args.onnx.read_bytes()[:1 << 24] + heads).hexdigest()[:12]
    thr = {"produce_min_prob": 0.7, "produce_min_margin": 0.15, "ood_min_energy": None, "head_min_prob": 0.55,
           "spoiled_alert_prob": 0.40, **{k: v for k, v in rd("thresholds.json").items() if k != "tuned_on"}}
    datasets = sorted({json.loads(l)["dataset_id"] for l in open(args.processed / "manifest.jsonl", encoding="utf-8")})
    bundle = {
        "bundle_version": 2, "backbone": "siglip2", "model_id": f"siglip2_{args.version}@{digest}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": {"size": 224, "layout": "NCHW", "mean": [0.5, 0.5, 0.5], "std": [0.5, 0.5, 0.5], "resize": "squash"},
        "outputs": {h: list(tax.classes(h)) for h in HEADS},
        "temperatures": rd("temperature.json"), "thresholds": thr, "quality": QUALITY,
        "supported_heads": rd("supported_heads_gated.json"),
        "produce_meta": {p: {k: v for k, v in tax.produce_meta[p].items()} for p in tax.produce},
        "label_he": tax.label_he, "training_datasets": datasets,
        "files": ["vision.onnx", "heads.npz"],
    }
    args.to.mkdir(parents=True, exist_ok=True)
    for old in ("model.onnx", "model.int8.onnx"):
        (args.to / old).unlink(missing_ok=True)
    shutil.copy(args.onnx, args.to / "vision.onnx")
    shutil.copy(args.run / "heads.npz", args.to / "heads.npz")
    (args.to / "bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=1), encoding="utf-8")
    print("released", bundle["model_id"], "->", args.to)


if __name__ == "__main__":
    main()
