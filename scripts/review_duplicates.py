#!/usr/bin/env python3
"""Render every multi-image duplicate cluster in a manifest as a contact sheet for
human review (threshold validation). Output: <processed>/dup_review.jpg + dup_review.json

  python scripts/review_duplicates.py --processed data/processed [--max-clusters 60]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.preprocessing.hashing import dihedral_phash, hamming  # noqa: E402

THUMB = 128


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--processed", type=Path, default=Path("data/processed"))
    ap.add_argument("--max-clusters", type=int, default=60)
    args = ap.parse_args()
    groups: dict[str, list[dict]] = defaultdict(list)
    for line in (args.processed / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        groups[r["group"]].append(r)
    multi = [g for g in groups.values() if len(g) > 1][: args.max_clusters]
    summary = []
    if not multi:
        print("no multi-image clusters")
        return 0
    cols = max(len(g) for g in multi)
    sheet = Image.new("RGB", (cols * THUMB, len(multi) * (THUMB + 14)), "white")
    d = ImageDraw.Draw(sheet)
    for row, g in enumerate(multi):
        imgs = [Image.open(args.processed / r["image"]).convert("RGB") for r in g]
        hashes = [dihedral_phash(i) for i in imgs]
        dists = [hamming(hashes[0], h) for h in hashes[1:]]
        summary.append({"group": g[0]["group"], "files": [r["source_path"] for r in g],
                        "splits": sorted({r["split"] for r in g}), "hamming_to_first": dists})
        for col, im in enumerate(imgs):
            im.thumbnail((THUMB, THUMB))
            sheet.paste(im, (col * THUMB, row * (THUMB + 14) + 14))
        d.text((2, row * (THUMB + 14)), f"{g[0]['group']} d={dists}", fill="black")
    sheet.save(args.processed / "dup_review.jpg", quality=85)
    (args.processed / "dup_review.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
