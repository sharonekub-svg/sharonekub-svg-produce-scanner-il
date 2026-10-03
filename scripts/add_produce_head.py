#!/usr/bin/env python3
"""Ship a fine-tuned produce head (scripts/finetune_produce_head.py) into the bundle.

  python3 scripts/add_produce_head.py runs/siglip/produce_v16c server/model [v0.16]
Replaces produce_W / produce_b, sets temperatures.produce (fitted on validation), new model_id, app copy.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np

run, model = Path(sys.argv[1]), Path(sys.argv[2])
version = sys.argv[3] if len(sys.argv) > 3 else "v0.16"
ph = np.load(run / "produce_head.npz")
heads = dict(np.load(model / "heads.npz"))
heads["produce_W"], heads["produce_b"] = ph["produce_W"].astype(np.float32), ph["produce_b"].astype(np.float32)
np.savez(model / "heads.npz", **heads)
b = json.loads((model / "bundle.json").read_text(encoding="utf-8"))
b["temperatures"]["produce"] = round(float(ph["T"]), 4)
b["produce_head"] = {"source": "scripts/finetune_produce_head.py", "lambda": float(ph["lam"])}
digest = hashlib.sha256((model / "heads.npz").read_bytes()).hexdigest()
b["files"]["heads.npz"] = {"sha256": digest}
b["model_id"] = f"siglip2_{version}@{digest[:12]}"
(model / "bundle.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
shutil.copy(model / "bundle.json", Path("app/assets/model/bundle.json"))
print(b["model_id"])
