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


def test_quality_gate():
    rng = np.random.default_rng(0)
    sharp = Image.fromarray(rng.integers(0, 255, (256, 256, 3), dtype=np.uint8))
    assert quality.assess(sharp).ok
    assert quality.assess(Image.new("RGB", (256, 256), (10, 10, 10))).reason == "too_dark"
    assert quality.assess(sharp.filter(ImageFilter.GaussianBlur(8))).reason == "blurry"
