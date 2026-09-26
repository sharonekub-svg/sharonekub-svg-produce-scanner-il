# Licensing

> This document is engineering due diligence, **not legal advice**. Every dataset marked anything other than `verified_primary` + `yes` requires review by counsel before commercial use.

## Rules enforced in code

`ml/preprocessing/registry.py::is_allowed` — used by the downloader, manifest builder and `scripts/verify_licenses.py`:

1. `planned_use == exclude` → blocked for every purpose.
2. `commercial_training` is allowed only if:
   - `commercial_use == yes` **and** `license_verification == verified_primary`, **or**
   - a legal sign-off entry exists in `data/license_signoffs.json` with `decision: approved_commercial` (fields: `dataset_id, reviewer, date, evidence_url, decision`). A sign-off with any other decision blocks the dataset even if the registry says `yes`.
3. Unclear licence ⇒ `DO NOT USE COMMERCIALLY UNTIL VERIFIED` (tested: `tests/data/test_registry_and_mapping.py`).
4. Every import writes `data/raw/<id>/.provenance.json` (URL, licence, archive SHA-256 or git commit, date).

Today only **Grocery Store (MIT)** and **our own collection** pass the commercial gate automatically.

## Per-dataset risks

| Dataset | Licence | Risk | Action |
|---|---|---|---|
| Grocery Store | MIT (verified) | Low. Packaged goods show brands → drop `Packages/` | Keep MIT notice + citation |
| Fruits-360 | CC BY-SA 4.0 (verified) | **Share-alike**: whether trained weights are "Adapted Material" is legally unsettled. If yes, model weights might have to be CC BY-SA | Counsel opinion before including in a shipped model; pipeline treats it as `conditional_legal_review` |
| FruitNet, Hass avocado, Strawberry-avocado | CC BY 4.0 (reported) | Low if confirmed. Attribution required | Confirm on Mendeley page; add sign-off; add to in-app credits |
| Open Images V7 | Annotations CC BY 4.0; images "CC BY 2.0" without warranty | Per-image: some Flickr images may have changed licence | Keep per-image `License`/`Author` columns; drop rows with missing data; attribution file |
| FruQ-DB | Unknown; frames from YouTube | **High**: dataset authors likely lack rights to third-party video frames | Research only |
| Laboro Tomato | CC BY-NC-SA 4.0 | Non-commercial | Excluded; commercial licence from Laboro.AI if ever needed |
| COCO | Mixed per-image incl. NC | NC images | Excluded from training |
| Kaggle / Roboflow uploads | Often unknown or re-licensed third-party data | Provenance | Excluded unless original source traced |

## Pretrained backbone weights (important, often overlooked)

Most timm/torchvision ImageNet-pretrained weights were trained on ImageNet, whose terms restrict use to non-commercial research. Industry practice is to use them commercially, but this is a **legal gray area**. Options, in order of preference for counsel to decide:

1. Weights whose licence explicitly permits commercial use and whose training data terms are compatible (check each timm model card's `license` field).
2. Self-supervised pretraining on our own + permissively licensed images (costly).
3. Accept ImageNet-pretrained weights with documented legal sign-off.

The training config records `model.backbone` and `pretrained`; the export bundle records `model_id`, so the weight provenance of any shipped model is traceable.

## Attribution

Ship an in-app "Data credits" screen generated from `dataset_registry.csv` rows with `attribution_required=yes` that were used by the shipped model's manifest.
