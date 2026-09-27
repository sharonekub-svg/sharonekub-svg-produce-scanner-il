"""Produce-care knowledge base (app/src/model/produce_care.json, docs/research/food-quality.md)."""
import json
from pathlib import Path

from ml.common.taxonomy import load_taxonomy
from ml.inference.decision import MOULD_RULE_HE

CARE = json.loads((Path(__file__).resolve().parents[1] / "app/src/model/produce_care.json").read_text(encoding="utf-8"))


def test_covers_every_supported_produce():
    tax = load_taxonomy()
    supported = {p for p, m in tax.produce_meta.items() if not m.get("is_negative_class")}
    assert set(CARE["produce"]) == supported


def test_fields_and_wording():
    for p, c in CARE["produce"].items():
        assert c["fridge"] in {"no", "after_ripening", "yes"}, p
        assert c["chill_below_c"] is None or 0 < c["chill_below_c"] < 20, p
        assert set(c["ethylene"]) == {"producer", "sensitive"}, p
        assert "בטוח" not in c["tip_he"], p  # never claim "safe"
    # chilling-sensitive and never refrigerated per Ministry of Agriculture guidance
    assert CARE["produce"]["banana"]["fridge"] == "no" and CARE["produce"]["tomato"]["fridge"] == "no"
    assert CARE["produce"]["kiwi"]["ethylene"]["sensitive"] and CARE["produce"]["apple"]["ethylene"]["producer"]


def test_mould_rule_matches_decision_policy():
    assert CARE["general_he"]["mould"] == MOULD_RULE_HE
