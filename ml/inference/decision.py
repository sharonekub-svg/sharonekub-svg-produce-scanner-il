"""Turn calibrated head probabilities into a user-facing Hebrew result.

Principles:
  * Abstain rather than guess (low confidence, OOD, 'other', failed quality gate).
  * Only report a head for produce types where that head was trained with real
    labels (`supported_heads`); otherwise say it is not available.
  * Never state that food is safe. Every result carries the visual-only disclaimer.
  * Recommendation is a transparent rule table on top of the model, not learned.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from ml.common.taxonomy import Taxonomy

DISCLAIMER_HE = "חשוב: זו הערכה חזותית בלבד ואינה מבטיחה שהמזון בטוח לאכילה."
RETAKE_HE = {
    "too_dark": "התמונה חשוכה מדי. נסה לצלם בתאורה טובה יותר.",
    "too_bright": "התמונה בהירה מדי. נסה להימנע מאור ישיר.",
    "overexposed": "יש בתמונה אזורים שרופים מאור. נסה לצלם בזווית אחרת.",
    "blurry": "התמונה מטושטשת. החזק את הטלפון יציב ונסה שוב.",
    "multiple_objects": "זוהו כמה פריטים. צלם פרי או ירק אחד בכל פעם.",
}
UNSURE_HE = "לא הצלחתי לזהות את הפרי בוודאות. נסה לצלם אותו מקרוב ובתאורה טובה יותר."
NOT_PRODUCE_HE = "לא זיהיתי פרי או ירק שאני מכיר בתמונה."

REC_HE = {
    "discard": "לא מומלץ לאכול – נראים סימני קלקול",
    "eat_soon": "כדאי לאכול בהקדם",
    "eat_now": "כדאי לאכול עכשיו",
    "wait": "כדאי לחכות – עדיין לא בשל",
    "wait_little": "כמעט בשל – כדאי לחכות עוד מעט",
    "overripe": "בשל מאוד – לאכול היום או להשתמש לבישול/אפייה",
    "inspect": "לא ניתן להעריך בוודאות – מומלץ לבדוק ידנית",
}

DEFAULT_THRESHOLDS = {
    "produce_min_prob": 0.70,
    "produce_min_margin": 0.15,     # top1 - top2
    "ood_min_energy": None,         # set from val (e.g. 5th percentile of in-dist energy)
    "head_min_prob": 0.55,
    "spoiled_alert_prob": 0.40,     # conservative: warn early on spoilage
}


@dataclass
class HeadResult:
    label: str | None
    label_he: str | None
    confidence: float | None
    available: bool


@dataclass
class ScanResult:
    status: str                                  # ok | retake | unsure | not_produce
    message_he: str | None = None
    produce: str | None = None
    produce_he: str | None = None
    emoji: str | None = None
    produce_confidence: float | None = None
    ripeness: HeadResult | None = None
    freshness: HeadResult | None = None
    visual_spoilage: HeadResult | None = None
    recommendation: str | None = None
    recommendation_he: str | None = None
    explanation_he: list[str] = field(default_factory=list)
    disclaimer_he: str = DISCLAIMER_HE

    def to_dict(self) -> dict:
        return asdict(self)


def _head(tax: Taxonomy, head: str, probs: np.ndarray | None, available: bool, min_prob: float) -> HeadResult:
    if not available or probs is None:
        return HeadResult(None, None, None, False)
    i = int(np.argmax(probs))
    conf = float(probs[i])
    if conf < min_prob:
        return HeadResult(tax.unknown, tax.label_he[head][tax.unknown], conf, True)
    lbl = tax.heads[head][i]
    return HeadResult(lbl, tax.label_he[head][lbl], conf, True)


def decide(tax: Taxonomy, probs: dict[str, np.ndarray], supported_heads: dict[str, list[str]],
           quality_reason: str | None = None, energy_score: float | None = None,
           thresholds: dict | None = None) -> ScanResult:
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    if quality_reason:
        return ScanResult("retake", RETAKE_HE.get(quality_reason, UNSURE_HE))

    p = probs["produce"]
    order = np.argsort(-p)
    top, second = int(order[0]), int(order[1]) if len(order) > 1 else None
    conf = float(p[top])
    margin = conf - (float(p[second]) if second is not None else 0.0)
    if t["ood_min_energy"] is not None and energy_score is not None and energy_score < t["ood_min_energy"]:
        return ScanResult("unsure", UNSURE_HE, produce_confidence=conf)
    name = tax.produce[top]
    if tax.produce_meta[name].get("is_negative_class"):
        return ScanResult("not_produce", NOT_PRODUCE_HE, produce_confidence=conf)
    if conf < t["produce_min_prob"] or margin < t["produce_min_margin"]:
        return ScanResult("unsure", UNSURE_HE, produce_confidence=conf)

    sup = set(supported_heads.get(name, []))
    r = _head(tax, "ripeness", probs.get("ripeness"), "ripeness" in sup, t["head_min_prob"])
    f = _head(tax, "freshness", probs.get("freshness"), "freshness" in sup, t["head_min_prob"])
    s = _head(tax, "visual_spoilage", probs.get("visual_spoilage"), "visual_spoilage" in sup, t["head_min_prob"])

    meta = tax.produce_meta[name]
    res = ScanResult("ok", produce=name, produce_he=meta["he"], emoji=meta["emoji"],
                     produce_confidence=conf, ripeness=r, freshness=f, visual_spoilage=s)

    p_spoiled = 0.0
    if f.available and probs.get("freshness") is not None:
        p_spoiled = float(probs["freshness"][tax.heads["freshness"].index("spoiled")])
    if s.available and probs.get("visual_spoilage") is not None:
        p_spoiled = max(p_spoiled, float(probs["visual_spoilage"][tax.heads["visual_spoilage"].index("severe")]))

    if p_spoiled >= t["spoiled_alert_prob"]:
        rec = "discard"
        res.explanation_he.append("זוהו סימנים חזותיים שמתאימים בדרך כלל לקלקול או ריקבון.")
    elif r.available and r.label not in (None, tax.unknown):
        rec = {"unripe": "wait", "partially_ripe": "wait_little", "ripe": "eat_now", "overripe": "overripe"}[r.label]
        res.explanation_he.append(f"הצבע והמראה החיצוני תואמים בדרך כלל ל{meta['he']} במצב '{r.label_he}'.")
    elif f.available and f.label == "fresh":
        rec = "eat_now"
        res.explanation_he.append("המראה החיצוני תואם בדרך כלל לפרי טרי. לא זוהו סימני ריקבון משמעותיים.")
    elif f.available and f.label == "declining":
        rec = "eat_soon"
        res.explanation_he.append("נראים סימנים ראשונים לירידה בטריות.")
    else:
        rec = "inspect"
        res.explanation_he.append("למודל אין מספיק ביטחון או נתוני אימון כדי להעריך בשילות/טריות לסוג זה.")
    res.recommendation, res.recommendation_he = rec, REC_HE[rec]
    return res


def supported_heads_from_manifest(rows: list[dict], min_exact: int = 200, min_per_class: int = 50,
                                  min_classes: int = 2) -> dict[str, list[str]]:
    """A head is 'supported' for a produce type only if the TRAIN split has >= `min_exact`
    exactly-labelled examples AND >= `min_classes` distinct classes with >= `min_per_class`
    each (a head trained on one class only - e.g. Fruits-360 'Avocado ripe' - is not a
    ripeness model). Written into the model bundle and enforced by `decide`."""
    from collections import Counter
    c: Counter = Counter()
    for r in rows:
        if r["split"] != "train" or not isinstance(r["labels"]["produce"], str):
            continue
        for h in ("ripeness", "freshness", "visual_spoilage"):
            v = r["labels"][h]
            if isinstance(v, str) and v != "unknown":
                c[(r["labels"]["produce"], h, v)] += 1
    per: dict[tuple[str, str], list[int]] = {}
    for (prod, h, _), n in c.items():
        per.setdefault((prod, h), []).append(n)
    out: dict[str, list[str]] = {}
    for (prod, h), ns in per.items():
        if sum(ns) >= min_exact and sum(n >= min_per_class for n in ns) >= min_classes:
            out.setdefault(prod, []).append(h)
    return {k: sorted(v) for k, v in out.items()}
