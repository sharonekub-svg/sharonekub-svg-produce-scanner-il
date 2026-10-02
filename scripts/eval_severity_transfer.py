#!/usr/bin/env python3
"""Can "how bad" (R head, trained on graded types only) be used for a type that has no graded labels?

For every non-graded type, on val + test photos labelled rotten-only (freshness "spoiled" or spoilage "severe", no
"declining"/"mild" in the set) it reports the share R calls rotten (P(rotten | not good) >= 0.5) with the type bias
set to 0 (the type never had graded data). Together with leave-one-type-out AUROC on the graded types
(train_quality_v3.py report) this is the evidence for showing early / rotten on transferred types.

  python3 scripts/eval_severity_transfer.py runs/siglip/quality_v3
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_quality_v3 import SOURCES, as_set  # noqa: E402

run = Path(sys.argv[1])
q = np.load(run / "quality_v3.npz")
graded = set(q["R_graded"].tolist()); Rt = list(q["R_types"])
bias0 = float(np.mean(q["R_b"]))  # unknown type: mean of the graded types' biases
sig = lambda z: 1 / (1 + np.exp(-z))
res = {}
for man, embp in SOURCES:
    z = np.load(embp); emb = dict(zip(z["sha256"].tolist(), z["emb"].astype(np.float32)))
    for line in open(man, encoding="utf-8"):
        r = json.loads(line)
        p = r["labels"].get("produce")
        if r["split"] not in ("val", "test") or r["sha256"] not in emb or p in graded:
            continue
        fr, sp = as_set(r["labels"].get("freshness")), as_set(r["labels"].get("visual_spoilage"))
        if not (fr == {"spoiled"} or sp == {"severe"}):
            continue
        pr = sig((emb[r["sha256"]] @ q["R_W"] + bias0) / float(q["R_T"]))
        res.setdefault(p, []).append(pr)
out = {p: {"n": len(v), "called_rotten": round(float(np.mean(np.array(v) >= 0.5)), 3), "mean_p": round(float(np.mean(v)), 3)}
       for p, v in sorted(res.items())}
rep = json.loads((run / "report.json").read_text())
out["_leave_one_type_out_auroc"] = rep.get("R_leave_one_type_out")
(run / "severity_transfer.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
