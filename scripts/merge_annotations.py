#!/usr/bin/env python3
"""Merge per-annotator CSVs into annotations.csv + consensus labels.csv.

  python scripts/merge_annotations.py --root data/raw/own_il_collection annotations_*.csv

Consensus per image and head: strict majority wins; ties become a set-valued label
('a|b'); if every annotator left it empty the label stays empty (unknown).
Metadata columns come from the first annotator (sorted by name); disagreement in
fruit_instance_id / produce is an error.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

HEADS = ("ripeness", "freshness", "visual_spoilage")
IDENTITY = ("fruit_instance_id", "produce")


def consensus(values: list[str]) -> str:
    vals = [v for v in values if v]
    if not vals:
        return ""
    c = Counter(vals).most_common()
    top = [v for v, n in c if n == c[0][1]]
    return top[0] if len(top) == 1 else "|".join(sorted(top))


def merge(files: list[Path]) -> tuple[list[dict], list[dict], list[str]]:
    all_rows, errors = [], []
    for f in files:
        with open(f, newline="", encoding="utf-8-sig") as fh:
            all_rows.extend(csv.DictReader(fh))
    by_path: dict[str, list[dict]] = defaultdict(list)
    for r in all_rows:
        by_path[r["path"]].append(r)
    labels = []
    for path in sorted(by_path):
        rows = sorted(by_path[path], key=lambda r: r["annotator"])
        for k in IDENTITY:
            if len({r[k] for r in rows}) > 1:
                errors.append(f"{path}: annotators disagree on {k}: {sorted({r[k] for r in rows})}")
        out = {k: v for k, v in rows[0].items() if k not in ("annotator", "notes")}
        for h in HEADS:
            out[h] = consensus([r[h] for r in rows])
        out["n_annotators"] = str(len(rows))
        labels.append(out)
    return all_rows, labels, errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args()
    ann, labels, errors = merge(args.files)
    for e in errors:
        print("ERROR", e)
    if errors:
        return 1
    for name, rows in (("annotations.csv", ann), ("labels.csv", labels)):
        with open(args.root / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(f"{len(ann)} annotations -> {len(labels)} consensus labels")
    return 0


if __name__ == "__main__":
    sys.exit(main())
