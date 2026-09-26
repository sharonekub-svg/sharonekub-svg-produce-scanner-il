#!/usr/bin/env python3
"""Validate our own collection before it enters the manifest.

  python scripts/validate_collection.py --root data/raw/own_il_collection [--agreement]

Checks: required columns, vocabularies, files exist and decode, one produce/variety per
fruit instance, no duplicate paths, day indices consistent with dates, ripeness only for
produce types with a grading guide, set-valued syntax. --agreement computes Cohen's kappa
from annotations.csv (quadratic-weighted for ripeness) against the protocol threshold.
Exit code 1 on any error.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.common.taxonomy import load_taxonomy  # noqa: E402
from ml.evaluation.agreement import cohen_kappa, pairwise_from_rows  # noqa: E402
from ml.preprocessing.image_io import check_image  # noqa: E402

REQUIRED = ["path", "fruit_instance_id", "produce", "variety", "capture_date", "day", "device", "lighting",
            "background", "distance_cm", "ripeness", "freshness", "visual_spoilage", "storage", "cut_check"]
LIGHTING = {"daylight", "kitchen_led", "dim"}
BACKGROUND = {"counter", "in_hand", "fruit_bowl", "plastic_bag", "plate", "market_stall", "supermarket_shelf", "other"}
CUT_CHECK = {"", "n/a", "ok", "internal_browning", "mould", "rot"}
RIPENESS_GRADED = {"banana", "avocado", "tomato", "mango", "peach", "nectarine", "strawberry", "pear", "plum", "kiwi", "persimmon", "melon"}
KAPPA_MIN = 0.6


def validate(root: Path, check_files: bool = True) -> list[str]:
    tax = load_taxonomy()
    errors: list[str] = []
    path = root / "labels.csv"
    if not path.exists():
        return [f"missing {path}"]
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            return [f"labels.csv missing columns {missing}"]
        rows = list(reader)
    seen = set()
    inst = defaultdict(set)
    first_date: dict[str, tuple[dt.date, int]] = {}
    for n, r in enumerate(rows, start=2):
        loc = f"labels.csv:{n}"
        if r["path"] in seen:
            errors.append(f"{loc}: duplicate path {r['path']}")
        seen.add(r["path"])
        if r["produce"] not in tax.produce or r["produce"] == "other":
            errors.append(f"{loc}: produce '{r['produce']}' not a target produce")
        inst[r["fruit_instance_id"]].add((r["produce"], r["variety"]))
        for head in ("ripeness", "freshness", "visual_spoilage"):
            v = r[head].strip()
            if v:
                try:
                    tax.encode(head, v.split("|") if "|" in v else v)
                except ValueError as e:
                    errors.append(f"{loc}: {e}")
        if r["ripeness"].strip() and r["produce"] not in RIPENESS_GRADED:
            errors.append(f"{loc}: ripeness given for {r['produce']}, which has no ripeness grading guide")
        if r["lighting"] not in LIGHTING:
            errors.append(f"{loc}: lighting '{r['lighting']}' not in {sorted(LIGHTING)}")
        if r["background"] not in BACKGROUND:
            errors.append(f"{loc}: background '{r['background']}' not in {sorted(BACKGROUND)}")
        if r["cut_check"] not in CUT_CHECK:
            errors.append(f"{loc}: cut_check '{r['cut_check']}' invalid")
        try:
            d, day = dt.date.fromisoformat(r["capture_date"]), int(r["day"])
            if day < 0:
                raise ValueError
            fd = first_date.setdefault(r["fruit_instance_id"], (d - dt.timedelta(days=day), day))
            if (d - fd[0]).days != day:
                errors.append(f"{loc}: day={day} inconsistent with capture_date for {r['fruit_instance_id']}")
        except ValueError:
            errors.append(f"{loc}: bad capture_date/day")
        try:
            if int(r["distance_cm"]) <= 0:
                raise ValueError
        except ValueError:
            errors.append(f"{loc}: bad distance_cm")
        if check_files:
            chk = check_image(root / r["path"])
            if not chk.ok:
                errors.append(f"{loc}: image {r['path']}: {chk.reason or 'missing'}")
    for fid, pv in inst.items():
        if len(pv) > 1:
            errors.append(f"fruit_instance_id {fid} has multiple produce/variety values {sorted(pv)}")
    return errors


def agreement(root: Path) -> tuple[dict[str, float], list[str]]:
    tax = load_taxonomy()
    with open(root / "annotations.csv", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["_item"] = f"{r['fruit_instance_id']}@{r['day']}"
    out, errs = {}, []
    for head, w in (("ripeness", "quadratic"), ("freshness", "quadratic"), ("visual_spoilage", "quadratic")):
        a, b = pairwise_from_rows(rows, "_item", head)
        if len(a) < 20:
            errs.append(f"{head}: only {len(a)} double-graded items (need >= 20)")
            continue
        k = cohen_kappa(a, b, tax.heads[head], weights=w)
        out[head] = k
        if head in ("ripeness", "freshness") and k < KAPPA_MIN:
            errs.append(f"{head}: kappa {k:.2f} < {KAPPA_MIN} - revise grading guide before scaling")
    return out, errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("data/raw/own_il_collection"))
    ap.add_argument("--agreement", action="store_true")
    ap.add_argument("--no-file-check", action="store_true")
    args = ap.parse_args()
    errors = validate(args.root, not args.no_file_check)
    if args.agreement:
        k, errs = agreement(args.root)
        print("kappa:", {h: round(v, 3) for h, v in k.items()})
        errors += errs
    for e in errors[:200]:
        print("ERROR", e)
    print(f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
