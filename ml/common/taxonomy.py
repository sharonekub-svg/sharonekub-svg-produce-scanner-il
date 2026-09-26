"""Unified label taxonomy loaded from data/label_mapping.json.

A label for one head is represented as a frozenset of allowed class indices:
  - frozenset({i})        -> exact label
  - frozenset({i, j,..})  -> set-valued (partial) label; truth is one of these
  - None                  -> unknown; the head is ignored for this sample
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAPPING_PATH = REPO_ROOT / "data" / "label_mapping.json"

HEADS = ("produce", "ripeness", "freshness", "visual_spoilage")

LabelSet = frozenset[int] | None


@dataclass(frozen=True)
class Taxonomy:
    produce: tuple[str, ...]
    heads: dict[str, tuple[str, ...]]
    unknown: str
    produce_meta: dict[str, dict[str, Any]]
    label_he: dict[str, dict[str, str]]
    datasets: dict[str, dict[str, Any]] = field(default_factory=dict)

    def classes(self, head: str) -> tuple[str, ...]:
        return self.produce if head == "produce" else self.heads[head]

    def num_classes(self, head: str) -> int:
        return len(self.classes(head))

    def encode(self, head: str, value: Any) -> LabelSet:
        """Encode a raw mapping value (str | list[str] | None | 'unknown')."""
        if value is None or value == self.unknown:
            return None
        values = [value] if isinstance(value, str) else list(value)
        if not values:
            return None
        classes = self.classes(head)
        idx = set()
        for v in values:
            if v not in classes:
                raise ValueError(f"'{v}' is not a valid {head} label; valid: {classes}")
            idx.add(classes.index(v))
        # A set covering every class carries no information -> unknown.
        if len(idx) == len(classes):
            return None
        return frozenset(idx)

    def decode(self, head: str, label: LabelSet) -> str | list[str]:
        if label is None:
            return self.unknown
        names = [self.classes(head)[i] for i in sorted(label)]
        return names[0] if len(names) == 1 else names


def load_taxonomy(path: str | Path = DEFAULT_MAPPING_PATH) -> Taxonomy:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return Taxonomy(
        produce=tuple(raw["produce"].keys()),
        heads={k: tuple(v) for k, v in raw["heads"].items()},
        unknown=raw["unknown"],
        produce_meta=raw["produce"],
        label_he=raw["label_he"],
        datasets=raw.get("datasets", {}),
    )
