#!/usr/bin/env python3
"""Compute measured visual signs (ml/inference/visual.py) for labelled val/test photos and test, per produce type,
which signs actually separate good from bad (and early from rotten) - before any of them touches the score.

  python3 scripts/visual_features_eval.py --out runs/visual   (features cache + report.json)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_quality_scores import auroc  # noqa: E402
from eval_quality_v3 import grade  # noqa: E402
from ml.inference.visual import measure  # noqa: E402

MANIFESTS = [("data/processed_commercial_v7", True), ("data/processed_quality_v8", False), ("data/processed_quality_v9", False)]
DEFECT = ["dark_frac", "very_dark_frac", "largest_dark", "spots_per_100", "brown_frac", "pale_frac"]
FEATS = ["dark_frac", "very_dark_frac", "largest_dark", "spots_per_100", "brown_frac", "pale_frac", "texture", "L", "chroma", "a", "b"]


def rows():
    out = []
    for d, use_raw in MANIFESTS:
        for line in open(f"{d}/manifest.jsonl", encoding="utf-8"):
            r = json.loads(line)
            g = grade(r["labels"])
            if r["split"] not in ("val", "test") or g is None:
                continue
            path = os.path.join("data/raw", r["dataset_id"], r["source_path"]) if use_raw else os.path.join(d, r["image"])
            out.append((r["sha256"], path, r["labels"]["produce"], r["dataset_id"], r["split"], g))
    return out


def work(item):
    try:
        return item[0], measure(Image.open(item[1]))
    except Exception:
        return item[0], None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    cache = a.out / "features.jsonl"
    done = {}
    if cache.exists():
        for l in open(cache):
            x = json.loads(l); done[x["sha"]] = x["f"]
    items = [i for i in rows()]
    todo = [i for i in items if i[0] not in done]
    with open(cache, "a") as fh, Pool(4) as pool:
        for k, (sha, f) in enumerate(pool.imap_unordered(work, todo, chunksize=16)):
            if f is not None:
                done[sha] = f; fh.write(json.dumps({"sha": sha, "f": f}) + "\n")
            if k % 2000 == 0:
                print(k, "/", len(todo), flush=True)
    report = {}
    by = {}
    for sha, _, p, ds, sp, g in items:
        if sha in done:
            by.setdefault(p, []).append((done[sha], g, sp, ds))
    for p, v in sorted(by.items()):
        rep = {"n": {k: sum(1 for x in v if x[1] == k) for k in ("good", "early", "bad", "rotten")}}
        for split in ("val", "test"):
            good = [x[0] for x in v if x[2] == split and x[1] == "good"]
            bad = [x[0] for x in v if x[2] == split and x[1] != "good"]
            early = [x[0] for x in v if x[2] == split and x[1] == "early"]
            rot = [x[0] for x in v if x[2] == split and x[1] == "rotten"]
            res = {}
            for f in FEATS:
                g_, b_ = np.array([x[f] for x in good]), np.array([x[f] for x in bad])
                au = auroc(b_, g_) if len(g_) >= 20 and len(b_) >= 20 else None   # >0.5 = higher in bad fruit
                er = auroc(np.array([x[f] for x in rot]), np.array([x[f] for x in early])) if len(rot) >= 20 and len(early) >= 20 else None
                res[f] = {"bad_vs_good": None if au is None else round(au, 3), "rotten_vs_early": None if er is None else round(er, 3)}
            rep[split] = res
        report[p] = rep
    # Within one dataset (same camera / background for good and bad): the only comparison that a source shortcut
    # cannot explain. Defect features only.
    within = {}
    for sha, _, p, ds, sp, g in items:
        if sha in done:
            within.setdefault(f"{p}|{ds}|{sp}", []).append((done[sha], g))
    report["_within_dataset"] = {}
    for k, v in sorted(within.items()):
        good = [x[0] for x in v if x[1] == "good"]; bad = [x[0] for x in v if x[1] != "good"]
        if len(good) >= 15 and len(bad) >= 15:
            report["_within_dataset"][k] = {"n_good": len(good), "n_bad": len(bad), **{
                f: round(auroc(np.array([x[f] for x in bad]), np.array([x[f] for x in good])), 3) for f in DEFECT}}
    (a.out / "report.json").write_text(json.dumps(report, indent=1))
    for p, rep in report.items():
        if p.startswith("_"):
            continue
        best = sorted(((max(v["bad_vs_good"], 1 - v["bad_vs_good"]), f) for f, v in rep.get("val", {}).items() if v["bad_vs_good"] is not None), reverse=True)[:3]
        print(f"{p:12} n={rep['n']} best on val: " + ", ".join(f"{f} {s:.2f}" for s, f in best))


if __name__ == "__main__":
    main()
