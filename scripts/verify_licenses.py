#!/usr/bin/env python3
"""Print the licence gate for every registered dataset, and fail (exit 1) if a
training config or manifest uses a dataset not cleared for its purpose.

  python scripts/verify_licenses.py
  python scripts/verify_licenses.py --manifest data/processed/manifest.jsonl --purpose commercial_training
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.preprocessing import registry  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--purpose", choices=registry.PURPOSES, default="commercial_training")
    args = ap.parse_args()
    reg = registry.load_registry()
    signoffs = registry.load_signoffs()
    print(f"{'dataset':32} {'commercial':6} reason")
    for ds, e in reg.items():
        ok, why = registry.is_allowed(e, "commercial_training", signoffs)
        print(f"{ds:32} {'YES' if ok else 'no':6} {why}")
    if not args.manifest:
        return 0
    used = set()
    with open(args.manifest, encoding="utf-8") as f:
        for line in f:
            used.add(json.loads(line)["dataset_id"])
    bad = [d for d in sorted(used) if d not in reg or not registry.is_allowed(reg[d], args.purpose, signoffs)[0]]
    if bad:
        print(f"\nFAIL: manifest uses datasets not cleared for {args.purpose}: {bad}")
        return 1
    print(f"\nOK: all {len(used)} datasets in manifest cleared for {args.purpose}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
