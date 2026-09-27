#!/usr/bin/env python3
"""Download a Mendeley Data dataset with its licence evidence (primary source: the public API).

  python scripts/fetch_mendeley.py 3xd9n945v8 1 --out data/raw/hass_avocado_ripening
  python scripts/fetch_mendeley.py zysvgmxcyz 1 --out data/raw/strawberry_avocado_ripening --ext .jpg .jpeg .png

Writes <out>/.provenance.json (name, DOI, licence object exactly as the API returns it, method text,
contributors, fetch time) and mirrors the dataset's folder tree. Every file is checked against the
API's SHA-256. Refuses datasets whose licence is not in ALLOWED (commercial use without share-alike),
unless --research (then data may only be used for research runs; the registry must say so).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "https://data.mendeley.com/public-api/datasets"
UA = {"User-Agent": "Mozilla/5.0 (produce-scanner-il dataset fetcher)"}
ALLOWED = {"CC BY 4.0", "CC0 1.0", "CC BY 3.0", "MIT"}


def get_json(url: str, tries: int = 4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json", **UA}), timeout=60) as r:
                return json.loads(r.read())
        except Exception:  # noqa: BLE001
            if k == tries - 1:
                raise
            time.sleep(2 ** k)


def walk(ds: str, ver: int):
    """Yield (relative_path, file_record) for every file in the dataset."""
    folders = get_json(f"{API}/{ds}/folders/{ver}")
    by_id = {f["id"]: f for f in folders}

    def path_of(fid: str) -> Path:
        parts = []
        while fid in by_id:
            parts.append(by_id[fid]["name"])
            fid = by_id[fid].get("parent_id")
        return Path(*reversed(parts)) if parts else Path()

    for fid in ["root"] + list(by_id):
        for f in get_json(f"{API}/{ds}/files?folder_id={fid}&version={ver}"):
            yield (path_of(fid) if fid != "root" else Path()) / f["filename"], f


def download(url: str, dest: Path, sha256: str, tries: int = 4) -> bool:
    if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() == sha256:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                data = r.read()
            if hashlib.sha256(data).hexdigest() != sha256:
                raise ValueError("sha256 mismatch")
            dest.write_bytes(data)
            return True
        except Exception:  # noqa: BLE001
            time.sleep(2 ** k)
    return False


def extract_zip(zp: Path, out: Path, exts: list[str], max_side: int, depth: int = 0) -> int:
    """Extract wanted members; images are resized on the way out. Nested .zip members (common on
    Mendeley: one archive per class) are extracted to disk, recursed into, then deleted."""
    import zipfile
    from PIL import Image, ImageOps
    n = 0
    with zipfile.ZipFile(zp) as z:
        for m in z.namelist():
            rel = Path(*[p for p in Path(m).parts if p not in ("/", "..")])  # no absolute / parent paths
            if not rel.parts:
                continue
            suf = rel.suffix.lower()
            if suf == ".zip" and depth < 3:
                inner = out / rel
                inner.parent.mkdir(parents=True, exist_ok=True)
                with z.open(m) as src, open(inner, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
                n += extract_zip(inner, inner.with_suffix(""), exts, max_side, depth + 1)
                inner.unlink()
            elif suf in exts:
                dest = out / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if suf in (".jpg", ".jpeg", ".png") and max_side:
                    try:
                        with z.open(m) as fh:
                            im = ImageOps.exif_transpose(Image.open(fh)).convert("RGB")
                        im.thumbnail((max_side, max_side))
                        im.save(dest, "PNG" if suf == ".png" else "JPEG", quality=92)
                    except Exception as e:  # noqa: BLE001 - corrupt member: skip, report
                        print("skip", m, e, file=sys.stderr)
                        continue
                else:
                    with z.open(m) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst, 1 << 20)
                n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("version", type=int)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ext", nargs="*", default=[".jpg", ".jpeg", ".png", ".csv", ".xlsx", ".txt", ".json", ".yaml", ".yml"])
    ap.add_argument("--research", action="store_true", help="allow non-commercial licences (research runs only)")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--max-side", type=int, default=1024, help="with --zip: resize images on extraction (0 = keep)")
    ap.add_argument("--zip", action="store_true",
                    help="use Mendeley's 'Download All' archive (the file listing API caps at 1,000 files per folder)")
    a = ap.parse_args()

    meta = get_json(f"{API}/{a.dataset}?version={a.version}")
    lic = (meta.get("data_licence") or {}).get("short_name", "UNKNOWN")
    if lic not in ALLOWED and not a.research:
        print(f"REFUSED: licence {lic!r} not in {sorted(ALLOWED)}", file=sys.stderr)
        return 2
    a.out.mkdir(parents=True, exist_ok=True)
    prov = {"source": f"https://data.mendeley.com/datasets/{a.dataset}/{a.version}", "doi": meta.get("doi"),
            "name": meta.get("name"), "licence": meta.get("data_licence"), "method": meta.get("method"),
            "description": meta.get("description"),
            "contributors": [c.get("first_name", "") + " " + c.get("last_name", "") for c in meta.get("contributors", [])],
            "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    if a.zip:
        import subprocess
        zp = a.out / f"{a.dataset}-{a.version}.zip"
        url = f"https://data.mendeley.com/public-api/zip/{a.dataset}/download/{a.version}"
        subprocess.run(["curl", "-sSL", "--retry", "4", "-A", UA["User-Agent"], "-o", str(zp), url], check=True)
        prov["zip_sha256"] = hashlib.sha256(zp.read_bytes()).hexdigest()
        members = extract_zip(zp, a.out, a.ext, a.max_side)
        zp.unlink()
        prov["files_extracted"] = members
        (a.out / ".provenance.json").write_text(json.dumps(prov, indent=2, ensure_ascii=False))
        print(f"{meta.get('name')} | {lic} | zip: {members} files extracted", flush=True)
        return 0
    files = [(p, f) for p, f in walk(a.dataset, a.version) if p.suffix.lower() in a.ext]
    total = sum(f["size"] for _, f in files)
    print(f"{meta.get('name')} | {lic} | {len(files)} files | {total / 1e6:.0f} MB", flush=True)

    def job(item):
        p, f = item
        c = f["content_details"]
        return download(c["download_url"], a.out / p, c["sha256_hash"])

    ok = 0
    with ThreadPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(job, files), 1):
            ok += r
            if i % 500 == 0:
                print(f"  {i}/{len(files)}", flush=True)
    prov["files_ok"], prov["files_failed"] = ok, len(files) - ok
    (a.out / ".provenance.json").write_text(json.dumps(prov, indent=2, ensure_ascii=False))
    print(f"done: {ok}/{len(files)} files", flush=True)
    return 0 if ok == len(files) else 1


if __name__ == "__main__":
    sys.exit(main())
