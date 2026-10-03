#!/usr/bin/env python3
"""Identification on quality-labelled photos (incl. spoiled fruit) and on real-world Open Images photos.

For each set: answered = top-1 prob >= produce_min_prob and margin >= produce_min_margin (what the app shows),
accuracy when answered, and overall top-1. Uses the shipped heads (or --heads) on cached SigLIP2 embeddings.

  python3 scripts/eval_identification.py [--heads server/model/heads.npz] [--split test]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_quality_v3 import SOURCES, as_set  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.evaluation.calibration import softmax  # noqa: E402


def logits(hd, X):
    neg = X @ hd["neg_W"].T
    m = neg.max(1, keepdims=True)
    other = (m[:, 0] + np.log(np.exp(neg - m).sum(1))) + hd["produce_b"][-1]
    return np.concatenate([X @ hd["produce_W"].T + hd["produce_b"][:-1], other[:, None]], 1)


def stats(P, y, t):
    top = P.argmax(1); s = np.sort(P, 1); conf, margin = s[:, -1], s[:, -1] - s[:, -2]
    ans = (conf >= t["produce_min_prob"]) & (margin >= t["produce_min_margin"])
    return {"n": int(len(y)), "top1": round(float((top == y).mean()), 3), "answered": round(float(ans.mean()), 3),
            "acc_when_answered": round(float((top[ans] == y[ans]).mean()), 3) if ans.any() else None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heads", type=Path, default=Path("server/model/heads.npz"))
    ap.add_argument("--produce", type=Path, help="fine-tuned produce_head.npz (produce_W, produce_b, T) to compare")
    ap.add_argument("--split", default="test")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    b = json.load(open("server/model/bundle.json")); P = b["outputs"]["produce"]; t = b["thresholds"]
    T = b["temperatures"]["produce"]; hd = dict(np.load(a.heads))
    if a.produce:
        ph = np.load(a.produce)
        hd["produce_W"], hd["produce_b"], T = ph["produce_W"], ph["produce_b"], float(ph["T"])
    rep = {}
    by = collections.defaultdict(lambda: ([], []))
    for man, embp in SOURCES:
        z = np.load(embp); emb = dict(zip(z["sha256"].tolist(), z["emb"].astype(np.float32)))
        for line in open(man, encoding="utf-8"):
            r = json.loads(line)
            p = r["labels"].get("produce")
            if r["split"] != a.split or r["sha256"] not in emb or p not in P or p == "other":
                continue
            fr, sp = as_set(r["labels"].get("freshness")), as_set(r["labels"].get("visual_spoilage"))
            cond = "bad" if (fr & {"declining", "spoiled"} or sp & {"mild", "severe"}) else "good"
            for key in (f"{r['dataset_id']}", f"_cond_{cond}"):
                by[key][0].append(emb[r["sha256"]]); by[key][1].append(P.index(p))
    for k, (X, y) in sorted(by.items()):
        rep[k] = stats(softmax(logits(hd, np.stack(X)), T), np.array(y), t)
    d = np.load("runs/siglip/oi_real3.npz", allow_pickle=True)
    split_oi = "test" if a.split == "test" else "cal"
    m = (d["split"] == split_oi) & np.isin(d["true"], P)
    y = np.array([P.index(x) for x in d["true"][m]])
    rep["_open_images_real"] = stats(softmax(logits(hd, d["emb"][m]), T), y, t)
    if a.out:
        a.out.write_text(json.dumps(rep, indent=1))
    for k, v in rep.items():
        print(f"{k:28} {v}")


if __name__ == "__main__":
    main()
