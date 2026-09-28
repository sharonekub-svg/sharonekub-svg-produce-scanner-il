"""Skin-appearance text and hand-check tip in the scan response (server/app.py)."""
from server.app import CARE, surface_he, touch_tip_he


def h(label):
    return {"label": label, "available": label is not None}


def test_surface_follows_heads_only():
    assert surface_he({"freshness": h("spoiled"), "visual_spoilage": h("defects")}) == "סימני ריקבון נראים בקליפה"
    assert surface_he({"freshness": h("fresh"), "visual_spoilage": h("defects")}) == "פגמים נראים בקליפה"
    assert surface_he({"freshness": h("declining"), "visual_spoilage": h("none")}) == "כתמים קלים או סימני התייבשות"
    assert surface_he({"freshness": h("fresh"), "visual_spoilage": h("none")}) == "קליפה נקייה, בלי פגמים נראים"
    assert surface_he({"freshness": h(None), "visual_spoilage": h(None)}) is None


def test_touch_tip_every_produce_and_no_safety_claims():
    for p, c in CARE["produce"].items():
        assert touch_tip_he(p) == c["touch_he"] and "בטוח" not in c["touch_he"], p
    assert touch_tip_he(None) is None and touch_tip_he("other") is None
