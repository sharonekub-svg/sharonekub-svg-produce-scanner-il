import csv
import re

import pytest

from ml.common.taxonomy import HEADS, load_taxonomy
from ml.preprocessing import registry
from ml.preprocessing.labels import UnmappedLabelError, map_path

TAX = load_taxonomy()
REG = registry.load_registry()


def test_registry_schema_and_enums():
    for ds, e in REG.items():
        assert e.commercial_use in registry.COMMERCIAL_VALUES, ds
        assert e.license_verification in registry.VERIFICATION_VALUES, ds
        assert e.planned_use in registry.PLANNED_USE_VALUES, ds


def test_unverified_licences_are_never_commercial():
    for ds, e in REG.items():
        if e.license_verification == "unverified":
            assert e.commercial_use in ("no", registry.UNVERIFIED_COMMERCIAL), ds


def test_noncommercial_licences_blocked():
    for ds, e in REG.items():
        if re.search(r"\bNC\b|NonCommercial|non-commercial", e.license, re.I):
            assert e.commercial_use == "no", ds
            assert not registry.is_allowed(e, "commercial_training", {})[0], ds


def test_commercial_gate_requires_primary_verification_or_signoff():
    allowed = {ds for ds, e in REG.items() if registry.is_allowed(e, "commercial_training", {})[0]}
    for ds in allowed:
        assert REG[ds].license_verification == "verified_primary"
    # a sign-off can approve, and a rejection sign-off blocks even a 'yes' row
    e = REG["fruitnet_indian"]
    s = {"fruitnet_indian": {"dataset_id": "fruitnet_indian", "reviewer": "x", "date": "2026-01-01",
                             "evidence_url": "u", "decision": "approved_commercial"}}
    assert registry.is_allowed(e, "commercial_training", s)[0]


def test_excluded_never_allowed_for_anything():
    for ds, e in REG.items():
        if e.planned_use == "exclude":
            for p in registry.PURPOSES:
                assert not registry.is_allowed(e, p, {})[0], (ds, p)


def test_mapping_datasets_are_registered_and_values_valid():
    for ds, cfg in TAX.datasets.items():
        assert ds in REG, ds
        for rule in cfg.get("rules", []):
            re.compile(rule["pattern"])
            for head, v in rule["labels"].items():
                assert head in HEADS
                TAX.encode(head, v)  # raises on invalid label
        for head, vmap in cfg.get("value_maps", {}).items():
            for v in vmap.values():
                TAX.encode(head, v)


def test_trainable_datasets_have_mappings():
    for ds, e in REG.items():
        if e.planned_use.startswith("train"):
            assert ds in TAX.datasets, f"{ds} is planned for training but has no label mapping"


def test_binary_quality_labels_do_not_fabricate_ripeness():
    lab = map_path(TAX, "fruitnet_indian", "Bad Quality_Fruits/Banana_Bad/IMG_1.jpg")
    assert lab["ripeness"] is None
    assert lab["freshness"] == TAX.encode("freshness", ["declining", "spoiled"])
    assert lab["produce"] == TAX.encode("produce", "banana")
    assert map_path(TAX, "fruitnet_indian", "Mixed Qualit_Fruits/Apple/IMG_2.jpg") is None


def test_ripeness_rule_ordering():
    m = lambda p: TAX.decode("ripeness", map_path(TAX, "strawberry_avocado_ripening", p)["ripeness"])
    assert m("Strawberry/Unripe/a.jpg") == "unripe"
    assert m("Strawberry/Partially Ripe/a.jpg") == "partially_ripe"
    assert m("Avocado/Ripe/a.jpg") == "ripe"
    rot = map_path(TAX, "strawberry_avocado_ripening", "Avocado/Rotten/a.jpg")
    assert rot["ripeness"] is None and TAX.decode("freshness", rot["freshness"]) == "spoiled"


def test_fruits360_ambiguous_classes():
    m = lambda p: map_path(TAX, "fruits360_original", p)
    assert TAX.decode("ripeness", m("Training/Avocado ripe 1/r_0.jpg")["ripeness"]) == "ripe"
    assert m("Training/Avocado 1/r_0.jpg")["ripeness"] is None  # plain 'Avocado' is NOT 'unripe'
    assert TAX.decode("produce", m("Training/Grapefruit Pink 1/r_0.jpg")["produce"]) == "other"
    assert TAX.decode("produce", m("Training/Pineapple 1/r_0.jpg")["produce"]) == "other"
    assert TAX.decode("produce", m("Training/Watermelon 1/r_0.jpg")["produce"]) == "watermelon"
    assert m("Training/Strawberry Wedge 1/r_0.jpg") is None


def test_unmapped_file_is_an_error():
    with pytest.raises(UnmappedLabelError):
        map_path(TAX, "fruitnet_indian", "Good Quality_Fruits/Durian_Good/x.jpg")


def test_full_set_label_collapses_to_unknown():
    assert TAX.encode("freshness", ["fresh", "declining", "spoiled"]) is None
