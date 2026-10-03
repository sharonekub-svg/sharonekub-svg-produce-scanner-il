#!/usr/bin/env python3
"""Fine-tune the produce (identification) head with spoiled / everyday photos, anchored to the shipped head.

Why: on the quality test sets, fruit in bad condition is identified (answered) far less often than good fruit
(51% vs 80%), so a rotten grape or cucumber gets no score at all. The shipped head was trained mostly on good fruit.

Train: train splits of data/processed_commercial_v7, processed_quality_v8/v9/v10 and the Open Images train crops
(runs/siglip/oi_train3.npz, grapefruit skipped as before). Loss: class-balanced softmax over the 39 outputs ("other"
= logsumexp of the fixed negative-prompt logits + bias, as shipped) + lam * ||W - W_shipped||^2. lam and the
temperature are chosen on validation (OI "cal" half + quality val), test is only reported.

  python3 scripts/finetune_produce_head.py --out runs/siglip/produce_v16
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
from train_quality_v3 import SOURCES as Q_SOURCES  # noqa: E402

# + MangoDHDS / EFIQD (v0.17): mango, avocado, kiwi and green apples, many of them spoiled
SOURCES = Q_SOURCES + [("data/processed_quality_v10/manifest.jsonl", "runs/siglip/emb_q10.npz")]


def load_rows(P):
    X, y, sp, src = [], [], [], []
    for man, embp in SOURCES:
        z = np.load(embp); emb = dict(zip(z["sha256"].tolist(), z["emb"].astype(np.float32)))
        for line in open(man, encoding="utf-8"):
            r = json.loads(line)
            p = r["labels"].get("produce")
            if r["sha256"] in emb and p in P:
                X.append(emb[r["sha256"]]); y.append(P.index(p)); sp.append(r["split"]); src.append(r["dataset_id"])
    d = np.load("runs/siglip/oi_train3.npz", allow_pickle=True)
    for e, t in zip(d["emb"].astype(np.float32), d["true"]):
        if t in P and t != "grapefruit":
            X.append(e); y.append(P.index(t)); sp.append("train"); src.append("open_images_v7")
    r3 = np.load("runs/siglip/oi_real3.npz", allow_pickle=True)
    for e, t, s in zip(r3["emb"], r3["true"], r3["split"]):
        if t in P:
            X.append(e.astype(np.float32)); y.append(P.index(t)); sp.append("val" if s == "cal" else "test"); src.append("oi_real")
    return np.stack(X), np.array(y), np.array(sp), np.array(src)


def other_logit(X, hd):
    neg = X @ hd["neg_W"].T
    m = neg.max(1)
    return m + np.log(np.exp(neg - m[:, None]).sum(1))


def logits(X, W, b, oth):
    return np.concatenate([X @ W.T + b[:-1], (oth + b[-1])[:, None]], 1)


def fit(X, y, w, oth, W0, b0, lam):
    C = W0.shape[0] + 1
    Y = np.eye(C)[y]

    def f(th):
        W = th[:W0.size].reshape(W0.shape); b = th[W0.size:]
        L = logits(X, W, b, oth); L -= L.max(1, keepdims=True)
        Pm = np.exp(L); Pm /= Pm.sum(1, keepdims=True)
        loss = -(w * np.log((Pm * Y).sum(1) + 1e-12)).sum() / w.sum() + lam * ((W - W0) ** 2).sum() + 1e-4 * ((b - b0) ** 2).sum()
        G = (Pm - Y) * (w / w.sum())[:, None]
        gW = G[:, :-1].T @ X + 2 * lam * (W - W0)
        gb = G.sum(0) + 2e-4 * (b - b0)
        return loss, np.concatenate([gW.ravel(), gb])
    th = minimize(f, np.concatenate([W0.ravel(), b0]), jac=True, method="L-BFGS-B", options={"maxiter": 300}).x
    return th[:W0.size].reshape(W0.shape).astype(np.float32), th[W0.size:].astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    b = json.load(open("server/model/bundle.json")); P = b["outputs"]["produce"]
    hd = dict(np.load("server/model/heads.npz"))
    X, y, sp, src = load_rows(P)
    oth = other_logit(X, hd)
    tr, va = sp == "train", sp == "val"
    # class-balanced, and each source counts at most as much as Open Images per class
    cnt = collections.Counter(zip(y[tr], src[tr]))
    per_class = collections.Counter(y[tr])
    w = np.array([1.0 / per_class[yy] / max(1, len({s for (c, s) in cnt if c == yy})) * (1.0 / cnt[(yy, ss)]) * per_class[yy]
                  for yy, ss in zip(y[tr], src[tr])])
    W0, b0 = hd["produce_W"].astype(np.float32), hd["produce_b"].astype(np.float32)
    T0 = b["temperatures"]["produce"]
    best = None
    for lam in (1e-3, 1e-4, 1e-5, 3e-6, 1e-6, 0.0):
        W, bb = fit(X[tr], y[tr], w, oth[tr], W0, b0, lam)
        L = logits(X[va], W, bb, oth[va]) / T0
        L -= L.max(1, keepdims=True); Pm = np.exp(L); Pm /= Pm.sum(1, keepdims=True)
        # validation objective: mean per-class NLL, OI real photos and quality photos weighted equally
        nll = -np.log(Pm[np.arange(len(L)), y[va]] + 1e-12)
        parts = [nll[src[va] == "oi_real"].mean(), nll[src[va] != "oi_real"].mean()]
        score = float(np.mean(parts))
        print("lam", lam, "val nll oi/quality", [round(float(x), 4) for x in parts], flush=True)
        if best is None or score < best[0]:
            best = (score, lam, W, bb)
    _, lam, W, bb = best
    Lv = logits(X[va], W, bb, oth[va])
    grid = np.exp(np.linspace(np.log(0.5), np.log(3), 60))

    def nllT(T):
        L = Lv / T; L = L - L.max(1, keepdims=True); Pm = np.exp(L); Pm /= Pm.sum(1, keepdims=True)
        return -np.log(Pm[np.arange(len(L)), y[va]] + 1e-12).mean()
    T = float(min(grid, key=nllT))
    a.out.mkdir(parents=True, exist_ok=True)
    np.savez(a.out / "produce_head.npz", produce_W=W, produce_b=bb, T=T, lam=lam)
    print("chosen lam", lam, "T", round(T, 3))


if __name__ == "__main__":
    main()
