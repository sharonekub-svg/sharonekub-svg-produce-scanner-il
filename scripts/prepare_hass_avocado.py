#!/usr/bin/env python3
"""metadata.csv for the 'Hass' Avocado Ripening Photographic Dataset (Mendeley 3xd9n945v8 v1, CC BY 4.0).

  python scripts/fetch_mendeley.py 3xd9n945v8 1 --out data/raw/hass_avocado_ripening --zip
  python scripts/prepare_hass_avocado.py

Labels are the authors' 5-stage Ripening Index (label_mapping value_maps: 1 unripe, 2 breaking ->
partially_ripe, 3 and 4 ripe, 5 overripe). Group = storage group + sample number, so every day and both
sides of one avocado stay in one split. Cultivar is Hass only (the dataset's method text).
"""
import csv
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1] / "data/raw/hass_avocado_ripening"
BASE = "Hass Avocado Ripening Photographic Dataset"


def main() -> int:
    wb = openpyxl.load_workbook(ROOT / BASE / "Avocado Ripening Dataset.xlsx", read_only=True)
    rows = list(wb.worksheets[0].iter_rows(values_only=True))
    head = [str(h) for h in rows[0]]
    i_file, i_group, i_sample, i_ri = (head.index(c) for c in
                                       ("File Name", "Storage Group", "Sample", "Ripening Index Classification"))
    n = missing = 0
    with open(ROOT / "metadata.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["filename", "sample", "ripening_index"])
        for r in rows[1:]:
            if not r[i_file]:
                continue
            rel = f"{BASE}/Avocado Ripening Dataset/{r[i_file]}.jpg"
            if not (ROOT / rel).exists():
                missing += 1
                continue
            w.writerow([rel, f"{r[i_group]}_{int(r[i_sample]):03d}", int(r[i_ri])])
            n += 1
    print(n, "rows,", missing, "listed files missing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
