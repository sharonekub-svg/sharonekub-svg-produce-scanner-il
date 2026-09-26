# Architecture

## System

```
┌──────────── iPhone (Expo dev build, RTL Hebrew UI) ────────────┐
│ Camera ─► Quality gate ─► ProduceModel (native module) ─► decide() ─► Result screen │
│                           │ Core ML .mlpackage (ANE/GPU/CPU)                       │
│                           │ bundle.json: classes, temps, thresholds, supported_heads│
└──────────────────────────────────────────────────────────────────────────────────┘
          ▲ model bundle download (versioned, signed) — optional, Phase 7+
┌─────────┴────────┐
│ Supabase (only   │  model bundle hosting, opt-in feedback / photo donation,
│ where needed)    │  anonymous analytics. No inference, no third-party AI API.
└──────────────────┘

Offline ML (this repo):
registry.csv ─► download (licence-gated) ─► data/raw ─► build_manifest (validate, hash,
dedup, group split) ─► data/processed ─► train ─► calibrate ─► gates ─► export (ONNX/Core ML)
─► bundle.json
```

## Module boundaries

| Layer | Path | Contract |
|---|---|---|
| Registry + licence gate | `data/dataset_registry.csv`, `ml/preprocessing/registry.py` | `is_allowed(entry, purpose)` |
| Taxonomy | `data/label_mapping.json`, `ml/common/taxonomy.py` | head → class list; label = set of indices or unknown |
| Adapters | `ml/preprocessing/labels.py` | raw file → `RawSample(labels, group_key)`; unmapped = error |
| Manifest | `ml/preprocessing/build_manifest.py` | `manifest.jsonl` rows: image, dataset_id, group, split, labels |
| Training | `ml/training/*` | YAML config → run dir |
| Evaluation | `ml/evaluation/*` | numpy-only; reused by CI and app parity tests |
| Decision | `ml/inference/decision.py` | probs → `ScanResult` (Hebrew). **Reference implementation**; the app ports it 1:1 and parity-tests against JSON fixtures |
| Export | `ml/export/export.py` | `model.onnx`, `ProduceScanner.mlpackage`, `bundle.json` |

The app depends only on `bundle.json` + model file. Replacing the model (new backbone, new classes) requires no app code change as long as `bundle_version` is unchanged.

## Mobile deployment (iOS first)

**Recommended path**: PyTorch → `coremltools` (`torch.jit.trace`) → `.mlpackage`, FP16 first; then 8-bit weight palettisation/linear quantisation only if size/latency requires, re-checking gates after quantisation (calibration shifts). Normalisation is inside the graph; input is an `ImageType` (RGB, scale 1/255).

**Runtime in the app**: Expo *development build* (not Expo Go) with a small custom Expo Module in Swift that loads the `.mlpackage` via Core ML/Vision (`VNCoreMLRequest`) with `computeUnits = .all`. Rationale: direct Core ML gives the Neural Engine, lowest latency and smallest binary. Alternatives kept open: `onnxruntime-react-native` (Core ML EP) for a shared iOS/Android path; `react-native-fast-tflite` if Android becomes first.

**Must be measured on device (not yet done)**: p50/p90 latency (Core ML Performance Report in Xcode), ANE vs CPU op placement, peak memory, energy impact (Instruments) for 20 consecutive scans, cold-start load time. Test on the oldest supported device (proposal: iPhone 11/12).

**Fallback if on-device is not ready for first release**: run the *same* exported ONNX model on our own small CPU container (ONNX Runtime; e.g. Cloud Run / Fly.io, scale-to-zero), called from the app over HTTPS. Cost is roughly one small CPU instance; latency adds ~300–800 ms network. Privacy: photos processed in memory, not stored unless the user opts in. This is still our model — no third-party vision API. Given the model sizes measured (4–15 MB int8), on-device is expected to be feasible; the fallback exists only to decouple app launch from native-module work.

## Data stored

- On device: last N results (local only).
- Backend (opt-in only): donated photos + user feedback ("was this right?") → feeds the real-world set after review. Requires privacy policy (Israeli Privacy Protection Law / Amendment 13), EXIF stripping, face blurring.
