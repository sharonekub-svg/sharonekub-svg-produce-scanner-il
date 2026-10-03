#!/usr/bin/env python3
"""Condition head v4: the v0.13 binary condition head (scripts/train_condition_head.py) retrained on every licensed
source, including the 2026-10-03 additions (MangoDHDS, EFIQD), compared with the shipped head photo-source by
photo-source.

Why (docs/quality-scoring.md §14): EFIQD green apples are a photo source the shipped head never saw; it gives
P(good) >= 0.8 to most of the bad (shrivelled) ones. A per-type bias cannot fix that without hurting the other
apple sources, so the shared weights are retrained with the new sources in, same recipe as v0.13: logistic
regression on SigLIP2 embeddings + per-type bias, each (type, dataset) cell weighted so good and bad count equally,
one-sided cells dropped, L2 chosen on val, one temperature on val, per-type abstain confidence on val
(error <= 2% above it), reliability ceiling = P(good | p >= 0.95) on val photos predicted by a model that never
saw their source (leave-one-dataset-out). Test is only reported.

  python3 scripts/train_condition_v4.py --out runs/siglip/condition_v4            (train + compare)
  python3 scripts/train_condition_v4.py --out runs/siglip/condition_v4 --ship apple   (v4 head for these types only)
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_quality_scores import truth_of  # noqa: E402
from train_condition_head import design, fit, predict, weights  # noqa: E402
from add_condition_types import abstain_conf, metrics  # noqa: E402

SOURCES = [("data/processed_commercial_v7/manifest.jsonl", "runs/siglip/emb_v9.npz"),
           ("data/processed_quality_v8/manifest.jsonl", "runs/siglip/emb_q8.npz"),
           ("data/processed_quality_v9/manifest.jsonl", "runs/siglip/emb_q9.npz"),
           ("data/processed_quality_v10/manifest.jsonl", "runs/siglip/emb_q10.npz")]
NEW_DATASETS = ["mango_dhds", "efiqd"]


def load(types):
    X, y, t, ds, sp = [], [], [], [], []
    for man, emb_path in SOURCES:
        z = np.load(emb_path)
        emb = dict(zip(z["sha256"].tolist(), z["emb"].astype(np.float32)))
        for line in open(man, encoding="utf-8"):
            r = json.loads(line)
            p, lab = r["labels"].get("produce"), truth_of(r["labels"])
            if p in types and lab is not None and r["sha256"] in emb:
                X.append(emb[r["sha256"]]); y.append(1.0 if lab == "good" else 0.0)
                t.append(p); ds.append(r["dataset_id"]); sp.append(r["split"])
    return np.stack(X), np.array(y), np.array(t), np.array(ds), np.array(sp)


def temperature(logit, y) -> float:
    def nll(T):
        p = 1 / (1 + np.exp(-logit / T))
        return -(y * np.log(p + 1e-12) + (1 - y) * np.log(1 - p + 1e-12)).mean()
    return float(minimize_scalar(nll, bounds=(0.05, 20), method="bounded").x)


def per_source(p, y, t, ds, sp, types):
    out = {}
    for x in types:
        for d in sorted(set(ds[t == x])):
            for split in ("val", "test"):
                m = (t == x) & (ds == d) & (sp == split)
                r = metrics(p[m], y[m])
                if r:
                    out[f"{x}|{d}|{split}"] = r
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ship", nargs="*", default=None, help="types that get the v4 head (chosen on val)")
    a = ap.parse_args()
    model = Path("server/model")
    b = json.loads((model / "bundle.json").read_text(encoding="utf-8"))
    heads = dict(np.load(model / "heads.npz"))
    produce = b["outputs"]["produce"]
    types = sorted(b["condition"]["types"])  # the shipped binary-head types; new types train the shared weights too
    train_types = sorted(set(types) | {"mango", "kiwi", "avocado"})
    X, y, t, ds, sp = load(train_types)
    Z = design(X, t, train_types)
    w = weights(y, t, ds, True)
    tr, va = sp == "train", sp == "val"

    best = None
    for lam in (1e-5, 1e-4, 1e-3):
        th = fit(Z[tr], y[tr], w[tr], lam)
        pv = predict(th, Z[va])
        ll = np.mean([-(np.log(np.where(y[va][t[va] == x] == 1, pv[t[va] == x], 1 - pv[t[va] == x]) + 1e-12)).mean()
                      for x in train_types if (t[va] == x).sum() >= 20])
        if best is None or ll < best[0]:
            best = (ll, lam, th)
    _, lam, th = best
    logit = Z @ th
    T = temperature(logit[va], y[va])
    p_new = 1 / (1 + np.exp(-logit / T))

    # shipped head (temperature already folded in)
    idx = np.array([produce.index(x) for x in t])
    p_old = 1 / (1 + np.exp(-(X @ heads["condition_W"] + heads["condition_b"][idx])))

    # leave-one-dataset-out: predictions for each source from a head that never saw it (same lambda, same T)
    p_lodo = np.full(len(y), np.nan)
    for d in sorted(set(ds)):
        m = ds == d
        keep = tr & ~m
        if len(set(y[m])) < 2 or m.sum() < 100:
            continue
        th_d = fit(Z[keep], y[keep], weights(y[keep], t[keep], ds[keep], True), lam)
        p_lodo[m] = 1 / (1 + np.exp(-(Z[m] @ th_d) / T))
    hv = va & ~np.isnan(p_lodo) & (p_lodo >= 0.95)
    hi = float(y[hv].mean()) if hv.sum() >= 30 else None

    abst = {x: abstain_conf(p_new[va & (t == x)], y[va & (t == x)]) for x in train_types if (va & (t == x)).sum() >= 20}
    res = {"lambda": lam, "temperature": round(T, 4), "reliability_hi": None if hi is None else round(hi, 4),
           "abstain_conf": abst, "n": dict(collections.Counter(f"{x}|{d}" for x, d in zip(t, ds))),
           "new": per_source(p_new, y, t, ds, sp, train_types), "shipped": per_source(p_old, y, t, ds, sp, train_types),
           "lodo_new": {}, "lodo_shipped_equiv": {}}
    for x in train_types:
        for d in sorted(set(ds[t == x])):
            m = (t == x) & (ds == d) & ~np.isnan(p_lodo)
            r = metrics(p_lodo[m], y[m])
            if r:
                res["lodo_new"][f"{x}|{d}"] = r
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "report.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("lambda", lam, "T", round(T, 3), "hi", hi)
    print(f"{'type|source|split':52} {'AUROC old→new':>16} {'bad≥.8 old→new':>18} {'good≤.4 old→new':>18}")
    for k in sorted(res["new"]):
        o, n = res["shipped"].get(k), res["new"][k]
        if o:
            print(f"{k:52} {o['auroc']:.3f}→{n['auroc']:.3f}   {o['bad_p_ge_0.8']:.3f}→{n['bad_p_ge_0.8']:.3f}   "
                  f"{o['good_p_le_0.4']:.3f}→{n['good_p_le_0.4']:.3f}")
    print("LODO (new recipe, source never seen):")
    for k, v in res["lodo_new"].items():
        print(f"  {k:40} auroc {v['auroc']:.3f} bad≥.8 {v['bad_p_ge_0.8']:.3f} good≤.4 {v['good_p_le_0.4']:.3f}")

    if a.ship is None:
        return
    # Per-type override (server/app.py::_heads): only the types where v4 is better on val get its logit; every other
    # type keeps the shipped head. Temperature folded into the weights (bundle temperature for condition stays 1.0).
    mask, bias = np.zeros(len(produce), np.float32), np.zeros(len(produce), np.float32)
    for x in a.ship:
        mask[produce.index(x)] = 1.0
        bias[produce.index(x)] = th[768 + train_types.index(x)] / T
        b["thresholds"]["condition_abstain"][x] = abst[x]
        if hi is not None:  # transfer types carry the ceiling of the head their P(good) comes from
            b["thresholds"].setdefault("condition_max_p_type", {})[x] = round(hi, 3)
    heads["condition_v4_W"] = (th[:768] / T).astype(np.float32)
    heads["condition_v4_b"] = bias
    heads["condition_v4_mask"] = mask
    np.savez(model / "heads.npz", **heads)
    b["condition"]["v4_types"] = list(a.ship)
    b["condition"]["v4_source"] = "scripts/train_condition_v4.py (docs/quality-scoring.md §14)"
    for d in NEW_DATASETS:
        if d not in b.get("training_datasets", []):
            b.setdefault("training_datasets", []).append(d)
    digest = hashlib.sha256((model / "heads.npz").read_bytes()).hexdigest()
    b["files"]["heads.npz"] = {"sha256": digest}
    b["model_id"] = f"siglip2_v0.17@{digest[:12]}"
    (model / "bundle.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.copy(model / "bundle.json", Path("app/assets/model/bundle.json"))
    print(b["model_id"])


if __name__ == "__main__":
    main()
