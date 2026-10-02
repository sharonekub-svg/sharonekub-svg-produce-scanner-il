# דירוג איכות פירות – אבחון, מחקר ותכנון (2.10.2026)

מסמך זה נכתב **לפני** שינוי הקוד. כל מספר כאן נמדד בפרויקט (סקריפטים בסוף) או מצוטט ממקור עם קישור. איפה שאין evidence – כתוב במפורש.

## 1. אבחון המערכת הנוכחית

**איך הציון מחושב היום** (`ml/inference/decision.py`, `app/src/model/decision.ts`): SigLIP2 → embedding → ראשים לינאריים
`freshness` (fresh/declining/spoiled), `visual_spoilage` (none/mild/severe, ברוב הפירות במצב "coarse": טוב/לא טוב) ו-`ripeness`
(unripe/partially_ripe/ripe/overripe). לכל ראש מחושב "ניקוד צפוי" (למשל fresh=10, spoiled=1), הציון = הרכיב הגרוע מבין הראשים.

**מה מדדנו** (`scripts/eval_quality_scores.py`, הסוג נכפה לסוג האמיתי כדי למדוד רק איכות; test = חצי שלא שימש לשום בחירה):

| סוג | טובים/פגומים (test) | פגום שקיבל ≥8 | טוב שקיבל ≤4 | AUROC | ECE |
|---|---|---|---|---|---|
| תפוח | 199/230 | 3.0% | 3.5% | 0.992 | 0.011 |
| בננה | 189/124 | 0% | 2.1% | 0.996 | 0.013 |
| רימון | 518/96 | 6.2% | 7.1% | 0.971 | 0.044 |
| תפוז | 211/194 | 3.6% | 3.3% | 0.991 | 0.030 |
| תות | 122/115 | 0% | 8.2% | 0.998 | 0.051 |
| גויאבה | 170/47 | 6.4% | 5.3% | 0.969 | 0.046 |
| **לימון** | 197/147 | 0.7% | **62.9%** | 0.733 | **0.316** |
| הכול | 2464/2186 | 1.8% | 10.1% | 0.950 | – |

ממצאים:

1. **על תמונות מהסוג שעליו אומן – המודל מפריד טוב** (AUROC 0.97–0.99). לכן "ציונים גבוהים מדי" לא נובעים מנוסחה שבורה, אלא מ:
2. **הציון בימודלי – כמעט אין אמצע.** בבננה (val): טובים קיבלו 9–10, פגומים 1–2; ציונים 5–7 כמעט לא קיימים (2% מהתמונות). הסיבה: **ה-labels בינאריים.** בכל ה-datasets אין אף תמונה שתויגה "declining" לבד או "mild" לבד – רק `fresh` מול `declining|spoiled` ו-`none` מול `mild|severe`. המודל לא יכול ללמוד "פגם קטן" או "תחילת ריקבון" כי אין לו דוגמה כזו.
3. **Domain shift לתמונות ביתיות.** על תמונות אמיתיות (Open Images, 560 תמונות של סוגים עם ראש מאומת) הביטחון יורד: 19% מההחלטות בביטחון <0.8, לעומת 10% על תמונות המעבדה. רוב תמונות הפגומים ב-datasets הן ריקבון בולט על רקע לבן/סטודיו (ראו `capture_conditions` ב-`data/dataset_registry.csv`).
4. **Shortcut של רקע – הוכח בלימון.** כל הלימונים על רקע שחור (`lemon_softwaremill`) שקיבלו label של freshness הם "spoiled" (לטובים שם יש רק `visual_spoilage=none`), וכל הלימונים ה"טריים" באים מ-`lemon_varieties` על רקע לבן. התוצאה: 98% מהלימונים התקינים על רקע שחור מקבלים P(fresh)≈0. בדיקה ויזואלית: הלימונים תקינים (שריטות קלות לכל היותר). זה בדיוק סוג ההטיה שגורם לטעויות בעולם האמיתי.
5. **מקורות חד-צדדיים / מוטים** (train, לפי סוג ו-dataset): בננה – `fruitnet_indian` 835 טובות / 0 פגומות; רימון – `fruitnet_indian` 3,988 טובים / 872 פגומים (82% טובים); תות – `strawberry_avocado_ripening` 90/2. מקור שתורם רק דוגמאות טובות מלמד את המודל "סגנון הצילום הזה = טוב".
6. **בננה בשלה מדי כמעט חסרה:** 34 תמונות `overripe` ב-train מול 830 `ripe` (+20 עמומות). בננה מנומרת בכתמים שחורים נופלת לכן ל-"ripe" → 10/10. זה מסביר ישירות את המקרה שדיווחת.
7. **Calibration של ההסתברויות סביר** (ECE 1–5%) חוץ מלימון. כיול לפי סוג (טמפרטורה לכל סוג, הותאם על val) **לא שיפר באופן עקבי** על test (תפוח 0.014→0.014, תפוז 0.028→0.045, רימון 0.049→0.062) – לכן לא נוסיף אותו.
8. **הימנעות עובדת:** אם לא נותנים ציון כשהביטחון במצב <0.9 – שיעור הטעות יורד (רימון 6.4%→1.0% עם כיסוי 78%; תפוח 3.5%→0.5% עם כיסוי 89%).

## 2. מחקרים ומקורות

**איכות פירות ממחשב-ראייה**
- Cubero et al. 2011, *Advances in Machine Vision Applications for Automatic Inspection and Quality Evaluation of Fruits and Vegetables*, Food Bioprocess Technol 4:487–504 – [Springer](https://link.springer.com/article/10.1007/s11947-010-0411-8). סקירה: פגמים בולטים נראים ב-RGB; פגמים מוקדמים דורשים לעיתים ספקטרום אחר.
- Mendoza & Aguilera 2004, *Application of Image Analysis for Classification of Ripening Bananas*, J Food Sci – [Wiley](https://ift.onlinelibrary.wiley.com/doi/pdf/10.1111/j.1365-2621.2004.tb09932.x). 7 שלבי הבשלה מ-L\*a\*b\*, **אחוז שטח כתמים חומים**, מספר כתמים לסמ"ר וטקסטורה; 98% דיוק. → בבננה, כתמים חומים הם סימן **בשלות** (לא בהכרח קלקול) עד שלב מסוים.
- סקירה: *Non-Destructive Banana Ripeness Detection Using Shallow and Deep Learning* (Sensors 2023) – [MDPI](https://www.mdpi.com/1424-8220/23/2/738).
- Hass אבוקדו: *Skin colour and pigment changes during ripening of 'Hass' avocado fruit* – [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0925521403001893). צבע הקליפה ירוק→סגול→שחור, אבל **צבע ורכות לא תמיד מסונכרנים** (פרי כהה יכול להיות לא בשל) → לבשלות אבוקדו מתמונה יש תקרת דיוק.
- חבלות בתפוח: מחקרים מראים שחבלות מוקדמות **כמעט לא נראות ב-RGB** ומזוהות ב-NIR/היפרספקטרלי – למשל [Postharvest Biol. Technol. 2024](https://www.sciencedirect.com/science/article/pii/S0925521424005271), [PMC9465011](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9465011/).
- ריקבון Penicillium בהדרים: זיהוי מוקדם נעשה ידנית תחת UV או בהיפרספקטרלי – Gómez-Sanchis et al. – [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0957417411010359); סקירה 2023 – [Springer](https://link.springer.com/article/10.1007/s11947-023-03005-4).
- עובש אפור (Botrytis) בתות: כתמים חומים עם "פרווה" אפורה; חומרה נמדדה בסגמנטציה – [Springer 2022](https://link.springer.com/article/10.1007/s41348-022-00578-8).

**מסקנה חשובה מהספרות:** "התחלה של ריקבון" ו"חבלה טרייה" הם לעיתים **לא נראים במצלמת טלפון**. אפליקציה שמצהירה שהיא מזהה אותם בביטחון – מטעה. מה שאפשר: פגמים נראים (כתמים, עובש גלוי, קמטים, סדקים) + בשלות לפי צבע.

**סטנדרטים להגדרת "פגם קטן" מול "משמעותי"** (במקום להמציא מספרים):
- UNECE FFV-50 תפוחים – Class I מתיר חבלה קלה עד **1 סמ"ר** לא מוכתמת ופגם מוארך עד 2 ס"מ – [UNECE](https://unece.org/fileadmin/DAM/trade/agr/standard/standard/fresh/FFV-Std/English/50_Apples.pdf).
- Codex CXS 205 בננות – Class I מתיר פגמי קליפה שטחיים עד **2 סמ"ר** שלא פוגעים בבשר – [Codex](https://unece.org/fileadmin/DAM/trade/agr/meetings/ge.01/document/Codex%20bananas%20E.pdf).
→ אלה מגדירים רובריקת תיוג (Extra / Class I / Class II / לא שיווקי) שאפשר לתייג לפיה תמונות, ולא מספרים שרירותיים.

**Calibration, אי-ודאות ודאטה לא מאוזן**
- Guo et al. 2017, *On Calibration of Modern Neural Networks* (temperature scaling) – [PMLR](https://proceedings.mlr.press/v70/guo17a/guo17a.pdf).
- Niculescu-Mizil & Caruana 2005, *Predicting Good Probabilities with Supervised Learning* (Platt מול Isotonic) – [Semantic Scholar](https://www.semanticscholar.org/paper/Predicting-good-probabilities-with-supervised-Niculescu-Mizil-Caruana/eae3948747c9d051314c1f5851957b833aa83eca).
- Geifman & El-Yaniv 2017, *Selective Classification for Deep Neural Networks* (risk–coverage, הימנעות) – [Semantic Scholar](https://www.semanticscholar.org/paper/Selective-Classification-for-Deep-Neural-Networks-Geifman-El-Yaniv/2ed7cc027367295b1a7d7cd49406acfa5c580138).
- Cao, Mirjalili & Raschka 2020, *Rank Consistent Ordinal Regression (CORAL)* – לשלבי בשלות סדורים – [GitHub](https://github.com/Raschka-research-group/coral-cnn).
- Shrivastava et al. 2016, OHEM (hard example mining) – [CVF](https://openaccess.thecvf.com/content_cvpr_2016/html/Shrivastava_Training_Region-Based_Object_CVPR_2016_paper.html).
- Cui et al. 2019, *Class-Balanced Loss* – [CVF](https://openaccess.thecvf.com/content_CVPR_2019/html/Cui_Class-Balanced_Loss_Based_on_Effective_Number_of_Samples_CVPR_2019_paper.html).

**Datasets מועמדים להשלמת החוסרים** (רישיון נבדק בדף המקור; **כל אחד דורש אישור שלך ב-`data/license_signoffs.json` לפני שימוש**):
- BananaID (אינדונזיה) – Unripe 408 / Half-ripe 488 / Ripe 616 / **Overripe 448**, CC BY 4.0 – [Mendeley](https://data.mendeley.com/datasets/h6n5srjjyw/1).
- Banana Prata Catarina – 1,000 תמונות ב-**8 שלבי הבשלה**, CC BY 4.0 – [Mendeley](https://data.mendeley.com/datasets/7vb4djkbrc/1).
- BananaImageBD – Green/Semi-ripe/Ripe/Overripe, CC BY 4.0 – [Mendeley](https://data.mendeley.com/datasets/ptfscwtnyz/2).
- Halabja Pomegranate – 2,178 תמונות מקוריות **מהמטע** (Healthy/Sunburn/Colletotrichum/Ectomyelois), CC BY 4.0 – [Zenodo](https://zenodo.org/records/15856012). הערה: פירות על העץ, לא על שיש.
- apple-defects (CIDIS) – פגמי תפוח עם סימון מיקום – [GitHub](https://github.com/cidis-vision/apple-defects). **רישיון לא נבדק עדיין.**

## 3. מאפיינים ויזואליים לפי פרי – ומה נתמך

| פרי | בשלות (נראה ב-RGB) | פגם/קלקול נראה | לא נראה / אין evidence | מה יש לנו בנתונים |
|---|---|---|---|---|
| בננה | צבע ירוק→צהוב, אחוז שטח כתמים חומים (Mendoza 2004) | ריקבון שחור רך, עובש בקצוות, סדקים | כתמי סוכר ≠ קלקול – ההבחנה דורשת labels מדורגים | ripe/unripe טוב; **overripe חסר** |
| תפוח | צבע (תלוי זן – לא אמין לבשלות) | ריקבון, עובש, קמטים, חבלה **מוכתמת** | חבלה טרייה (NIR) | טוב/רע בלבד |
| הדרים (תפוז/לימון/ליים) | צבע לא מעיד על בשלות (citrus degreening) | עובש ירוק/כחול גלוי, כתמים רכים | Penicillium מוקדם (UV) | טוב/רע; **shortcut רקע בלימון** |
| תות | צבע אדום, אחוז שטח לבן/ירוק | Botrytis (חום + פרווה אפורה), ריכוך | – | טוב/רע; בשלות 90 תמונות בלבד |
| רימון | – (צבע לפי זן) | ריקבון, סדקים, sunburn | ריקבון פנימי (Heart rot) | טוב/רע, מוטה לטוב (82%) |
| אבוקדו Hass | ירוק→סגול→שחור | עובש, שקיעות | רכות אמיתית (צבע ורכות לא מסונכרנים) | 4 שלבים, דיוק 0.71 |
| ענבים | – | עובש, התקמטות, השחמה | – | טוב/רע |

## 4. ארכיטקטורה מומלצת

```
image
 → quality gate (טשטוש/חושך/חשיפה – קיים)            → retake
 → identification (קיים, עם "לא בטוח")               → בחירה ידנית
 → embedding (SigLIP2, קיים)
 → condition head  P(good) – בינארי, מאומן מחדש בלי shortcuts (מקורות מאוזנים)
 → ripeness head   ordinal, רק לסוגים עם labels (בננה, אבוקדו; מנגו – וטו)
 → uncertainty     ביטחון = max(P,1−P) לכל ראש; סף הימנעות לכל סוג מ-val (risk ≤ יעד)
 → calibrated scoring (פרופיל לכל פרי) → Overall + Ripeness + Condition + Confidence
 → explanation     רק מתוך ראשים שבאמת קיימים ומאומתים
```

עקרונות:
- **Condition שולט:** `Overall ≤ Condition`. בשלות טובה לא מעלה פרי פגום.
- **ביטחון נמוך → ציון שמרני + בקשה לתמונה טובה יותר** (selective classification), לא "ניחוש בביטחון".
- **"Detected issues"** יכולים להיות רק דברים שיש להם ראש מאומת: "סימני קלקול נראים" (condition), "בשל מדי"/"לא בשל" (ripeness), "תמונה כהה/מטושטשת" (quality gate). **לא** "כתם חום קטן" או "התייבשות מוקדמת" – אין לנו labels לזה, וטענה כזו תהיה מומצאת.
- מה שאין לנו כלי לזהות (כמה פירות בתמונה, פרי מוסתר) – לא נטען שזיהינו. אפשר להוסיף בעתיד detector.

## 5. נוסחת הציון

```
Condition = 100 · P(good)                       # הסתברות מכוילת (temperature scaling, global)
Ripeness  = Σ P(stage) · U_fruit(stage)          # U = תועלת "לאכול עכשיו", לכל פרי (ראו למטה)
Overall   = min(Condition, Ripeness)             # פגם גובר על בשלות
אם conf(Condition) < τ_fruit:  Overall = min(Overall, 60) + "צלמו שוב"   # τ מ-val, risk ≤ 2%
```

למה זה עונה על הדרישות:
- **95+ נדיר מעצם ההגדרה:** Condition ≥ 95 דורש P(good) ≥ 0.95 *מכויל*, כלומר המודל צודק לפחות ב-95% מהמקרים בהם הוא נותן את זה – לא "חושב שזה נראה טוב".
- **אי-ודאות לא הופכת לציון גבוה:** P(good)=0.6 → 60, ובנוסף נכנס לכלל ההימנעות.
- **פגם משמעותי מוריד לא-לינארית** דרך ה-min והסתברות קלקול גבוהה. *פגם קוסמטי קטן מול משמעותי* – **אי אפשר להבחין היום** (אין labels מדורגים); זה מחכה לנתוני רובריקה (סעיף 7).
- **U_fruit** הוא החלטת מוצר (מה "מוכן לאכילה עכשיו"), לא נתון שנלמד; לכן הוא קבוע מתועד לכל פרי ולא מוסתר בתוך מודל.

## 6. Calibration – מה מתאים ולמה

- **Temperature scaling גלובלי (קיים)** – מספיק לראשים כרגע: ECE 1–5% על test. כיול לפי סוג נבדק ולא שיפר (סעיף 1.7).
- **Isotonic regression** – מתאים כשיש הרבה נתונים לכל סוג (Niculescu-Mizil & Caruana: Platt עדיף במעט נתונים, Isotonic נוטה ל-overfit במעט נתונים). יתאים **למיפוי הציון לרובריקה האנושית** כשיהיו מאות תמונות מתויגות לכל סוג.
- **Platt / logistic mapping** – לשלב ביניים (100–300 תמונות מתויגות לסוג).
- **Confidence-aware scoring** – כן, עכשיו: הימנעות לפי ביטחון (סעיף 1.8 – נמדד).
- **משמעות 50/65/75/85/95:** לא נגדיר אותם בעצמנו. מתייגים סט תמונות ברובריקה מבוססת UNECE/Codex (Extra / Class I / Class II / לא לשיווק / לא לאכילה) ומודדים את ההתפלגות של P(good) בכל דרגה; את המיפוי מאמנים ב-isotonic על val ובודקים על test.

## 7. אסטרטגיית נתונים

1. **תיקון shortcuts (אפשרי עכשיו, בלי נתונים חדשים):** ראש condition אחד שמאחד freshness+spoilage (כך הלימונים על רקע שחור מופיעים בשני ה-labels), **משקל מאוזן לכל (סוג, dataset, label)** כך שאף מקור לא "מלמד" את ה-label, וסינון מקורות חד-צדדיים. מדד ההצלחה: **leave-one-dataset-out** – אימון בלי dataset אחד ובדיקה עליו (הדמיה של מקור תמונות שלא ראינו, כמו תמונה ביתית).
2. **Overripe בננה + שלבים מדורגים:** BananaID, Prata Catarina (8 שלבים) – אחרי אישור רישיון שלך.
3. **פגמים קטנים/מוקדמים בתמונות ביתיות:** אין dataset ציבורי טוב. המקור: **שיתוף תמונות מהאפליקציה** עם הדירוג "איך היה הניתוח?" (נבנה היום) + תיוג ברובריקה. Hard-negative mining: התמונות שקיבלו "גרוע" נכנסות לתור תיוג ראשון (OHEM ברמת הדאטה).
4. **Augmentation:** שינויי תאורה/איזון לבן, רקעים משתנים (הדבקת הפרי על רקעים שונים מבטלת shortcut רקע), טשטוש קל, crop חלקי; **לא** augmentation שמייצר "ריקבון" מלאכותי (ייצור labels שקריים).
5. **Sampling:** class-balanced (Cui 2019) ברמת (סוג, label), ובנוסף איזון לפי מקור.

## 8. תוכנית הערכה

`scripts/eval_quality_scores.py` (נוסף) מודד לכל סוג ו-split: התפלגות ציונים לפי אמת, false-high (פגום ≥8), false-low (טוב ≤4), AUROC, ECE, confusion matrix לבשלות, כיסוי. בנוסף:
- **leave-one-dataset-out** לראש ה-condition (עמידות לשינוי מקור).
- **risk–coverage** לכלל ההימנעות.
- **MAE מול רובריקה אנושית** – ברגע שיהיה סט מתויג (לא ניתן היום: אין ציוני אמת רציפים, ו-MAE מול labels בינאריים הוא מספר מומצא).
- **סט test נפרד:** חצי ה-test הקיים (חלוקה לפי קבוצות צילום) + סט "ביתי" עתידי שלא נוגעים בו לאימון.
- **כלל שחרור:** גרסה חדשה עולה רק אם על test: AUROC לא יורד, false-high לא עולה, ושיפור ב-leave-one-dataset-out.

## 9. מה יושם (v0.13, 2.10.2026) – ותוצאות

**ראש condition חדש** (`scripts/train_condition_head.py`): label בינארי אחד מאוחד (fresh|none → טוב; declining|spoiled|mild|severe → פגום), רגרסיה לוגיסטית על embeddings של SigLIP2 + bias לכל סוג, משקל שווה לטוב/פגום בכל (סוג, dataset), מקורות חד-צדדיים מושמטים. L2 נבחר על val. Temperature גלובלי 0.727 על val. 9 סוגים: תפוח, בננה, ענבים, גויאבה, לימון, ליים, תפוז, רימון, תות.

**ניקוד** (`ml/inference/decision.py::_decide_condition` = `app/src/model/decision.ts::assessCondition`, parity על 2,000 מקרים):
```
Condition = 100 · min(P(good), 0.858)       # 0.858 = P(טוב | p≥0.95) על val ממקור שהמודל לא ראה
Ripeness  = 10 · Σ P(stage)·points          # points: unripe 5, partially 8, ripe 10, overripe 6 (מדיניות קיימת)
Overall   = min(Condition, Ripeness)
conf(Condition) < τ_type  →  Overall ≤ 60, "המצב לא ברור – צלמו שוב", issues: "המצב לא ברור מהתמונה"
```
τ לכל סוג נבחר על val כך שהשגיאה מעל הסף ≤ 2% (תפוח 0.91, תפוז 0.87, לימון 0.95, רימון 0.67, תות 0.72 …).
התצוגה: ציון כולל /100 + "בשלות · מצב · ביטחון" בקפיצות של 5 (אין דיוק מזויף), ו"מה זוהה" רק מראשים מאומתים.

**תוצאות על test** (`docs/results/quality_eval_current_test.json` מול `quality_eval_v013_test.json`):

| | לפני (v0.12) | אחרי (v0.13) |
|---|---|---|
| פגום שקיבל ≥8/10 (≥75/100) | 1.8% | **1.0%** |
| טוב שקיבל ≤4/10 | 10.1% | **2.0%** |
| AUROC ציון מול טוב/פגום | 0.950 | **0.987** |
| לימון – טוב שקיבל ≤4 | 62.9% | **9.1%** |
| רימון – פגום שקיבל ≥8 | 6.2% | **1.0%** |
| תפוח / תפוז – פגום ≥8 | 3.0% / 3.6% | 2.2% / 1.5% |

**על תמונות יומיומיות** (Open Images, 560, בלי labels איכות – רק התפלגות): ≥8: 61%→62%, 5–7: 13%→23%, ≤4: 26%→16%; **18%** מקבלים "לא ברור" (ציון שמרני + בקשה לצילום) במקום ניחוש בטוח; 95+ : 0%.

**מה נבדק ונדחה (עם נתונים):**
- כיול temperature לכל סוג – לא שיפר על test.
- כיול על תחזיות leave-one-dataset-out (T=3.6) – הורס את הכיול בתוך הדומיין (ECE 0.027→0.250) ומשפר מעט מחוץ לו (0.206→0.187).
- "רשת ביטחון" zero-shot מעל הראשים הישנים – כמעט לא שינתה דבר.
- רצפה תחתונה (P(טוב | p≤0.05, מקור חדש) = 0.30): **לא הוחלה** בכוונה – עלות אסימטרית: לומר שפרי רקוב תקין גרוע יותר מלבקש לבדוק פרי תקין ביד.
- איזון מקורות לבד (מול אותו מודל בלי איזון): כמעט זהה בתוך הדומיין; ב-leave-one-dataset-out מוריד false-high (מצלמת טלפון 22.6%→15.4%, Mendeley 16%→8%) במחיר יותר false-low – נבחר בגלל העלות האסימטרית.

## 10. מה עדיין לא נפתר (בכנות)

- **פער הדומיין נשאר:** על מקור צילום שלא נראה, פרי פגום מקבל P≥0.8 ב-8–15% מהמקרים. רק תמונות ביתיות מתויגות יסגרו את זה.
- **אין חומרת פגם** (קטן/משמעותי) ואין "התחלת ריקבון" – אין labels כאלה. לכן המערכת לא מציגה אותם.
- **בננה בשלה מדי** – 34 דוגמאות; דורש BananaID / Prata Catarina (אישור רישיון שלך).
- **לימון** – גם אחרי התיקון, רק 33% מהתמונות עוברות את סף הביטחון (השאר: "לא ברור").
- **כמה פירות / פרי מוסתר** – אין detector; לא נטען שזוהה.
- **MAE מול ציון אנושי** – ימדד כשיהיה סט מתויג ברובריקה (סעיף 6).

## 11. v0.14 – תמונות יומיומיות ושלוש דרגות (2.10.2026)

**Datasets חדשים** (CC BY 4.0, נבדק ב-Mendeley API, hash תואם; רשומים ב-`data/dataset_registry.csv`, קרדיט ב-`credits.json`):
- **AgriFreshNET** ([42m5tb7yv9](https://data.mendeley.com/datasets/42m5tb7yv9/1)) – צילומי טלפון בשווקים ובבתים, Fresh / Semi-fresh / Rotten. בשימוש: בננה, מלפפון, תפוז, אננס, עגבנייה (8,850). הערה: ה-labels לפי ימים מהקטיף, לא בדיקה ויזואלית.
- **BananaID** ([h6n5srjjyw](https://data.mendeley.com/datasets/h6n5srjjyw/1)) – 1,960 בננות ב-4 שלבים (448 בשלות מדי).
- **BananaImageBD** ([ptfscwtnyz](https://data.mendeley.com/datasets/ptfscwtnyz/2)) – 820 בננות ב-4 שלבים.
- נבדקו ונדחו: banana-defect-segmentation (CC BY-NC), apple-defects CIDIS (אין רישיון), FruitQ (פריימים מיוטיוב).

**מה השתנה** (`scripts/train_quality_v3.py`, `scripts/add_quality_v3.py`; כל בחירה על val):
- 5 סוגים מדורגים (יש להם נתוני "בעיות קטנות"): `Condition = 100·p + 60·(1−p)(1−r) + 10·(1−p)·r`, p = P(טוב) מוגבל ל-0.744 (אמינות על מקור לא מוכר, val), r = P(ריקבון | לא טוב).
- שאר הסוגים נשארו על v0.13: ראש v3 היה גרוע יותר שם על val (רימון ρ 0.81→0.41, ענבים 0.78→0.63, גויאבה 0.90→0.75).
- ראש בשלות משותף חדש (T=1.12 על val).

**תוצאות על test (בננה, AgriFreshNET – תמונות שלא היו באימון):** טרייה 89–90, "בעיות קטנות" 60–67, רקובה 13–34.

| סוג | ממוצע ציון מצב: טוב / בעיות קטנות / רקוב (test) | רקוב שקיבל ≥75 |
|---|---|---|
| בננה | 98.7 / 60.4 / 24.6 (לפני: 83.7 / 22.3 / 10.1) | 2.3% |
| מלפפון (חדש) | 95.8 / 55.6 / 22.6 | 0% |
| תפוז | 92.9 / 62.6 / 31.1 (לפני: 83.4 / 71.3 / 9.7) | 4.0% |
| אננס (חדש) | 94.1 / 61.6 / 21.7 | 4.2% |
| עגבנייה (חדש) | 86.3 / 66.4 / 20.1 | 1.4% |

(הממוצעים לפני ה-ceiling; באפליקציה הציון המקסימלי לסוגים האלה ≈ 90.)
- **בשלות בננה (test):** BananaImageBD 31%→86%, BananaID 54%→71%; אבוקדו ללא שינוי (70.6%→71.0%).
- **End-to-end על test:** סט מקורי – פגום ≥8: 1.0%→0.6%, AUROC 0.988; סט יומיומי – פגום ≥8: 1.1%, טוב ≤4: 2.0%, AUROC 0.911.
- **כיסוי הביטחון (val):** בננה 93%, אננס 82%, מלפפון 76%, תפוז ועגבנייה 56% – השאר מקבלים "לא ברור, צלמו שוב".
- **מחיר:** בננה רקובה מקבלת ~25 במקום ~10, כי "כמה רקוב" מופרד פחות טוב מ"טוב/לא טוב" (AUROC 0.92–0.96).

**עדיין חסר:**
- זיהוי **מיקום** פגם קטן (מדבקה, כתם בודד, חבלה) – אין dataset מותר לשימוש מסחרי עם סימון פגמים. הדרך: תמונות שלכם + סימון.
- דרגות ביניים לשאר הסוגים (תפוח, רימון, ענבים, תות…) – אין נתונים מדורגים מותרים.
