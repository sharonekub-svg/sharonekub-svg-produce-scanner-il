# Mobile deployment (Phase 6) — measured results and decision

All numbers below were measured in the Linux build environment on the Phase 3 baseline (`runs/p3_baseline_commercial_mnv3/…`, MobileNetV3-L, 224 px), using the Grocery Store official test split (n = 1,704). Raw data: `exports/p3_baseline/verify_report.json` and `runs/…/weight_quant_sim.json`. **No iPhone measurement exists yet.**

## Export variants

| Variant | Size | top-1 | macro-F1 | worst-class recall | Agreement with fp32 | Host CPU p50 (1 thread)* |
|---|---|---|---|---|---|---|
| PyTorch fp32 (reference) | — | 0.849 | 0.788 | 0.32 | — | — |
| ONNX fp32 | 16.5 MB | 0.849 | 0.788 | 0.32 | 100% (max logit diff 0.0) | 4.7 ms |
| ONNX static int8 (QDQ, per-channel, 256 val images calibration) | 4.5 MB | 0.788 | 0.681 | 0.17 | 87.0% | 5.6 ms |
| Core ML fp16 (ML Program) | 8.2 MB | 0.850† | 0.788† | 0.32† | 99.9%† | not measurable on Linux |
| Core ML 8-bit palettised (per-tensor k-means) | ~4 MB | 0.821† | 0.739† | 0.07† | 94.1%† | — |
| Core ML 6-bit palettised | ~3 MB | 0.703† | 0.568† | 0.00† | 78.1%† | — |

\* Measured while other training jobs were running on the same 4-core Xeon, so treat these as relative numbers only.
† Simulated in PyTorch by applying the same weight transform (`ml/export/simulate_weight_quant.py`). Core ML itself cannot execute on Linux.

## Decision

**Ship the Core ML fp16 ML Program** (8.2 MB).
- **fp16:** it is numerically equivalent to fp32 (99.9% top-1 agreement) and within the 25 MB budget.
- **Static int8:** rejected. It fails the rule that gates must still pass after quantization (−6 points top-1; worst class 0.32 → 0.17) and is not faster on CPU. MobileNetV3's hard-swish and squeeze-excite layers are known to be quantization-sensitive.
- **Palettization:** not needed at this size. Per-tensor 8-bit already hurts the worst class. If size ever matters, re-test per-grouped-channel palettization or quantization-aware training.

## On-device plan (requires a Mac and iPhones; not possible in this environment)

1. `cd app && npx expo prebuild -p ios && npx expo run:ios --device` (or `npx eas-cli@latest build --profile development --platform ios`).
2. `scripts/sync_model_to_app.sh exports/<version>` copies `ProduceScanner.mlpackage` into `app/modules/produce-model/models/`. The Swift module compiles it on first launch and caches the `.mlmodelc`.
3. **Parity check.** For 50 test images, compare on-device logits (debug log from `ProduceModelModule.analyze`) with `server/app.py` `/v1/analyze` on the same JPEGs. Top-1 must agree ≥ 99%, and the quality-gate reasons must match exactly.
4. **Performance.** Use the Xcode Core ML Performance Report plus Instruments (Time Profiler, Energy Log). Record:
   - cold model load (first compile plus load)
   - warm p50/p90 latency for `analyze`
   - how many ops run on the Neural Engine versus the CPU
   - peak memory
   - energy impact over 20 consecutive scans

   Test on the oldest supported device (proposed: iPhone 11/12) and on one current model.
5. **Gates** (from evaluation.md): end-to-end p90 < 150 ms on iPhone 12, model ≤ 25 MB, and Neural Engine placement for ≥ 90% of ops.

## Fallback

If the native module is not ready for release, set `app.json → extra.inference = {"mode": "remote", "serverUrl": "https://…"}`. The app then calls our own `server/app.py` (Dockerfile provided), which runs the same ONNX model on 1–2 vCPUs with scale-to-zero. The UI and the decision logic are unchanged. The server receives a downscaled 768-px JPEG, keeps it in memory only, and returns logits.
