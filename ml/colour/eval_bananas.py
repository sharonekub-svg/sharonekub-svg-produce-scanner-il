"""Leave-one-fruit-out evaluation of banana colour grading on psolymos/bananas (MIT).

  python -m ml.colour.eval_bananas --root data/raw/bananas_psolymos
Labels: U under ripe, R ripe, V very ripe, O over ripe (dataset author's, per image).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from ml.colour.banana import peel_fractions

ORDER = ["U", "R", "V", "O"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    files = sorted((args.root / "images").glob("*.png"))
    X, y, fruit, fridge = [], [], [], []
    for f in files:
        c = peel_fractions(Image.open(f))
        X.append([c.green, c.yellow, c.brown]); y.append(ORDER.index(f.stem[-1])); fruit.append(f.stem.split("_")[0])
        fridge.append(f.stem.split("_")[1] == "F")
    X, y, fruit, fridge = np.array(X), np.array(y), np.array(fruit), np.array(fridge)
    # Ordinal 1-D score: brown pushes later, green earlier. Thresholds are fit per fold on the other fruits.
    score = X[:, 2] - X[:, 0]
    pred = np.empty_like(y)
    for fr in np.unique(fruit):
        tr = fruit != fr
        cuts = []
        for k in range(len(ORDER) - 1):  # best cut between class <=k and >k on training fruits
            cand = np.unique(score[tr])
            acc = [((score[tr] > c) == (y[tr] > k)).mean() for c in cand]
            cuts.append(cand[int(np.argmax(acc))])
        te = ~tr
        pred[te] = (score[te][:, None] > np.array(cuts)[None, :]).sum(1)
    exact = float((pred == y).mean())
    within1 = float((np.abs(pred - y) <= 1).mean())
    cm = np.zeros((4, 4), int)
    for a, b in zip(y, pred):
        cm[a, b] += 1
    res = {"n_images": int(len(y)), "n_fruits": int(len(np.unique(fruit))), "exact": exact, "within_one_stage": within1,
           "confusion_rows_true_URVO": cm.tolist(),
           # consumer view: very ripe and over ripe both mean "eat now / bake" -> 3 classes U | R | V+O
           "exact_3class": float((np.minimum(pred, 2) == np.minimum(y, 2)).mean()),
           "room_temperature_only": {"n": int((~fridge).sum()), "exact": float((pred == y)[~fridge].mean()),
                                     "exact_3class": float((np.minimum(pred, 2) == np.minimum(y, 2))[~fridge].mean())},
           "mean_fractions_by_label": {ORDER[k]: X[y == k].mean(0).round(3).tolist() for k in range(4)}}
    print(json.dumps(res, indent=2))
    if args.out:
        args.out.write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
