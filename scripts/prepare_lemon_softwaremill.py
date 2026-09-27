#!/usr/bin/env python3
"""Turn the SoftwareMill lemon dataset (COCO, MIT) into the `table` adapter's metadata.csv.

  git clone https://github.com/softwaremill/lemon-dataset data/raw/lemon_softwaremill
  (cd data/raw/lemon_softwaremill/data && unzip lemon-dataset.zip)
  python scripts/prepare_lemon_softwaremill.py

Label policy (no fabricated labels; docs/research/food-quality.md):
  mould or gangrene region -> visual_spoilage {mild|severe} (set-valued: area is not a severity grade),
                              freshness spoiled (Ministry of Health: mouldy produce is discarded)
  no illness / mould / gangrene region -> visual_spoilage none (blemishes, pedicel, style remains are cosmetic)
  illness only -> unknown (disease spots; not a spoilage grade)
  greening is ignored: citrus colour is not ripeness (docs/research/produce-science.md).
Group = the 4-digit fruit/batch id in the file name, so every photo of the same fruit stays in one split.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data/raw/lemon_softwaremill"


def main() -> int:
    base = ROOT / "data/lemon-dataset"
    coco = json.loads((base / "annotations/instances_default.json").read_text())
    cat = {c["id"]: c["name"] for c in coco["categories"]}
    regions: dict[int, set] = {im["id"]: set() for im in coco["images"]}
    for a in coco["annotations"]:
        regions[a["image_id"]].add(cat[a["category_id"]])
    counts = Counter()
    with open(ROOT / "metadata.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["filename", "group", "visual_spoilage", "freshness"])
        for im in coco["images"]:
            r = regions[im["id"]]
            if r & {"mould", "gangrene"}:
                sp, fr = "mild|severe", "spoiled"
            elif "illness" not in r:
                sp, fr = "none", ""
            else:
                sp, fr = "", ""
            name = Path(im["file_name"]).name
            w.writerow([f"data/lemon-dataset/images/{name}", name[:4], sp, fr])
            counts[sp or "unknown"] += 1
    print(dict(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
