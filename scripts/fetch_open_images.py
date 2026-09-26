#!/usr/bin/env python3
"""Fetch the Open Images V7 produce subset as object crops, keeping only images whose
per-image licence metadata says CC BY 2.0, and write an attribution file.

  python scripts/fetch_open_images.py --per-class 400 --workers 16

Output (data/raw/open_images_v7/):
  crops/<class>/<ImageID>_<k>.jpg   one crop per box (15% margin)
  crops.csv                         path, class_name, image_id, split, box coords
  attribution.csv                   image_id, license, author, author_profile, original_url
  .provenance.json, fetch_report.json

Filters (documented in docs/datasets.md): IsGroupOf=0, IsDepiction=0 (no drawings/
plastic-looking depictions), box >= 1.5% of image area, crop >= 64 px, Rotation == 0.
Official Open Images splits are kept as split hints (train/validation/test -> train/val/test).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import sys
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.preprocessing import registry  # noqa: E402

BASE = "https://storage.googleapis.com/openimages"
IMG_URL = "https://open-images-dataset.s3.amazonaws.com/{split}/{image_id}.jpg"
BOX_CSV = {"validation": f"{BASE}/v5/validation-annotations-bbox.csv",
           "test": f"{BASE}/v5/test-annotations-bbox.csv",
           "train": f"{BASE}/v6/oidv6-train-annotations-bbox.csv"}
META_CSV = {"validation": f"{BASE}/2018_04/validation/validation-images-with-rotation.csv",
            "test": f"{BASE}/2018_04/test/test-images-with-rotation.csv",
            "train": f"{BASE}/2018_04/train/train-images-boxable-with-rotation.csv"}
SPLIT_HINT = {"train": "train", "validation": "val", "test": "test"}
CC_BY_2 = "creativecommons.org/licenses/by/2.0"
OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "open_images_v7"


def stream_csv(url: str):
    with urllib.request.urlopen(url, timeout=120) as r:
        yield from csv.DictReader(io.TextIOWrapper(r, encoding="utf-8"))


def stable(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=400, help="max images per class (all splits)")
    ap.add_argument("--splits", nargs="+", default=["validation", "test", "train"])
    ap.add_argument("--min-area", type=float, default=0.015)
    ap.add_argument("--min-crop", type=int, default=64)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--purpose", choices=registry.PURPOSES, default="research_training")
    args = ap.parse_args()

    ok, why = registry.is_allowed(registry.load_registry()["open_images_v7"], args.purpose)
    print(f"licence gate for {args.purpose}: {'OK' if ok else 'BLOCK'} ({why})")
    if not ok:
        return 1
    mapping = json.loads((Path(__file__).resolve().parents[1] / "data" / "label_mapping.json").read_text())
    class_map = mapping["datasets"]["open_images_v7"]["class_name_map"]
    mids = {r["LabelName"]: r["DisplayName"] for r in
            csv.DictReader(io.StringIO(urllib.request.urlopen(f"{BASE}/v7/oidv7-class-descriptions-boxable.csv").read().decode()),
                           fieldnames=["LabelName", "DisplayName"])}
    wanted = {m: n for m, n in mids.items() if n in class_map}
    missing = set(class_map) - set(wanted.values())
    if missing:
        raise SystemExit(f"class names not found in Open Images: {missing}")

    report = defaultdict(int)
    boxes: dict[tuple[str, str], list[dict]] = defaultdict(list)  # (split, image_id) -> boxes
    for split in args.splits:
        for r in stream_csv(BOX_CSV[split]):
            if r["LabelName"] not in wanted:
                continue
            report["boxes_seen"] += 1
            if r["IsGroupOf"] == "1" or r["IsDepiction"] == "1":
                report["boxes_dropped_group_or_depiction"] += 1
                continue
            x0, x1, y0, y1 = (float(r[k]) for k in ("XMin", "XMax", "YMin", "YMax"))
            if (x1 - x0) * (y1 - y0) < args.min_area:
                report["boxes_dropped_small"] += 1
                continue
            boxes[(split, r["ImageID"])].append({"cls": wanted[r["LabelName"]], "box": (x0, y0, x1, y1)})
        print(f"{split}: {len(boxes)} candidate images so far", flush=True)

    # Deterministic per-class image cap (an image counts toward each class it contains).
    by_class: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for key, bs in boxes.items():
        for c in {b["cls"] for b in bs}:
            by_class[c].append(key)
    chosen = set()
    for c, keys in by_class.items():
        chosen.update(sorted(keys, key=lambda k: stable(k[1]))[: args.per_class])
    report["images_chosen"] = len(chosen)

    ids_by_split = defaultdict(set)
    for s, i in chosen:
        ids_by_split[s].add(i)
    meta = {}
    for split, ids in ids_by_split.items():
        for r in stream_csv(META_CSV[split]):
            if r["ImageID"] in ids:
                meta[(split, r["ImageID"])] = r
    usable = []
    for key in sorted(chosen):
        m = meta.get(key)
        if m is None:
            report["dropped_no_metadata"] += 1
        elif CC_BY_2 not in (m.get("License") or ""):
            report["dropped_license_not_cc_by_2"] += 1
        elif (m.get("Rotation") or "0").strip() not in ("0", "0.0", ""):
            report["dropped_rotated"] += 1
        else:
            usable.append(key)

    (OUT / "crops").mkdir(parents=True, exist_ok=True)

    def fetch(key):
        split, iid = key
        try:
            data = urllib.request.urlopen(IMG_URL.format(split=split, image_id=iid), timeout=60).read()
            img = Image.open(io.BytesIO(data)).convert("RGB")
        except Exception as e:  # network / decode errors are counted, not fatal
            return key, [], f"fetch_error:{type(e).__name__}"
        W, H = img.size
        rows = []
        for k, b in enumerate(boxes[key]):
            x0, y0, x1, y1 = b["box"]
            mx, my = 0.15 * (x1 - x0), 0.15 * (y1 - y0)
            crop = img.crop((max(0, (x0 - mx) * W), max(0, (y0 - my) * H), min(W, (x1 + mx) * W), min(H, (y1 + my) * H)))
            if min(crop.size) < args.min_crop:
                continue
            crop.thumbnail((768, 768))
            rel = f"crops/{b['cls'].replace(' ', '_')}/{iid}_{k}.jpg"
            (OUT / rel).parent.mkdir(parents=True, exist_ok=True)
            crop.save(OUT / rel, quality=92)
            rows.append({"path": rel, "class_name": b["cls"], "image_id": iid, "split": SPLIT_HINT[split],
                         "xmin": x0, "ymin": y0, "xmax": x1, "ymax": y1})
        return key, rows, None

    crop_rows, attr_rows = [], []
    with ThreadPoolExecutor(args.workers) as ex:
        for n, (key, rows, err) in enumerate(ex.map(fetch, usable)):
            if err:
                report[err.split(":")[0]] += 1
                continue
            if rows:
                crop_rows.extend(rows)
                m = meta[key]
                attr_rows.append({"image_id": key[1], "license": m["License"], "author": m.get("Author", ""),
                                  "author_profile": m.get("AuthorProfileURL", ""), "original_url": m.get("OriginalURL", ""),
                                  "landing_url": m.get("OriginalLandingURL", "")})
            if n % 500 == 0:
                print(f"downloaded {n}/{len(usable)}", flush=True)

    for name, rows in (("crops.csv", crop_rows), ("attribution.csv", attr_rows)):
        with open(OUT / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    report["crops_written"] = len(crop_rows)
    report["images_with_crops"] = len(attr_rows)
    per_class = defaultdict(int)
    for r in crop_rows:
        per_class[r["class_name"]] += 1
    out = {**report, "per_class_crops": dict(sorted(per_class.items()))}
    (OUT / "fetch_report.json").write_text(json.dumps(out, indent=2))
    (OUT / ".provenance.json").write_text(json.dumps({
        "dataset_id": "open_images_v7", "sources": {**BOX_CSV, **{f"meta_{k}": v for k, v in META_CSV.items()}},
        "license": "annotations CC BY 4.0; images filtered to per-image CC BY 2.0 (see attribution.csv)",
        "imported_at": dt.datetime.now(dt.timezone.utc).isoformat(), "args": vars(args)}, indent=2))
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
