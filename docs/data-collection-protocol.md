# Own data collection protocol (Phase 2c)

Goal: the only dataset with Israeli produce, real conditions, **ground-truth** ripeness/freshness and a physical-fruit ID that makes leakage-free splits possible. Output feeds `own_il_collection` (`data/raw/own_il_collection/labels.csv`), validated by `scripts/validate_collection.py`.

## 1. Two collection streams

| Stream | Purpose | Who | Volume (MVP) |
|---|---|---|---|
| **A. Longitudinal** | Train + val + test. Each fruit photographed daily from purchase to visible rot | Collection team | ≥ 60 fruits × ~8 days × 5 shots per produce type |
| **B. Wild** | Real-world test set only (never trained on) | Different people, different phones | ≥ 2,000 photos, ≥ 100 per P1 produce |

Stream B photographers must not see stream A photos or model outputs before shooting.

## 2. Longitudinal capture (stream A)

1. Buy fruit at ≥ 3 different retailers (supermarket chain, open market / שוק, greengrocer) over ≥ 3 weeks. Buy mixed stages (green bananas + yellow ones, hard + soft avocados).
2. Put a small numbered sticker on the **bottom** of each fruit → `fruit_instance_id` = `<produce>-<batch>-<n>` (e.g. `banana-B03-17`). Sticker must not be visible in photos.
3. Store as consumers do (counter / fridge per produce norm). Record storage in `storage`.
4. Every day at a fixed time, per fruit, take 5 shots rotating the conditions matrix below; keep the phone's default camera app, no filters, no zoom beyond 2×.
5. Grade (section 4) immediately after shooting, before looking at previous days' grades.
6. Continue until severe spoilage or 14 days. For 10–20% of fruits per produce, **cut-check** at a random day (then that fruit's series ends): record interior state in `cut_check`.

Conditions matrix (rotate so each fruit sees every level across days):

| Factor | Levels |
|---|---|
| Phone | ≥ 3 models incl. one ≥ 4 years old (`device`) |
| Light | daylight window · kitchen LED · dim evening lamp (`lighting`) |
| Setting | counter · in hand · fruit bowl with other fruit · plastic bag · plate (`background`) |
| Distance | 20 · 40 · 60 cm (`distance_cm`) |

## 3. File naming and metadata

`images/<fruit_instance_id>/<YYYYMMDD>_<shot>.jpg` (in the labeller, select the `images` folder itself so exported paths start with `images/`). Strip GPS EXIF on ingest; keep timestamp. No faces; hands are fine. `labels.csv` columns (enforced by validator):

| Column | Values |
|---|---|
| path, fruit_instance_id, produce | produce ∈ `label_mapping.json` produce keys |
| variety | free text (e.g. `Ettinger`, `Hass`, `Cavendish`, `Or`) |
| capture_date, day | ISO date; day index since purchase (0..) |
| device, lighting, background, distance_cm | as above |
| ripeness, freshness, visual_spoilage | taxonomy values or empty (= unknown); `a|b` for set-valued |
| storage, cut_check, annotator, notes | cut_check ∈ `ok, internal_browning, mould, rot, n/a` |

Per-annotator exports (`annotations_<name>.csv` from `tools/labeler/index.html`) are merged by `scripts/merge_annotations.py` into `annotations.csv` and a consensus `labels.csv`: strict majority wins; a tie becomes a **set-valued** label (e.g. `partially_ripe|ripe`), which the partial-label loss trains on honestly.

## 4. Grading guide (ground truth, not "what the photo looks like")

Ripeness is graded by **reference charts + touch**, so the label reflects the fruit's actual state; the model then learns whatever is visually predictable, and the evaluation tells us honestly how much is.

| Produce | unripe | partially_ripe | ripe | overripe |
|---|---|---|---|---|
| Banana (7-stage peel colour index) | stages 1–2 (green, trace of yellow) | 3–4 (more green than yellow / more yellow than green) | 5–7 (yellow, green tip → yellow with brown flecks) | > 7: large brown areas, peel mostly brown, very soft |
| Avocado (all cultivars) | hard, no give | slight give under firm palm pressure | yields to gentle palm pressure | very soft, dents, loose skin |
| Tomato (USDA colour stages) | green, breaker | turning, pink | light red, red, firm | red, soft, wrinkling |
| Mango | hard, no aroma | slight give | yields gently, aromatic at stem | very soft, shrivel |
| Peach / nectarine | hard, green ground colour | slight give, ground colour turning | gives at shoulder, aromatic | very soft, bruising |
| Strawberry | white/green | ≥ 50% red | fully red, glossy | dark red, soft, dull |
| Pear | hard | slight give at neck | neck yields | soft at body, browning |
| Others (apple, citrus, cucumber, pomegranate…) | ripeness **not graded** (leave empty) — these are sold ripe; only freshness/spoilage apply | | | |

Freshness / spoilage (all produce):

| freshness | visual_spoilage | Definition |
|---|---|---|
| fresh | none | Firm, turgid, no wrinkles, no lesions |
| declining | none or mild | Wrinkling, dull skin, soft spots, small bruises; still edible by typical consumer standard |
| spoiled | mild or severe | Mould, leaking, rot lesions, fermentation smell, collapse |

`mild` = lesions < 10% of visible surface; `severe` ≥ 10% or any mould.

## 5. Quality control

- 20% of fruit-days graded independently by 2 annotators. Required agreement before scaling up: quadratic-weighted Cohen's κ ≥ 0.6 for ripeness, κ ≥ 0.6 for freshness (`scripts/validate_collection.py --agreement`). Below that: revise this guide, re-train annotators.
- Validator must pass with zero errors before `build_manifest` (it also runs inside the build via the table adapter's strict vocabulary).
- Weekly: run `build_manifest` + `scripts/review_duplicates.py` on the collection.

## 6. Legal / privacy

Every photographer signs the contributor agreement (`docs/legal/contributor-agreement-he.md`, draft — counsel review required). Photos contain no faces or identifying home details; GPS is stripped; storage access-controlled.

## 7. Budget estimate

Per produce type: 60 fruits (~₪150–300) + ~8 days × 60 fruits × 5 shots ≈ 2,400 photos ≈ 8–10 person-hours of shooting and grading per day-batch. 10 types over ~6 weeks with 2 people part-time.
