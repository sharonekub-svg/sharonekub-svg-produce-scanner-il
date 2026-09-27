import numpy as np
from PIL import Image, ImageFilter

from ml.common.taxonomy import load_taxonomy
from ml.evaluation import calibration, gates, metrics, ood
from ml.inference import decision, quality

TAX = load_taxonomy()


def test_prf_and_topk():
    y = np.array([0, 0, 1, 1, 2])
    p = np.array([[.9, .05, .05], [.2, .7, .1], [.1, .8, .1], [.1, .8, .1], [.3, .3, .4]])
    s = metrics.summarize(p, y, ["a", "b", "c"])
    assert s["top1"] == 0.8
    assert s["per_class"]["a"]["recall"] == 0.5
    assert s["per_class"]["b"]["precision"] == 2 / 3
    assert s["worst_class_recall"] == 0.5
    assert metrics.topk_accuracy(p, y, 2) == 1.0


def test_ece_zero_for_perfectly_calibrated():
    p = np.array([[1.0, 0.0]] * 10)
    assert metrics.expected_calibration_error(p, np.zeros(10, int)) == 0.0


def test_temperature_scaling_recovers_overconfidence():
    rng = np.random.default_rng(0)
    n, c = 4000, 5
    true_logits = rng.normal(0, 1.5, (n, c))
    y = np.array([rng.choice(c, p=calibration.softmax(true_logits[i:i + 1])[0]) for i in range(n)])
    t = calibration.fit_temperature(true_logits * 3.0, y)  # model is 3x overconfident
    assert 2.5 < t < 3.5
    before = metrics.expected_calibration_error(calibration.softmax(true_logits * 3), y)
    after = metrics.expected_calibration_error(calibration.softmax(true_logits * 3, t), y)
    assert after < before


def test_auroc():
    assert ood.auroc(np.array([2., 3.]), np.array([0., 1.])) == 1.0
    assert ood.auroc(np.array([1., 1.]), np.array([1., 1.])) == 0.5


def test_gates_catch_weak_priority_class():
    y = np.array([0] * 90 + [1] * 10)
    p = np.zeros((100, 2)); p[:, 0] = 1  # never predicts class 1
    s = {"produce": metrics.summarize(p, y, ["apple", "banana"])}
    fails = gates.check_gates(s, {"produce": {"min_class_recall": {"default": 0.8, "banana": 0.9}}})
    assert any("banana" in f for f in fails)  # 90% accuracy still fails


def _probs(produce="banana", pp=0.95, ripeness=None, freshness=None):
    p = np.full(len(TAX.produce), (1 - pp) / (len(TAX.produce) - 1))
    p[TAX.produce.index(produce)] = pp
    out = {"produce": p}
    if ripeness is not None:
        out["ripeness"] = np.array(ripeness)
    if freshness is not None:
        out["freshness"] = np.array(freshness)
    return out


def test_decision_ok_hebrew_and_disclaimer():
    r = decision.decide(TAX, _probs(ripeness=[.02, .08, .85, .05], freshness=[.9, .08, .02]),
                        {"banana": ["ripeness", "freshness"]})
    assert r.status == "ok" and r.produce_he == "בננה" and r.ripeness.label == "ripe"
    assert r.recommendation == "eat_now"
    assert "הערכה חזותית בלבד" in r.disclaimer_he


def test_decision_abstains_when_unsure_or_bad_photo_or_other():
    assert decision.decide(TAX, _probs(pp=0.4), {}).status == "unsure"
    assert decision.decide(TAX, _probs(), {}, quality_reason="blurry").status == "retake"
    assert decision.decide(TAX, _probs(produce="other"), {}).status == "not_produce"


def test_decision_spoilage_overrides_ripeness():
    r = decision.decide(TAX, _probs(ripeness=[0, 0, 1, 0], freshness=[.3, .2, .5]),
                        {"banana": ["ripeness", "freshness"]})
    assert r.recommendation == "discard"


def test_unsupported_head_is_not_reported():
    r = decision.decide(TAX, _probs(produce="kiwi", ripeness=[0, 0, 1, 0]), {"kiwi": []})
    assert r.status == "ok" and not r.ripeness.available and r.recommendation == "inspect"


def test_supported_heads_requires_multiple_classes():
    rows = [{"split": "train", "labels": {"produce": "avocado", "ripeness": "ripe", "freshness": "unknown",
                                          "visual_spoilage": "unknown"}}] * 500
    assert decision.supported_heads_from_manifest(rows) == {}
    rows += [{"split": "train", "labels": {"produce": "avocado", "ripeness": "unripe", "freshness": "unknown",
                                           "visual_spoilage": "unknown"}}] * 100
    assert decision.supported_heads_from_manifest(rows) == {"avocado": ["ripeness"]}


def test_ripeness_visual_vetoes_ripeness():
    def rows(prod, cultivar=None):
        base = {"split": "train", "labels": {"produce": prod, "freshness": "unknown", "visual_spoilage": "unknown"}}
        if cultivar:
            base["cultivar"] = cultivar
        return [{**base, "labels": {**base["labels"], "ripeness": v}} for v in ("ripe", "unripe") for _ in range(150)]
    rv = {"banana": "strong", "orange": "not_applicable", "melon": "weak", "avocado": "cultivar_dependent"}
    all_rows = rows("banana") + rows("orange") + rows("melon") + rows("avocado")
    assert decision.supported_heads_from_manifest(all_rows, ripeness_visual=rv) == {"banana": ["ripeness"]}
    assert decision.supported_heads_from_manifest(all_rows + rows("avocado", "hass"), ripeness_visual=rv) == {
        "avocado": ["ripeness"], "banana": ["ripeness"]}
    # real mapping: every produce has a valid value, citrus never gets ripeness
    tax = load_taxonomy()
    vals = {m["ripeness_visual"] for m in tax.produce_meta.values()}
    assert vals <= {"strong", "cultivar_dependent", "weak", "not_applicable"}
    assert all(tax.produce_meta[c]["ripeness_visual"] == "not_applicable" for c in ("orange", "mandarin", "lemon"))

def test_quality_gate():
    rng = np.random.default_rng(0)
    sharp = Image.fromarray(rng.integers(0, 255, (256, 256, 3), dtype=np.uint8))
    assert quality.assess(sharp).ok
    assert quality.assess(Image.new("RGB", (256, 256), (10, 10, 10))).reason == "too_dark"
    assert quality.assess(sharp.filter(ImageFilter.GaussianBlur(8))).reason == "blurry"


def test_feature_ood_scores_separate_far_points():
    from ml.evaluation import feature_ood
    rng = np.random.default_rng(0)
    f = np.concatenate([rng.normal(0, 1, (200, 8)) + 5 * np.eye(8)[0], rng.normal(0, 1, (200, 8)) - 5 * np.eye(8)[0]])
    y = np.repeat([0, 1], 200)
    mu, prec = feature_ood.fit_mahalanobis(f, y)
    near, far = f[:50], rng.normal(0, 1, (50, 8)) + 5 * np.eye(8)[1]
    m_in, m_out = feature_ood.mahalanobis_score(near, mu, prec), feature_ood.mahalanobis_score(far, mu, prec)
    assert ood.auroc(m_in, m_out) > 0.95
    k_in, k_out = feature_ood.knn_score(near, f, k=10), feature_ood.knn_score(far, f, k=10)
    assert ood.auroc(k_in, k_out) > 0.9


def test_restrict_produce_follows_model_classes():
    from ml.common.taxonomy import restrict_produce
    names = [p for p in TAX.produce if p not in ("lime", "grapefruit")]
    t = restrict_produce(TAX, names)
    assert t.produce == tuple(names) and t.produce[-1] == "other" and "lime" not in t.produce_meta
    import pytest
    with pytest.raises(ValueError):
        restrict_produce(TAX, ["banana", "durian"])


def test_quality_score_worst_head_decides_and_is_bounded():
    avail = {"freshness": True, "visual_spoilage": True, "ripeness": True}
    fresh_ripe = {"freshness": np.array([1.0, 0, 0]), "visual_spoilage": np.array([1.0, 0, 0]),
                  "ripeness": np.array([0, 0, 1.0, 0])}
    assert decision.quality_score(TAX, fresh_ripe, avail, False)[0] == 10
    mouldy = {**fresh_ripe, "visual_spoilage": np.array([0, 0, 1.0])}
    sc, why = decision.quality_score(TAX, mouldy, avail, False)
    assert sc == 1 and "עובש" in why
    unripe = {**fresh_ripe, "ripeness": np.array([1.0, 0, 0, 0])}
    assert decision.quality_score(TAX, unripe, avail, False) == (5, decision.SCORE_REASON_HE["unripe"])
    assert decision.quality_score(TAX, fresh_ripe, avail, True)[0] == 2          # discard caps the score
    none = {"freshness": False, "visual_spoilage": False, "ripeness": False}
    assert decision.quality_score(TAX, fresh_ripe, none, False) == (None, decision.NO_SCORE_HE)


def test_identify_only_types_get_no_score():
    r = decision.decide(TAX, _probs(produce="kiwi"), {"kiwi": []})
    assert r.status == "ok" and r.score is None and r.score_reason_he == decision.NO_SCORE_HE


def test_coarse_heads_support_and_decision():
    def row(prod, fr, sp):
        return {"split": "train", "labels": {"produce": prod, "ripeness": "unknown", "freshness": fr, "visual_spoilage": sp}}
    rows = [row("orange", "fresh", "none")] * 150 + [row("orange", ["declining", "spoiled"], ["mild", "severe"])] * 150
    sup = decision.supported_heads_from_manifest(rows)
    assert sup == {"orange": ["freshness~coarse", "visual_spoilage~coarse"]}
    bad = _probs(produce="orange")
    bad["freshness"] = np.array([0.1, 0.1, 0.8]); bad["visual_spoilage"] = np.array([0.1, 0.1, 0.8])
    r = decision.decide(TAX, bad, sup)
    assert r.recommendation == "check_defects"      # coarse "bad" never becomes "discard"
    assert r.freshness.label == "not_fresh" and r.score == 4 and decision.MOULD_RULE_HE in r.explanation_he
    good = _probs(produce="orange")
    good["freshness"] = np.array([0.95, 0.03, 0.02]); good["visual_spoilage"] = np.array([0.95, 0.03, 0.02])
    g = decision.decide(TAX, good, sup)
    assert g.recommendation == "eat_now" and g.score == 10


def test_quality_gate_keeps_only_heads_that_passed():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("g", Path(__file__).resolve().parents[2] / "scripts/gate_quality_heads.py")
    g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
    q = {"visual_spoilage": {"apple": {"n_good": 200, "n_bad": 180, "balanced_accuracy": 0.93, "auroc": 0.97},
                             "lemon": {"n_good": 20, "n_bad": 20, "balanced_accuracy": 0.99, "auroc": 1.0}},
         "ripeness": {"avocado": {"n": 1400, "accuracy": 0.66, "within_one_stage": 0.97}}}
    sup = {"apple": ["visual_spoilage~coarse"], "lemon": ["visual_spoilage~coarse"], "avocado": ["ripeness"],
           "orange": ["freshness~coarse"]}
    kept, _ = g.gate(q, sup)
    assert kept == {"apple": ["visual_spoilage~coarse"]}   # lemon: too few test photos; avocado: below 0.70; orange: no evidence
