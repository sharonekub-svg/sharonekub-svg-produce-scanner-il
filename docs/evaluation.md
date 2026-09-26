# Evaluation

**No real evaluation results exist yet.** This file defines what will be measured and the pass criteria.

## Test sets

| # | Set | Construction | Purpose |
|---|---|---|---|
| 1 | Standard test | `split=test` from group-aware split of training datasets | In-distribution sanity |
| 2 | Cross-dataset | Whole datasets held out (`--holdout`, e.g. Grocery Store for produce ID) incl. any cross-dataset duplicates | Domain shift |
| 3 | **Real-world (primary)** | ≥2,000 photos from Israeli homes/markets, collected by people not involved in training capture, different phones | Release decision |
| 4 | Hard examples | Mined failures + adversarial-ish: plastic fruit, similar pairs (peach/nectarine, orange/mandarin, lemon/lime) | Robustness |
| 5 | Low-light | Real-world subset with mean luma < 70 (not synthetic darkening) | Robustness |
| 6 | Multi-object | Fruit bowls, bags, FruitNet "Mixed" (research only) | Detector / abstention |
| 7 | Unseen produce | Produce outside the 22 types (e.g. dragon fruit, lychee, fig, kohlrabi) + non-produce | OOD: must abstain |

Sets 3–7 are **never** used for training, threshold tuning or model selection except where stated (thresholds are tuned on val; set 3 is looked at only at phase gates).

## Metrics (all implemented in `ml/evaluation/`)

Per head: top-1, top-5 (produce), macro-F1, balanced accuracy, **per-class precision/recall/F1**, **worst-class recall**, confusion matrix, ECE (15 bins), Brier, NLL, AURC (selective risk), risk@coverage. OOD: AUROC and FPR@95%TPR (energy, MSP, entropy). System: host latency, on-device latency p50/p90, model size, peak memory. Only exactly-labelled samples are scored; set-valued labels are excluded from accuracy (they have no single truth).

## Leakage controls (tested)

- Split unit = union of exact dupes, re-encoded dupes, rotation/flip-invariant perceptual near-dupes, and same-physical-fruit metadata groups.
- `check_no_leakage` asserts no group spans splits (manifest build fails otherwise).
- Holding out a dataset also pulls every cluster that contains one of its images.
- Fruits-360 is never in any evaluation set.

## Acceptance gates (initial targets — revise after first real baseline)

Gates are config-driven (`gates:` in YAML; `ml/evaluation/gates.py`) so "95% overall but 60% on bananas" fails automatically.

| Head | Gate on real-world set (release) |
|---|---|
| Produce | macro-F1 ≥ 0.85; recall ≥ 0.90 for banana, apple, tomato, avocado, cucumber; ≥ 0.80 others; ECE ≤ 0.05 |
| Freshness | recall(spoiled) ≥ 0.90 (missing rot is the costly error); ECE ≤ 0.08 |
| Ripeness (per supported produce) | balanced accuracy ≥ 0.75, adjacent-class confusion allowed; unripe↔overripe confusion ≤ 2% |
| Abstention | ≥ 90% of unseen-produce images yield `unsure`/`not_produce`; coverage on in-scope real-world ≥ 80% |
| On-device | p90 < 150 ms end-to-end on iPhone 12; model ≤ 25 MB |

A head that fails its gate ships as "not available" for that produce — it is not shipped with a disclaimer instead.

## Reporting template (per run)

`runs/<exp>/<ts>/`: `config.yaml`, `git.txt`, `metrics.jsonl`, `val_summary.json` (all metrics per head per class), `temperature.json`, `gates.json`. Comparison tables in this file must link the run directory and state seeds.
