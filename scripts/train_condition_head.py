#!/usr/bin/env python3
"""Condition head v2: one calibrated P(good condition) per photo, trained without source shortcuts.

Why (docs/quality-scoring.md §1, §7): the shipped freshness/spoilage heads learned capture conditions as labels
(e.g. every black-background lemon with a freshness label is "spoiled"; FruitNet bananas are all "good").
Here: one binary label from either head (fresh|none -> good, declining|spoiled|mild|severe -> bad), and every
(type, dataset) cell is weighted so its good and bad halves count equally; a cell with <10% of one label
(one-sided source) is left out. Logistic regression on the cached SigLIP2 embeddings + a per-type bias.

  python3 scripts/train_condition_head.py --out runs/siglip/condition_v2 [--plain] [--lodo]
--plain trains the same model without the source balancing (ablation). --lodo adds leave-one-dataset-out:
train without dataset D, test on all of D's photos (a stand-in for a photo source the model never saw).
L2 strength is chosen on val only; test is reported, never used for a choice.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_quality_scores import auroc, ece, truth_of  # noqa: E402


def load(manifest: Path, emb_path: Path, types: list[str]):
    z = np.load(emb_path)
    emb = dict(zip(z["sha256"].tolist(), z["emb"].astype(np.float32)))
    X, y, t, ds, sp = [], [], [], [], []
    for line in open(manifest, encoding="utf-8"):
        r = json.loads(line)
        p = r["labels"].get("produce")
        lab = truth_of(r["labels"])
        if lab is None or p not in types or r["sha256"] not in emb:
            continue
        X.append(emb[r["sha256"]]); y.append(1.0 if lab == "good" else 0.0)
        t.append(p); ds.append(r["dataset_id"]); sp.append(r["split"])
    return np.stack(X), np.array(y), np.array(t), np.array(ds), np.array(sp)


def weights(y, t, ds, balanced: bool) -> np.ndarray:
    w = np.ones(len(y))
    if not balanced:
        return w
    cell = collections.Counter(zip(t, ds, y))
    for i in range(len(y)):
        g, b = cell[(t[i], ds[i], 1.0)], cell[(t[i], ds[i], 0.0)]
        if min(g, b) / (g + b) < 0.10:
            w[i] = 0.0  # one-sided source for this type: it can only teach "this photo style = this label"
        else:
            w[i] = 0.5 * (g + b) / cell[(t[i], ds[i], y[i])]
    return w * (len(w) / w.sum())


def design(X, t, types):
    T = np.zeros((len(t), len(types)), np.float32)
    T[np.arange(len(t)), [types.index(x) for x in t]] = 1.0
    return np.concatenate([X, T], 1)


def fit(Z, y, w, lam):
    d = Z.shape[1]

    def f(theta):
        s = Z @ theta
        p = 1.0 / (1.0 + np.exp(-s))
        loss = -(w * (y * np.log(p + 1e-12) + (1 - y) * np.log(1 - p + 1e-12))).mean() + lam * (theta[:-len_t] ** 2).sum()
        g = Z.T @ (w * (p - y)) / len(y)
        g[:-len_t] += 2 * lam * theta[:-len_t]
        return loss, g

    len_t = d - 768
    return minimize(f, np.zeros(d), jac=True, method="L-BFGS-B", options={"maxiter": 500}).x


def predict(theta, Z):
    return 1.0 / (1.0 + np.exp(-(Z @ theta)))


def report(p, y, t, types) -> dict:
    out = {}
    for x in types + ["_all"]:
        m = np.ones(len(y), bool) if x == "_all" else t == x
        if m.sum() < 20 or len(set(y[m])) < 2:
            continue
        out[x] = {"n": int(m.sum()), "auroc": round(auroc(p[m][y[m] == 1], p[m][y[m] == 0]), 4),
                  "ece": round(ece(p[m], y[m]), 4),
                  "bad_p_ge_0.8": round(float((p[m][y[m] == 0] >= 0.8).mean()), 4),
                  "good_p_le_0.4": round(float((p[m][y[m] == 1] <= 0.4).mean()), 4)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=Path("data/processed_commercial_v7/manifest.jsonl"))
    ap.add_argument("--emb", type=Path, default=Path("runs/siglip/emb_v9.npz"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--plain", action="store_true")
    ap.add_argument("--lodo", action="store_true")
    a = ap.parse_args()
    bundle = json.load(open("server/model/bundle.json"))
    types = sorted(p for p, h in bundle["supported_heads"].items() if "freshness" in h or "visual_spoilage" in h
                   or "visual_spoilage~coarse" in h)
    X, y, t, ds, sp = load(a.manifest, a.emb, types)
    Z = design(X, t, types)
    w = weights(y, t, ds, not a.plain)
    tr, va, te = sp == "train", sp == "val", sp == "test"
    best = None
    for lam in (1e-5, 1e-4, 1e-3):
        th = fit(Z[tr], y[tr], w[tr], lam)
        pv = predict(th, Z[va])
        # model choice on val: balanced log-loss across types (each type counts once)
        ll = np.mean([-(np.log(np.where(y[va][t[va] == x] == 1, pv[t[va] == x], 1 - pv[t[va] == x]) + 1e-12)).mean()
                      for x in types if (t[va] == x).sum() >= 20])
        if best is None or ll < best[0]:
            best = (ll, lam, th)
    _, lam, th = best
    res = {"lambda": lam, "balanced": not a.plain, "types": types,
           "val": report(predict(th, Z[va]), y[va], t[va], types),
           "test": report(predict(th, Z[te]), y[te], t[te], types)}
    if a.lodo:
        res["lodo"] = {}
        for d in sorted(set(ds)):
            m = ds == d
            if len(set(y[m])) < 2 or m.sum() < 100:
                continue
            keep = tr & ~m
            th_d = fit(Z[keep], y[keep], weights(y[keep], t[keep], ds[keep], not a.plain), lam)
            res["lodo"][d] = report(predict(th_d, Z[m]), y[m], t[m], types)
    a.out.mkdir(parents=True, exist_ok=True)
    np.savez(a.out / "condition_head.npz", W=th[:768].astype(np.float32), b_type=th[768:].astype(np.float32),
             types=np.array(types))
    (a.out / "report.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: res[k]["_all"] for k in ("val", "test")}, indent=1), "lambda", lam)


if __name__ == "__main__":
    main()
