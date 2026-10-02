#!/usr/bin/env python3
"""Ship quality v3 (scripts/train_quality_v3.py) into the SigLIP bundle, on top of the v0.13 condition head.

  python3 scripts/add_quality_v3.py runs/siglip/quality_v3 server/model

- ripeness head  <- the shared softmax trained with BananaID / BananaImageBD (runs/.../ripeness_shared.npz) + its
                    temperature (val).
- condition      <- graded types (good / early problems / rotten; AgriFreshNET-backed): P(good) from the v3 G head,
                    P(rotten | not good) from the R head ("condition_rot"). Other types keep the v0.13 head.
                    Logits are emitted already divided by their temperatures (bundle temperature 1).
- thresholds     condition_abstain for graded types, condition_max_p_graded (reliability on unseen sources, val).
Choice of types: docs/quality-scoring.md §11 (validation only).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np

NEW_DATASETS = ["agrifreshnet", "banana_id", "banana_image_bd"]


def main(run: Path, model: Path) -> None:
    q = np.load(run / "quality_v3.npz")
    rs = np.load(run / "ripeness_shared.npz")
    cal = json.loads((run / "calibration.json").read_text())
    hi = json.loads((run / "reliability_bounds.json").read_text())["hi"]
    b = json.loads((model / "bundle.json").read_text(encoding="utf-8"))
    produce = b["outputs"]["produce"]
    heads = dict(np.load(model / "heads.npz"))
    graded = [str(x) for x in q["R_graded"]]
    Gt, Rt = [str(x) for x in q["G_types"]], [str(x) for x in q["R_types"]]
    Tc = float(b["temperatures"].get("condition", 1.0))

    # ripeness
    heads["ripeness_W"] = rs["W"].astype(np.float32)
    heads["ripeness_b"] = rs["b"].astype(np.float32)
    b["temperatures"]["ripeness"] = round(cal["ripeness_T"], 4)
    # condition: fold the v0.13 temperature into its weights, add the graded heads (temperature folded too)
    if b.get("condition", {}).get("folded_T") is None:
        heads["condition_W"] = (heads["condition_W"] / Tc).astype(np.float32)
        heads["condition_b"] = (heads["condition_b"] / Tc).astype(np.float32)
    TG, TR = float(q["G_T"]), float(q["R_T"])
    gb = np.zeros(len(produce), np.float32); rb = np.zeros(len(produce), np.float32); mask = np.zeros(len(produce), np.float32)
    for p in graded:
        i = produce.index(p)
        gb[i] = q["G_b"][Gt.index(p)] / TG
        rb[i] = q["R_b"][Rt.index(p)] / TR
        mask[i] = 1.0
    heads["condition_g_W"] = (q["G_W"] / TG).astype(np.float32)
    heads["condition_g_b"] = gb
    heads["condition_r_W"] = (q["R_W"] / TR).astype(np.float32)
    heads["condition_r_b"] = rb
    heads["condition_graded"] = mask
    np.savez(model / "heads.npz", **heads)

    b["temperatures"]["condition"] = 1.0
    for p in graded:
        sh = [h for h in b["supported_heads"].setdefault(p, []) if h not in ("condition", "condition~graded")]
        b["supported_heads"][p] = sh + ["condition~graded"]
        if "ripeness" in sh or p == "banana":
            pass
    b["thresholds"].setdefault("condition_abstain", {}).update(cal["abstain_conf_graded"])
    b["thresholds"]["condition_max_p_graded"] = round(hi, 3)
    b["condition"] = {**b.get("condition", {}), "folded_T": True, "graded_types": graded,
                      "graded_source": "scripts/train_quality_v3.py (docs/quality-scoring.md §11)"}
    for d in NEW_DATASETS:
        if d not in b.get("training_datasets", []):
            b.setdefault("training_datasets", []).append(d)
    digest = hashlib.sha256((model / "heads.npz").read_bytes()).hexdigest()
    b["files"]["heads.npz"] = {"sha256": digest}
    b["model_id"] = f"siglip2_v0.14@{digest[:12]}"
    (model / "bundle.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.copy(model / "bundle.json", Path("app/assets/model/bundle.json"))
    print(b["model_id"], "graded:", graded)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
