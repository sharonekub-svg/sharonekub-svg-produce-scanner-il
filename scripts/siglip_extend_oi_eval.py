#!/usr/bin/env python3
"""Extend the real-photo evaluation set (Open Images crops, never trained on) when new produce types are added.

  PYTHONPATH=. python3 scripts/siglip_extend_oi_eval.py --real runs/siglip/oi_real.npz --out runs/siglip/oi_real2.npz

1. Relabel existing rows from data/label_mapping.json (e.g. Carrot crops were "other", now "carrot").
2. Add up to --per-class new crops (min side 200 px) for Open Images classes that have no rows yet,
   split cal/test by md5(image_id) exactly like the original set. Image ids already used in the set are
   reused only with the split they already have.
Training (scripts/siglip_embed_oi_train.py --real <this file>) then excludes every image id in here.
"""
import argparse
import csv
import hashlib
import json
import random
from pathlib import Path

import numpy as np
from PIL import Image

from ml.inference import quality
from ml.siglip.features import Encoder

OI = Path("data/raw/open_images_v7")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--onnx", type=Path, default=Path("exports/siglip2/vision.onnx"))
    ap.add_argument("--per-class", type=int, default=80)
    ap.add_argument("--min-test", type=int, default=30,
                    help="top up any supported type with fewer test-half crops than this (the gate needs n >= 30)")
    a = ap.parse_args()
    cmap = json.loads(Path("data/label_mapping.json").read_text(encoding="utf-8"))["datasets"]["open_images_v7"]["class_name_map"]
    z = np.load(a.real, allow_pickle=True)
    rows = [dict(path=str(p), split=str(s), q=q) for p, s, q in zip(z["path"], z["split"], z["q"])]
    cls_of = {r["path"]: r["class_name"] for r in csv.DictReader(open(OI / "crops.csv", encoding="utf-8"))}
    for r in rows:
        r["true"] = cmap[cls_of[r["path"]]]
    have = {cls_of[r["path"]] for r in rows}
    random.seed(1)
    by: dict[str, list[dict]] = {}
    for r in csv.DictReader(open(OI / "crops.csv", encoding="utf-8")):
        if r["class_name"] in cmap and r["class_name"] not in have:
            by.setdefault(r["class_name"], []).append(r)
    new, ims = [], []
    for c, rs in sorted(by.items()):
        random.shuffle(rs)
        k = 0
        for r in rs:
            im = Image.open(OI / r["path"]).convert("RGB")
            if min(im.size) < 200:
                continue
            split = "cal" if int(hashlib.md5(r["image_id"].encode()).hexdigest(), 16) % 2 == 0 else "test"
            new.append(dict(path=r["path"], true=cmap[c], split=split, q=str(quality.assess(im).reason)))
            ims.append(im)
            k += 1
            if k >= a.per_class:
                break
        print(f"{c}: +{k}")
    # 3. Top-up: supported types whose test half is below --min-test get more crops from unused image ids.
    #    Only the COUNT decides (fixed rule), never the accuracy.
    used_ids = {Path(r["path"]).name.rsplit("_", 1)[0] for r in rows + new}
    by_all: dict[str, list[dict]] = {}
    for r in csv.DictReader(open(OI / "crops.csv", encoding="utf-8")):
        if r["class_name"] in cmap and cmap[r["class_name"]] != "other" and r["image_id"] not in used_ids:
            by_all.setdefault(r["class_name"], []).append(r)
    for c, rs in sorted(by_all.items()):
        n_test = sum(1 for r in rows + new if cls_of[r["path"]] == c and r["split"] == "test")
        if n_test >= a.min_test:
            continue
        random.shuffle(rs)
        added = 0
        for r in rs:
            if n_test >= a.min_test:
                break
            split = "cal" if int(hashlib.md5(r["image_id"].encode()).hexdigest(), 16) % 2 == 0 else "test"
            im = Image.open(OI / r["path"]).convert("RGB")
            if min(im.size) < 200:
                continue
            new.append(dict(path=r["path"], true=cmap[c], split=split, q=str(quality.assess(im).reason)))
            ims.append(im)
            added += 1
            n_test += split == "test"
        print(f"{c}: top-up +{added} (test now {n_test})")
    E_new = Encoder(a.onnx, threads=8)(ims) if ims else np.zeros((0, z["emb"].shape[1]), np.float32)
    allr = rows + new
    np.savez(a.out, emb=np.concatenate([z["emb"].astype(np.float32), E_new]), true=np.array([r["true"] for r in allr]),
             split=np.array([r["split"] for r in allr]), path=np.array([r["path"] for r in allr]),
             q=np.array([str(r["q"]) for r in allr]))
    from collections import Counter
    print(a.out, len(allr), Counter(r["true"] for r in allr).most_common())


if __name__ == "__main__":
    main()
