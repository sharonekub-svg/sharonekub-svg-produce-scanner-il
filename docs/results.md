# Measured results (Phases 3–6)

Everything here was measured in the build environment (4-core Xeon CPU, no GPU) on 2026-09-26. Raw JSON is stored under `docs/results/`. **These are produce-identification results only.** No ripeness, freshness or spoilage labels were available, so those heads are untrained and flagged unsupported in every bundle.

**None of these is the Israeli real-world set** (Phase 5), which has not been collected yet. The closest proxy is the Grocery Store official test split: smartphone photos taken in Swedish supermarkets on different store visits from training.

## Phase 3 — baseline (commercially-cleared data only)

Config `ml/configs/p3_baseline_commercial.yaml`:
- MobileNetV3-Large with ImageNet weights, first 4 stages frozen.
- 224 px, 20 epochs, class-balanced sampling (α = 0.5).
- Trained on Grocery Store only: 1,510 train images, 462 validation images carved out of train by cluster.

| Split | n | top-1 | top-5 | macro-F1 | balanced acc. | worst-class recall | ECE (after T-scaling) |
|---|---|---|---|---|---|---|---|
| val (carved from train store visits) | 462 | 0.955 | — | 0.940 | — | 0.64 | 0.12 → (T = 0.63) |
| **test (official, different store visits)** | 1,704 | **0.849** | 0.990 | **0.788** | 0.741 | **0.32 (mandarin)** | 0.070 |

Per-class test recall, worst first:

| Class | Recall |
|---|---|
| mandarin | 0.32 (mostly → orange) |
| mango | 0.36 |
| nectarine | 0.40 |
| lemon | 0.44 |
| cucumber | 0.59 |
| avocado | 0.65 |
| kiwi | 0.67 |
| pomegranate | 0.68 |
| orange | 0.77 |
| plum | 0.77 |
| melon | 0.89 |
| pear | 0.89 |
| other | 0.91 |
| watermelon | 0.91 |
| peach | 0.92 |
| banana | 0.93 |
| tomato | 0.99 |
| pepper | 0.99 |
| apple | 1.00 |

**Gates (evaluation.md): FAIL.** Macro-F1 is 0.788 against a 0.85 gate. Recall is below 0.80 for 10 classes, including avocado and cucumber, whose gate is 0.90.

Decision policy on test, with thresholds tuned on validation for 95% accepted accuracy:
- 61.9% of scans get a result.
- Accuracy when a result is shown is **90.4%**. This misses the 95% target, so validation-tuned thresholds don't transfer to new store visits.

Findings:
1. **Carved validation sets are optimistic.** Clusters only catch near-duplicates, not "same store, same day", so val (0.955) overstates test (0.849). Validation for gating must be session-disjoint. That's easy for our own collection (split by fruit and date), but not possible for Grocery Store.
2. **Citrus is the weak spot.** Mandarin/orange/lemon confusion dominates. Israeli priorities include both mandarin and orange, so own-collected citrus data is a P0 need.
3. The overall-accuracy trap is real here. Top-1 of 0.85 hides a class that is recognized one time in three.

**Reproducibility (acceptance criterion: same seed gives metrics within ±0.5 points): PASS.** The same-seed rerun `p3_repro_commercial_mnv3` reproduced every epoch's loss and validation metrics exactly (val macro-F1 0.9443279 in both runs; identical gate failures).

## Phase 4 — benchmark matrix (research data; NOT commercially shippable)

Common setup:
- `data/processed_research`, 10 epochs × 5,000 class-balanced samples, 224 px, first 4 stages frozen.
- **12 produce classes are held out entirely** and form the unseen-produce OOD set: asparagus, leek, beet, passion fruit, mushroom, fig, radish, quince, cherimoya, pitahaya, carambola.
- Thresholds are tuned on validation for 95% accepted accuracy.
- "Grocery test" = official Grocery Store test minus the held-out classes (n = 1,586): phone photos from store visits not seen in training.

| Run | Training data | Backbone | Grocery test top-1 | macro-F1 | worst-class recall | Shown-result accuracy / coverage | Unseen produce: AUROC (energy) / app abstains |
|---|---|---|---|---|---|---|---|
| P3 baseline (commercial) | Grocery | MobileNetV3-L | **0.839** | 0.787 | 0.32 | 0.904 / 0.62 (full test) | — (classes seen as "other") |
| R1 | Grocery + Open Images + Fruits-360 | MobileNetV3-L | 0.813 | **0.790** | **0.44** | **0.947** / 0.45 | 0.64 / 89% |
| R2 | same as R1 | EfficientNet-B0 | 0.796 | 0.772 | 0.38 | 0.987 / 0.33 | 0.64 / 86% |
| **R4 cross-dataset** | Open Images + Fruits-360 only | MobileNetV3-L | **0.318** | **0.183** | 0.00 | 0.984 / **0.04** | 0.26 / 90% |
| R3 (no Fruits-360) | — | — | skipped (CPU budget; R1 vs P3 already answers "does public data help?") | | | | |

Findings:
1. **Public web and studio data does not transfer to phone photos of real produce (R4).** A model that never saw phone photos gets 32% top-1 on them. The abstention policy keeps shown results 98% correct, but it shows a result for only 4% of scans. That makes the product useless without our own phone-photo data. This is the strongest evidence behind the collection plan in [data-collection-protocol.md](data-collection-protocol.md).
2. **Adding about 23k public images to Grocery Store (R1 vs P3)** leaves macro-F1 flat (0.790 vs 0.787) and top-1 slightly lower. It helps the worst class (0.44 vs 0.32). It is not worth the licensing cost of Open Images and Fruits-360 for the release.
3. **OOD detection by logit scores is weak.** AUROC for unseen produce is 0.64–0.69 on in-domain data and inverted under domain shift (R4: 0.26). In practice the app still abstains on about 90% of unseen produce, but mostly because the thresholds are strict, and that also costs coverage. A dedicated OOD approach (e.g. feature-space distance, or training "other" with more diverse negatives) is future work.
4. **Backbone:** EfficientNet-B0 (R2) is no better than MobileNetV3-L (R1) on phone photos (macro-F1 0.772 vs 0.790) and trains about 2× slower on CPU. Its host inference is also slower (22 vs 15 ms, `benchmarks/`). **MobileNetV3-L is selected.**
5. **Architecture options A/B/C for ripeness could not be benchmarked**: no ripeness labels exist in usable data. The code supports all three (`ripeness_mode`, `head_weights`).

## Phase 4 — commercial track (Grocery Store only, i.e. shippable today) and model selection

The model is selected on **validation** macro-F1; the test set is used only to report the chosen model.

| Run | Backbone / training | val macro-F1 | test top-1 | test macro-F1 | test worst-class recall | test ECE | App: shown / accuracy when shown |
|---|---|---|---|---|---|---|---|
| P3 | MobileNetV3-L, first 4 stages frozen | 0.944 | 0.849 | 0.788 | 0.32 | 0.070 | 62% / 0.904 |
| **C1 (selected)** | MobileNetV3-L, full fine-tune | **0.949** | **0.892** | **0.851** | **0.44** | **0.039** | 63% / 0.930 |
| C2 | EfficientNet-B0, first 4 stages frozen | 0.945 | 0.898 | 0.845 | 0.42 | 0.056 | 62% / 0.938 |

C1 per-class test recall, worst first:

| Class | Recall |
|---|---|
| lemon | 0.44 |
| mandarin | 0.53 |
| mango | 0.58 |
| cucumber | 0.67 |
| orange | 0.70 |
| nectarine | 0.77 |
| kiwi | 0.78 |
| pomegranate | 0.84 |
| avocado | 0.85 |
| plum | 0.86 |
| melon | 0.88 |
| watermelon | 0.89 |
| peach | 0.92 |
| other | 0.94 |
| pear | 0.94 |
| banana | 0.98 |
| apple | 0.99 |
| tomato | 1.00 |
| pepper | 1.00 |

Gate results for C1:
- **Passes** the macro-F1 gate (0.851 ≥ 0.85).
- **Fails** the per-class recall gates for 8 classes: citrus, mango, cucumber, nectarine, kiwi, avocado.

## Release candidate `v0.1-dev` (C1)

Produced by `scripts/release_model.sh runs/p4_c1_commercial_mnv3_full/… data/processed_commercial v0.1-dev --allow-gate-failures`.

| Check | Result |
|---|---|
| Licence gate: training manifest uses only commercially-cleared data | ✅ Grocery Store (MIT) only |
| ONNX == PyTorch | ✅ 100% agreement, max logit diff 0.0 |
| Core ML fp16 | ✅ 8.2 MB (converted; not executed — needs macOS) |
| Host CPU latency (ONNX, 1 thread) | 4.8 ms p50 (not a phone number) |
| Abstention threshold | produce_min_prob raised from the tuned 0.30 to the product floor 0.70 (never show a "low confidence" answer): test shown 63.0% → 61.3%, accuracy when shown 93.0% → 94.3% |
| Acceptance gates on test | ❌ 8 per-class recall failures (see above) → **internal dev build only; NOT releasable to users** |
| Synced into app | ✅ `app/assets/model/bundle.json`, credits, `ProduceScanner.mlpackage`; app typecheck, 604 tests and iOS bundle pass |
| End-to-end via self-hosted server (real photos) | ✅ avocado/tomato identified; banana at 0.52 → "unsure"; asparagus → "not produce"; dark photo → "retake"; satsuma → "orange" at 1.00 (known citrus confusion) |
| Ripeness / freshness / spoilage | Unsupported (no licensed labels). The app shows "not available yet for this type" and the recommendation "check manually" |

## Follow-ups after `v0.1-dev` (2026-09-27): negatives, lighting, and `v0.2-dev`

All runs use the C1 recipe on Grocery Store only (commercial). Every column is measured on **identical test rows**: in-distribution = test minus the five lookalike types. Lookalikes are lime, grapefruit, zucchini, potato and passion fruit, and should end as "unsure" or "not produce". Warm light is the synthetic tungsten proxy. Single seed each (`scripts/compare_runs.py`).

| Run | Change | top-1 | macro-F1 | worst class | shown | acc. when shown | lookalikes abstained | energy AUROC (lookalikes) | warm macro-F1 | warm acc. shown |
|---|---|---|---|---|---|---|---|---|---|---|
| C1 (`v0.1-dev`) | lookalikes inside "other" | 0.896 | 0.861 | 0.44 | 68.3% | 94.8% | 96.8% | 0.700 | 0.826 | 93.2% |
| C3 | lookalikes removed from training | 0.900 | 0.851 | 0.37 | 69.9% | 92.0% | **68.9%** | 0.864 | 0.771 | 86.2% |
| C4 | C1 + white-balance augmentation | 0.892 | 0.848 | 0.45 | 68.2% | 95.0% | 99.5% | 0.640 | **0.849** | **94.7%** |
| **C5 (`v0.2-dev`)** | lookalikes as **named negative classes** | **0.898** | **0.874** | **0.52** | 67.3% | 94.6% | 98.4% | 0.693 | 0.797 | 93.1% |
| C6 | C5 + white-balance augmentation | 0.894 | 0.858 | 0.45 | 67.4% | 95.0% | 98.9% | 0.683 | 0.836 | 94.1% |
| C7 | C5 + 2,690 studio lemons (SoftwareMill, MIT) | 0.878 | 0.824 | 0.34 | 52.1% | 97.0% | 100% | 0.675 | 0.750 | 96.3% |

In-distribution per-class recall, C1 → C5: lemon 0.44 → 0.54, mandarin 0.53 → 0.66, kiwi 0.78 → 0.91, avocado 0.85 → 0.95, cucumber 0.67 → 0.70, mango 0.68 → 0.68. Orange drops 0.70 → 0.52: 10 of 56 oranges are now called grapefruit. Grapefruit is a negative class, so those photos end as "not something I know", not as a wrong answer, and accuracy when shown is unchanged.

Decisions:
- **C3 rejected.** Without seeing lookalikes in training, only 69% of them are caught. The OOD score cannot replace negatives.
- **C7 rejected.** Adding studio lemons on a black background *lowered* lemon recall on phone photos (0.54 → 0.34) and macro-F1 (0.874 → 0.824). The model learned "black background = lemon", and 'shown' fell to 52%. This is the domain gap measured before (results R4). Scored from the best checkpoint (epoch 14); the run stopped at epoch 18 of 20. The lemon mould labels stay registered, to be used only once they're paired with phone-photo lemons.
- **C5 adopted → `v0.2-dev`.** It has the best macro-F1 and the best worst-class recall of any run, catches more lookalikes than C1, and keeps accuracy when shown.
- **White balance (C4/C6) not adopted yet.** It clearly helps warm light (+0.02–0.04 macro-F1, +1.0–1.5 points accuracy when shown). But on one seed it costs in-distribution macro-F1 (−0.013 and −0.016), mostly on mango and citrus. Warm-light accuracy of what is *shown* is 93.1% for C5 anyway, because abstention absorbs the difference. Re-test on the real-world set, where warm kitchen light is real rather than synthetic. The switch is `augment.white_balance_p`.

### `v0.2-dev` release (`scripts/release_model.sh runs/p4_c5_named_negatives/… data/processed_commercial_v2 v0.2-dev --allow-gate-failures`)

| Check | Result |
|---|---|
| Licence gate | ✅ Grocery Store (MIT) only |
| ONNX == PyTorch | ✅ 100% agreement; 16.55 MB |
| Core ML fp16 | ✅ 8.5 MB weights |
| Full test (28 classes incl. negatives, quality gate on) | top-1 0.891, macro-F1 0.847, ECE 0.046; accuracy when shown 94.3% |
| Gates | ❌ 7 per-class failures (orange, mandarin, lemon, cucumber, mango, nectarine, passion fruit), down from 8 → **internal dev build only** |
| Synced | app bundle, credits, `ProduceScanner.mlpackage`, `server/model` (Vercel API) |
| Server class list | Now read from the bundle (`restrict_produce`). Previously it used the mapping file, which would have mislabelled index 22 after classes were added. |

Also measured, in [research/ml-methods.md §6](research/ml-methods.md):
- Feature-space OOD. Mahalanobis AUROC is 0.83 vs energy 0.70 on lookalikes, and 0.71 vs 0.69 on unseen produce. Not shipped yet.
- Blur-gate sweep. The threshold moved 60 → 30: same accuracy on what passes, and unnecessary retakes on mild blur fall from 67% to 16%.

## First quality model: C8 → `v0.3-dev` (27 Sep 2026)

**Data** (all licences verified at the primary source, 5 datasets):
- Grocery Store and FruitNet (phone photos), used for identification and quality.
- Quality only, with produce loss masked:
  - Hass avocado ripening: 478 fruits, 5-stage index;
  - psolymos bananas;
  - SoftwareMill lemons.
- Studio sets are split by physical fruit.
- MobileNetV3-L, 12 epochs of 6,000 samples, CPU.

**Quality heads on held-out photos** (`scripts/gate_quality_heads.py`; the bar was fixed before results):

| Fruit | Head | Test photos | Result | Gate |
|---|---|---|---|---|
| Avocado (Hass) | ripeness, 4 stages | 1,470 | 71% exact, 99.9% within one stage | ✅ |
| Apple | good vs visible defects | 174 / 55 | balanced accuracy 1.00, AUROC 1.00 | ✅ |
| Orange | good vs visible defects | 138 / 91 | 0.967, AUROC 0.987 | ✅ |
| Pomegranate | good vs visible defects | 613 / 99 | 0.975, AUROC 1.00 | ✅ |
| Guava | good vs visible defects | 195 / 32 | 1.00 | ✅ |
| Lemon | visible defects | 105 / 47 | 0.833, AUROC 0.894 | ❌ no score |

**Caveat:** these are in-dataset test photos (same cameras and settings as training, different fruit). Clear rot is easy. On real Israeli phone photos, and for mild defects, expect lower numbers. The real-world test set remains the deciding measurement.

**Identification regressed** on the Grocery phone-photo test (the same 1,514 rows as C5):
- top-1 0.876 (C5: 0.898), macro-F1 0.820 (C5: 0.874);
- accuracy when shown 97.5% (C5: 94.6%), at a lower share shown, 62.7% vs 67.3%;
- orange recall 0.52 → 0.39: FruitNet's Indian "oranges" are green citrus.

C9 therefore moves FruitNet to quality-only.

Released as **`v0.3-dev`** (internal; the identification gates still fail). It is the first build where the app shows a 1–10 score, for avocado, apple, orange, pomegranate and guava.

## Round 2: C9 → `v0.4-dev` (27 Sep 2026)

**Data** (9 datasets, all CC BY 4.0 or MIT, verified):
- Identification and quality: Grocery Store, plus expert-graded fresh/rotten photos of 7 fruits.
- Quality only, with a fixed epoch share: FruitNet (moved here after the C8 orange regression), Hass avocado, psolymos bananas, lemons, apple good/bad, GrapeNet, mango/banana ripeness.
- 12 epochs; validation on a fixed 4,000-photo subsample.

| Fruit | Head | Held-out test | Gate |
|---|---|---|---|
| Apple | freshness (full: expert "rotten" = spoiled) | 238 / 230, balanced accuracy 0.983, AUROC 1.00 | ✅ |
| Banana | ripeness | 266 photos, 100% (grouped by capture session; same-dataset test) | ✅ new |
| Grape | freshness | 1,417 / 1,171, 0.868, AUROC 0.981 | ✅ new |
| Orange | freshness | 0.967, AUROC 0.993 | ✅ |
| Pomegranate | freshness | 0.987 | ✅ |
| Guava | freshness | 0.980 | ✅ |
| Avocado (Hass) | ripeness | 1,470, 69.9% exact (bar 70%), 99.9% within one stage | ❌ (C8 passed at 71%) |
| Strawberry | freshness | 17 / 20 photos: too few to count as evidence | ❌ |
| Banana | freshness | 21 bad photos: too few | ❌ |
| Lemon | defects | 0.831 | ❌ |

**Identification** on Grocery (same rows):
- top-1 0.871, macro-F1 0.826, accuracy when shown 95.3%, shown 52.5%;
- avocado recall 0.85 → 0.93, pomegranate 0.40 → 0.72;
- orange 0.38 and mandarin 0.50 are still weak.

The lower "shown" rate means more "not sure" answers. That is the next thing to fix: the confidence floor and the class balance.

Released as **`v0.4-dev`** (internal). Scores are live for **apple, banana (ripeness), grapes, orange, pomegranate and guava**. Avocado drops out until it clears the ripeness bar again. The bar is not lowered after seeing results.

Smoke test through the server:
- rotten apple → 1/10, "discard" (with the Ministry of Health mould rule);
- banana → 8/10, "ripe";
- orange → 10/10.

## Round 3: C10 → `v0.5-dev` (27 Sep 2026)

Config `p5_c10_calibrated.yaml`:
- 16 epochs; aux share 0.46; 2 loader workers.
- Validation masks the produce labels of aux (quality-only) rows. This fixes C9's inflated produce temperature, 0.94 → 0.53.

Test set (`eval_test_all`, n = 8,833), C9 → C10:

| Head | Metric | C9 | C10 |
|---|---|---|---|
| Freshness | top-1 | 0.912 | **0.969** |
| Freshness | ECE | 0.071 | 0.014 |
| Visual spoilage | top-1 | 0.913 | **0.995** |
| Ripeness | top-1 | 0.774 | **0.790** |
| Ripeness | "partially ripe" recall | 0.40 | 0.52 |

**Identification threshold.** The val-tuned `produce_min_prob` (0.70) gave more coverage but lower accuracy when shown. We raised it to **0.93**: the smallest value whose Grocery-**val** accuracy (0.9938, n = 397) matches what C9 shipped with (0.9936 at 0.74). It was chosen on val, not test (`thresholds.json` → `tuned_on.override_note`). The confidence + margin rule on Grocery test, without OOD or photo gates:

| Model | Threshold | Shown | Accuracy when shown |
|---|---|---|---|
| C9 | 0.74 | 67.9% | 95.3% |
| C10 | 0.93 | **73.8%** | **97.0%** |

**Per-fruit quality gate** (same bar as before):
- New: **avocado ripeness passes** (0.724 exact, 0.999 within one stage, n = 1,470).
- All six C9 types still pass.
- Lemon (bal. acc. 0.74) and strawberry (37 test photos) still fail.
- Banana freshness and grape spoilage pass the accuracy bar, but have only 21 "bad" test photos each, below the 30 required.
- Lime passes but stays off: lime is a held-out "look-alike" class in the OOD test.

Scores are live for **apple, banana, grapes, orange, pomegranate, guava and avocado**. Released as **`v0.5-dev`** (`p5_c10_calibrated@2f3772e51859`). The Grocery-only identification recall gates still fail (e.g. passion fruit 0.30, n = 27), so it stays a dev build.

## Round 4: C11 → `v0.6-dev` (28 Sep 2026)

**New data.** Two datasets, both CC BY 4.0 (checked via the Mendeley API), both **train only** (`force_split`). They can't leak into val/test.
- `strawberry_avocado_ripening` (zysvgmxcyz). Class order is from the paper. Only single-class images are used: 226 rotten avocados and 258 not rotten, plus 92 strawberries. There are no avocado ripeness labels, because the cultivars are mixed.
- `mango_ripening_mm8` (mm8g66d7rc). 949 single mangoes. It is used for identification. Mango ripeness stays vetoed because the cultivar is unknown.

Manifest v6. The Grocery test is unchanged. About 3% of the fresh/rotten and FruitNet test rows moved, so **C10 was re-evaluated on the v6 test** for the comparison below.

| Test set (v6) | C10 | C11 |
|---|---|---|
| Freshness balanced acc. | 0.960 | **0.964** |
| Ripeness balanced acc. | **0.742** | 0.707 |
| Produce top-1 (all test rows) | 0.435 | **0.478** |

**Identification.** The threshold was chosen on Grocery-**val** with the same rule as before: the smallest value whose accuracy is at least 0.9936 gives **0.96** (val 0.9942, n = 397). Results on Grocery test, confidence + margin rule:

| Model | Threshold | Shown | Accuracy when shown |
|---|---|---|---|
| C10 | 0.93 | 73.8% | 97.0% |
| C11 | 0.96 | **76.7%** | **97.7%** |

**Per-fruit quality gate** (balanced accuracy, C10 → C11):

| Fruit | Head | C10 | C11 |
|---|---|---|---|
| Apple | freshness | 0.948 | 0.991 |
| Guava | freshness | 0.951 | 0.981 |
| Orange | freshness | 0.959 | 0.983 |
| Pomegranate | freshness | 0.893 | 0.971 |
| Grapes | freshness | 0.953 | 0.931 |
| Avocado | ripeness (exact) | 0.724 | 0.717 |

- All of the above still pass.
- Lemon improved (0.74 → 0.83) but is still below 0.85.
- Avocado freshness has **no test photos**, because the new set is train only. It therefore gets no score: no evidence means no score.

Released as **`v0.6-dev`** (`p5_c11_more_data@148a9ebb894c`). The same 7 fruit types have scores, now more accurate.

## Round 5: C12 → `v0.7-dev` (28 Sep 2026)

**New data** (both CC BY 4.0, checked via the Mendeley API; manifest v7):
- `fruit_inspection_6ps` (6ps7gtp2wg): 12,000 phone photos on kitchen surfaces, fresh vs non-fresh for strawberry, tomato, orange, lime (Colombian "limón"), mango and banana. Split by fruit (blocks of 100 consecutive shots), so it adds held-out test photos. Lulo and tamarillo excluded. A visual audit found fresh and spoiled photos share the same backgrounds, so there is no background shortcut; the spoilage in it is obvious, which makes this test easy.
- `lemon_varieties` (mygrsk3vyb): 1,956 original lemon photos (fresh / rotten), quality-only aux.

**Per-fruit quality gate** (balanced accuracy on the v7 test, C11 → C12):

| Fruit | Head | C11 | C12 | Gate |
|---|---|---|---|---|
| Strawberry | freshness | 0.576 | **1.000** | pass (new) |
| Lemon | freshness | 0.916 | **0.944** | pass (new) |
| Lemon | visual spoilage | 0.833 | **0.915** | pass (new) |
| Banana | freshness | 0.831 | **1.000** | pass (new) |
| Orange | freshness | 0.812 | **0.982** | pass |
| Grapes | freshness | 0.931 | **0.980** | pass |
| Apple | freshness | 0.989 | 0.985 | pass |
| Pomegranate | freshness | 0.992 | 0.983 | pass |
| Guava | freshness | 0.980 | 0.953 | pass |
| Avocado | ripeness (exact) | 0.717 | 0.710 | pass |
| Tomato | freshness | 0.789 | 1.000 | **fail**: only 1 fresh test photo |
| Mango | freshness | – | – | **fail**: no test photos |

Lime passes but stays off (held-out look-alike class in the OOD test, as before).

**Identification got slightly worse.** Threshold chosen on Grocery-**val** with the same rule (smallest value with accuracy ≥ 0.9936): **0.98** (val 0.9947, 374 of 461 shown). On Grocery test (confidence + margin, photo-quality gate on):

| Model | Threshold | Shown | Accuracy when shown |
|---|---|---|---|
| C11 | 0.97 (same rule on v7) | 50.2% | 98.3% |
| C12 | 0.98 | 47.4% | 97.5% |

Released as **`v0.7-dev`** because the quality gains are large (strawberry, lemon and banana freshness get scores; orange and grapes much more accurate), at the cost of about 3 points fewer identifications shown and 0.8 points lower accuracy when shown on Grocery. The Grocery-only identification recall gates still fail (lemon recall 0.55, n = 11), so it stays a dev build. On all test photos (release gates), produce macro-F1 rose 0.557 → 0.589 and recall improved for orange (0.46 → 0.72), mango (0.19 → 0.50), lime and banana, but fell for mandarin (0.57 → 0.40) and avocado (0.66 → 0.52), partly because of the stricter threshold.

## Round 6: SigLIP2 backbone → `v0.8-dev` (29 Sep 2026)

**Why.** First real use on an Android phone failed: an apple was called an avocado, a sharp well-lit photo was
sent back as "retake", and web photos got "try another angle". We measured the app's exact path on **real web
photos the model never trained on** (Open Images crops, 900 photos, 15 supported types): v0.7 top-1 **0.29**,
answer shown for 14% of photos, 65% correct when shown; 9% of photos rejected by the photo-quality check.
The v0.7 CNN had learned our uniform datasets, not real photos.

**New model.** Google SigLIP2-base (Apache-2.0) image encoder, exported to ONNX with weight-only 8-bit weights
(109 MB; same accuracy as fp32 — plain int8 dropped real-photo top-1 to 0.55, so it was not used). Every head is
linear on its 768-d embedding (`ml/siglip/`, `scripts/siglip_*.py`):
- identification = half zero-shot text prompts + half fitted on our photos (blend chosen on real photos + val);
  "not supported" prompts form the `other` class;
- freshness / spoilage / ripeness = regression on our labelled photos (same data and per-fruit gate as before).

**Real photos** (Open Images, 2,133 incl. 693 unsupported produce; threshold chosen on the calibration half,
reported on the other half):

| | v0.7 | v0.8 |
|---|---|---|
| top-1 (supported) | 0.29 | **0.78** |
| answer shown | 14% | **56%** |
| correct when shown | 65% | **94%** |
| unsupported produce shown as a supported one | – | 4% |

Below the threshold the app now shows its top guesses and the user picks the fruit ("chosen by user"), instead of
only asking for another angle.

**Photo-quality check.** On real photos the model is almost as accurate on "blurry" (texture below 30) and
"overexposed" (white background) photos as on the rest, so only extreme cases ask for a retake now
(texture < 8, clipped > 85%, luma < 20 or > 245).

**Per-fruit gate** (held-out test, same bar): scores for apple, banana, grapes (freshness), guava, lemon, orange,
pomegranate, strawberry. Avocado ripeness 0.68 (< 0.70): no score for now. Lime stays off (look-alike class).
Tomato / mango: not enough test photos, as before.

## Round 7: a score for every type → `v0.8.1` (29 Sep 2026)

**General score** (`freshness~general`): zero-shot SigLIP2 text prompts (fresh vs. rotten), plus one global
scale and bias fitted on the fruits that have labels. Leave-one-fruit-out balanced accuracy (fresh vs. spoiled):
mean 0.866, min 0.758. It is used only for types without a verified freshness head: they get a coarse fresh/not-fresh
score, marked in the app as "ציון כללי" (general score) with an explanation. Verified types are unchanged (9 types incl. lime, which now passes the gate).

**5 look-alike types** (lime, grapefruit, zucchini, potato, passion fruit) are no longer "not supported":
they are identified, get a general score, and have care tips.

**Advice**: a stage card with what to do at each ripeness stage (banana, avocado, mango), and a nectarine/peach
hand check (smell, background color, the yellow stripe at the stem end).

## Round 10: checks after v0.10 (nothing shipped — none beat the current model on the calibration half)

| tried | chosen on | result | shipped |
|---|---|---|---|
| all 11,143 Open Images train crops instead of 500/class (`runs/siglip/v11`) | real cal | 0.856 vs 0.861 | no |
| richer fresh/rotten prompts for the general score | val, leave-one-fruit-out | 0.799 vs 0.805 | no |
| mirror test-time augmentation (2x server time) | real cal | 0.858 vs 0.861 | no |
| centre-square / centre-80% crop instead of squashing the whole photo | full-frame cal | 0.946 / 0.935 vs 0.952 | no |

Full-frame check (the app sends the whole photo, not a crop): 631 evaluation-set images where one fruit type fills
>= 20% of the frame, downloaded whole. Current v0.10 top-1 (supported, excl. grapefruit): **0.95 cal, 0.92 test**.
Open Images cucumber/zucchini labels are visibly mixed (and often sliced or cooked), so that pair's ~0.6 is partly label noise.

## Round 9: produce head trained on real-world photos → `v0.10` (29 Sep 2026)

7,723 Open Images crops (18 of our types + 9 unsupported look-alikes as "other"; `scripts/siglip_embed_oi_train.py`)
are added to the produce-head training. Every image id with any crop in the real-photo evaluation set is excluded (checked:
0 overlap). Open Images "Grapefruit" is left out of training: a visual check showed it is mostly oranges, and including it
dropped orange from 0.71 to 0.41 (so the eval's grapefruit class is also mostly oranges; its score is not meaningful).
Selection rules unchanged (real-cal + val; threshold rule acc-when-shown >= 0.92 on cal -> 0.70).

| real-photo test half | v0.9 | v0.10 |
|---|---|---|
| top-1, supported types without grapefruit | 0.82 | **0.88** |
| top-1, all (incl. noisy grapefruit + other) | 0.80 | 0.83 |
| answer shown (not "unsure") | 56% | **79%** |
| correct when shown | 94% | 90% |
| unsupported shown as a fruit | 4% | 5% |

Largest gains: lemon 0.53 -> 0.86, potato 0.73 -> 0.92, peach 0.67 -> 0.82, orange 0.71 -> 0.90, cucumber 0.46 -> 0.59.
Still weak: cucumber vs zucchini (~0.6). Studio val top-1 0.972 -> 0.963. Quality heads and the gate unchanged.
Note: "correct when shown" is lower (0.90 on test vs 0.92 target on cal), in exchange for answering 79% of photos instead of 56%;
when unsure the app shows its top guesses to pick from.

## Round 8: avocado ripeness passes → `v0.9` (29 Sep 2026)

The shared ripeness probe had seen only 1,200 of the 10,000 Hass training photos (embedding caps). Now all
14,710 Hass rows are embedded (`scripts/siglip_embed_dataset.py`, merged into `runs/siglip/emb_v9.npz`) and the heads
retrained with the same script and selection rules (`runs/siglip/v09`). Val ripeness exact 0.729 (all types).

Held-out test, avocado ripeness (n = 1,470): exact 0.677 → **0.706**, within one stage 0.997 → 0.998 → passes the
gate (0.70 / 0.95). Weakest class: "partially ripe" (recall 0.34, mostly read as unripe). Nothing else changed in the
gate; produce top-1 on real photos 0.78 (test) as before.

Tried and not shipped: adding hand-made colour statistics to the embedding (val +0.012). It relies on a pale
studio background, so it is likely to be worse on real phone photos.

## Phase 5 — validation (stress proxies on the P3 model, Grocery official test, n = 1,704)

The Israeli real-world set does not exist yet. These are **synthetic proxies** (`ml/evaluation/evaluate.py --stress`), not a substitute for it.

| Condition | top-1 | macro-F1 | worst-class recall | Quality gate stops | App shows result | Accuracy when shown |
|---|---|---|---|---|---|---|
| clean | 0.849 | 0.788 | 0.32 | 8 (0.5%) as blurry | 62% | 0.904 |
| dark (γ 1.8, ×0.45, noise) | 0.788 | 0.671 | 0.06 | **97% "too dark"** | 1% | 1.00 |
| blur (σ ≈ 3 px) | 0.803 | 0.732 | 0.37 | **100% "blurry"** | 0% | — |
| JPEG q20 | 0.842 | 0.776 | 0.34 | — | 61% | 0.891 |
| warm light (tungsten WB) | 0.829 | 0.750 | 0.11 | — | 62% | 0.871 |
| occlusion (~25% of frame) | 0.834 | 0.759 | 0.29 | — | 58% | 0.908 |

Findings:
- The quality gate turns dark and blurry photos into a "retake" prompt instead of a wrong answer. The blur threshold is conservative: the model still gets 80% of those blurred images right, so it should be retuned on real phone photos.
- **Warm light is the dangerous case.** It passes the gate, drops the worst class to 0.11, and lowers shown-result accuracy to 0.87. Colour-cast photos must be in our collection matrix (evening kitchen light).

**Hard examples** (`scripts/mine_hard_examples.py`):
- 257 errors on test, 101 of which would be shown to users.
- Top confusions:

  | True → predicted | Count |
  |---|---|
  | mandarin → orange | 38 |
  | nectarine → apple | 21 |
  | lemon → other | 21 |
  | kiwi → other | 15 |
  | avocado → other | 14 |

- Most of these have 0.97–1.00 confidence, so no threshold can catch them.
- Two causes:
  - The "other" class contains lookalikes (passion fruit, lime, grapefruit, potato) that absorb real target produce. Negatives should not be near-duplicates of targets.
  - Shelf photos show several products under a single label.

## Phase 6 — export and quantization (baseline model)

See [mobile.md](mobile.md). ONNX fp32 matches PyTorch exactly. Static int8 loses 6 points of top-1 and is rejected. **Core ML fp16 (8.2 MB) is chosen**, with 99.9% agreement.
