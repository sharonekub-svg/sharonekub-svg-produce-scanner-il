#!/usr/bin/env python3
"""Add the condition head v2 (scripts/train_condition_head.py) to the shipped SigLIP bundle.

  python3 scripts/add_condition_head.py runs/siglip/condition_v2 server/model
-> heads.npz gains condition_W (768,) and condition_b (one bias per produce output; 0 = no head for that type),
   bundle.json gains temperatures.condition and thresholds.condition_abstain (per-type confidence below which the
   score is capped and a better photo is requested; both fitted on val only),
   "condition" in supported_heads for the trained types, a new model_id, updated file hashes, and the app copy
   (app/assets/model/bundle.json). Same training data as the shipped heads (data/processed_commercial_v7), so no
   new dataset enters the licence gate.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np


def main(run: Path, model: Path) -> None:
    h = np.load(run / "condition_head.npz")
    cal = json.loads((run / "calibration.json").read_text())
    b = json.loads((model / "bundle.json").read_text(encoding="utf-8"))
    produce = b["outputs"]["produce"]
    types = [str(x) for x in h["types"]]
    bias = np.zeros(len(produce), np.float32)
    for i, p in enumerate(types):
        bias[produce.index(p)] = h["b_type"][i]
    heads = dict(np.load(model / "heads.npz"))
    heads["condition_W"] = h["W"].astype(np.float32)
    heads["condition_b"] = bias
    np.savez(model / "heads.npz", **heads)
    for p in types:
        sh = b["supported_heads"].setdefault(p, [])
        if "condition" not in sh:
            sh.append("condition")
    b["temperatures"]["condition"] = cal["temperature"]
    b["thresholds"]["condition_abstain"] = cal["abstain_conf"]
    rb = run / "reliability_bounds.json"  # P(good | p >= .95) on val photos from a held-out source (docs/quality-scoring.md)
    if rb.exists():
        b["thresholds"]["condition_max_p"] = round(json.loads(rb.read_text())["hi"], 3)
    b["condition"] = {"source": "scripts/train_condition_head.py (docs/quality-scoring.md)", "types": types}
    digest = hashlib.sha256((model / "heads.npz").read_bytes()).hexdigest()
    b["files"]["heads.npz"] = {"sha256": digest}
    b["model_id"] = f"siglip2_v0.13@{digest[:12]}"
    (model / "bundle.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.copy(model / "bundle.json", Path("app/assets/model/bundle.json"))
    print(b["model_id"], "condition types:", types)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
