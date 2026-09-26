"""Dataset adapters: raw dataset files -> unified (possibly partial) labels.

Unmapped files are an ERROR, never silently dropped or guessed.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from ml.common.taxonomy import HEADS, LabelSet, Taxonomy
from ml.preprocessing.image_io import IMAGE_EXTENSIONS


class UnmappedLabelError(ValueError):
    pass


@dataclass(frozen=True)
class RawSample:
    dataset_id: str
    rel_path: str
    labels: dict[str, LabelSet]      # head -> label set (None = unknown)
    group_key: str | None            # namespaced "dataset_id:group"
    split_hint: str | None = None    # official split (train/val/test) or forced split, if any


def _encode_all(tax: Taxonomy, raw: dict[str, Any]) -> dict[str, LabelSet]:
    unknown = set(raw) - set(HEADS)
    if unknown:
        raise UnmappedLabelError(f"unknown heads {unknown}")
    return {h: tax.encode(h, raw.get(h)) for h in HEADS}


def map_path(tax: Taxonomy, dataset_id: str, rel_path: str) -> dict[str, LabelSet] | None:
    """Apply path_rules. Returns None if the file is excluded."""
    cfg = tax.datasets[dataset_id]
    for pat in cfg.get("exclude_patterns", []):
        if re.search(pat, rel_path, flags=re.IGNORECASE):
            return None
    raw: dict[str, Any] = {}
    for rule in cfg["rules"]:
        if re.search(rule["pattern"], rel_path, flags=re.IGNORECASE):
            for head, val in rule["labels"].items():
                raw.setdefault(head, val)
    if "produce" not in raw:
        if "default_produce" in cfg:
            raw["produce"] = cfg["default_produce"]
        else:
            raise UnmappedLabelError(f"{dataset_id}: no produce rule matched '{rel_path}'")
    return _encode_all(tax, raw)


def _group(cfg: dict, dataset_id: str, rel_path: str) -> str | None:
    pat = cfg.get("group_pattern")
    if not pat:
        return None
    m = re.search(pat, rel_path)
    return f"{dataset_id}:{m.group('group')}" if m else None


def _split_hint(cfg: dict, rel_path: str) -> str | None:
    if "force_split" in cfg:
        return cfg["force_split"]
    pat = cfg.get("split_pattern")
    if not pat:
        return None
    m = re.search(pat, rel_path)
    return m.group("split") if m else None


def _stable(key: str) -> str:
    import hashlib
    return hashlib.sha256(key.encode()).hexdigest()


def iter_path_rules(tax: Taxonomy, dataset_id: str, root: Path) -> Iterator[RawSample]:
    """`max_per_group` keeps a deterministic hash-ordered subset per metadata group
    (e.g. 80 of ~700 near-identical video frames per Fruits-360 class)."""
    cfg = tax.datasets[dataset_id]
    cap = cfg.get("max_per_group")
    if cap:
        by_group: dict[str | None, list[RawSample]] = {}
        for s in _iter_path_rules_all(tax, dataset_id, root):
            by_group.setdefault(s.group_key, []).append(s)
        for g in sorted(by_group, key=str):
            yield from sorted(by_group[g], key=lambda s: _stable(s.rel_path))[:cap]
        return
    yield from _iter_path_rules_all(tax, dataset_id, root)


def _iter_path_rules_all(tax: Taxonomy, dataset_id: str, root: Path) -> Iterator[RawSample]:
    cfg = tax.datasets[dataset_id]
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        rel = p.relative_to(root).as_posix()
        labels = map_path(tax, dataset_id, rel)
        if labels is not None:
            yield RawSample(dataset_id, rel, labels, _group(cfg, dataset_id, rel), _split_hint(cfg, rel))


def iter_table(tax: Taxonomy, dataset_id: str, root: Path) -> Iterator[RawSample]:
    cfg = tax.datasets[dataset_id]
    with open(root / cfg["table"], newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw: dict[str, Any] = dict(cfg.get("constant_labels", {}))
            for head, col in cfg["columns"].items():
                v = (row.get(col) or "").strip()
                if not v:
                    continue
                vmap = cfg.get("value_maps", {}).get(head)
                if vmap is not None:
                    if v not in vmap:
                        raise UnmappedLabelError(f"{dataset_id}: {head} value '{v}' not in value_map")
                    v = vmap[v]
                raw[head] = v.split("|") if "|" in v else v
            if "produce" not in raw:
                raise UnmappedLabelError(f"{dataset_id}: row without produce: {row}")
            g = row.get(cfg.get("group_column", ""), "")
            hint = cfg.get("force_split") or (row.get(cfg["split_column"]) if "split_column" in cfg else None) or None
            if hint is not None and hint not in ("train", "val", "test"):
                raise UnmappedLabelError(f"{dataset_id}: bad split value '{hint}'")
            yield RawSample(dataset_id, row[cfg["path_column"]], _encode_all(tax, raw),
                            f"{dataset_id}:{g}" if g else None, hint)


ADAPTERS = {"path_rules": iter_path_rules, "table": iter_table}


def iter_dataset(tax: Taxonomy, dataset_id: str, root: Path) -> Iterator[RawSample]:
    adapter = tax.datasets[dataset_id]["adapter"]
    if adapter not in ADAPTERS:
        raise NotImplementedError(f"adapter '{adapter}' for {dataset_id} not implemented yet")
    yield from ADAPTERS[adapter](tax, dataset_id, root)
