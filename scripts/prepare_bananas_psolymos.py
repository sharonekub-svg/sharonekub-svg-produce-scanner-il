#!/usr/bin/env python3
"""metadata.csv for psolymos/bananas (MIT): 11 bananas photographed over 21 days, author's labels.

  git clone https://github.com/psolymos/bananas data/raw/bananas_psolymos
  python scripts/prepare_bananas_psolymos.py

Ripeness mapping (author's classes -> ours): U under ripe -> {unripe, partially_ripe}; R ripe -> ripe;
V very ripe -> {ripe, overripe}; O over ripe -> overripe. Fridge-stored fruits get NO ripeness label:
chilling browns the peel without ripening the pulp (docs/research/food-quality.md), so their colour is
not a ripeness signal. Group = fruit id (every day of the same banana stays in one split).
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data/raw/bananas_psolymos"
MAP = {"U": "unripe|partially_ripe", "R": "ripe", "V": "ripe|overripe", "O": "overripe"}


def main() -> int:
    rows = list(csv.DictReader(open(ROOT / "data-raw/data-colors.csv", encoding="utf-8")))
    with open(ROOT / "metadata.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["filename", "fruit", "ripeness"])
        for r in rows:
            w.writerow([f"images/{r['file']}", r["fruit"], "" if r["group"] == "F" else MAP[r["ripeness"]]])
    print(len(rows), "rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
