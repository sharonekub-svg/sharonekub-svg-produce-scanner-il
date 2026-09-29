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
    # Verified per-fruit heads (gate on held-out test) + the general fresh-vs-spoiled score for every other type.
    supported = rd("supported_heads_gated.json")
    if "general_ab" in __import__("numpy").load(args.run / "heads.npz"):
        for p in tax.produce:
            if tax.produce_meta[p].get("is_negative_class"):
                continue
            hs = supported.setdefault(p, [])
            if not any(h.split("~")[0] == "freshness" for h in hs):
                hs.append("freshness~general")
    datasets = sorted({json.loads(l)["dataset_id"] for l in open(args.processed / "manifest.jsonl", encoding="utf-8")})
    bundle = {
        "bundle_version": 2, "backbone": "siglip2", "model_id": f"siglip2_{args.version}@{digest}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": {"size": 224, "layout": "NCHW", "mean": [0.5, 0.5, 0.5], "std": [0.5, 0.5, 0.5], "resize": "squash"},
        "outputs": {h: list(tax.classes(h)) for h in HEADS},
        "temperatures": rd("temperature.json"), "thresholds": thr, "quality": QUALITY,
        "supported_heads": supported,
        "produce_meta": {p: {k: v for k, v in tax.produce_meta[p].items()} for p in tax.produce},
        "label_he": tax.label_he, "training_datasets": datasets,
    }
    args.to.mkdir(parents=True, exist_ok=True)
    for old in ("model.onnx", "model.int8.onnx"):
        (args.to / old).unlink(missing_ok=True)
    for old in args.to.glob("vision.onnx*"):
        old.unlink()
    data, part, names = args.onnx.read_bytes(), 90 * 2**20, []
    for i in range(0, len(data), part):  # git hosting rejects files > 100 MB; the server joins the parts
        name = f"vision.onnx.{i // part:02d}"
        (args.to / name).write_bytes(data[i:i + part])
        names.append(name)
    shutil.copy(args.run / "heads.npz", args.to / "heads.npz")
    bundle["files"] = {f: {"sha256": hashlib.sha256((args.to / f).read_bytes()).hexdigest()} for f in (*names, "heads.npz")}
    (args.to / "bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=1), encoding="utf-8")
    print("released", bundle["model_id"], "->", args.to)


if __name__ == "__main__":
    main()
