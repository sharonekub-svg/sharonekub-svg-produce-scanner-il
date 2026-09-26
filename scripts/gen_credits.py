#!/usr/bin/env python3
"""Generate the in-app data-credits file from a model bundle + the dataset registry.

  python scripts/gen_credits.py --bundle exports/v1/bundle.json --out app/assets/model/credits.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.preprocessing.registry import load_registry  # noqa: E402

ATTRIBUTION = {
    "grocery_store_klasson": "Klasson, Zhang, Kjellström. A Hierarchical Grocery Store Image Dataset with Visual and Semantic Labels. WACV 2019. MIT License.",
    "open_images_v7": "Open Images V7 (Google LLC), annotations CC BY 4.0; images CC BY 2.0 by their Flickr authors (full list available in the app's source attribution file).",
    "fruits360_original": "Mihai Oltean, Fruits-360 dataset, CC BY-SA 4.0.",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    b = json.loads(args.bundle.read_text(encoding="utf-8"))
    reg = load_registry()
    ds = []
    for d in b.get("training_datasets", []):
        e = reg[d]
        ds.append({"dataset_id": d, "name": e.name, "license": e.license, "url": e.url,
                   "attribution": ATTRIBUTION.get(d, e.original_source)})
    args.out.write_text(json.dumps({"model_id": b["model_id"], "datasets": ds}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.out, [d["dataset_id"] for d in ds])
    return 0


if __name__ == "__main__":
    sys.exit(main())
