#!/usr/bin/env python3
"""Compare the shipped condition head (v0.13) with quality v3 on the same test photos.

Grades: good (fresh|none), early (declining-only|mild-only), rotten (spoiled-only|severe-only), bad-any (mixed set).
Reports per type: mean condition score per grade, Spearman(score, grade), share of rotten scored >= 75, share of
good scored < 50, share of early scored in the middle band 30-74, and banana ripeness confusion (old vs new).

  python3 scripts/eval_quality_v3.py --split test --out docs/results/quality_v3_test.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_quality_v3 import RIP, SOURCES, as_set  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def grade(labels):
    fr, sp = as_set(labels.get("freshness")), as_set(labels.get("visual_spoilage"))
    if fr == {"spoiled"} or sp == {"severe"}:
        return "rotten"
    if fr == {"declining"} or sp == {"mild"}:
        return "early"
    if fr & {"declining", "spoiled"} or sp & {"mild", "severe"}:
        return "bad"
    if "fresh" in fr or "none" in sp:
        return "good"
    return None


def spearman(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--model", type=Path, default=Path("runs/siglip/quality_v3/quality_v3.npz"))
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    b = json.load(open("server/model/bundle.json")); P = b["outputs"]["produce"]
    hd = np.load("server/model/heads.npz"); Tc = b["temperatures"].get("condition", 1.0)
    maxp = b["thresholds"].get("condition_max_p", 1.0); old_types = set(b.get("condition", {}).get("types", []))
    q = np.load(a.model)
    Gt, Rt, Mt = list(q["G_types"]), list(q["R_types"]), list(q["M_types"])
    graded = set(q["R_graded"].tolist()) if "R_graded" in q.files else set(Rt)
    sig = lambda z: 1 / (1 + np.exp(-z))
    res = {}
    rip = {"old": [], "new": [], "true": []}
    for man, embp in SOURCES:
        z = np.load(embp); emb = dict(zip(z["sha256"].tolist(), z["emb"].astype(np.float32)))
        for line in open(man, encoding="utf-8"):
            r = json.loads(line)
            p = r["labels"].get("produce")
            if r["split"] != a.split or r["sha256"] not in emb or p not in P:
                continue
            x = emb[r["sha256"]]
            if p == "banana" and isinstance(r["labels"].get("ripeness"), str) and r["labels"]["ripeness"] != "unknown":
                lo = x @ hd["ripeness_W"].T + hd["ripeness_b"]
                rip["old"].append(RIP[int(np.argmax(lo))])
                rip["new"].append(RIP[int(np.argmax(x @ q["M_W"].T + q["M_b"][:, Mt.index("banana")]))])
                rip["true"].append(r["labels"]["ripeness"])
            g = grade(r["labels"])
            if g is None or p not in Gt:
                continue
            pg = sig((x @ q["G_W"] + q["G_b"][Gt.index(p)]) / float(q["G_T"]))
            if p in graded:
                pr = sig((x @ q["R_W"] + q["R_b"][Rt.index(p)]) / float(q["R_T"]))
                new = 100 * pg + 60 * (1 - pg) * (1 - pr) + 10 * (1 - pg) * pr
            else:
                new = 100 * pg
            old = None
            if p in old_types:
                po = sig((float(x @ hd["condition_W"]) + hd["condition_b"][P.index(p)]) / Tc)
                old = 100 * min(po, maxp)
            d = res.setdefault(p, {"g": [], "new": [], "old": [], "ds": []})
            d["g"].append(g); d["new"].append(new); d["old"].append(old); d["ds"].append(r["dataset_id"])
    order = {"good": 2, "early": 1, "bad": 0.5, "rotten": 0}
    report = {}
    for p, d in sorted(res.items()):
        g = np.array(d["g"]); rep = {"n": {k: int((g == k).sum()) for k in order if (g == k).any()}}
        for key in ("old", "new"):
            s = np.array([v if v is not None else np.nan for v in d[key]], float)
            if np.isnan(s).all():
                continue
            m = ~np.isnan(s)
            rep[key] = {"mean_by_grade": {k: round(float(s[m & (g == k)].mean()), 1) for k in order if (m & (g == k)).any()},
                        "spearman": round(spearman(s[m], np.array([order[x] for x in g[m]])), 3),
                        "rotten_ge75": round(float((s[m & (g == "rotten")] >= 75).mean()), 3) if (m & (g == "rotten")).any() else None,
                        "badany_ge75": round(float((s[m & (g != "good")] >= 75).mean()), 3) if (m & (g != "good")).any() else None,
                        "good_lt50": round(float((s[m & (g == "good")] < 50).mean()), 3) if (m & (g == "good")).any() else None,
                        "early_mid": round(float(((s >= 30) & (s < 75))[m & (g == "early")].mean()), 3) if (m & (g == "early")).any() else None}
        report[p] = rep
    if rip["true"]:
        cm = lambda pred: {t: {pp: int(sum(1 for a_, b_ in zip(rip["true"], pred) if a_ == t and b_ == pp)) for pp in RIP} for t in RIP}
        report["_banana_ripeness"] = {"old_acc": round(float(np.mean([a_ == b_ for a_, b_ in zip(rip["true"], rip["old"])])), 3),
                                      "new_acc": round(float(np.mean([a_ == b_ for a_, b_ in zip(rip["true"], rip["new"])])), 3),
                                      "old": cm(rip["old"]), "new": cm(rip["new"])}
    if a.out:
        a.out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    for p, rep in report.items():
        if p.startswith("_"):
            print(p, rep["old_acc"], "->", rep["new_acc"]); continue
        o, n = rep.get("old", {}), rep["new"]
        print(f"{p:12} n={rep['n']}\n   old: {o.get('mean_by_grade')} rho={o.get('spearman')} bad>=75={o.get('badany_ge75')} good<50={o.get('good_lt50')}"
              f"\n   new: {n['mean_by_grade']} rho={n['spearman']} bad>=75={n['badany_ge75']} good<50={n['good_lt50']} early_mid={n['early_mid']}")


if __name__ == "__main__":
    main()
