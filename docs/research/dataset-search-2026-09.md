# Dataset search, 27 Sep 2026: GitHub, Mendeley, Kaggle, Hugging Face, AgML

Question: can public internet photos replace our own Israeli collection? Short answer: they help, but they don't replace it.

- **We can't use "millions of internet photos".** Web images are copyrighted by their photographers. A commercial model may train only on data whose licence allows it (CC BY, CC0, MIT, Apache), and the licence must come from the person who took the photos, not from someone who re-uploaded them.
- **Few public sets have ripeness labels**, and most of those are lab or studio captures.
- **Public data transfers poorly.** Measured here: training on Open Images and Fruits-360 gives 0.32 top-1 on real phone photos (results.md, R4).

## A. Downloaded, licence verified at the primary source, integrated (GitHub is reachable from the build environment)

| Dataset | Licence (evidence) | What it adds | Integrated as |
|---|---|---|---|
| [SoftwareMill lemon quality control](https://github.com/softwaremill/lemon-dataset) | MIT (README in the cloned repo) | 2,690 lemon photos, 35 fruit/batch ids, COCO regions for **mould, gangrene, illness, blemish**. Studio, black background. | `lemon_softwaremill`: produce = lemon; mould/gangrene → spoilage {mild, severe} + freshness spoiled; clean → spoilage none (`scripts/prepare_lemon_softwaremill.py`). Training run C7 measures whether it helps lemon on phone photos. |
| [psolymos/bananas](https://github.com/psolymos/bananas) | MIT (LICENSE + DESCRIPTION) | 11 bananas × 20 days, author ripeness labels: under / ripe / very / over; fridge vs room | `bananas_psolymos`: ripeness labels for room-temperature fruit only (fridge browning is chilling, not ripeness). **Used to validate banana colour grading** (below). |

## B. Strong candidates, reported CC BY 4.0, but the host (Mendeley Data) is blocked from the build environment

CC BY 4.0 allows commercial use with attribution. Each one still needs its primary landing page read, and a check that the photos were taken by the authors.

| Dataset | Content | Why it matters |
|---|---|---|
| ['Hass' Avocado Ripening Photographic Dataset](https://data.mendeley.com/datasets/3xd9n945v8/1) | 14,710 photos of **478 fruits**, 5-stage ripening index, with firmness and days tracked | Best ripeness set found. Hass only; green-skinned Israeli cultivars need our own data. |
| [Strawberry & avocado ripening](https://data.mendeley.com/datasets/zysvgmxcyz/1) ([paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12152553/)) | 1,333 originals (14,630 with augmentations): unripe / partially ripe / ripe / rotten | Strawberry ripeness and rot |
| [Mango and Banana ripe/unripe](https://data.mendeley.com/datasets/y3649cmgg6/3) | 5,000 photos, indoor and outdoor | Banana and mango ripeness in varied light |
| [Alphonso mango ripening stages](https://data.mendeley.com/datasets/tyghd6gxw2/1) | 750 photos, 3 stages | Mango (single cultivar; the colour cue is cultivar-dependent) |
| [Ripening detection of mango](https://data.mendeley.com/datasets/mm8g66d7rc/1) | 4 ripeness levels | Mango |
| [BananaImageBD](https://www.sciencedirect.com/science/article/pii/S2352340924012010) | 4 varieties; green / semi-ripe / ripe / overripe | Banana ripeness. Varieties differ from Israeli Cavendish. |
| [Ripen banana](https://pmc.ncbi.nlm.nih.gov/articles/PMC12151241/) | 1,404 originals, natural vs carbide ripening | Banana ripeness |
| [FruitNet](https://data.mendeley.com/datasets/b6fftwbr2v/3) | about 14.7k, good / bad quality (apple, banana, orange, pomegranate, guava, lime) | Freshness head |
| [FruitVision](https://data.mendeley.com/datasets/xkbjx8959c/2) | fresh / rotten / formalin, 5 fruits (81k, mostly augmented) | Freshness. Check how many originals. |

The **"CC BY" printed on a Data in Brief article covers the article, not the images.** The dataset's own page is what counts.

### B2. More candidates, by fruit (all on hosts blocked here; licence to verify on each landing page)

| Produce | Candidate | Content | Note |
|---|---|---|---|
| Apple | [Good and bad classification of apple](https://data.mendeley.com/datasets/n2gsjb3vk3/1) | good vs bad (mould, bruise, cut, rot) | Freshness/spoilage. Apple ripeness is not visual. |
| Apple | Healthy-defective fruits ([paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10537567/)) | fresh / bruise / rot / scab | Early bruises are invisible in RGB (produce-science.md) |
| Grapes | [GrapeNet](https://data.mendeley.com/datasets/3j3zzsc7wb/1) | 25,425 photos, 3 varieties, freshness subcategories | Freshness |
| Pomegranate, grapes and 14 more | [Fresh and rotten fruits for machine-based quality evaluation](https://data.mendeley.com/datasets/bdd69gyhv8/1) | 3,200 photos, 16 fresh/rotten classes | Freshness |
| Pomegranate | [Pomegranate images](https://data.mendeley.com/datasets/kgwsthf2w6/5) | 5,857, growth stages on the tree | Orchard, off-domain |
| Peach | [Hairy peach ripeness](https://www.scidb.cn/en/detail?dataSetId=d44f02c0fb6543eba6210f39b36240ff) | 1,245 smartphone photos, 3 stages | Orchard, but smartphone. Peach is `cultivar_dependent`. |
| Cucumber | Cucumber disease and freshness (Zenodo, DOI 10.5281/zenodo.16816441) | CC BY 4.0 (reported) | Freshness |
| Several | [Multimodal perishable fruits and vegetables](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12925515/) | Daily sRGB + thermal, unripe → spoiled | Time series: the right design for freshness |
| Watermelon / melon | [Qilin watermelon](https://github.com/crf0409/watermelon_eval) | Photos + tapping sound + sugar | CC BY-NC (rejected). It also shows watermelon ripeness is in the sound, not the image. |
| Pear, plum, kiwi, persimmon, guava, pepper, zucchini | Nothing licence-clean with quality labels found | — | Use the web-CC crawl (§E) + our own collection |

## C. Rejected (and why)

| Source | Reason |
|---|---|
| [LaboroTomato](https://github.com/laboroai/LaboroTomato), [tomatOD](https://github.com/up2metric/tomatOD), [strawberry-pp-w-r](https://github.com/imanlab/strawberry-pp-w-r-dataset) | Non-commercial licences (CC BY-NC(-SA)). [Tomato-Segmentation-with-YOLOv8](https://github.com/JeanN00B/Tomato-Segmentation-with-YOLOv8) is Apache, but its images are LaboroTomato, and a repo licence can't relicense someone else's photos. |
| [afeefaaazam03/Tomato_dataset](https://github.com/afeefaaazam03/Tomato_dataset), [CFD-DETR-Dataset](https://github.com/Daric-Weng/CFD-DETR-Dataset), [banana-ripeness-classification](https://github.com/giovannipcarvalho/banana-ripeness-classification), [Tomato-ripening-stages](https://github.com/subedisandesh24/Tomato-ripening-stages) | No licence file = all rights reserved |
| Most Kaggle "fresh/rotten" sets, including ones labelled CC0 | Re-uploads of other datasets or web scrapes; the uploader can't grant rights they don't hold |
| [BananaRipeness](https://github.com/luischuquim/BananaRipeness) (161k images) | Synthetic brightness variants, no licence |
| AgML catalogue (UC Davis, `pip download agml`) | Orchard and field imagery (fruit on the plant), not produce in a kitchen |
| Web image search / scraping | Copyright. Not usable for a commercial model. |

## D. Colour grading: can we grade ripeness from peel colour?

For the "strong" produce in [produce-science.md](produce-science.md), official colour scales already define ripeness:

- **Tomato:** [USDA colour classification (7 CFR 51, Subpart S)](https://www.ecfr.gov/current/title-7/subtitle-B/chapter-I/subchapter-C/part-51/subpart-S/subject-group-ECFR23199cd1e0bd4d1). Green; Breakers ≤ 10% of the surface coloured; Turning 10–30%; Pink 30–60%; Light red > 60% with ≤ 90% red; Red > 90%.
- **Banana:** peel colour index 1–7 (all green → yellow with brown flecks); see [USDA AMS banana ripening guide](https://www.ams.usda.gov/sites/default/files/media/Bananas_Visual_Aid[1].pdf).

**Built:** `ml/colour/banana.py` measures the green / yellow / brown fractions of the peel. `ml/colour/eval_bananas.py` validates it on psolymos/bananas with leave-one-fruit-out (fitted on 10 bananas, tested on the 11th):

| | All 11 fruits (220 photos) | Room temperature only (6 fruits, 120 photos) |
|---|---|---|
| Exact stage (under / ripe / very / over) | 82.7% | 85.8% |
| Within one stage | 100% | — |
| 3 classes (under / ripe / very-or-over) | 95.5% | 95.0% |

**Not yet in the app, deliberately.** These photos are masked on white, so the test covers colour → stage but **not finding the banana in a cluttered kitchen photo**. A wooden counter would be counted as "brown". Before the app can show a colour grade it needs:
1. fruit segmentation (a small mask model or on-device saliency), and
2. validation on phone photos. This is the cheapest data task in the whole project: buy green bananas and tomatoes, photograph them daily on different counters (data-collection-protocol stream A). In one week that yields the full colour range, with our own labels.

## E. Openly licensed web photos (Openverse and Wikimedia Commons): the "internet photos" route, done legally

[Openverse](https://openverse.org/about) indexes about 800 million openly licensed images, mostly Flickr, and exposes each image's licence through an anonymous API. [Wikimedia Commons](https://commons.wikimedia.org/wiki/Category:Unripe_fruit) has per-file licences in its API. Its ripeness and rot categories are small, for example [Rotting tomatoes](https://commons.wikimedia.org/wiki/Category:Rotting_tomatoes) has 11 files.

**Built:** `scripts/fetch_web_cc.py`, tested offline in `tests/test_fetch_web_cc.py`.
- It keeps **only CC0, Public Domain and CC BY** (no NC, ND or SA). It drops Commons files that carry personality or trademark restrictions.
- It re-encodes every photo, which strips GPS, and writes `attribution.csv` (licence, creator, landing page) for the credits screen.
- The search term is saved as a *hint*, never as a label. Every photo is graded by a person before training.

This source is **real-world and phone-like**: kitchens, markets, rot and mould, the imagery public datasets lack. It needs grading, but grading about 200 photos per fruit and state takes about an hour each.

**Crawl plan for every produce type:** `data/web_cc_queries.json` holds 149 queries, run by `python scripts/fetch_web_cc.py plan`.
- Every type gets identification and rot/mould queries.
- Unripe/ripe/overripe queries run **only** for types whose ripeness is visible (`ripeness_visual` = strong or cultivar_dependent). Apples, pears, citrus, melons, watermelon, grapes, pomegranate, persimmon, cucumber and pepper get no ripeness hints, because colour carries no ripeness evidence for them (test: `test_plan_covers_every_supported_produce`).

Examples (hint → what graders confirm):

| Query / category | Hint | Graded into |
|---|---|---|
| "overripe banana", "brown banana", "green banana", "banana bunch kitchen" | banana | ripeness (colour index) |
| "ripe avocado", "avocado halves", "hass avocado", "green avocado" | avocado | produce ID; ripeness only for Hass (produce-science.md) |
| "moldy fruit", "mouldy orange", "rotten tomato", "moldy strawberries", Commons "Rotting tomatoes" | spoiled | visual spoilage / freshness |
| "unripe tomato", "green tomatoes", "tomatoes ripening windowsill" | tomato | USDA colour stage |
| "clementine", "mandarin orange", "lemon", "lime", "grapefruit", "pomelo" | citrus | produce ID (our weakest classes) |
| "mango", "persimmon", "pomegranate", "prickly pear", "kiwi" | ID | produce ID |

## F. What unblocks sections B and E

1. **Network:** allow these in the environment's network settings:
   - Mendeley: `data.mendeley.com`, `prod-dcd-datasets-cache-zipfiles.s3.eu-west-1.amazonaws.com`
   - Openverse: `api.openverse.org`, `live.staticflickr.com`
   - Wikimedia: `commons.wikimedia.org`, `upload.wikimedia.org`
   - optional: `zenodo.org`, `huggingface.co`

   Kaggle also needs a Kaggle API token, and most Kaggle fruit sets fail provenance anyway.
2. **Then (here):** download each set, read and save the primary licence page as evidence, check the photos are the authors' own, write the adapter and train. Target: avocado (Hass), banana, strawberry and mango ripeness; freshness from FruitNet.
3. **Grading (people, about 1 h per 200 photos):** web photos go through `tools/labeler` before they can train.
4. **Owner sign-off:** add an `approved_commercial` entry per dataset in `data/license_signoffs.json`. That is the licence gate the build enforces.
