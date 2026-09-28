#!/usr/bin/env python3
"""Sort Mendeley zysvgmxcyz (strawberry & avocado ripening, CC BY 4.0) into class folders.

  python scripts/prepare_strawberry_avocado.py data/raw/strawberry_avocado_ripening

YOLO class order, from the dataset paper (PMC12152553): 0-3 strawberry unripe / partially ripe /
ripe / rotten, 4-7 avocado in the same order. Only images whose boxes all share ONE class are used
(multi-class scenes are skipped). Images are moved to sorted/<class>/ for path_rules mapping.
"""
import sys
from collections import Counter
from pathlib import Path

NAMES = ["strawberry_unripe", "strawberry_partially_ripe", "strawberry_ripe", "strawberry_rotten",
         "avocado_unripe", "avocado_partially_ripe", "avocado_ripe", "avocado_rotten"]
root = Path(sys.argv[1]); out = root / "sorted"; n = Counter()
for lab in sorted((root / "labels").glob("*.txt")):
    img = root / "images" / (lab.stem + ".jpg")
    ids = {l.split()[0] for l in lab.read_text().splitlines() if l.strip()}
    if not img.exists():
        n["no_image"] += 1; continue
    if len(ids) != 1:
        n["multi_or_empty"] += 1; continue
    d = out / NAMES[int(ids.pop())]; d.mkdir(parents=True, exist_ok=True)
    img.rename(d / img.name); n[d.name] += 1
print(dict(n))
