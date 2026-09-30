#!/usr/bin/env python3
"""Photographer credits for every Open Images photo used to train the model (CC BY 2.0 requires attribution).

  python3 scripts/gen_oi_attribution.py --emb runs/siglip/oi_train.npz --out server/web/credits/open_images.html

One line per photo: author (link to their profile), the photo (link to the original page) and the licence.
Served at /web/credits/open_images.html and linked from the app's credits screen.
"""
import argparse
import csv
import html
from pathlib import Path

import numpy as np

OI = Path("data/raw/open_images_v7")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb", type=Path, required=True, help="training crops (scripts/siglip_embed_oi_train.py)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    used = sorted(set(np.load(a.emb)["image_id"].tolist()))
    attr = {r["image_id"]: r for r in csv.DictReader(open(OI / "attribution.csv", encoding="utf-8"))}
    missing = [i for i in used if i not in attr]
    if missing:
        raise SystemExit(f"{len(missing)} training photos have no attribution row (e.g. {missing[:3]}): refusing to publish")
    rows = []
    for i in used:
        r = attr[i]
        author = html.escape(html.unescape(r["author"] or "unknown"))
        prof = html.escape(r["author_profile"] or r["landing_url"])
        rows.append(f'<li><a href="{html.escape(r["landing_url"])}">photo</a> by <a href="{prof}">{author}</a>, '
                    f'<a href="{html.escape(r["license"])}">CC BY 2.0</a></li>')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Scan Fruit AI – photo credits</title>
<style>body{{font:14px/1.5 system-ui,sans-serif;margin:16px;max-width:900px;color:#222}}li{{margin:2px 0}}</style></head><body>
<h1>Photo credits (Open Images)</h1>
<p>Scan Fruit AI's fruit and vegetable identification was trained with {len(used):,} photos from
<a href="https://storage.googleapis.com/openimages/web/index.html">Open Images V7</a> (Google; annotations CC BY 4.0).
Each photo is licensed <a href="https://creativecommons.org/licenses/by/2.0/">CC BY 2.0</a> by its author, listed below.
The photos were cropped and resized; they are not redistributed in the app.</p>
<ul>
{chr(10).join(rows)}
</ul></body></html>
""", encoding="utf-8")
    print(a.out, len(used), "photos")


if __name__ == "__main__":
    main()
