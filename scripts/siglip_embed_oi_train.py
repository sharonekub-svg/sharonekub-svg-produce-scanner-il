#!/usr/bin/env python3
"""Embed Open Images crops for TRAINING the produce head on real-world photos.

  PYTHONPATH=. python3 scripts/siglip_embed_oi_train.py --real runs/siglip/oi_real.npz --out runs/siglip/oi_train.npz

Every image_id that has any crop in the real-photo evaluation set (--real, cal + test) is excluded, so the
evaluation stays unseen. Up to --cap crops per class (min side 100 px). Unsupported classes -> "other".
Resumable.
"""
import argparse, csv, random
from pathlib import Path
import numpy as np
from PIL import Image
from ml.siglip.features import Encoder

OI = Path("data/raw/open_images_v7")
MAP = {"Apple": "apple", "Banana": "banana", "Orange (fruit)": "orange", "Lemon (plant)": "lemon", "Strawberry": "strawberry",
       "Tomato": "tomato", "Cucumber": "cucumber", "Pear": "pear", "Peach": "peach", "Pomegranate": "pomegranate", "Mango": "mango",
       "Grape": "grape", "Watermelon": "watermelon", "Bell pepper": "pepper", "Cantaloupe": "melon", "Grapefruit": "grapefruit",
       "Zucchini": "zucchini", "Potato": "potato"}
UNSUP = ["Broccoli", "Carrot", "Pumpkin", "Cabbage", "Radish", "Pineapple", "Common fig", "Squash (Plant)", "Winter melon"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--onnx", type=Path, default=Path("exports/siglip2/vision.onnx"))
    ap.add_argument("--cap", type=int, default=500)
    ap.add_argument("--cap-other", type=int, default=250)
    a = ap.parse_args()
    z = np.load(a.real, allow_pickle=True)
    held = {Path(p).name.rsplit("_", 1)[0] for p in z["path"]}          # image ids used in the evaluation
    random.seed(0)
    by: dict[str, list[dict]] = {}
    for r in csv.DictReader(open(OI / "crops.csv")):
        if (r["class_name"] in MAP or r["class_name"] in UNSUP) and r["image_id"] not in held:
            by.setdefault(r["class_name"], []).append(r)
    rows = []
    for c, rs in sorted(by.items()):
        random.shuffle(rs)
        rows += rs[: a.cap if c in MAP else a.cap_other]
    done = {}
    if a.out.exists():
        o = np.load(a.out, allow_pickle=True)
        done = dict(zip(o["path"].tolist(), o["emb"]))
    enc = Encoder(a.onnx, threads=8)

    def save():
        k = [r for r in rows if r["path"] in done]
        np.savez(a.out, path=np.array([r["path"] for r in k]), image_id=np.array([r["image_id"] for r in k]),
                 true=np.array([MAP.get(r["class_name"], "other") for r in k]), emb=np.stack([done[r["path"]] for r in k]))
    todo = [r for r in rows if r["path"] not in done]
    for i in range(0, len(todo), 128):
        ch, ims = [], []
        for r in todo[i:i + 128]:
            im = Image.open(OI / r["path"]).convert("RGB")
            if min(im.size) >= 100:
                ch.append(r); ims.append(im)
            else:
                rows.remove(r)
        if ims:
            done.update({r["path"]: v.astype(np.float16) for r, v in zip(ch, enc(ims))})
        if (i // 128) % 10 == 0:
            save(); print(len(done), "/", len(rows), flush=True)
    save(); print("done", len(done), "held-out image ids excluded:", len(held))


if __name__ == "__main__":
    main()
