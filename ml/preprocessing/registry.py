"""Dataset registry loading and the licence gate.

The gate is deliberately conservative: a dataset may enter a *commercial*
training run only if
  (a) the registry marks commercial_use == "yes" AND the licence was verified
      against the primary source, OR
  (b) a human legal sign-off exists in data/license_signoffs.json.
Everything else is research-only at best.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from ml.common.taxonomy import REPO_ROOT

REGISTRY_PATH = REPO_ROOT / "data" / "dataset_registry.csv"
SIGNOFF_PATH = REPO_ROOT / "data" / "license_signoffs.json"

REQUIRED_COLUMNS = (
    "dataset_id", "name", "url", "original_source", "n_images", "n_original_images",
    "classes", "produce_types", "ripeness_labels", "freshness_labels", "spoilage_labels",
    "license", "license_verification", "commercial_use", "attribution_required",
    "share_alike", "known_restrictions", "duplication_notes", "image_resolution",
    "capture_conditions", "quality", "suitability", "planned_use", "priority", "license_evidence",
)
UNVERIFIED_COMMERCIAL = "DO NOT USE COMMERCIALLY UNTIL VERIFIED"
COMMERCIAL_VALUES = {"yes", "no", "conditional_legal_review", "conditional_per_image", UNVERIFIED_COMMERCIAL}
VERIFICATION_VALUES = {"verified_primary", "reported_secondary", "unverified"}
PLANNED_USE_VALUES = {
    "train+real_world_test", "train+cross_dataset_test", "train+test (after sign-off)",
    "train_aux", "train+ood", "research_only", "candidate", "exclude",
}
SIGNOFF_DECISIONS = ("approved_commercial", "research_only", "rejected")
PURPOSES = ("commercial_training", "research_training", "internal_evaluation")


@dataclass(frozen=True)
class DatasetEntry:
    row: dict[str, str]

    def __getattr__(self, item: str) -> str:
        try:
            return self.row[item]
        except KeyError as e:
            raise AttributeError(item) from e


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, DatasetEntry]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = set(REQUIRED_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"registry missing columns: {sorted(missing)}")
        entries = {}
        for row in reader:
            if None in row:
                raise ValueError(f"row {row.get('dataset_id')} has extra fields")
            if row["dataset_id"] in entries:
                raise ValueError(f"duplicate dataset_id {row['dataset_id']}")
            entries[row["dataset_id"]] = DatasetEntry(row)
    return entries


def load_signoffs(path: Path = SIGNOFF_PATH) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {"dataset_id", "reviewer", "date", "evidence_url", "decision"}
    out = {}
    for s in data:
        if not required <= s.keys():
            raise ValueError(f"sign-off missing fields: {required - s.keys()}")
        if s["decision"] not in SIGNOFF_DECISIONS:
            raise ValueError(f"sign-off decision must be one of {SIGNOFF_DECISIONS}")
        out[s["dataset_id"]] = s
    return out


def is_allowed(entry: DatasetEntry, purpose: str, signoffs: dict[str, dict] | None = None) -> tuple[bool, str]:
    """Return (allowed, reason)."""
    if purpose not in PURPOSES:
        raise ValueError(f"purpose must be one of {PURPOSES}")
    signoffs = load_signoffs() if signoffs is None else signoffs
    if entry.planned_use == "exclude":
        return False, "excluded in registry"
    s = signoffs.get(entry.dataset_id)
    if s is not None and s["decision"] == "rejected":
        return False, f"rejected by {s['reviewer']} on {s['date']}"
    if purpose == "commercial_training":
        if s is not None:
            ok = s["decision"] == "approved_commercial"
            return ok, f"legal sign-off by {s['reviewer']} on {s['date']}: {s['decision']}"
        if entry.commercial_use == "yes" and entry.license_verification == "verified_primary":
            return True, f"{entry.license} verified at primary source"
        return False, f"commercial_use={entry.commercial_use}, verification={entry.license_verification}"
    # Research / internal evaluation: anything not excluded, but keep the reason visible.
    return True, f"{purpose} permitted ({entry.license})"
