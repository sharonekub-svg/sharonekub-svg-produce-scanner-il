# Israeli Fruit & Produce Scanner (סורק פירות וירקות)

Photograph a fruit or vegetable → our own on-device computer-vision model estimates **produce type, ripeness, freshness and visible spoilage**, and returns a Hebrew recommendation with a visual-only disclaimer. No third-party vision API.

> **Status (all phases worked through; see [roadmap](docs/roadmap.md) and [results](docs/results.md)):**
> - **Trained and measured:** a produce-identification model (MobileNetV3-L) trained only on commercially-cleared data. On unseen supermarket phone photos it reaches top-1 0.892 and macro-F1 0.851, but it **fails the per-class gates** (citrus, mango, cucumber and 5 more). Build `v0.1-dev` is therefore an internal dev build, **not releasable**.
> - **Working and tested here:** the Expo app, the parity-tested decision logic, the self-hosted inference server, the Core ML fp16 export, the release pipeline, CI.
> - **Not possible here:** ripeness, freshness and spoilage. No legally usable labelled data was reachable, so those heads are unsupported and the app says so.
> - **Blocked on people and devices:** the Israeli photo collection and real-world test set, licence sign-offs, a Mac/iPhone build with on-device benchmarks, TestFlight beta.
> - **Strongest measured finding:** public web and studio data scores 0.32 top-1 on phone photos, so our own data collection is the critical path.


## Docs

| | |
|---|---|
| [product-spec](docs/product-spec.md) | UX, Hebrew wording rules, MVP scope |
| [architecture](docs/architecture.md) | System, module contracts, iOS deployment |
| [datasets](docs/datasets.md) | Registry summary, duplicates, data estimate, gaps, own collection |
| [licensing](docs/licensing.md) | Licence gate, risks, pretrained-weights issue |
| [model-strategy](docs/model-strategy.md) | Architecture options, backbone benchmark, training recipe |
| [evaluation](docs/evaluation.md) | 7 test sets, metrics, leakage controls, gates |
| [roadmap](docs/roadmap.md) | Phases 1–9 with acceptance criteria |
| [ingestion-report](docs/ingestion-report.md) | Phase 2 real-data run: counts, duplicates, defects found |
| [license-verification](docs/license-verification.md) | Per-dataset evidence, sign-off procedure, author request template |
| [data-collection-protocol](docs/data-collection-protocol.md) | Own Israeli data: capture, grading guide, QA, legal |
| [results](docs/results.md) | **All measured results**: baseline, benchmark matrix, stress/OOD validation, export, release candidate |
| [mobile](docs/mobile.md) | Export/quantisation measurements, Core ML fp16 decision, on-device plan |
| [competitor-ux-research](docs/competitor-ux-research.md) | 7 scanner apps × 20 UX dimensions, patterns to adopt/avoid |
| [ux-principles](docs/ux-principles.md) | Our UX principles + final v1 UI architecture |
| [beta-and-production](docs/beta-and-production.md) | Beta entry/exit criteria, release checklist, monitoring, retraining |

## Layout

```
data/dataset_registry.csv    every candidate dataset, licence, verification level, planned use
data/label_mapping.json      unified taxonomy + per-dataset source→unified label rules (Hebrew labels)
data/license_signoffs.json   human legal approvals (empty until reviewed)
ml/preprocessing/            registry gate, image validation, hashing, dedup, splits, manifest builder
ml/training/                 multi-task model, partial-label loss, realistic augmentation, trainer
ml/evaluation/               metrics, calibration, OOD, acceptance gates (numpy only)
ml/inference/                quality gate + decision/Hebrew result (reference for the app)
ml/export/                   ONNX / Core ML export + bundle.json, backbone benchmark
ml/configs/                  YAML experiment configs
scripts/                     download/fetch, licence check, dedup review, label audit, collection merge/validate
tools/labeler/               offline Hebrew labelling tool (single HTML file)
tests/                       data/, ml/ (incl. end-to-end smoke), app/ (Phase 7)
app/                         mobile app (Phase 7 — not started by design)
```

## Reproduce

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt           # torch/timm needed for training + model tests
pip install onnx onnxruntime onnxscript   # export tests (optional)
python -m pytest -q                       # 49 tests: registry/licence rules, mapping, dedup, splits,
                                          # metrics, calibration, decision, model, e2e smoke

# 1. See what may be used for what
python scripts/verify_licenses.py

# 2. Fetch data (licence-gated; blocked datasets refuse)
python scripts/download_datasets.py --purpose commercial_training --datasets grocery_store_klasson
python scripts/download_datasets.py --purpose research_training --datasets fruitnet_indian \
       --import-archive ~/Downloads/fruitnet.zip   # login-walled sources: manual download

python scripts/fetch_open_images.py --per-class 400 --workers 24   # produce crops, per-image CC BY 2.0 only

# 3. Build the deduplicated, leakage-safe manifests (see docs/ingestion-report.md for the real run)
python -m ml.preprocessing.build_manifest --purpose commercial_training \
       --datasets grocery_store_klasson --out data/processed_commercial
python -m ml.preprocessing.build_manifest --purpose research_training \
       --datasets grocery_store_klasson open_images_v7 fruits360_original --out data/processed_research
python scripts/verify_licenses.py --manifest data/processed_commercial/manifest.jsonl --purpose commercial_training
python scripts/review_duplicates.py --processed data/processed_research          # dedup QA sheet
python scripts/audit_samples.py --processed data/processed_research --dataset open_images_v7 --classes banana

# Own collection (docs/data-collection-protocol.md): label with tools/labeler/index.html, then
python scripts/merge_annotations.py --root data/raw/own_il_collection annotations_*.csv
python scripts/validate_collection.py --root data/raw/own_il_collection --agreement

# 4. Train (writes runs/<experiment>/<timestamp>/ with metrics, checkpoints, temperatures, gates)
python -m ml.training.train --config ml/configs/baseline_mobilenetv3.yaml

# 5. Export + release (licence gate -> export -> parity -> eval -> gates -> sync into app)
python scripts/fetch_weights.py
scripts/release_model.sh runs/<exp>/<ts> data/processed_commercial v1     # refuses models failing gates
python -m ml.export.export --ckpt runs/<exp>/<ts>/best.pt --out exports/v0 [--coreml --fp16] [--int8-calib data/processed_commercial]
python -m ml.export.benchmark            # host-CPU relative latency/size of candidate backbones
```

Determinism: fixed seeds, `torch.use_deterministic_algorithms`, stable hash-based split assignment; each run stores its config and git commit.

## Principles

- Publicly downloadable ≠ commercially usable. Unclear licence ⇒ blocked (enforced in code).
- Never fabricate labels: coarse labels become set-valued or unknown, trained with a marginal likelihood.
- Augmented copies and same-fruit photos always share a split.
- Report per-class metrics and calibration; a model with a weak priority class fails its gate.
- Visual assessment only — never a food-safety guarantee.
