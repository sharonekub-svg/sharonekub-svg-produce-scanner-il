# Product spec — סורק פירות וירקות

## Users & promise

Israeli consumers who want a quick, honest **visual** read on a fruit/vegetable: what it is, how ripe it looks, whether it shows visible spoilage, and what to do. Not a food-safety device.

## Flow

`פתיחה → מצלמה → סריקה → תוצאה` — no dashboard, no login for core use.

1. **Camera** (full screen, RTL): one primary button **"סרוק פרי"**, hint "צלמו פרי או ירק אחד, מקרוב ובאור טוב". The layout and its rationale are in [ux-principles.md](ux-principles.md), based on [competitor-ux-research.md](competitor-ux-research.md).
2. **Scan**: on-device, target < 1 s total.
3. **Result** card, one of four states (from `ScanResult.status`):

| status | Screen |
|---|---|
| `ok` | Emoji + name, ripeness chip, freshness chip, recommendation sentence, confidence, expandable "מה זיהינו?" / "מה גרם למודל לחשוב כך?", disclaimer |
| `unsure` | "לא הצלחתי לזהות את הפרי בוודאות. נסה לצלם אותו מקרוב ובתאורה טובה יותר." + retake |
| `retake` | Specific reason (dark / blurry / overexposed / several items) + retake |
| `not_produce` | "לא זיהיתי פרי או ירק שאני מכיר בתמונה." |

Example `ok`:

```
🍌 בננה                         ביטחון בזיהוי: 91%
בשילות:  🟢 בשלה
טריות:   🟢 טרי
המלצה:   כדאי לאכול עכשיו
▸ מה גרם למודל לחשוב כך?
   הצבע והמראה החיצוני תואמים בדרך כלל לבננה במצב 'בשל'. לא זוהו סימני ריקבון משמעותיים.
ⓘ חשוב: זו הערכה חזותית בלבד ואינה מבטיחה שהמזון בטוח לאכילה.
```

## Wording rules

- Always "נראה", "תואם בדרך כלל" — never "בטוח", "תקין לאכילה".
- A head without validated support shows "לא זמין עדיין לסוג זה" — never a guess.
- **No 0–100 freshness score in MVP.** A number like "92/100" implies measured precision we do not have. Show a category + calibrated confidence. Revisit only if a score is validated against graded real-world data.
- "Confidence" = calibrated probability of the produce head, rounded to 5%. Show it for produce; for other heads show only the category unless calibrated on the real-world set.
- Disclaimer visible on every result, not hidden behind a tap.
- Spoilage signal overrides ripeness (conservative: alert at P(spoiled) ≥ 0.40).

## Colour/label mapping

| Ripeness | Chip | Freshness | Chip |
|---|---|---|---|
| לא בשל | 🟡 | טרי | 🟢 |
| כמעט בשל | 🟡 | פחות טרי | 🟠 |
| בשל | 🟢 | מקולקל | 🔴 |
| בשל מדי | 🟠 | לא ידוע | ⚪ |

Colour is never the only carrier of meaning (text always present; accessibility).

## MVP scope (proposed)

- Produce ID: the 22 types in `label_mapping.json` + "other"; release only types that pass their recall gate.
- Ripeness: banana, avocado (Hass + green-skinned once collected), tomato, strawberry — **only** after own-collection data passes gates.
- Freshness/spoilage: apple, banana, orange, pomegranate, tomato, cucumber first.
- iOS only, Hebrew only, on-device, offline-capable.
- Out of MVP: Android, multi-fruit scenes (abstain instead), history/sync, accounts, English.
