"""Turn calibrated head probabilities into a user-facing Hebrew result.

Principles:
  * Abstain rather than guess (low confidence, OOD, 'other', failed quality gate).
  * Only report a head for produce types where that head was trained with real
    labels (`supported_heads`); otherwise say it is not available.
  * Never state that food is safe. Every result carries the visual-only disclaimer.
  * Recommendation is a transparent rule table on top of the model, not learned.
"""
from __future__ import annotations

import math
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
# Israeli Ministry of Health guidance (docs/research/food-quality.md): discard mouldy food whole,
# do not cut the visible mould out. Stricter than USDA's firm-produce exception, and it is the local rule.
MOULD_RULE_HE = "לפי משרד הבריאות: מזון שצמח עליו עובש – לזרוק בשלמותו, ולא לחתוך רק את החלק שנראה עבש."
NOT_PRODUCE_HE = "לא זיהיתי פרי או ירק שאני מכיר בתמונה."

REC_HE = {
    "discard": "לא מומלץ לאכול – נראים סימני קלקול",
    "eat_soon": "כדאי לאכול בהקדם",
    "eat_now": "כדאי לאכול עכשיו",
    "wait": "כדאי לחכות – עדיין לא בשל",
    "wait_little": "כמעט בשל – כדאי לחכות עוד מעט",
    "overripe": "בשל מאוד – לאכול היום או להשתמש לבישול/אפייה",
    "check_defects": "נראים פגמים או סימני קלקול – בדקו את הפרי לפני שאוכלים",
    "inspect": "לא ניתן להעריך בוודאות – מומלץ לבדוק ידנית",
}

# Coarse heads: trained from good/bad datasets whose "bad" mixes mild defects and rot (e.g. FruitNet;
# audit in docs/research/dataset-search-2026-09.md). They can say good vs bad, never HOW bad, so they never
# trigger "discard" and score bad with a fixed 3. Marked in supported_heads as "<head>~coarse".
COARSE = {"freshness": ("fresh", ("declining", "spoiled"), "not_fresh"),
          "visual_spoilage": ("none", ("mild", "severe"), "defects")}
COARSE_LABEL_HE = {"not_fresh": "לא טרי", "defects": "פגמים נראים"}
COARSE_BAD_POINTS = 3.0

# 1-10 visual quality score (docs/research/quality-score.md). Each available quality head gives an
# expected score over its probabilities; the WORST one decides (rot beats "ripe"). Only heads that are
# supported for this produce type count, so a type without trained quality heads gets no score.
SCORE_POINTS = {
    "freshness": {"fresh": 10.0, "declining": 6.0, "spoiled": 1.0},
    "visual_spoilage": {"none": 10.0, "mild": 5.0, "severe": 1.0},
    "ripeness": {"unripe": 5.0, "partially_ripe": 8.0, "ripe": 10.0, "overripe": 6.0},
}
SCORE_REASON_HE = {
    "good": "נראה טרי, בלי סימני קלקול נראים.",
    "spoilage": "נראים סימני ריקבון, עובש או פגמים בקליפה.",
    "spoiled": "המראה מתאים לפרי שהתקלקל.",
    "not_fresh": "המראה מראה ירידה בטריות או קלקול.",
    "declining": "מתחיל לאבד טריות – כדאי לאכול בקרוב.",
    "unripe": "עדיין לא בשל – יהיה טעים יותר בעוד כמה ימים.",
    "overripe": "בשל מאוד – לאכול היום או להשתמש לאפייה.",
}
LOW_CONF_SCORE_HE = "לא ניתן לדרג בביטחון מהתמונה הזו – נסו לצלם מקרוב ובאור טוב."
NO_SCORE_HE = "עדיין אין דירוג איכות לסוג הזה – המודל מזהה אותו אבל עוד לא אומן להעריך את מצבו."

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
    score: int | None = None                     # 1-10 visual quality, None = not available for this type
    score_reason_he: str | None = None
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


def _coarse_head(tax: Taxonomy, head: str, probs: np.ndarray | None, min_prob: float) -> HeadResult:
    if probs is None:
        return HeadResult(None, None, None, False)
    good, _, group = COARSE[head]
    p_good = float(probs[tax.heads[head].index(good)])
    p_bad = 1.0 - p_good
    if p_good >= min_prob:
        return HeadResult(good, tax.label_he[head][good], p_good, True)
    if p_bad >= min_prob:
        return HeadResult(group, COARSE_LABEL_HE[group], p_bad, True)
    return HeadResult(tax.unknown, tax.label_he[head][tax.unknown], max(p_good, p_bad), True)


def quality_score(tax: Taxonomy, probs: dict[str, np.ndarray], available: dict[str, bool],
                  discard: bool, coarse: frozenset | set = frozenset()) -> tuple[int | None, str]:
    comps: dict[str, float] = {}
    for head in ("freshness", "visual_spoilage", "ripeness"):
        p = probs.get(head)
        if available.get(head) and p is not None:
            e = 0.0
            if head in coarse:
                pg = float(p[tax.heads[head].index(COARSE[head][0])])
                e = pg * 10.0 + (1.0 - pg) * COARSE_BAD_POINTS
            else:
                for i, lbl in enumerate(tax.heads[head]):
                    e += float(p[i]) * SCORE_POINTS[head][lbl]
            comps[head] = e
    if not comps:
        return None, NO_SCORE_HE
    worst = min(comps, key=lambda h: comps[h])  # first of equal minima, in the order above
    score = int(min(10.0, max(1.0, math.floor(comps[worst] + 0.5))))
    if discard:
        score = min(score, 2)
    top = tax.heads[worst][int(np.argmax(probs[worst]))]
    if score >= 8:
        reason = "good"
    elif worst == "visual_spoilage":
        reason = "spoilage"
    elif worst == "freshness" and worst in coarse:
        reason = "not_fresh"
    elif worst == "freshness":
        reason = "spoiled" if top == "spoiled" else "declining"
    else:
        reason = "overripe" if top == "overripe" else "unripe"
    return score, SCORE_REASON_HE[reason]


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
    coarse = {h for h in COARSE if h not in sup and f"{h}~coarse" in sup}
    r = _head(tax, "ripeness", probs.get("ripeness"), "ripeness" in sup, t["head_min_prob"])
    f = (_coarse_head(tax, "freshness", probs.get("freshness"), t["head_min_prob"]) if "freshness" in coarse
         else _head(tax, "freshness", probs.get("freshness"), "freshness" in sup, t["head_min_prob"]))
    s = (_coarse_head(tax, "visual_spoilage", probs.get("visual_spoilage"), t["head_min_prob"]) if "visual_spoilage" in coarse
         else _head(tax, "visual_spoilage", probs.get("visual_spoilage"), "visual_spoilage" in sup, t["head_min_prob"]))

    meta = tax.produce_meta[name]
    res = ScanResult("ok", produce=name, produce_he=meta["he"], emoji=meta["emoji"],
                     produce_confidence=conf, ripeness=r, freshness=f, visual_spoilage=s)

    p_spoiled = 0.0  # only fully graded heads may trigger "discard"
    if f.available and "freshness" not in coarse and probs.get("freshness") is not None:
        p_spoiled = float(probs["freshness"][tax.heads["freshness"].index("spoiled")])
    if s.available and "visual_spoilage" not in coarse and probs.get("visual_spoilage") is not None:
        p_spoiled = max(p_spoiled, float(probs["visual_spoilage"][tax.heads["visual_spoilage"].index("severe")]))

    if p_spoiled >= t["spoiled_alert_prob"]:
        rec = "discard"
        res.explanation_he.append("זוהו סימנים חזותיים שמתאימים בדרך כלל לקלקול או ריקבון.")
        res.explanation_he.append(MOULD_RULE_HE)
    elif (f.available and f.label == "not_fresh") or (s.available and s.label == "defects"):
        rec = "check_defects"
        res.explanation_he.append("המראה מתאים לפרי עם פגמים, מכות או סימני ריקבון.")
        res.explanation_he.append(MOULD_RULE_HE)
    elif r.available and r.label not in (None, tax.unknown):
        rec = {"unripe": "wait", "partially_ripe": "wait_little", "ripe": "eat_now", "overripe": "overripe"}[r.label]
        res.explanation_he.append(f"הצבע והמראה החיצוני תואמים בדרך כלל ל{meta['he']} במצב '{r.label_he}'.")
        if meta.get("ripeness_note_he"):  # cultivar-dependent colour cue (docs/research/produce-science.md)
            res.explanation_he.append(meta["ripeness_note_he"])
    elif f.available and f.label == "fresh":
        rec = "eat_now"
        res.explanation_he.append("המראה החיצוני תואם בדרך כלל לפרי טרי. לא זוהו סימני ריקבון משמעותיים.")
    elif f.available and f.label == "declining":
        rec = "eat_soon"
        res.explanation_he.append("נראים סימנים ראשונים לירידה בטריות.")
    elif s.available and s.label == "none":
        rec = "eat_now"
        res.explanation_he.append("לא נראים פגמים או סימני ריקבון בקליפה.")
    else:
        rec = "inspect"
        res.explanation_he.append("למודל אין מספיק ביטחון או נתוני אימון כדי להעריך בשילות/טריות לסוג זה.")
    res.recommendation, res.recommendation_he = rec, REC_HE[rec]
    res.score, res.score_reason_he = quality_score(
        tax, probs, {"freshness": f.available, "visual_spoilage": s.available, "ripeness": r.available}, rec == "discard",
        coarse)
    if rec == "inspect" and res.score is not None:  # heads available but not confident: no number
        res.score, res.score_reason_he = None, LOW_CONF_SCORE_HE
    return res


def supported_heads_from_manifest(rows: list[dict], min_exact: int = 200, min_per_class: int = 50,
                                  min_classes: int = 2,
                                  ripeness_visual: dict[str, str] | None = None) -> dict[str, list[str]]:
    """A head is 'supported' for a produce type only if the TRAIN split has >= `min_exact`
    exactly-labelled examples AND >= `min_classes` distinct classes with >= `min_per_class`
    each (a head trained on one class only - e.g. Fruits-360 'Avocado ripe' - is not a
    ripeness model). Written into the model bundle and enforced by `decide`.

    `ripeness_visual` (label_mapping produce.*.ripeness_visual, docs/research/produce-science.md)
    vetoes ripeness where the skin carries no ripeness evidence ('weak', 'not_applicable'), and for
    'cultivar_dependent' produce counts only rows that name their cultivar (row["cultivar"])."""
    from collections import Counter
    c: Counter = Counter()
    grp: Counter = Counter()  # rows labelled with exactly a coarse "bad" group, per (produce, head)
    for r in rows:
        if r["split"] != "train" or not isinstance(r["labels"]["produce"], str):
            continue
        prod = r["labels"]["produce"]
        for h in ("ripeness", "freshness", "visual_spoilage"):
            if h == "ripeness" and ripeness_visual is not None:
                rv = ripeness_visual.get(prod, "not_applicable")
                if rv in ("weak", "not_applicable") or (rv == "cultivar_dependent" and not r.get("cultivar")):
                    continue
            v = r["labels"][h]
            if isinstance(v, str) and v != "unknown":
                c[(r["labels"]["produce"], h, v)] += 1
            elif isinstance(v, list) and h in COARSE and sorted(v) == sorted(COARSE[h][1]):
                grp[(prod, h)] += 1
    per: dict[tuple[str, str], list[int]] = {}
    for (prod, h, _), n in c.items():
        per.setdefault((prod, h), []).append(n)
    out: dict[str, list[str]] = {}
    for (prod, h), ns in per.items():
        if sum(ns) >= min_exact and sum(n >= min_per_class for n in ns) >= min_classes:
            out.setdefault(prod, []).append(h)
    # Coarse support: enough exact "good" AND enough "bad" (exact bad classes or the bad group).
    for (prod, h) in {(p, h) for (p, h, _) in c} | set(grp):
        if h not in COARSE or h in out.get(prod, []):
            continue
        good_label, bad_labels, _ = COARSE[h]
        n_good = c[(prod, h, good_label)]
        n_bad = grp[(prod, h)] + sum(c[(prod, h, b)] for b in bad_labels)
        if n_good >= min_per_class and n_bad >= min_per_class and n_good + n_bad >= min_exact:
            out.setdefault(prod, []).append(f"{h}~coarse")
    return {k: sorted(v) for k, v in out.items()}
