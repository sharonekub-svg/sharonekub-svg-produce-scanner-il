#!/usr/bin/env python3
"""Evaluation framework for the quality score (docs/quality-scoring.md, "Evaluation").

Runs the shipped heads on cached SigLIP embeddings of the labelled photos (runs/siglip/emb_v9.npz) and the app's
decision logic (ml/inference/decision.py, parity-tested with the app), with the produce forced to the true type so
only the quality part is measured. Per type and split it reports:
  - score distribution for photos labelled good (fresh / no spoilage) and bad (declining-or-spoiled / spoilage)
  - false high  = bad photo scored >= 8;  false low = good photo scored <= 4
  - AUROC of the score for good-vs-bad, Spearman of score vs the ordinal label
  - ECE (expected calibration error, 10 bins) of P(good) from the condition head
  - ripeness confusion matrix (types with a ripeness head)
  - coverage: share of photos that get a score at all
The test split is reported but never used to choose anything; choices are made on val.

  python3 scripts/eval_quality_scores.py --split val --out docs/results/quality_eval_val.json
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.common.taxonomy import HEADS  # noqa: E402
from ml.evaluation.calibration import softmax  # noqa: E402
from ml.inference import decision  # noqa: E402
from server import app as srv  # noqa: E402

BAD_FR = {"declining", "spoiled"}
BAD_SP = {"mild", "severe"}


def as_set(v):
    return set(v) if isinstance(v, list) else ({v} if v and v != "unknown" else set())


def truth_of(labels) -> str | None:
    fr, sp = as_set(labels.get("freshness")), as_set(labels.get("visual_spoilage"))
    if fr & BAD_FR or sp & BAD_SP:
        return "bad"
    if "fresh" in fr or "none" in sp:
        return "good"
    return None


def auroc(pos: np.ndarray, neg: np.ndarray) -> float | None:
    if len(pos) == 0 or len(neg) == 0:
        return None
    s = np.concatenate([pos, neg]); r = s.argsort().argsort() + 1.0
    # ties: average ranks
    _, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, r); r = (sums / cnt)[inv]
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float | None:
    if len(p) == 0:
        return None
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum(abs(p[idx == b].mean() - y[idx == b].mean()) * (idx == b).mean() for b in range(bins) if (idx == b).any()))


def probs_for(e, emb: np.ndarray, temps: dict) -> dict:
    lg = e._heads(emb)
    probs = {h: softmax(lg[h][None], temps.get(h, 1.0))[0] for h in HEADS}
    probs["freshness_general"] = 1.0 / (1.0 + np.exp(-lg["freshness_general"]))
    if "condition" in lg:
        probs["condition"] = 1.0 / (1.0 + np.exp(-lg["condition"] / temps.get("condition", 1.0)))
    if "condition_rot" in lg:
        probs["condition_rot"] = 1.0 / (1.0 + np.exp(-lg["condition_rot"]))
    return probs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="val", choices=["val", "test"])
    ap.add_argument("--manifest", type=Path, default=Path("data/processed_commercial_v7/manifest.jsonl"))
    ap.add_argument("--emb", type=Path, default=Path("runs/siglip/emb_v9.npz"))
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()

    e = srv.engine(); b = e.bundle; temps = b.get("temperatures", {}); sup = b["supported_heads"]
    P = b["outputs"]["produce"]; R = b["outputs"]["ripeness"]
    z = np.load(a.emb); emb = dict(zip(z["sha256"].tolist(), z["emb"].astype(np.float32)))
    decide = decision.decide
    per = collections.defaultdict(lambda: {"good": [], "bad": [], "pgood": [], "y": [], "unscored": 0, "rip": []})
    for line in open(a.manifest, encoding="utf-8"):
        r = json.loads(line)
        if r["split"] != a.split or r["sha256"] not in emb:
            continue
        L = r["labels"]; prod = L.get("produce")
        if prod not in P:
            continue
        t = truth_of(L); rl = L.get("ripeness")
        rip_true = rl if isinstance(rl, str) and rl != "unknown" else None
        if t is None and rip_true is None:
            continue
        probs = probs_for(e, emb[r["sha256"]], temps)
        oh = np.zeros(len(P)); oh[P.index(prod)] = 1.0; probs["produce"] = oh
        res = decide(e.tax, probs, sup, thresholds=b.get("thresholds"))
        d = per[prod]
        if rip_true and "ripeness" in sup.get(prod, []):
            d["rip"].append((rip_true, R[int(np.argmax(probs["ripeness"]))]))
        if t is None:
            continue
        if res.score is None:
            d["unscored"] += 1
            continue
        d[t].append(res.score)
        d["low"] = d.get("low", 0) + int(bool(getattr(res, "low_confidence", False)))
        if res.condition is not None and res.condition.available:
            cond = float(probs["condition"][P.index(prod)])
        else:
            fr = probs["freshness"]; cond = float(fr[b["outputs"]["freshness"].index("fresh")])
        d["pgood"].append(cond); d["y"].append(1.0 if t == "good" else 0.0)

    report = {}
    for prod, d in sorted(per.items()):
        g, bd = np.array(d["good"], float), np.array(d["bad"], float)
        hist = lambda x: {int(k): int(v) for k, v in zip(*np.unique(x, return_counts=True))} if len(x) else {}
        rep = {"n_good": len(g), "n_bad": len(bd), "unscored": d["unscored"],
               "false_high_bad_ge8": round(float((bd >= 8).mean()), 3) if len(bd) else None,
               "false_low_good_le4": round(float((g <= 4).mean()), 3) if len(g) else None,
               "share_ge8_all": round(float((np.concatenate([g, bd]) >= 8).mean()), 3) if len(g) + len(bd) else None,
               "auroc_score": None if auroc(g, bd) is None else round(auroc(g, bd), 3),
               "ece_condition": None if not d["y"] else round(ece(np.array(d["pgood"]), np.array(d["y"])), 3),
               "low_confidence_share": round(d.get("low", 0) / max(len(g) + len(bd), 1), 3),
               "hist_good": hist(g), "hist_bad": hist(bd)}
        if d["rip"]:
            labels = R
            cm = {t: {p: 0 for p in labels} for t in labels}
            for t_, p_ in d["rip"]:
                if t_ in cm:
                    cm[t_][p_] += 1
            rep["ripeness_confusion"] = cm
            rep["ripeness_acc"] = round(float(np.mean([t_ == p_ for t_, p_ in d["rip"]])), 3)
        report[prod] = rep
    allg = np.concatenate([np.array(d["good"], float) for d in per.values()])
    allb = np.concatenate([np.array(d["bad"], float) for d in per.values()])
    report["_all"] = {"n_good": len(allg), "n_bad": len(allb),
                      "false_high_bad_ge8": round(float((allb >= 8).mean()), 3),
                      "false_low_good_le4": round(float((allg <= 4).mean()), 3),
                      "share_ge8_all": round(float((np.concatenate([allg, allb]) >= 8).mean()), 3),
                      "auroc_score": round(auroc(allg, allb), 3)}
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"{'type':12} {'good':>5} {'bad':>5} {'falseHi':>8} {'falseLo':>8} {'>=8':>6} {'AUROC':>6} {'ECE':>6} {'ripAcc':>6}")
    for k, v in report.items():
        print(f"{k:12} {v['n_good']:5} {v['n_bad']:5} {str(v['false_high_bad_ge8']):>8} {str(v['false_low_good_le4']):>8} "
              f"{str(v['share_ge8_all']):>6} {str(v['auroc_score']):>6} {str(v.get('ece_condition')):>6} {str(v.get('ripeness_acc', '')):>6}")


if __name__ == "__main__":
    main()
