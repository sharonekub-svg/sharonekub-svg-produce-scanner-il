#!/usr/bin/env python3
"""Embed every row of a processed manifest with the shipped SigLIP2 vision encoder (resumable).

  PYTHONPATH=. python3 scripts/siglip_embed_manifest.py data/processed_quality_v8 runs/siglip/emb_q8.npz
Same output format as siglip_embed_dataset.py (sha256, split, dataset_id, emb float16).
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from ml.siglip.features import Encoder

P, out = Path(sys.argv[1]), Path(sys.argv[2])
rows = [json.loads(l) for l in open(P / "manifest.jsonl", encoding="utf-8")]
done = {}
if out.exists():
    z = np.load(out)
    done = dict(zip(z["sha256"].tolist(), z["emb"]))
enc = Encoder(Path("exports/siglip2/vision.onnx"), threads=8)


def save():
    k = [r for r in rows if r["sha256"] in done]
    np.savez(out, sha256=np.array([r["sha256"] for r in k]), split=np.array([r["split"] for r in k]),
             dataset_id=np.array([r["dataset_id"] for r in k]),
             emb=np.stack([done[r["sha256"]] for r in k]).astype(np.float16))


todo = [r for r in rows if r["sha256"] not in done]
for i in range(0, len(todo), 64):
    ch = todo[i:i + 64]
    e = enc([Image.open(P / r["image"]).convert("RGB") for r in ch])
    done.update({r["sha256"]: v.astype(np.float16) for r, v in zip(ch, e)})
    if (i // 64) % 20 == 0:
        save(); print(len(done), "/", len(rows), flush=True)
save(); print("done", len(done))
