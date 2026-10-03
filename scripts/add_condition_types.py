#!/usr/bin/env python3
"""Condition (good / not good) for more produce types, on the shipped condition head.

  python3 scripts/add_condition_types.py --out runs/siglip/condition_types            (evaluate, write report.json)
  python3 scripts/add_condition_types.py --out runs/siglip/condition_types --ship mango kiwi   (also update server/model)

The shipped v0.13 condition head is one weight vector over SigLIP2 embeddings shared by every type plus one bias
per type (scripts/train_condition_head.py). A new type therefore needs only its own bias: one number fitted on
its train photos (each (dataset, label) cell weighted equally, like the shipped head). The shared vector is not
touched, so no existing type changes.

Measured per type (docs/quality-scoring.md §14): AUROC / ECE / "bad scored >= 0.8" on val and test, and with two
sources, leave-one-dataset-out (bias fitted without that source, tested on all of its photos). The abstain
confidence is chosen on val (error <= 2% above it, as for the shipped types). Gate, declared before looking at
test: val AUROC >= 0.85 and, when a second source exists, leave-one-dataset-out AUROC >= 0.75.
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
from eval_quality_scores import auroc, ece, truth_of  # noqa: E402

SOURCES = [("data/processed_commercial_v7/manifest.jsonl", "runs/siglip/emb_v9.npz"),
           ("data/processed_quality_v8/manifest.jsonl", "runs/siglip/emb_q8.npz"),
           ("data/processed_quality_v9/manifest.jsonl", "runs/siglip/emb_q9.npz"),
           ("data/processed_quality_v10/manifest.jsonl", "runs/siglip/emb_q10.npz")]
CANDIDATES = ["mango", "kiwi", "avocado"]
REPORT_ONLY = ["apple"]  # already shipped: EFIQD green apples are a new, independent test source for it
GATE_VAL_AUROC, GATE_LODO_AUROC, MAX_ERR = 0.85, 0.75, 0.02


def rows(types):
    out = []
    for man, emb_path in SOURCES:
        if not Path(man).exists() or not Path(emb_path).exists():
            continue
        z = np.load(emb_path)
        emb = dict(zip(z["sha256"].tolist(), z["emb"].astype(np.float32)))
        for line in open(man, encoding="utf-8"):
            r = json.loads(line)
            p, lab = r["labels"].get("produce"), truth_of(r["labels"])
            if p in types and lab is not None and r["sha256"] in emb:
                out.append((p, r["dataset_id"], r["split"], 1.0 if lab == "good" else 0.0, emb[r["sha256"]]))
    return out


def cell_weights(y, ds):
    c = collections.Counter(zip(ds, y))
    w = np.array([0.5 * (c[(d, 1.0)] + c[(d, 0.0)]) / c[(d, v)] for d, v in zip(ds, y)])
    return w / w.mean()


def fit_bias(s, y, w) -> float:
    def nll(b):
        p = 1 / (1 + np.exp(-(s + b)))
        return -(w * (y * np.log(p + 1e-12) + (1 - y) * np.log(1 - p + 1e-12))).mean()
    return float(minimize_scalar(nll, bounds=(-30, 30), method="bounded").x)


def metrics(p, y) -> dict | None:
    if len(set(y)) < 2 or len(y) < 20:
        return None
    return {"n": int(len(y)), "n_bad": int((y == 0).sum()), "auroc": round(auroc(p[y == 1], p[y == 0]), 4),
            "ece": round(ece(p, y), 4), "bad_p_ge_0.8": round(float((p[y == 0] >= 0.8).mean()), 4),
            "good_p_le_0.4": round(float((p[y == 1] <= 0.4).mean()), 4)}


def abstain_conf(p, y) -> float:
    conf, pred = np.maximum(p, 1 - p), (p >= 0.5).astype(float)
    for tau in np.round(np.arange(0.50, 1.0, 0.01), 2):
        m = conf >= tau
        if m.sum() >= 10 and (pred[m] != y[m]).mean() <= MAX_ERR:
            return float(tau)
    return 0.99


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ship", nargs="*", default=[])
    a = ap.parse_args()
    model = Path("server/model")
    heads = dict(np.load(model / "heads.npz"))
    b = json.loads((model / "bundle.json").read_text(encoding="utf-8"))
    produce = b["outputs"]["produce"]
    W = heads["condition_W"]  # temperature already folded in (v0.15+)
    data = rows(CANDIDATES + REPORT_ONLY)
    rep, fitted = {}, {}
    for t in CANDIDATES + REPORT_ONLY:
        R = [r for r in data if r[0] == t]
        if not R:
            continue
        ds = np.array([r[1] for r in R]); sp = np.array([r[2] for r in R]); y = np.array([r[3] for r in R])
        s = np.stack([r[4] for r in R]) @ W
        res = {"n": dict(collections.Counter(f"{d}/{'good' if v else 'bad'}" for d, v in zip(ds, y)))}
        if t in REPORT_ONLY:  # shipped bias, photos never used for anything
            bias = float(heads["condition_b"][produce.index(t)])
            for d in sorted(set(ds)):
                m = ds == d
                res[f"shipped/{d}"] = metrics(1 / (1 + np.exp(-(s[m] + bias))), y[m])
            rep[t] = res
            continue
        tr = sp == "train"
        bias = fit_bias(s[tr], y[tr], cell_weights(y[tr], ds[tr]))
        p = 1 / (1 + np.exp(-(s + bias)))
        res["bias"] = round(bias, 4)
        for split in ("val", "test"):
            m = sp == split
            res[split] = metrics(p[m], y[m])
            for d in sorted(set(ds[m])):
                res[f"{split}/{d}"] = metrics(p[m & (ds == d)], y[m & (ds == d)])
        lodo = {}
        for d in sorted(set(ds)):
            keep = tr & (ds != d)
            if len(set(y[keep])) < 2:
                continue
            bd = fit_bias(s[keep], y[keep], cell_weights(y[keep], ds[keep]))
            lodo[d] = metrics(1 / (1 + np.exp(-(s[ds == d] + bd))), y[ds == d])
        res["lodo"] = lodo
        va = sp == "val"
        res["abstain_conf"] = abstain_conf(p[va], y[va])
        res["coverage_val"] = round(float((np.maximum(p[va], 1 - p[va]) >= res["abstain_conf"]).mean()), 4)
        ok_val = res["val"] is not None and res["val"]["auroc"] >= GATE_VAL_AUROC
        ok_lodo = all(v is None or v["auroc"] >= GATE_LODO_AUROC for v in lodo.values())
        res["gate"] = {"val_auroc_ok": ok_val, "lodo_ok": ok_lodo, "two_sources": len(lodo) >= 2,
                       "pass": bool(ok_val and ok_lodo)}
        rep[t] = res
        fitted[t] = (bias, res["abstain_conf"])
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps(rep, indent=1))

    if not a.ship:
        return
    for t in a.ship:
        if not rep.get(t, {}).get("gate", {}).get("pass"):
            sys.exit(f"{t}: did not pass the gate, not shipped")
    for t in a.ship:
        bias, tau = fitted[t]
        heads["condition_b"][produce.index(t)] = np.float32(bias)
        sh = b["supported_heads"].setdefault(t, [])
        if "condition" not in sh:
            sh.append("condition")
        b["thresholds"]["condition_abstain"][t] = tau
    np.savez(model / "heads.npz", **heads)
    b["condition"]["types"] = sorted(set(b["condition"].get("types", [])) | set(a.ship))
    b["condition"]["bias_only_types"] = sorted(set(b["condition"].get("bias_only_types", [])) | set(a.ship))
    for d in ("mango_dhds", "efiqd"):
        if d not in b.get("training_datasets", []):
            b.setdefault("training_datasets", []).append(d)
    digest = hashlib.sha256((model / "heads.npz").read_bytes()).hexdigest()
    b["files"]["heads.npz"] = {"sha256": digest}
    b["model_id"] = f"siglip2_v0.17@{digest[:12]}"
    (model / "bundle.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.copy(model / "bundle.json", Path("app/assets/model/bundle.json"))
    print(b["model_id"], "shipped:", a.ship)


if __name__ == "__main__":
    main()
