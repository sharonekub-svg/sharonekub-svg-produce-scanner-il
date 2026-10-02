#!/usr/bin/env python3
"""Audit the quality labels (ripeness / freshness / visual spoilage) in a processed manifest.

For every produce type: label counts per head and split, how many datasets and which capture conditions they come
from, and the share of "good" vs "bad" examples. Set-valued labels (e.g. ["declining", "spoiled"]) are counted
under a joined name ("declining|spoiled"). Output: JSON + a markdown table (docs/results/quality_audit.*).

  python3 scripts/audit_quality_data.py data/processed_commercial_v7 docs/results/quality_audit
"""
from __future__ import annotations

import collections
import csv
import json
import sys
from pathlib import Path

HEADS = ("ripeness", "freshness", "visual_spoilage")


def lab(v) -> str | None:
    if v is None or v == "unknown":
        return None
    return "|".join(v) if isinstance(v, list) else v


def main(processed: Path, out: Path) -> None:
    reg = {r["dataset_id"]: r for r in csv.DictReader(open("data/dataset_registry.csv", encoding="utf-8"))}
    rows = [json.loads(l) for l in open(processed / "manifest.jsonl", encoding="utf-8")]
    stats: dict = collections.defaultdict(lambda: {"n": 0, "datasets": collections.Counter(),
                                                    **{h: collections.defaultdict(collections.Counter) for h in HEADS}})
    for r in rows:
        p = r["labels"].get("produce")
        if not p:
            continue
        s = stats[p]
        has_quality = False
        for h in HEADS:
            v = lab(r["labels"].get(h))
            if v:
                s[h][r["split"]][v] += 1
                has_quality = True
        if has_quality:
            s["n"] += 1
            s["datasets"][r["dataset_id"]] += 1
    report = {}
    for p, s in sorted(stats.items()):
        if not s["n"]:
            continue
        report[p] = {
            "n_quality_labelled": s["n"],
            "datasets": {d: {"n": n, "capture": (reg.get(d, {}).get("capture_conditions") or "")[:120]}
                         for d, n in s["datasets"].most_common()},
            **{h: {sp: dict(c) for sp, c in s[h].items()} for h in HEADS if s[h]},
        }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    lines = ["| type | head | train | val | test |", "|---|---|---|---|---|"]
    for p, r in report.items():
        for h in HEADS:
            if h in r:
                cell = lambda sp: ", ".join(f"{k} {v}" for k, v in sorted(r[h].get(sp, {}).items())) or "–"
                lines.append(f"| {p} | {h} | {cell('train')} | {cell('val')} | {cell('test')} |")
    out.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
