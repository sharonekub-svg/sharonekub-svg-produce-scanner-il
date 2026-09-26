"""Torch dataset over data/processed/manifest.jsonl."""
from __future__ import annotations

import json
from pathlib import Path

import torch
from torch.utils.data import Dataset

from ml.common.taxonomy import HEADS, Taxonomy
from ml.preprocessing.image_io import load_rgb


def read_manifest(path: Path, splits: set[str] | None = None, datasets: set[str] | None = None) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if (splits is None or r["split"] in splits) and (datasets is None or r["dataset_id"] in datasets):
                rows.append(r)
    return rows


def select_rows(cfg: dict, splits: set[str], data_root: Path) -> list[dict]:
    """Rows for a config: dataset filter plus `exclude_source_regex` (classes held out of
    training entirely, e.g. to serve as an unseen-produce OOD set)."""
    import re
    d = cfg["data"]
    ds = set(d["datasets"]) if d.get("datasets") else None
    rows = read_manifest(data_root / "manifest.jsonl", splits, ds)
    pat = d.get("exclude_source_regex")
    if pat:
        rows = [r for r in rows if not re.search(pat, r["source_path"])]
    return rows


def label_mask(tax: Taxonomy, head: str, value) -> torch.Tensor:
    m = torch.zeros(tax.num_classes(head), dtype=torch.bool)
    enc = tax.encode(head, value)
    if enc is not None:
        m[list(enc)] = True
    return m


class ManifestDataset(Dataset):
    def __init__(self, rows: list[dict], root: Path, tax: Taxonomy, transform):
        self.rows, self.root, self.tax, self.transform = rows, root, tax, transform

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, i: int):
        r = self.rows[i]
        x = self.transform(load_rgb(self.root / r["image"]))
        y = {h: label_mask(self.tax, h, r["labels"][h]) for h in HEADS}
        return x, y


def collate(batch):
    xs, ys = zip(*batch)
    return torch.stack(xs), {h: torch.stack([y[h] for y in ys]) for h in HEADS}
