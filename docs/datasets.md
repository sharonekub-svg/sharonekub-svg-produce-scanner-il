# Datasets

Source of truth: [`data/dataset_registry.csv`](../data/dataset_registry.csv) (19 rows). Label mapping: [`data/label_mapping.json`](../data/label_mapping.json).

## How this registry was researched (read before trusting it)

Research date: 2026-09-26. The build environment's egress proxy **blocked** Kaggle, Zenodo, Mendeley Data, ScienceDirect, PMC and Hugging Face. Therefore:

| `license_verification` | Meaning | Rows |
|---|---|---|
| `verified_primary` | Licence read on the dataset's own page (GitHub README/LICENSE) | Fruits-360 (both), Grocery Store, own collection |
| `reported_secondary` | Licence seen only in search-engine snippets of the landing page / paper | FruitNet, Hass avocado, Strawberry-avocado, Laboro Tomato, Open Images, COCO, ImageNet |
| `unverified` | Not confirmed at all | FruQ-DB, Kaggle sriramr, Mendeley fresh/rotten (BD), VegNet, XYZ, Ripen-banana, Roboflow, Kaggle leftin |

Image counts marked "verify" and folder names in `label_mapping.json` (`verified_against_download: false`) come from papers/READMEs and **must be confirmed after download**. The manifest builder fails on any unmapped file, so wrong assumptions surface as errors rather than silent mislabels.

## Recommended (subject to licence gate)

| Dataset | Use | Why | Caveat |
|---|---|---|---|
| **Own Israeli collection** | train + real-world test | Only source with Israeli varieties, real kitchens/markets, all 4 heads, physical-fruit IDs | Must be collected (see [roadmap](roadmap.md)) |
| **Grocery Store (Klasson)** | produce ID train + cross-dataset test | MIT (verified), real supermarket smartphone photos | Small (5,125); no quality labels |
| **Open Images V7 (produce subset)** | detection pre-stage, produce ID, OOD negatives | Real-world clutter, multi-object, CC BY | Per-image licence not warranted by Google — keep per-image metadata, drop unconfirmable |
| **FruitNet** | freshness (fresh vs not-fresh) | Phone photos, varied backgrounds, 6 fruits | "Bad" ≠ "rotten": mapped as set `{declining, spoiled}` |
| **Hass avocado ripening** | avocado ripeness | 5-stage expert index, 478 fruits tracked daily | Studio only; Hass only (Israel sells green-skinned Ettinger/Pinkerton/Reed); group by fruit |
| **Strawberry & avocado ripening** | strawberry ripeness | 4 stages incl. partially ripe | 91% augmented copies → originals only |
| **Fruits-360 original-size** | auxiliary produce-ID only | Many classes, CC BY-SA | Near-zero diversity; share-alike legal question; **never** used for evaluation |

## Excluded

| Dataset | Reason |
|---|---|
| Fruits-360 100×100 | Derivative (resized) of the original-size set — would double-count the same videos |
| Kaggle "fresh and rotten" (sriramr) | Undocumented provenance; rotated/flipped copies inflate published accuracies (leakage) |
| FruQ-DB | Frames from third-party YouTube videos — dataset authors likely cannot grant commercial rights. Research benchmark only |
| Laboro Tomato | CC BY-NC-SA — non-commercial; also on-vine greenhouse domain |
| COCO | Mixed per-image Flickr licences incl. NC |
| ImageNet images | Non-commercial terms |
| XYZ vegetable degradation | Colorimetric CSV, not photos; 5 samples/vegetable |
| Roboflow Universe | Frequent re-uploads of third-party data under new licences; case-by-case only |

## Duplicates and derivatives found

1. **Fruits-360 100×100 ⊂ Fruits-360 original-size** (same videos, resized).
2. **Fruits-360 frames**: every class is 1–few fruits rotating on a motor; consecutive frames are near-identical, and the official test split comes from the same capture setup. Any accuracy on its test split is not evidence of generalisation.
3. **Strawberry & avocado ripening**: 14,630 files from 1,333 originals.
4. **Kaggle fresh/rotten derivatives**: widely re-uploaded; rotated/flipped augmentations inside the set.
5. **FruQ-DB** re-hosted on Kaggle (`sholzz/fruitq-dataset`).
6. **Laboro Tomato** re-hosted on Roboflow Universe under different licence labels.
7. **Open Images / COCO**: both Flickr-sourced; possible image overlap → resolved by hashing.

Pipeline defence (`ml/preprocessing/dedup.py`): SHA-256 + decoded-pixel digest + rotation/flip-invariant pHash (Hamming ≤ 6, exact recall via 8-band multi-index hashing) + metadata groups (same physical fruit) → union-find clusters → cluster is the split unit, across datasets.

## Measured after ingestion

See [ingestion-report.md](ingestion-report.md): commercial manifest 3,676 images (Grocery Store, produce ID only); research manifest 34,175 images / 10,531 independent clusters (Grocery + Open Images + Fruits-360), still 0 ripeness/freshness labels.

## Estimated usable training data (Phase 1 estimates)

| Tier | Produce ID | Freshness | Ripeness |
|---|---|---|---|
| Commercially cleared **today** (gate passes automatically) | Grocery Store ≈ 4–5k produce images | **0** | **0** |
| After legal sign-off on CC BY rows | + Open Images produce crops (tens of thousands of boxes, noisy) | FruitNet ≈ 14.7k (6 fruits; apple/banana/orange/pomegranate relevant) | Hass avocado (478 physical fruits) + 1,333 strawberry/avocado originals |
| + Fruits-360 (if SA cleared) | +108k images but only ~150 physical objects of effective diversity | 0 | trivial (1 class per fruit) |

**Effective sample size = number of independent physical fruits, not image count.**

## Biggest gaps

1. **No commercially usable ripeness data for banana, tomato, mango, peach/nectarine, melon, grape** — the core Israeli use case.
2. **"declining" / "overripe" / mild spoilage** almost absent; public sets are mostly fresh-vs-rotten extremes.
3. **Israeli varieties**: green-skinned avocados, Israeli (Beit Alpha) cucumbers, Or/Orri mandarins, local persimmon, pomegranate cultivars.
4. **Real-world conditions**: most sets are studio/white background; few low-light, in-hand, in-bag, multi-object images.
5. **Ground truth for internal quality**: nothing links exterior appearance to cut-open interior.
6. **Israeli consumption data**: CBS / Plants Production & Marketing Board sites were unreachable from the build environment. Reported (secondary) figure: ~75 kg fruit/person/year. Priorities in `label_mapping.json` are provisional until official data is obtained.

## What we must collect ourselves

Protocol (details in [roadmap.md](roadmap.md) Phase 2b):

- **Longitudinal capture**: buy N fruits per type, give each a physical ID sticker, photograph daily until visible rot. Label = day + expert grading against a per-produce visual reference card (and cut-open check for a 10–20% subset). Yields real ripeness *and* freshness trajectories, and the fruit ID is the leakage-proof split key.
- **Target size (MVP)**: ≥ 60 physical fruits × ~8 days × 5 shots ≈ 2,400 images per produce type × 10 priority types ≈ 24k images; plus ≥ 2,000 "wild" real-world photos (markets, supermarkets, home) for the real-world test set, collected by people **not** involved in training data collection.
- **Conditions matrix**: ≥ 3 phone models (incl. older iPhone), daylight / kitchen LED / dim evening, in-hand / on counter / in bag / fruit bowl, 20–60 cm distance.
- **Negatives**: non-produce objects, plastic fruit, photos of screens, packaged produce → `other` class and OOD sets.
- Legal: contributor agreements; strip EXIF GPS; blur faces.
