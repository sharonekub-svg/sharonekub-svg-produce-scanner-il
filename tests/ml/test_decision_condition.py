"""Condition-first scoring rules (docs/quality-scoring.md §5) hold for every input."""
import numpy as np

from ml.common.taxonomy import HEADS, load_taxonomy
from ml.inference.decision import LOW_CONF_CAP, decide


def _probs(tax, rng, name, pg):
    probs = {}
    for h in HEADS:
        x = rng.uniform(0, 1, tax.num_classes(h)); probs[h] = x / x.sum()
    p = np.full(tax.num_classes("produce"), 0.001); p[tax.produce.index(name)] = 1.0
    probs["produce"] = p / p.sum()
    probs["condition"] = np.full(tax.num_classes("produce"), 0.5); probs["condition"][tax.produce.index(name)] = pg
    return probs


def test_condition_rules():
    tax = load_taxonomy()
    rng = np.random.default_rng(0)
    sup = {"banana": ["ripeness", "condition"], "apple": ["condition"]}
    th = {"condition_abstain": {"banana": 0.8, "apple": 0.9}}
    for _ in range(2000):
        name = rng.choice(["banana", "apple"])
        pg = float(rng.uniform(0, 1))
        r = decide(tax, _probs(tax, rng, name, pg), sup, thresholds=th)
        assert r.status == "ok" and r.condition.available
        assert r.overall <= r.condition_score                      # a defect is never outweighed by ripeness
        if r.ripeness_score is not None:
            assert r.overall <= r.ripeness_score
        if r.low_confidence:
            assert r.overall <= LOW_CONF_CAP and r.recommendation == "inspect"   # unsure -> conservative + retake
        if pg < 0.5:
            assert r.overall <= 50 and r.recommendation in ("check_defects", "inspect")
        assert 1 <= r.score <= 10
        assert all(i for i in r.issues_he)                         # issues only from heads that reported them
