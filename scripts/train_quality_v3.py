#!/usr/bin/env python3
"""Quality heads v3: graded condition (good / early problems / rotten) + ripeness, on everyday photos too.

Data: data/processed_commercial_v7 (+ runs/siglip/emb_v9.npz), data/processed_quality_v8 (AgriFreshNET everyday
phone photos with Fresh / Semi-fresh / Rotten, BananaID + BananaImageBD ripeness; runs/siglip/emb_q8.npz) and
data/processed_quality_v9 (VegNet bell pepper + tomato: Ripe / Old / Dried+Damaged; runs/siglip/emb_q9.npz).

Heads (logistic / softmax on SigLIP2 embeddings + a per-type bias; L2 and temperature chosen on val only):
  G  P(good)                 good = fresh|none, bad = declining|spoiled|mild|severe (all sources, as v2)
  R  P(rotten | not good)    only photos with a definite grade (declining-only vs spoiled-only, mild vs severe)
  ripeness softmax           unripe / partially_ripe / ripe / overripe (set-valued labels allowed)
Every (type, dataset, label) cell is weighted so a source cannot teach "this photo style = this label";
cells with <10% of the minority label are left out (one-sided source).

Condition points (existing policy, docs/quality-scoring.md): good 100, early problems 60, rotten 10:
  Condition = 100 P(good) + 60 (1-P(good))(1-P(rotten|bad)) + 10 (1-P(good)) P(rotten|bad)

  python3 scripts/train_quality_v3.py --out runs/siglip/quality_v3 [--lodo]
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
from eval_quality_scores import auroc, ece  # noqa: E402

RIP = ["unripe", "partially_ripe", "ripe", "overripe"]
SOURCES = [("data/processed_commercial_v7/manifest.jsonl", "runs/siglip/emb_v9.npz"),
           ("data/processed_quality_v8/manifest.jsonl", "runs/siglip/emb_q8.npz"),
           ("data/processed_quality_v9/manifest.jsonl", "runs/siglip/emb_q9.npz")]


def as_set(v):
    return set(v) if isinstance(v, list) else ({v} if v and v != "unknown" else set())


def load(types: list[str]):
    rows = []
    for man, embp in SOURCES:
        z = np.load(embp)
        emb = dict(zip(z["sha256"].tolist(), z["emb"].astype(np.float32)))
        for line in open(man, encoding="utf-8"):
            r = json.loads(line)
            p = r["labels"].get("produce")
            if p in types and r["sha256"] in emb:
                r["x"] = emb[r["sha256"]]
                rows.append(r)
    return rows


def targets(r):
    fr, sp = as_set(r["labels"].get("freshness")), as_set(r["labels"].get("visual_spoilage"))
    bad = bool(fr & {"declining", "spoiled"} or sp & {"mild", "severe"})
    good = None if not (bad or "fresh" in fr or "none" in sp) else (0.0 if bad else 1.0)
    rot = None
    if bad:
        if fr == {"spoiled"} or sp == {"severe"}:
            rot = 1.0
        elif fr == {"declining"} or sp == {"mild"}:
            rot = 0.0
    rl = r["labels"].get("ripeness")
    rmask = None
    if rl and rl != "unknown":
        rs = as_set(rl)
        rmask = np.array([c in rs for c in RIP])
    return good, rot, rmask


def balance(keys, y):
    """keys: (type, dataset) per row; y: label per row (hashable). Equal weight per label within each cell."""
    cell = collections.Counter(zip(keys, y))
    per = collections.defaultdict(dict)
    for (k, lab), n in cell.items():
        per[k][lab] = n
    w = np.zeros(len(y))
    for i, (k, lab) in enumerate(zip(keys, y)):
        c = per[k]
        if len(c) < 2 or min(c.values()) / sum(c.values()) < 0.10:
            continue  # one-sided source for this type
        w[i] = sum(c.values()) / (len(c) * c[lab])
    return w * (len(w) / max(w.sum(), 1e-9))


def design(X, t, types):
    T = np.zeros((len(t), len(types)), np.float32)
    T[np.arange(len(t)), [types.index(x) for x in t]] = 1.0
    return np.concatenate([X, T], 1)


def fit_binary(Z, y, w, lam):
    nt = Z.shape[1] - 768

    def f(th):
        s = Z @ th
        p = 1 / (1 + np.exp(-s))
        loss = -(w * (y * np.log(p + 1e-12) + (1 - y) * np.log(1 - p + 1e-12))).mean() + lam * (th[:-nt] ** 2).sum()
        g = Z.T @ (w * (p - y)) / len(y)
        g[:-nt] += 2 * lam * th[:-nt]
        return loss, g
    return minimize(f, np.zeros(Z.shape[1]), jac=True, method="L-BFGS-B", options={"maxiter": 500}).x


def fit_softmax(Z, M, w, lam):
    """Set-valued softmax: loss = -log sum_{allowed} p. Z includes type one-hots (not regularised)."""
    nt, C = Z.shape[1] - 768, M.shape[1]

    def f(th):
        W = th.reshape(C, -1)
        L = Z @ W.T
        L = L - L.max(1, keepdims=True)
        P = np.exp(L); P /= P.sum(1, keepdims=True)
        pa = (P * M).sum(1)
        loss = -(w * np.log(pa + 1e-12)).mean() + lam * (W[:, :-nt] ** 2).sum()
        G = P - (P * M) / (pa[:, None] + 1e-12)          # d(-log pa)/dL
        gW = (w[:, None] * G).T @ Z / len(w)
        gW[:, :-nt] += 2 * lam * W[:, :-nt]
        return loss, gW.ravel()
    return minimize(f, np.zeros(C * Z.shape[1]), jac=True, method="L-BFGS-B", options={"maxiter": 400}).x.reshape(C, -1)


def fit_T(s, y):
    grid = np.exp(np.linspace(np.log(0.3), np.log(5), 80))
    nll = lambda T: -(np.log(np.where(y == 1, 1 / (1 + np.exp(-s / T)), 1 - 1 / (1 + np.exp(-s / T))) + 1e-12)).mean()
    return float(min(grid, key=nll))


def choose(fitf, Z, y, w, tr, va, metric):
    best = None
    for lam in (1e-6, 1e-5, 1e-4, 1e-3):
        th = fitf(Z[tr], y[tr], w[tr], lam)
        m = metric(th, Z[va], y[va])
        if best is None or m < best[0]:
            best = (m, lam, th)
    return best[1], best[2]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--lodo", action="store_true")
    a = ap.parse_args()
    bundle = json.load(open("server/model/bundle.json"))
    types = [p for p in bundle["outputs"]["produce"] if p != "other"]
    rows = load(types)
    X = np.stack([r["x"] for r in rows]); t = np.array([r["labels"]["produce"] for r in rows])
    ds = np.array([r["dataset_id"] for r in rows]); sp = np.array([r["split"] for r in rows])
    G, R, RM = zip(*[targets(r) for r in rows])
    tr, va, te = sp == "train", sp == "val", sp == "test"
    cond_types = sorted({x for x, g in zip(t, G) if g is not None})
    out = {"types": types}

    # ---- G: P(good)
    mg = np.array([g is not None for g in G]); yg = np.array([g if g is not None else 0 for g in G], float)
    Zg = design(X[mg], t[mg], cond_types)
    keys = list(zip(t[mg], ds[mg])); wg = balance(keys, yg[mg].tolist())
    nll = lambda th, Z, y: -(np.log(np.where(y == 1, 1 / (1 + np.exp(-Z @ th)), 1 - 1 / (1 + np.exp(-Z @ th))) + 1e-12)).mean()
    lam_g, th_g = choose(fit_binary, Zg, yg[mg], wg, tr[mg], va[mg], nll)
    Tg = fit_T(Zg[va[mg]] @ th_g, yg[mg][va[mg]])

    # ---- R: P(rotten | not good), graded photos only
    mr0 = np.array([x is not None for x in R]); yr = np.array([x if x is not None else 0 for x in R], float)
    w0 = balance(list(zip(t[mr0], ds[mr0])), yr[mr0].tolist())
    # R is fitted, calibrated and used only for types that have BOTH grades with weight in train (graded data,
    # e.g. AgriFreshNET). Other types' "spoiled-only" rows are one-sided: including them only squashes the
    # calibration towards 0.5 (measured: rotten 0.53 vs early 0.46 despite AUROC 0.93).
    graded = sorted(x for x in set(t[mr0]) if all(((t[mr0] == x) & tr[mr0] & (w0 > 0) & (yr[mr0] == v)).any() for v in (0.0, 1.0)))
    mr = mr0 & np.isin(t, graded)
    rot_types = graded
    Zr = design(X[mr], t[mr], rot_types)
    wr = balance(list(zip(t[mr], ds[mr])), yr[mr].tolist())
    lam_r, th_r = choose(fit_binary, Zr, yr[mr], wr, tr[mr], va[mr], nll)
    Tr = fit_T(Zr[va[mr]] @ th_r, yr[mr][va[mr]])

    # ---- ripeness softmax
    mm = np.array([m is not None for m in RM]); M = np.stack([m if m is not None else np.ones(4, bool) for m in RM])
    rip_types = sorted(set(t[mm]))
    Zm = design(X[mm], t[mm], rip_types)
    first = np.array([RIP[int(np.argmax(m))] + "|" + str(int(m.sum())) for m in M[mm]])
    wm = balance(list(zip(t[mm], ds[mm])), first.tolist())
    wm = np.where(wm > 0, wm, 1.0)  # ripeness sets are single-source per stage: keep them, balance only the mix

    def snll(W, Z, Mv):
        L = Z @ W.T; L -= L.max(1, keepdims=True); P = np.exp(L); P /= P.sum(1, keepdims=True)
        return -np.log((P * Mv).sum(1) + 1e-12).mean()
    lam_m, W_m = choose(fit_softmax, Zm, M[mm], wm, tr[mm], va[mm], snll)

    np.savez(args_out(a) / "quality_v3.npz",
             G_W=th_g[:768].astype(np.float32), G_b=th_g[768:].astype(np.float32), G_types=np.array(cond_types), G_T=Tg,
             R_W=th_r[:768].astype(np.float32), R_b=th_r[768:].astype(np.float32), R_types=np.array(rot_types), R_graded=np.array(graded), R_T=Tr,
             M_W=W_m[:, :768].astype(np.float32), M_b=W_m[:, 768:].astype(np.float32), M_types=np.array(rip_types))
    out.update({"lambda": {"G": lam_g, "R": lam_r, "ripeness": lam_m}, "T": {"G": Tg, "R": Tr},
                "cond_types": cond_types, "rot_types": rot_types, "R_graded": graded, "rip_types": rip_types})

    # ---- held-out-type check for R (does "how bad" transfer to a type it never saw graded?)
    out["R_leave_one_type_out"] = {}
    for x in rot_types:
        keep = tr[mr] & (t[mr] != x); m = (t[mr] == x) & (te[mr] | va[mr])
        if len(set(yr[mr][m])) < 2:
            continue
        Zx = design(X[mr], t[mr], [y_ for y_ in rot_types if y_ != x] + [x])
        th = fit_binary(Zx[keep], yr[mr][keep], wr[keep], lam_r)
        th[-1] = 0.0  # the held-out type's bias is unknown -> 0
        s = 1 / (1 + np.exp(-(Zx[m] @ th) / Tr))
        out["R_leave_one_type_out"][x] = round(auroc(s[yr[mr][m] == 1], s[yr[mr][m] == 0]), 3)

    if a.lodo:
        out["G_lodo"] = {}
        for d in sorted(set(ds[mg])):
            m = ds[mg] == d
            if len(set(yg[mg][m])) < 2 or m.sum() < 100:
                continue
            keep = tr[mg] & ~m
            th = fit_binary(Zg[keep], yg[mg][keep], balance([k for k, kk in zip(keys, keep) if kk], yg[mg][keep].tolist()), lam_g)
            p = 1 / (1 + np.exp(-(Zg[m] @ th) / Tg)); y = yg[mg][m]
            out["G_lodo"][d] = {"n": int(m.sum()), "auroc": round(auroc(p[y == 1], p[y == 0]), 3),
                                "bad_p_ge_0.8": round(float((p[y == 0] >= .8).mean()), 3),
                                "good_p_le_0.4": round(float((p[y == 1] <= .4).mean()), 3)}
    (args_out(a) / "report.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("lambda", "T", "R_leave_one_type_out")}, indent=1))


def args_out(a):
    a.out.mkdir(parents=True, exist_ok=True)
    return a.out


if __name__ == "__main__":
    main()
