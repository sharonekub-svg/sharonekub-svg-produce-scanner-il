#!/usr/bin/env python3
"""Embed every manifest image once with the SigLIP2 encoder (ml/siglip/features.py).

  python scripts/siglip_embed.py --processed data/processed_commercial_v7 --onnx exports/siglip2/vision.onnx \
      --out runs/siglip/emb_v7.npz
Output: sha256 (row key), split, dataset_id, float16 embeddings. Resumable: rows already in --out are skipped.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from ml.siglip.features import Encoder


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--processed", type=Path, required=True)
    ap.add_argument("--onnx", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--cap-train", type=int, default=0, help="max train rows per dataset (0 = all)")
    ap.add_argument("--cap-val", type=int, default=0, help="max val rows per dataset (0 = all)")
    ap.add_argument("--cap-test", type=int, default=0, help="max test rows per dataset (0 = all)")
    args = ap.parse_args()
    rows = [json.loads(l) for l in open(args.processed / "manifest.jsonl", encoding="utf-8")]
    done: dict[str, np.ndarray] = {}
    if args.out.exists():
        z = np.load(args.out)
        done = dict(zip(z["sha256"].tolist(), z["emb"]))
    rng = np.random.default_rng(0)
    for split, cap in (("train", args.cap_train), ("val", args.cap_val), ("test", args.cap_test)):
        if not cap:
            continue
        by: dict[str, list[dict]] = {}
        for r in rows:
            if r["split"] == split:
                by.setdefault(r["dataset_id"], []).append(r)
        drop = set()
        for ds, rs in by.items():
            if len(rs) > cap:
                keep = set(rng.choice(len(rs), cap, replace=False).tolist())
                drop.update(r["sha256"] for i, r in enumerate(rs) if i not in keep and r["sha256"] not in done)
        rows = [r for r in rows if not (r["split"] == split and r["sha256"] in drop)]
    todo = [r for r in rows if r["sha256"] not in done]
    enc = Encoder(args.onnx, threads=args.threads)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def save():
        keep = [r for r in rows if r["sha256"] in done]
        np.savez(args.out, sha256=np.array([r["sha256"] for r in keep]), split=np.array([r["split"] for r in keep]),
                 dataset_id=np.array([r["dataset_id"] for r in keep]),
                 emb=np.stack([done[r["sha256"]] for r in keep]).astype(np.float16))

    for i in range(0, len(todo), 256):
        chunk = todo[i:i + 256]
        e = enc([Image.open(args.processed / r["image"]) for r in chunk])
        done.update({r["sha256"]: v.astype(np.float16) for r, v in zip(chunk, e)})
        if (i // 256) % 10 == 0:
            save()
            print(f"{len(done)}/{len(rows)}", flush=True)
    save()
    print(f"done {len(done)} rows -> {args.out}")


if __name__ == "__main__":
    main()
