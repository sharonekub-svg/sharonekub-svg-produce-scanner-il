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
| Acceptance gates on test | ❌ 8 per-class recall failures (see above) → **internal dev build only; NOT releasable to users** |
| Synced into app | ✅ `app/assets/model/bundle.json`, credits, `ProduceScanner.mlpackage`; app typecheck, 604 tests and iOS bundle pass |
| End-to-end via self-hosted server (real photos) | ✅ avocado/tomato identified; banana at 0.52 → "unsure"; asparagus → "not produce"; dark photo → "retake"; satsuma → "orange" at 1.00 (known citrus confusion) |
| Ripeness / freshness / spoilage | Unsupported (no licensed labels). The app shows "not available yet for this type" and the recommendation "check manually" |

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
