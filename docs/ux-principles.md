# UX principles — סורק פירות וירקות

Derived from [competitor-ux-research.md](competitor-ux-research.md). Priority order: **1. scan speed · 2. clear result · 3. trust · 4. useful recommendation · 5. minimal friction.** When two principles conflict, the higher one wins.

## Principles

1. **The camera is the home screen.** The app opens straight into the viewfinder. There are no tabs, no dashboard and no feed. The only primary action is one large button labelled **"סרוק פרי"**, in the thumb zone at the bottom centre. The label stays centred in RTL, so it reads the same for right-handed and left-handed users.
2. **Two taps to an answer.** Open → "סרוק פרי" → result. Target: under 1.5 s from tap to result on device. There is no onboarding carousel. The only pre-camera screen is the one-time permission request, which explains in one sentence *why* we need the camera and that photos stay on the phone.
3. **Answer first.** The result screen's hero line is the *recommendation* (what to do), next to the produce name and emoji. Supporting facts (ripeness, freshness chips) come second. "Why" and "what else it could be" are collapsed. Nothing on the result needs scrolling to reach the answer.
4. **Honest uncertainty is a feature, not an error.** Low confidence produces a helpful retry, not a guess:
   - "לא בטוח — צלם מזווית נוספת" offers **one** extra capture, whose evidence is combined with the first.
   - Multi-angle capture is a *fallback*, never a toll (unlike FreshScanAI's default 3-angle flow).
   - Bad photos get a specific fix ("חשוך מדי", "מטושטש").
   - Unsupported heads say "לא זמין עדיין לסוג זה". We never display a guess we can't stand behind.
5. **Confidence in words, number second.** "ביטחון גבוה / בינוני" plus the calibrated percentage, rounded to 5%. We never show a 0–100 "freshness score" or a "N days left" estimate we haven't validated.
6. **Visual, not safety.** One short disclaimer is always visible, never a modal: "הערכה חזותית בלבד". We never write "בטוח לאכילה".
7. **End with one useful action.** Every `ok` result ends with a recommendation. Where the model can't assess ripeness or freshness yet, it ends with **general storage guidance for that produce**, visibly labelled as general advice rather than a result about *this* fruit. This fills the gap without overclaiming.
8. **Trust signals in plain sight.** "מעובד במכשיר · בלי הרשמה · בלי פרסומות" appears on the permission screen and in the About/credits area. There are no accounts and no ads.
9. **No Frankenstein features.** Not in v1: recipes, calories, pantry, chat, market prices, PLU scanning, social features, scan history.
   - **History is deliberately out.** The job is "decide now". Storing photos adds privacy cost for little value, so it's reconsidered only if beta feedback asks for it.
10. **Monetization never interrupts the core journey** (if and when introduced).
    - No weekly plans.
    - No paywall before a result, and never a paywall on the core answer.
    - Cancelling must be one tap away. Competitor reviews show billing is the category's top trust-killer.
11. **Hebrew-first, RTL-native.**
    - Layout is mirrored by the platform (`forceRTL`).
    - All copy is short and spoken-register Hebrew ("כדאי לאכול היום", not "מומלץ לצרוך").
    - The produce emoji carries recognition before text.
    - Numbers and percentages render correctly inside RTL text.
12. **Calm motion.**
    - Only three animations: the shutter press, a short "בודק…" state over the frozen frame (no spinner-only screen), and the result sheet sliding up.
    - Nothing loops and nothing is decorative.
    - Everything respects Reduce Motion.
13. **Accessible by default.**
    - Colour is never the only signal: chips carry text.
    - Tap targets are at least 44 pt.
    - Every control has a VoiceOver label.
    - Contrast is AA or better.
    - Dynamic Type is supported (layouts wrap rather than truncate).

## Resulting UI architecture (v1)

```
[Permission screen: once]
          │
          ▼
┌───────────── Camera (home) ─────────────┐
│  hint: "צלמו פרי אחד, מקרוב ובאור טוב"  │
│  framing square                          │
│  [ סרוק פרי ]  ← single primary action   │
│  "הערכה חזותית · מעובד במכשיר"          │
└──────────────────────────────────────────┘
          │ tap
          ▼
 frozen frame + "בודק…" (~1 s, no separate screen)
          │
          ▼
┌───────────── Result ────────────────────┐
│ 🍌 בננה · ביטחון גבוה (90%)              │  ← identity + confidence in words
│ ▶ כדאי לאכול עכשיו                       │  ← HERO: recommendation
│ בשילות [🟢 בשלה]  טריות [🟢 טרי]          │  ← chips (or "לא זמין עדיין")
│ 💡 טיפ אחסון (כללי): …                   │  ← one useful action
│ ⓘ הערכה חזותית בלבד…                    │  ← always visible
│ ▸ מה זיהינו?  ▸ למה?                     │  ← collapsed detail
│ [ סרוק פרי נוסף ]   האם צדקנו? 👍 👎      │
└──────────────────────────────────────────┘

Low confidence → "לא בטוח" card + [ צלם מזווית נוספת ] (combines both photos) + [ נסה שוב ]
Bad photo      → specific fix ("חשוך מדי…") + [ נסה שוב ]
Not produce    → "לא זיהיתי פרי או ירק" + [ נסה שוב ]
```

Steps to a result: **2 taps** (open, "סרוק פרי"). In the worst case: 3 (plus one extra angle).

## What we adopted, and from where

| Pattern | Seen in | Our version |
|---|---|---|
| Camera-first launch | PickFresh, FreshScanAI | Camera is the only home screen |
| Verdict-first result | Fruit Scanner, RipenessAI | Recommendation is the hero line |
| Confidence shown | RipenessAI | Words + calibrated % |
| Multi-angle | FreshScanAI (default, 3 angles) | Optional, one extra angle, only when unsure |
| Storage advice | FreshScanAI, PickFresh | One general tip per produce, labelled "כללי" |
| No account, on-device | RipenessAI, FreshScanAI | Stated on the permission screen |

## What we rejected

- Real-time live verdicts (flicker hurts trust; the model is tuned for a single deliberate frame).
- Recipes, calories, pantry, chat, prices, PLU.
- Numeric freshness scores and day-count shelf life.
- Health/safety claims.
- Weekly subscriptions and small free quotas.
- Onboarding carousels.
