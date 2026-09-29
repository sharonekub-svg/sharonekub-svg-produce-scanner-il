"""General fresh-vs-spoiled score for types without a verified head (ml/inference/decision.py, v0.8)."""
import numpy as np

from ml.common.taxonomy import load_taxonomy
from ml.inference import decision as d


def _probs(tax, p_bad):
    n = len(tax.produce)
    pp = np.full(n, 0.001)
    pp[tax.produce.index("mango")] = 1 - 0.001 * (n - 1)
    out = {"produce": pp, "freshness": np.ones(3) / 3, "visual_spoilage": np.ones(3) / 3,
           "ripeness": np.ones(len(tax.heads["ripeness"])) / len(tax.heads["ripeness"])}
    if p_bad is not None:
        out["freshness_general"] = np.full(n, p_bad)
    return out


def test_general_score_matches_app_and_is_marked():
    tax = load_taxonomy()
    sup = {"mango": ["freshness~general"]}
    bad = d.decide(tax, _probs(tax, 0.9), sup)
    assert (bad.status, bad.score, bad.freshness.label, bad.general_score) == ("ok", 4, "not_fresh", True)
    assert bad.explanation_he[-1] == d.GENERAL_SCORE_HE
    good = d.decide(tax, _probs(tax, 0.05), sup)
    assert (good.score, good.general_score) == (10, True)
    assert d.decide(tax, _probs(tax, None), sup).score is None  # no general head in the bundle: no score


def test_general_never_overrides_a_verified_head():
    tax = load_taxonomy()
    r = d.decide(tax, _probs(tax, 0.99), {"mango": ["freshness", "freshness~general"]})
    assert r.general_score is False
