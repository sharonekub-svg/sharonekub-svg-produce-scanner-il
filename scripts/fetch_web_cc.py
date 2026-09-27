#!/usr/bin/env python3
"""Fetch openly licensed produce photos from Openverse (Flickr and others) and Wikimedia Commons,
keeping ONLY licences that allow commercial use without share-alike: CC0, Public Domain Mark, CC BY.

  python scripts/fetch_web_cc.py openverse --query "overripe banana" --tag banana:overripe --max 300
  python scripts/fetch_web_cc.py commons --category "Rotting tomatoes" --tag tomato:rotting --max 300
  python scripts/fetch_web_cc.py plan            # every produce type: data/web_cc_queries.json

Needs network access to api.openverse.org / commons.wikimedia.org + upload.wikimedia.org + the
original image hosts (e.g. live.staticflickr.com) — see docs/research/dataset-search-2026-09.md §E.

Output (data/raw/web_cc/):
  images/<provider>_<id>.jpg     max side 1024
  candidates.csv                 file, provider, id, query_tag, title, width, height
  attribution.csv                file, license, license_version, license_url, creator, landing_url
The query/category tag is a SEARCH HINT, not a label: every photo goes to the labeller
(tools/labeler) for grading before it can train anything (docs/data-collection-protocol.md §0).
Per-image licences are the uploader's claim; photos that look like stock/press images are dropped
during grading, and the owner sign-off in data/license_signoffs.json still gates commercial use.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/web_cc"
UA = "produce-scanner-il dataset builder (research; contact in README)"
ALLOWED = {"cc0", "pdm", "by"}  # no NC, no ND, no SA


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def normalise_commons_license(short: str) -> tuple[str, str] | None:
    """'CC BY 4.0' -> ('by', '4.0'); 'CC0' -> ('cc0', '1.0'); 'Public domain' -> ('pdm', ''); SA/NC/ND -> None."""
    s = short.strip().lower()
    if s in ("cc0", "cc0 1.0", "cc-zero"):
        return "cc0", "1.0"
    if s.startswith("public domain") or s == "pd":
        return "pdm", ""
    m = re.fullmatch(r"cc[ -]by[ -]?(\d\.\d)?", s)
    if m:
        return "by", m.group(1) or ""
    return None


def openverse_items(query: str, max_items: int, page_size: int = 20):
    """Openverse /v1/images: anonymous access; license filter server-side, re-checked here."""
    page = 1
    while max_items > 0:
        q = urllib.parse.urlencode({"q": query, "license": ",".join(sorted(ALLOWED)), "page_size": page_size,
                                    "page": page, "mature": "false"})
        data = json.loads(_get(f"https://api.openverse.org/v1/images/?{q}"))
        for r in data.get("results", []):
            if r.get("license") not in ALLOWED:
                continue
            yield {"provider": "openverse", "id": r["id"], "url": r["url"], "title": r.get("title") or "",
                   "license": r["license"], "license_version": r.get("license_version") or "",
                   "license_url": r.get("license_url") or "", "creator": r.get("creator") or "",
                   "landing_url": r.get("foreign_landing_url") or ""}
            max_items -= 1
            if max_items <= 0:
                return
        if page >= data.get("page_count", 0):
            return
        page += 1
        time.sleep(1.0)


def commons_items(category: str, max_items: int):
    """Wikimedia Commons files in one category, licence from extmetadata.LicenseShortName."""
    cont: dict = {}
    while max_items > 0:
        params = {"action": "query", "format": "json", "generator": "categorymembers",
                  "gcmtitle": f"Category:{category}", "gcmtype": "file", "gcmlimit": 50,
                  "prop": "imageinfo", "iiprop": "url|extmetadata|mime", "iiurlwidth": 1024, **cont}
        data = json.loads(_get("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)))
        for p in (data.get("query", {}).get("pages", {}) or {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            if ii.get("mime") not in ("image/jpeg", "image/png"):
                continue
            meta = ii.get("extmetadata", {})
            lic = normalise_commons_license(meta.get("LicenseShortName", {}).get("value", ""))
            if lic is None or meta.get("Restrictions", {}).get("value"):
                continue  # SA/NC/ND, unknown, or personality/trademark restrictions
            creator = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
            yield {"provider": "commons", "id": str(p["pageid"]), "url": ii.get("thumburl") or ii["url"],
                   "title": p.get("title", ""), "license": lic[0], "license_version": lic[1],
                   "license_url": meta.get("LicenseUrl", {}).get("value", ""), "creator": creator,
                   "landing_url": ii.get("descriptionurl", "")}
            max_items -= 1
            if max_items <= 0:
                return
        if "continue" not in data:
            return
        cont = data["continue"]
        time.sleep(1.0)


def save(items, tag: str, out: Path = OUT) -> int:
    from PIL import Image
    (out / "images").mkdir(parents=True, exist_ok=True)
    new_c = not (out / "candidates.csv").exists()
    n = 0
    with open(out / "candidates.csv", "a", newline="", encoding="utf-8") as fc, \
         open(out / "attribution.csv", "a", newline="", encoding="utf-8") as fa:
        wc, wa = csv.writer(fc), csv.writer(fa)
        if new_c:
            wc.writerow(["file", "provider", "id", "query_tag", "title", "width", "height"])
            wa.writerow(["file", "license", "license_version", "license_url", "creator", "landing_url"])
        for it in items:
            name = f"images/{it['provider']}_{re.sub(r'[^A-Za-z0-9_-]', '_', it['id'])}.jpg"
            if (out / name).exists():
                continue
            try:
                im = Image.open(io.BytesIO(_get(it["url"]))).convert("RGB")
            except Exception as e:  # noqa: BLE001 - one bad image must not stop the crawl
                print("skip", it["id"], e, file=sys.stderr)
                continue
            im.thumbnail((1024, 1024))
            im.save(out / name, "JPEG", quality=90)  # re-encode: drops EXIF/GPS
            wc.writerow([name, it["provider"], it["id"], tag, it["title"], im.width, im.height])
            wa.writerow([name, it["license"], it["license_version"], it["license_url"], it["creator"], it["landing_url"]])
            n += 1
            time.sleep(0.5)
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("provider", choices=["openverse", "commons", "plan"])
    ap.add_argument("--query", help="openverse search text")
    ap.add_argument("--category", help="commons category name without 'Category:'")
    ap.add_argument("--tag", help="search hint, e.g. banana:overripe (NOT a label)")
    ap.add_argument("--plan", type=Path, default=ROOT / "data/web_cc_queries.json")
    ap.add_argument("--max", type=int, default=200)
    a = ap.parse_args()
    if a.provider == "plan":
        plan = json.loads(a.plan.read_text(encoding="utf-8"))
        total = 0
        for q in plan["queries"]:
            it = (openverse_items(q["query"], plan["per_query_max"]) if q["provider"] == "openverse"
                  else commons_items(q["category"], plan["per_query_max"]))
            try:
                n = save(it, q["tag"])
            except Exception as e:  # noqa: BLE001 - report and continue with the next query
                print("query failed", q, e, file=sys.stderr)
                continue
            total += n
            print(f"{q['tag']:<28} {q.get('query') or q.get('category')!r}: {n}")
        print(total, "images saved to", OUT)
        return 0
    if not a.tag:
        ap.error("--tag is required")
    items = openverse_items(a.query, a.max) if a.provider == "openverse" else commons_items(a.category, a.max)
    print(save(items, a.tag), "images saved to", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
