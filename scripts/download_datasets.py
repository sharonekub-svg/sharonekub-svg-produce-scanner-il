#!/usr/bin/env python3
"""Download / import datasets into data/raw/<dataset_id>/ — licence-gated.

  python scripts/download_datasets.py --purpose commercial_training --datasets grocery_store_klasson
  python scripts/download_datasets.py --purpose research_training --datasets fruitnet_indian --manual

Datasets behind logins (Kaggle, Mendeley) are imported manually: download the
archive yourself, then `--import-archive path.zip`. Every import writes
data/raw/<id>/.provenance.json (source URL, licence, sha256 of archive, date).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.preprocessing import registry  # noqa: E402

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

# Only sources that can be fetched non-interactively. Others need --import-archive.
GIT_SOURCES = {
    "grocery_store_klasson": "https://github.com/marcusklasson/GroceryStoreDataset.git",
    "fruits360_original": "https://github.com/fruits-360/fruits-360-original-size.git",
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def write_provenance(ds: str, entry, extra: dict) -> None:
    d = RAW / ds
    d.mkdir(parents=True, exist_ok=True)
    prov = {"dataset_id": ds, "url": entry.url, "license": entry.license,
            "license_verification": entry.license_verification, "commercial_use": entry.commercial_use,
            "imported_at": dt.datetime.now(dt.timezone.utc).isoformat(), **extra}
    (d / ".provenance.json").write_text(json.dumps(prov, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", nargs="+", required=True)
    ap.add_argument("--purpose", choices=registry.PURPOSES, required=True)
    ap.add_argument("--import-archive", type=Path, help="manually downloaded zip for a single dataset")
    args = ap.parse_args()
    reg = registry.load_registry()
    signoffs = registry.load_signoffs()
    rc = 0
    for ds in args.datasets:
        entry = reg[ds]
        ok, why = registry.is_allowed(entry, args.purpose, signoffs)
        print(f"[{ 'OK ' if ok else 'BLOCK'}] {ds}: {why}")
        if not ok:
            rc = 1
            continue
        dest = RAW / ds
        if args.import_archive:
            if len(args.datasets) != 1:
                raise SystemExit("--import-archive needs exactly one dataset")
            with zipfile.ZipFile(args.import_archive) as z:
                z.extractall(dest)
            write_provenance(ds, entry, {"archive": args.import_archive.name, "archive_sha256": sha256(args.import_archive)})
        elif ds in GIT_SOURCES:
            if dest.exists():
                shutil.rmtree(dest)
            subprocess.run(["git", "clone", "--depth", "1", GIT_SOURCES[ds], str(dest)], check=True)
            commit = subprocess.check_output(["git", "-C", str(dest), "rev-parse", "HEAD"], text=True).strip()
            write_provenance(ds, entry, {"git_commit": commit})
        else:
            print(f"  -> manual download required: {entry.url}\n     then rerun with --import-archive <file.zip>")
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
