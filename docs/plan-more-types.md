# Plan: every common fruit and vegetable in an Israeli supermarket (2026-09-30)

## Where we are
27 fixed types (22 fruits + tomato, cucumber, pepper, zucchini, potato). Anything else -> "not supported".
Accurate 1-10 score (verified on held-out photos) for 10 types; "general score" (fresh / not fresh, less accurate) for the rest.

## Feasibility check (real Open Images photos, names only, no training on them)
Zero-shot over 55 types: pineapple 1.00, broccoli 0.94, pumpkin 0.94, carrot 0.88, cabbage 0.76, radish 0.76 (n = 80 each).
Existing types: 0.849 -> 0.828 when the label set doubles. Training on real photos (as in v0.10: 0.82 -> 0.88) should recover it.
Note: v0.10 was trained with these vegetables as "other", so they must become real classes, not rows added on top.

## Scope: three levels per type
| level | what the user gets | needs |
|---|---|---|
| 1. identify | name + care tips + "general score" | name prompts (+ real photos when available) |
| 2. general freshness | fresh vs not fresh (zero-shot, leave-one-fruit-out 0.87) | nothing extra |
| 3. accurate score / ripeness | 1-10 + ripeness stage | labelled photos of that type, passes the per-type gate |

## Types to add (levels 1-2 first)
Vegetables: carrot, onion, garlic, eggplant, lettuce, cabbage, cauliflower, broccoli, radish, beet, sweet potato,
pumpkin, corn, kohlrabi, celery, green beans, mushroom, leafy greens, leek, chili pepper.
Fruits: pineapple, fig, date, cherry, apricot, papaya, lychee, coconut, blueberry, raspberry, prickly pear (sabra),
pomelo, loquat, quince.

## Steps
1. Taxonomy + Hebrew names + care/touch tips per new type (produce_care.json, both copies); label_mapping entries.
2. Real-photo data: Open Images crops already on disk for carrot, broccoli, cabbage, radish, pumpkin, pineapple, fig
   (eval ids kept out); fetch more Open Images classes that exist for the other new types.
3. Retrain the produce head with the new classes (same selection rules: real-cal + val) and extend the real-photo eval
   set with the new classes (cal/test by image id), so every added type has a measured accuracy.
4. Decision code: nothing structural (list-driven); regenerate the Python/TS parity fixtures; app wording
   ("סרוק פרי או ירק"), info-page lists.
5. Gate: a type is shown by name only if its real-photo accuracy (test) >= 0.80 with n >= 30; otherwise it stays
   "not supported" until data arrives.
6. Level 3 per type as labelled data arrives (user photo donations, open datasets with rot labels).

## Held back: pumpkin (real-photo test n = 26 < 30)
Re-enable: set `is_negative_class: false` in data/label_mapping.json and restore this care line in both produce_care.json copies:
```
    "pumpkin":     {"fridge": "no",             "chill_below_c": 10,   "ethylene": {"producer": false, "sensitive": true},  "tip_he": "דלעת שלמה – במקום קריר ויבש מחוץ למקרר, נשמרת חודשים. פרוסה – במקרר, עטופה, כמה ימים.", "touch_he": "קליפה קשה בלי כתמים רכים, ועוקץ יבש. כתמים רכים או עובש – לא לקנות."},
```
