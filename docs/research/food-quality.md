# Food quality at home: evidence behind the app's advice

What the app tells a user beyond the model's output (storage, ripening, mould) comes from official or extension sources. It lives in one file, `app/src/model/produce_care.json`, which is tested by `tests/test_produce_care.py`. [produce-science.md](produce-science.md) covers what a *photo* can tell. This page covers what to *do* with the fruit.

> Verification note: gov.il, USDA and UC Davis pages are blocked by this build environment's network policy, so the claims below were checked through search-engine excerpts of those pages and through secondary extension sources, not by reading the originals. Re-read the primary pages before public launch (checklist item in beta-and-production.md).

## 1. Mould: discard whole (Israeli Ministry of Health)

| Source | Rule |
|---|---|
| Israeli Ministry of Health warning, reported by [Maariv](https://www.maariv.co.il/news/health/article-1170427) | Throw away mouldy food whole. Do not cut out only the mouldy part: mould particles can spread through the whole food, including parts where no mould is visible yet. |
| USDA FSIS "Molds on Food", via [UConn Extension](https://extension.uconn.edu/publication/handling-food-with-mold/), [UC Master Food Preserver](https://ucanr.edu/program/uc-master-food-preserver-program/article/mold-cut-or-toss-april-2025) and [NC State Extension](https://brunswick.ces.ncsu.edu/2024/09/moldy-foods-use-or-pitch) | Soft, high-moisture produce (strawberries, peaches, cucumbers, tomatoes): discard. Firm produce (cabbage, bell peppers, carrots): cut away at least 1 inch (2.5 cm) around and below the spot. |

**Implemented:** we follow the stricter local rule. Whenever the recommendation is "discard", `decide()` in Python and its TS port add `MOULD_RULE_HE` to the explanation ("לפי משרד הבריאות: מזון שצמח עליו עובש – לזרוק בשלמותו…"). The app never suggests cutting mould out, and it never says "safe" (tested). Consistent with produce-science.md, the app also does not claim to *detect* mould reliably. The spoilage head is unsupported until licensed labelled data exists.

## 2. Fridge or counter (Israeli Ministry of Agriculture, UC Davis)

| Finding | Source |
|---|---|
| Home fridge is 4–6 °C. Cold-sensitive produce such as bananas should not be refrigerated at all. Unripe fruit (green tomatoes, avocado, kiwi, hard peaches) ripens on the counter first, then goes in the fridge. Best storage temperature for an orange/red tomato is 21 °C. Cucumber doesn't like cold, so keep it in the vegetable drawer. | [Ministry of Agriculture consumer storage guidelines](https://www.moag.gov.il/subject/the_food_we_eat/Storage_Guidelines_For_Fruits_Vegetables/Pages/Storage_Guidelines_consumer.aspx) |
| Chilling-injury thresholds: banana < 13 °C, tomato and mango < 10 °C, cucumber < 7 °C, avocado < 5–7 °C (cultivar-dependent). Damage often shows only after the fruit warms up again. | UC Davis PREC fact sheets ([cucumber](https://postharvest.ucdavis.edu/produce-facts-sheets/cucumber), [banana](https://postharvest.ucdavis.edu/produce-facts-sheets/banana), [avocado](https://postharvest.ucdavis.edu/produce-facts-sheets/avocado)); [IIR cold-storage conditions](https://iifiir.org/en/encyclopedia-of-refrigeration/cold-storage-conditions-for-fruits-and-vegetables); [Cornell CCE cold storage chart](https://rvpadmin.cce.cornell.edu/uploads/doc_500.pdf); tomato chilling review [PMC11586204](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11586204/) |
| Refrigerated storage times: citrus 1–3 weeks; apples 3–4 weeks in a separate bag; wash only just before eating, because moisture speeds rot. | USDA/FMI FoodKeeper, via [Virginia Tech Extension 348-960](https://www.pubs.ext.vt.edu/348/348-960/348-960.html) and the [FoodKeeper PDF](https://ifdaonline.org/wp-content/uploads/2024/02/food-keeper-2015-pdf.pdf) |

**Implemented:** `fridge` (`no` / `after_ripening` / `yes`) and `chill_below_c` per produce, with the tip text written to match. Two corrections to the v0.1 tips: bananas are no longer told they can go in the fridge (Ministry of Agriculture: not at all), and cucumber goes in the drawer (the warmer part) and is eaten within days.

## 3. Ethylene: what to keep apart

| Finding | Source |
|---|---|
| High ethylene producers: apples, avocados, bananas, pears, peaches, tomatoes (moderate). Kiwifruit is extremely ethylene-sensitive. Sensitive vegetables include cucumbers, peppers and summer squash. Store producers away from sensitive produce. | [UCSD Community Health, *Ethylene in fruits and vegetables*](https://ucsdcommunityhealth.org/wp-content/uploads/2017/09/ethylene.pdf); [Lancaster Farming](https://www.lancasterfarming.com/country-life/food-and-recipes/keep-fruit-fresher-longer-the-role-of-ethylene-in-storing-produce/article_a94185ec-5d38-56c8-9c29-647ef36f731b.html); [UC Davis compatibility chart](https://postharvest.ucdavis.edu/compatibility-chart-short-term-transport-or-storage) (ethylene < 1 ppm for sensitive groups) |
| Cucumbers turn yellow when exposed to ethylene. | [UC Davis PREC, cucumber](https://postharvest.ucdavis.edu/produce-facts-sheets/cucumber) |
| Commercial ripening of bananas and avocados uses ethylene exposure. At home, a paper bag with a banana does the same. | UC Davis PREC ([banana](https://postharvest.ucdavis.edu/produce-facts-sheets/banana), [avocado](https://postharvest.ucdavis.edu/produce-facts-sheets/avocado)) |

**Implemented:** `ethylene.producer` / `ethylene.sensitive` per produce. The storage tip appends the matching rule: a producer gets "keep apart from…", a sensitive type gets "keep apart from bananas, apples, avocado and tomatoes". The ripening tips use this deliberately (avocado with a banana, kiwi next to an apple).

## 4. What is *not* implemented, and why

- **Shelf-life countdown** ("good for 3 more days"). The app doesn't know purchase date, temperature history or cultivar, and the freshness head is unsupported. A number would be invented.
- **Firm-produce "cut around the mould"** (USDA). Replaced by the stricter Israeli Ministry of Health rule (§1).
- **Pesticide or washing claims** beyond "wash just before eating". Not visible in a photo, and out of scope.
