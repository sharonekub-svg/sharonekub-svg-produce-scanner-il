# Phase 2 ingestion report — real data run (2026-09-26)

Everything below was **measured** by running the pipeline on downloaded data in the build environment. Raw reports: `data/processed_*/report.json` (not committed; regenerate with the README commands). Pinned sources: `data/raw/<id>/.provenance.json`.

## Datasets ingested

| Dataset | Source / pin | Purpose gate | Valid images | Rejected |
|---|---|---|---|---|
| Grocery Store | git clone, MIT `LICENSE` in repo | **commercial** ✅ | 3,676 (packages, iconic images, sample_images excluded) | 0 |
| Open Images V7 produce subset | `scripts/fetch_open_images.py` — 27 classes, ≤ 400 images/class, val+test+train | research (needs sign-off) | 18,450 crops from 6,727 images | 32 too small |
| Fruits-360 original-size | git clone (8.1 GB), CC BY-SA `LICENSE` in repo | research (share-alike review) | 12,049 (80 frames/class cap of 108,597) | 0 |

Open Images filter funnel: 61,526 boxes seen → −12,126 group-of/depiction → −19,361 < 1.5% of image → 6,884 images chosen → −151 rotated → −4 download errors → **6,727 images, 18,451 crops**. **0 images dropped for licence**: every selected image's per-image metadata was CC BY 2.0. Attribution for each image is in `data/raw/open_images_v7/attribution.csv`.

Fetching data from Kaggle, Mendeley, Zenodo, Hugging Face, PMC and ScienceDirect was blocked by the environment's egress policy, so FruitNet, Hass avocado, strawberry–avocado, FruQ-DB and the other Mendeley/Kaggle sets are **not ingested**. They need a manual download (`scripts/download_datasets.py --import-archive`).

## Manifests

| Manifest | Datasets | Images | Clusters (split unit) | train / val / test |
|---|---|---|---|---|
| `data/processed_commercial` | Grocery Store | 3,676 | 3,668 | 1,776 / 196 / 1,704 (official split) |
| `data/processed_research` | Grocery + Open Images + Fruits-360 | 34,175 | 10,531 | 28,129 / 1,186 / 4,860 |

Leakage checks (all passed; the build aborts otherwise):
- No cluster is in more than one split.
- Grocery Store official split: the closest test→train pair is pHash distance 10, and it shows unrelated images. No same-scene leakage was found across the authors' split.
- 1 cross-split conflict between Open Images splits; the whole cluster was moved to test.
- 0 clusters span two datasets after verification.

### Per-produce counts (research manifest)

| produce | train | val | test | independent clusters |
|---|---|---|---|---|
| other (negatives) | 10,217 | 466 | 1,684 | 4,047 |
| apple | 3,530 | 55 | 381 | 1,052 |
| tomato | 2,223 | 122 | 375 | 694 |
| orange | 1,760 | 86 | 262 | 647 |
| strawberry | 1,647 | 37 | 166 | 408 |
| pear | 1,622 | 14 | 188 | 481 |
| cucumber | 1,452 | 61 | 253 | 497 |
| pepper | 1,200 | 61 | 263 | 580 |
| banana | 777 | 17 | 101 | 497 |
| peach | 693 | 46 | 212 | 276 |
| lemon | 626 | 60 | 202 | 504 |
| watermelon | 513 | 31 | 142 | 450 |
| pomegranate | 318 | 17 | 58 | 266 |
| melon | 313 | 27 | 130 | 337 |
| avocado | 281 | 5 | 40 | 89 |
| grape | 271 | 59 | 178 | 109 |
| mango | 272 | 12 | 55 | 184 |
| plum | 182 | 0 | 22 | 46 |
| nectarine | 116 | 0 | 35 | 72 |
| mandarin | 70 | 5 | 68 | 143 |
| kiwi | 46 | 5 | 45 | 96 |
| guava, persimmon | 0 | 0 | 0 | 0 |

The commercial manifest has 22–278 train images per target produce type (banana 45, avocado 41, cucumber 28). It has **no** strawberry or grape images, and it has **no ripeness, freshness or spoilage labels at all**.

## Defects found by running on real data (and fixed)

1. **Near-duplicate chaining (critical).** pHash alone linked differently coloured fruits of the same shape on white backgrounds (plum ↔ tomato at distance 6). Through union-find transitivity this merged all 151 Fruits-360 classes and 18 Open Images crops into **one 11,484-image cluster**. That cluster inherited the `test` split from an Open Images member, which put all of Fruits-360 into test.
   - **Fix:** every pHash edge is now verified with a brightness-invariant foreground chromaticity histogram. Studio (white-background) pairs need distance ≤ 2 and chroma L1 ≤ 0.15; other pairs need chroma L1 ≤ 0.40.
   - **How the thresholds were set:** the real duplicate pairs ranged from 0.02 to 0.17, and flip/brightness/saturation augmentations went up to 0.34.
   - **Result:** 14,167 false edges rejected; the largest cluster is now 240. Regression tests: `test_studio_same_shape_different_colour_not_linked` and `test_studio_brightness_copy_still_linked`.
2. **Grocery Store grouping bug.** The Phase 1 `group_pattern` would have put each entire class into a single split. It was replaced by the authors' official split (`split_pattern`) plus hash dedup.
3. **Fruits-360 real class names differ from the documentation.**
   - There is no `Avocado ripe` class. There are `Avocado Black` and `Avocado Green`, which are deliberately **not** mapped to ripeness because skin colour depends on the cultivar.
   - `Orange peeled` is now excluded.
   - This version has no mandarin, kiwi, mango, watermelon or persimmon classes.
4. **Fruits-360 labels the same physical fruit under two class names** (verified visually): `Apple Braeburn 1` ≡ `apple_braeburn_1`, and `Pear 14` ≡ `Pear common 1`. The verified dedup merges them. `apple_golden_2/3` and `apple_granny_smith_1` also merge (all apple, all train; harmless).
5. **Open Images class names** are `Orange (fruit)` and `Lemon (plant)`, not `Orange`/`Lemon`. The mapping is fixed.

## Label-quality audit (Open Images, 40 random crops per class, visual)

| Class | Wrong object | Out of scope (cut/peeled/processed) | Notes |
|---|---|---|---|
| peach | ~5 / 40 (apples, leaves only, too dark) | 2 cut halves | ≈ 15–18% unusable |
| banana | 0 / 40 | ~8 peeled / partly peeled, 1 chocolate-coated | Species correct; ~20% not whole fruit |

Consequence: treat Open Images as a **weak** produce-ID source. Before it trains a released model, run a reject pass with the labeller (≈ 1–2 s per crop), or at minimum train with label smoothing and never use it for any head other than produce.

## Remaining gaps (unchanged by this run, now quantified)

- **Ripeness/freshness labels available for commercial training: 0.** Ingested data provides produce-type only.
- Validation splits are small for several classes (plum and nectarine have 0 in val). Phase 3 must carve a group-aware val split out of train for gating.
- Guava and persimmon have no data at all; mandarin and kiwi come from Grocery Store only.
