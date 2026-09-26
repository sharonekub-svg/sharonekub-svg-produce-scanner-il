# Licence verification log (Phase 2b)

Status legend: ✅ verified at primary source · 🟡 reported only (primary page unreachable from build env) · ❌ unverified · ⛔ excluded.

| Dataset | Status | Evidence | Remaining action (owner: human with unrestricted web + counsel) |
|---|---|---|---|
| Grocery Store | ✅ MIT | `LICENSE` in cloned repo; commit pinned in `.provenance.json` | None. Keep MIT notice in credits |
| Fruits-360 original | ✅ CC BY-SA 4.0 | `LICENSE` in cloned repo | **Counsel**: are trained weights "Adapted Material"? Until answered: research only |
| Open Images V7 | ✅ annotations CC BY 4.0; images "CC BY 2.0" (no warranty) | Fetched facts page 2026-09-26; per-image `License` column filtered to CC BY 2.0 → `attribution.csv` | **Counsel**: accept Google's per-image metadata as sufficient diligence? Then add sign-off |
| FruitNet | 🟡 CC BY 4.0 | Search snippets of Mendeley + Data in Brief | Open https://data.mendeley.com/datasets/b6fftwbr2v/3, screenshot licence box, record in sign-off |
| Hass avocado ripening | 🟡 CC BY 4.0 | Search snippet of Mendeley | Same, https://data.mendeley.com/datasets/3xd9n945v8/1 |
| Strawberry & avocado ripening | 🟡 "CC BY" (version unknown) | Search snippet | Same, https://data.mendeley.com/datasets/zysvgmxcyz/1; confirm version (4.0?) |
| Mendeley fresh/rotten (BD) | ❌ | — | Check https://data.mendeley.com/datasets/bdd69gyhv8/1 |
| Ripen banana | ❌ | — | Find data repository from the PMC article, check licence |
| VegNet | ❌ | — | Find data repository from the Data in Brief article |
| FruQ-DB | ❌ + provenance risk | Frames from third-party YouTube videos | Email authors (template below); default: research only |
| Kaggle leftin ripeness | ❌ | — | Inspect Kaggle page; trace original source |
| Laboro Tomato | ⛔ CC BY-NC-SA 4.0 | GitHub README snippet | Only if a commercial licence is purchased from Laboro.AI |
| COCO, ImageNet, Kaggle sriramr, Roboflow, XYZ, Fruits-360 100×100 | ⛔ | see registry | — |

## How to record a sign-off

Append to `data/license_signoffs.json`:

```json
{"dataset_id": "fruitnet_indian", "reviewer": "<name, role>", "date": "YYYY-MM-DD",
 "evidence_url": "https://data.mendeley.com/datasets/b6fftwbr2v/3",
 "decision": "approved_commercial",
 "notes": "Licence box shows CC BY 4.0; attribution text: ..."}
```

`decision` ∈ `approved_commercial`, `research_only`, `rejected`. Then set the registry row's `license_verification` to `verified_primary` and fill `license_evidence`. `scripts/verify_licenses.py` shows the effect; the test suite checks the file's schema.

## Permission request template (for FruQ-DB and any unclear dataset)

> Subject: Commercial-use permission for <dataset> in a produce-freshness app
>
> Dear <authors>,
>
> We are developing a consumer mobile app (Israel) that estimates fruit ripeness and visible spoilage using our own on-device model. We would like to use <dataset> (<DOI>) as part of our training data.
>
> 1. Under which licence is the dataset released, and does it permit commercial use of models trained on it?
> 2. Do you hold the rights to all images (in particular <frames taken from third-party videos / images collected from the web>)?
> 3. How would you like to be credited?
>
> We will cite your paper in the app's data-credits screen. Thank you,
> <name, company>
