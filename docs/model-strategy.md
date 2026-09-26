# Model strategy

**Status: no model has been trained on real data yet. No accuracy numbers exist.** The only runs so far are a synthetic-data smoke test (`tests/ml/test_e2e_smoke.py`) that proves wiring, not quality.

## Recommended architecture (hypothesis to be tested, not a conclusion)

```
photo ─► quality gate (blur/dark/overexposed, model-free) ─► retake message
      └► [Phase 4+] produce detector (crop + count; >1 dominant object ─► "one at a time")
      └► classifier: shared backbone
            ├─ produce head (22 types + "other" negative class)
            ├─ ripeness head   (Option A shared  | Option C per-produce rows)
            ├─ freshness head  (fresh / declining / spoiled)
            └─ visual-spoilage head (none / mild / severe)
      └► temperature scaling per head ─► OOD score (energy) ─► decision rules ─► Hebrew result
```

Why this default:
- **Multi-task with masked, set-valued losses** is the only way to use heterogeneous datasets without fabricating labels: FruitNet trains freshness only, Hass trains ripeness only, Grocery Store trains produce only. A per-head loss ignores unknowns; `{declining, spoiled}` trains the marginal (`ml/training/losses.py`).
- **Per-produce ripeness (Option C)** is likely needed because ripeness cues differ (banana: green→yellow→brown spots; Hass: green→black; tomato: green→red; green-skinned avocado: nearly none). Option C costs only `P×4` extra weights, so it is benchmarked in the same codebase (`model.ripeness_mode`).
- **Option B** (separate models) = same trainer with other head weights zeroed. It is the fallback if negative transfer appears.
- **Recommendation is rule-based** (`ml/inference/decision.py`), transparent and auditable, not learned.
- **Heads are gated per produce** (`supported_heads`): a head is only shown for a produce type with ≥200 exact train labels spanning ≥2 classes; otherwise the UI says "not available for this produce".

## Backbone candidates

Host-CPU measurement (Xeon 2.1 GHz, 1 thread, batch 1, 224², fp32, untrained multi-task net). **Relative ranking only — not phone latency.** Raw: [`benchmarks/host_cpu_untrained_2026-09-26.jsonl`](benchmarks/host_cpu_untrained_2026-09-26.jsonl).

| Backbone | Params (M) | fp32 MB | ~int8 MB | Host CPU ms (median) | Notes |
|---|---|---|---|---|---|
| mobilenetv3_large_100 | 4.2 | 16.2 | 4.0 | 14.6 | Baseline; well supported by Core ML / ANE |
| efficientnet_b0 | 4.1 | 15.4 | 3.9 | 22.4 | Strong accuracy/size; SiLU fine on ANE |
| efficientvit_b1 | 7.6 | 28.8 | 7.2 | 22.1 | Linear attention; verify ANE op coverage |
| mobilenetv4_conv_medium | 8.5 | 32.3 | 8.1 | 25.2 | Designed for mobile accelerators |
| fastvit_t8 | 3.3 | 12.5 | 3.1 | 34.5 | Apple-designed for ANE (reparameterise before export) |
| convnext_nano | 15.0 | 57.1 | 14.3 | 55.9 | Robustness candidate; larger |
| vit_small_patch16_224 | 21.7 | 82.7 | 20.7 | 74.3 | Upper bound; likely too big for v1 |

All candidates fit a mobile budget (< 25 MB int8). Selection criteria, in order: worst-priority-class recall on the **real-world** test set → calibration (ECE) → on-device latency p90 on the oldest supported iPhone → size.

## Benchmark matrix (Phase 3–4)

| Factor | Levels |
|---|---|
| Backbone | mobilenetv3_large_100, efficientnet_b0, mobilenetv4_conv_medium, fastvit_t8, convnext_nano |
| Head design | A shared · C per-produce · B separate models |
| Data | cleared-only · cleared + signed-off CC BY · + Fruits-360 aux |
| Augmentation | none · realistic (default) · realistic + background replacement for studio sets |
| Resolution | 224 · 256 |

Each cell: 3 seeds; report mean ± std on val, cross-dataset and (Phase 5) real-world sets. Choose by the criteria above, not by overall top-1.

## Training recipe

- AdamW, OneCycle, label smoothing 0.05, 30 epochs, batch 64, grad-clip 5; deterministic seeds; config snapshot + git hash per run (`runs/<exp>/<ts>/`).
- **Sampling**: class-balanced per head is the planned next step once real counts are known (avoid Fruits-360 dominating).
- **Augmentation** (`ml/training/augment.py`): crop 0.35–1, rotation ±30°, flips, brightness ±0.35, contrast ±0.3, **saturation ±0.15, hue ±0.01 only** (colour carries ripeness), soft shadows, blur, sensor noise, JPEG q35–95, background replacement for white-background sets. No mixup/cutmix on ripeness (mixes labels that are visual gradients).
- **Calibration**: per-head temperature scaling fit on val (`ml/evaluation/calibration.py`).
- **OOD**: energy score + explicit `other` class trained on negatives (non-target produce, packages, household objects from Open Images). Threshold chosen at 95% in-distribution TPR on val, reported on held-out OOD set.

## Image-quality model

Phase 3 ships a model-free gate (`ml/inference/quality.py`: luma mean, clipped fraction, Laplacian variance). Promote to a learned gate only if Phase 5 shows the heuristic misses >10% of bad photos; the "no produce"/"too many objects" cases are handled by the `other` class and the Phase 4 detector.

## What visual analysis cannot do

Internal browning (avocado), mould under the skin, pesticide residue, bacterial contamination and flavour are not observable from one exterior photo. The product must never phrase output as a safety guarantee (enforced in `decision.py` disclaimer and product spec).
