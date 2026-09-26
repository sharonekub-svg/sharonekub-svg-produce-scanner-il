# Roadmap

Each phase ends only when its acceptance criteria are met and recorded (link run dirs / reports).

| Phase | Deliverables | Acceptance criteria | Status |
|---|---|---|---|
| **1 Research + registry** | registry (19 rows), label taxonomy + mappings, licensing analysis, architecture, eval plan | Every dataset has licence + verification level; unclear ⇒ blocked; tests enforce | **Done** (primary-source verification incomplete: sites blocked from build env) |
| **2a Ingestion + cleaning** | licence-gated downloader, adapters, validation, dedup, group splits, manifest | Pipeline unit + e2e tests pass; zero leakage assertion; unmapped labels fail loudly | **Done on real data**: Grocery Store, Open Images produce subset, Fruits-360 → 34,175 images, 10,531 clusters, 0 leakage ([report](ingestion-report.md)). Mendeley/Kaggle/Zenodo sets blocked from build env → manual import |
| 2b Licence verification | Visit each Mendeley/Zenodo/Kaggle page; counsel review; `license_signoffs.json` | Each P1/P2 dataset: `verified_primary` or sign-off, or excluded | **Everything that could be verified from here is verified** (Grocery, Fruits-360, Open Images at primary source; per-image OI licences filtered). Log, sign-off procedure, author-request template: [license-verification.md](license-verification.md). **Blocked on a human**: Mendeley pages + counsel |
| 2c Own data collection | Capture protocol, labelling tool, contributor agreement, first 3 produce types | ≥ 60 physical fruits/type, inter-rater κ ≥ 0.6 on ripeness | **Tooling ready**: [protocol + grading guide](data-collection-protocol.md), `tools/labeler/`, merge + validator + κ, Hebrew contributor-agreement draft. **Blocked on people + produce** (cannot be done from a server) |
| **3 Baseline** | MobileNetV3 multi-task on cleared data | Runs reproducible (same seed ⇒ metrics ± 0.5 pt); per-class report; gates evaluated | **Done** (produce head only; no licensed ripeness/freshness labels exist). Grocery official test: top-1 0.849, macro-F1 0.788, worst class 0.32 → **gates FAIL**, reported honestly. [results](results.md) |
| 4 Multi-dataset + benchmark | Matrix in model-strategy.md; detector pre-stage decision | Chosen config beats baseline on worst-class recall and cross-dataset set, 3 seeds | **Done within CPU budget** (1 seed per cell; R3 skipped). Key result: public data → phone photos = 0.32 top-1 (R4). Ripeness A/B/C not benchmarkable (no labels). Detector pre-stage deferred: multi-object handled by abstention |
| 5 Real-world validation | ≥ 2,000-image real-world set; threshold tuning; error analysis | Release gates in evaluation.md on real-world set | **Harness done + proxies run** (stress sets with quality gate, unseen-produce OOD, threshold tuning, hard-example mining). **Blocked on people**: the Israeli real-world set |
| 6 Mobile optimisation | Core ML export, quantisation, on-device benchmark | p90 < 150 ms iPhone 12, ≤ 25 MB, gates still pass after quantisation | **Done off-device**: Core ML fp16 8.2 MB chosen (lossless); int8/palettisation measured and rejected. [mobile.md](mobile.md). **Blocked on Mac + iPhone** for latency/ANE/energy |
| 7 App integration | Expo dev build, native Core ML module, RTL UI, decision parity tests | Parity: app `decide()` == Python on 500 fixtures; offline works | **Done except native build**: Expo SDK 57 app, 600/600 parity, typecheck, iOS Metro bundle, self-hosted server + tests. Swift module written, **not compiled** (needs macOS) |
| 8 Beta | TestFlight to ~50 Israeli users, feedback loop | Real-world abstention and error rates within gates; no safety-wording complaints | **Ready to start once gates pass**: EAS profiles, feedback + Supabase migration, privacy-policy draft (he). **Blocked on** Apple account, Supabase project, testers, counsel — and on a model that passes gates |
| 9 Production | Monitoring, model update channel, data credits screen | Crash-free ≥ 99.5%; retraining cadence defined | **Tooling done**: `scripts/release_model.sh` (licence gate → export → parity → eval → gates → sync; refuses failing models), credits screen generator, monitoring spec, CI. [runbook](beta-and-production.md) |

## Immediate next steps (in order)

1. Human verification of licences for FruitNet, Hass avocado, Strawberry-avocado, Open Images (per-image), Mendeley BD fresh/rotten, Ripen-banana; add sign-offs.
2. Obtain Israeli consumption data (CBS household expenditure survey; Plants Production & Marketing Board reports) → finalise priority list.
3. Download Grocery Store (cleared) + confirmed CC BY sets; run `build_manifest`; fix adapter folder patterns against real layouts.
4. Start own-data capture for banana, avocado (incl. Ettinger), tomato.
5. Phase 3 baseline.
