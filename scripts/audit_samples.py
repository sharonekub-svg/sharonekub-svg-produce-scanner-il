#!/usr/bin/env python3
"""Label-noise audit: contact sheet of a deterministic random sample per class.

  python scripts/audit_samples.py --processed data/processed_research --dataset open_images_v7 \
      --classes banana orange tomato --n 40

A human marks wrong/ambiguous tiles; record the counts in docs/ingestion-report.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

T = 112


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--processed", type=Path, required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--classes", nargs="+", required=True)
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--cols", type=int, default=10)
    args = ap.parse_args()
    rows = [json.loads(l) for l in (args.processed / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    for c in args.classes:
        sel = sorted((r for r in rows if r["dataset_id"] == args.dataset and r["labels"]["produce"] == c),
                     key=lambda r: hashlib.sha256(r["sha256"].encode()).hexdigest())[: args.n]
        if not sel:
            print(f"{c}: no samples")
            continue
        nrows = (len(sel) + args.cols - 1) // args.cols
        sheet = Image.new("RGB", (args.cols * T, nrows * T), "white")
        d = ImageDraw.Draw(sheet)
        for k, r in enumerate(sel):
            im = Image.open(args.processed / r["image"]).convert("RGB")
            im.thumbnail((T - 4, T - 4))
            x, y = (k % args.cols) * T, (k // args.cols) * T
            sheet.paste(im, (x + 2, y + 2))
            d.text((x + 3, y + 2), str(k), fill="yellow")
        out = args.processed / f"audit_{args.dataset}_{c}.jpg"
        sheet.save(out, quality=85)
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
