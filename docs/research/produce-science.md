# Produce science: what a photo can and cannot tell (per fruit)

**Purpose:** decide, per produce type, which assessments the app is *allowed* to make from a single exterior phone photo, and what the grading guide (`docs/data-collection-protocol.md`) should measure as ground truth.

**Method and limits:**
- Web research on 2026-09-26/27. Most publisher pages (ScienceDirect, PMC, MDPI) are blocked from the build environment, so evidence comes from abstracts and search-indexed summaries.
- Accuracy numbers quoted from papers are **laboratory results on controlled images**. They are **not** predictions for our app: our own cross-dataset experiment (R4) fell to 0.32 top-1 when moving from studio/web images to phone photos.
- Sources marked ⚠︎ are low-reliability (blogs, SEO pages) and are used only as leads, never as evidence.

## Summary: what the app may claim (drives `ripeness_visual` in `data/label_mapping.json`)

| Produce | Ripeness visible from exterior? | Evidence strength | Freshness/spoilage visible? | App policy |
|---|---|---|---|---|
| Banana | **Yes**: 7-stage peel colour index, sugar spots | Strong | Yes (browning, rot) | Ripeness head allowed once trained on our data |
| Tomato | **Yes**: USDA 6 colour stages via hue | Strong | Yes (soft rot, cracks, mould) | Ripeness allowed |
| Strawberry | **Yes**: red-area ratio | Strong | Yes (grey mould *Botrytis*) | Ripeness allowed |
| Avocado, **Hass** (dark-skinned) | **Yes**: skin darkening (L*, b* ↓, a* ↑) correlates with firmness | Moderate–strong | Partly (external only; internal browning invisible) | Ripeness allowed **for Hass only** |
| Avocado, **Ettinger/Pinkerton/Reed** (green-skinned, ~38% of the Israeli crop) | **No**: skin stays green while flesh softens | Strong evidence of *absence* | Partly | Ripeness **not** shown; "check by gentle press" guidance |
| Mango | **Cultivar-dependent**: some yellow (e.g. Tainong), Keitt stays green when ripe; Israeli Shelly/Maya/Omer differ | Moderate | Yes (anthracnose spots, shrivel) | Ripeness only per cultivar with data; default off |
| Peach / nectarine | **Partly**: *ground* colour (not blush) tracks firmness, cultivar-specific | Moderate | Yes (bruises, rot) | Off until per-cultivar data |
| Pear | **Weak**: many cultivars ripen with little colour change; "neck softness" is tactile | Weak | Yes | Off |
| Citrus (orange, mandarin, lemon, grapefruit) | **No**: peel colour ≠ internal ripeness; early fruit is harvested green and *degreened* with ethylene; Israeli PPIS standards use TSS ≥ 9%, acidity ≤ 1.3%, TSS/acid ≥ 7 | Strong evidence of *absence* | Yes (green/blue mould *Penicillium*, shrivel) | **Never** ripeness; freshness/spoilage only |
| Persimmon | **No for astringency**: astringent cultivars stay astringent when fully coloured (the Israeli "Sharon fruit" is de-astringed commercially) | Strong evidence of *absence* | Yes | No ripeness/eating advice from colour |
| Watermelon / melon | **Weak**: field spot colour, netting, stem slip; the reliable signals are acoustic or aroma | Weak (visual) | Partly | Off (a cut-melon mode is a possible future feature) |
| Cucumber | Not a ripeness product (eaten immature); **yellowing = over-mature/senescent** | Strong for yellowing | **Yes**: yellowing, shrivel, pitting, decay | Freshness/spoilage only |
| Apple | Sold ripe; ripeness n/a | — | Late bruises/rot visible; **early bruises invisible in RGB** (need NIR/hyperspectral) | Freshness only, with the honest limit |
| Grapes | Sold ripe | — | **Rachis (stem) browning** is the key visible freshness marker; berry shrivel, mould | Freshness only; hint "include the stem in the photo" |
| Pomegranate | Sold ripe | — | Bruises mostly need hyperspectral; visible cracks/rot yes | Freshness only (visible defects) |

## Per-produce notes and sources

### Banana
- Standard 7-stage colour index: 1 green · 2 green with trace of yellow · 3 more green than yellow · 4 more yellow than green · 5 green tip · 6 all yellow · 7 yellow flecked with brown. Sugar spots come from polyphenol (L-DOPA) oxidation to melanin.
- Image analysis with L\*a\*b\*, brown-area % and texture classified 7 stages at 98% (49 samples, lab). A CNN on 4 stages reached 96% validation (lab).
- A 2025 study specifically tested **robustness under varying illumination**, which is directly relevant to our warm-light weakness (Phase 5).
- Consumer meaning of spots is cultural: East Asian consumers read early spotting as "sweet", others as "over-ripe". Our grading guide therefore calls stages 5–7 "ripe" and only extensive browning "overripe".
- Sources:
  - [Application of image analysis for classification of ripening bananas](https://www.researchgate.net/publication/229734831_Application_of_Image_Analysis_for_Classification_of_Ripening_Bananas)
  - [Predicting ripening stages of bananas by computer vision](https://www.researchgate.net/publication/284871590_Predicting_ripening_stages_of_bananas_Musa_cavendish_by_computer_vision)
  - [Colorimetric indicator for classification of bananas](https://www.sciencedirect.com/science/article/pii/S0304423812005432)
  - [DL robustness for banana ripeness under varying illumination](https://www.sciencedirect.com/science/article/pii/S2772375525005647)
  - [Senescent spotting of banana peel](https://www.academia.edu/21376460/Senescent_spotting_of_banana_peel_is_inhibited_by_modified_atmosphere_packaging)
  - [Polyphenol dynamics during ripening (ACS JAFC)](https://pubs.acs.org/jafcau/article/74/1/1772/5085886/Spatiotemporal-Dynamics-of-Polyphenolic-Compounds)

### Avocado
- Hass: during ripening, L\* and b\* decrease and a\* increases (anthocyanin up, chlorophyll down). Skin-colour features predict firmness: a CNN (ResNet-18) regression reached R² 0.919 (lab).
- Green-skinned Ettinger: "the skin will remain green as the flesh softens". Israeli crop share is about 62% Hass (black) and 38% green (Ettinger, Pinkerton), with Ettinger early season (Sep–Dec) and Reed late. **A colour-based ripeness claim would be wrong for roughly a third of Israeli avocados**, so the taxonomy must distinguish dark- from green-skinned before any ripeness output.
- Sources:
  - [Avocado ripeness via image processing + ML (IJFST)](https://academic.oup.com/ijfst/article/61/1/vvag005/8425003)
  - [Explainable AI + mobile imaging for avocado ripeness](https://www.sciencedirect.com/science/article/pii/S2665927125002278)
  - [Hass skin colour as ripeness parameter (ISHS)](https://ishs.org/ishs-article/945_25/)
  - [Ettinger (green skin) description](https://goodfruitguide.co.uk/product/ettinger-green-skin-avocado/)
  - [Israeli crop 62% Hass / 38% green (FreshPlaza)](https://www.freshplaza.com/asia/article/9260501/one-israeli-company-dominating-avocado-exports/)
  - [Israel avocado industry overview](https://israelagri.com/israels-avocado-industry-overview/)

### Tomato
- USDA stages: Green, Breakers, Turning, Pink, Light Red, Red. Classification uses hue-angle area fractions. Colour indexes (a\*/b\*, (a\*/b\*)², hue, chroma) were compared across 11 cultivars. Spectral imaging discriminates better than RGB, but RGB hue is adequate for the 6 stages.
- Sources:
  - [Comparison of colour indexes for tomato ripening (SciELO)](http://www.scielo.br/j/hb/a/nKQ4gGWYRc9CV37YWSKCGZt/?lang=en)
  - [Spectral image analysis for tomato ripeness](https://www.researchgate.net/publication/40119578_SPECTRAL_IMAGE_ANALYSIS_FOR_MEASURING_RIPENESS_OF_TOMATOES)
  - [USDA stages figure](https://www.researchgate.net/figure/Maturity-and-Ripening-Stages-of-Tomatoes-Based-on-United-States-Standards-for-Grades-of_fig4_337655286)

### Strawberry
- Red-colour ratio as the ripeness parameter: 95.9% (Swin-based network) and 97.8% (YOLOv8+ with red-pixel ratio), in greenhouse/lab settings. Grey mould (*Botrytis cinerea*) is the main postharvest decay; deeper red colouring correlated with lower spoilage across 17 genotypes (r = −0.63).
- Sources:
  - [Red colour ratio ripeness classification](https://www.sciencedirect.com/science/article/abs/pii/S0168169923007019)
  - [YOLOv8+ ripeness (MDPI Agriculture)](https://www.mdpi.com/2077-0472/14/5/751)
  - [Botrytis susceptibility vs colour](https://www.sciencedirect.com/science/article/abs/pii/S0308814622012146)

### Mango
- Firmness is the key quality indicator. Peel colour is cultivar-dependent: Tainong yellows, **Keitt stays green at full maturity**. Hyperspectral cultivar-specific models are needed. Israeli cultivars include Maya, Shelly (Tommy Atkins × Keitt), Omer, Noa, Tali, Orly, Keitt, Kent and Palmer.
- Sources:
  - [Cultivar-specific mango firmness via hyperspectral](https://www.sciencedirect.com/science/article/pii/S0023643826008777)
  - [Colour of "all yellow" mango cultivars (IJABE)](https://ijabe.org/index.php/ijabe/article/view/1861)
  - [Israeli mango varieties (israelagri)](https://israelagri.com/israels-mango-industry-overview/)
  - [Shelly/Tango in Israel (Fruitnet)](https://www.fruitnet.com/fresh-produce-journal/tango-mango-and-shelly-impress-israelis/132176.article)

### Citrus (orange, mandarin, lemon)
- Early varieties reach internal maturity **before** colour break. Degreening with ethylene changes only the peel colour. Israeli Satsuma harvest requires PPIS internal-quality minimums (TSS > 9%, acidity < 1.3%, ratio ≥ 7).
- Hence a green mandarin can be ripe and an orange one unripe, so **the app never infers citrus ripeness from colour**.
- This also explains part of our mandarin/orange confusion: colour is not a stable class cue either.
- Sources:
  - [Satsuma conditioning + degreening, incl. Israeli PPIS standards](https://www.sciencedirect.com/science/article/abs/pii/S0925521410000293)
  - [Degreening of citrus fruit](http://www.globalsciencebooks.info/Online/GSBOnline/images/0812/TFSB_2(SI1)/TFSB_2(SI1)71-76o.pdf)
  - [Quality of postharvest degreened citrus (IntechOpen)](https://www.intechopen.com/chapters/82262)

### Cucumber
- Main postharvest failures: moisture loss → shriveling, yellowing (ethylene, high temperature, over-mature harvest), pitting, decay. Image analysis over 28 days showed increasing yellowness and textural disorder, clearly by day 13. These are exactly the visible signals our freshness head should learn.
- Sources:
  - [Cucumber quality during storage via instrumental + image analysis (Appl. Sci.)](https://doi.org/10.3390/app14198676)
  - [UC Davis cucumber fact sheet](https://postharvest.ucdavis.edu/produce-facts-sheets/cucumber)
  - [Peel yellowing transcriptomics](https://www.sciencedirect.com/science/article/pii/S0304423825006065)

### Peach / nectarine / pear
- Harvest maturity uses firmness plus **ground colour** per cultivar. The index of absorbance difference (IAD, a NIR index) correlates best with firmness.
- Sources:
  - [Peach ripening and softening](https://www.sciencedirect.com/science/article/abs/pii/S0925521413002421)
  - [IAD maturity model (PLOS One)](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0177511)
  - [Peach/nectarine ripening, mealiness (extension)](https://shaponline.org/wp-content/uploads/2016/02/Peach-and-Nectarine-Fruit-Ripening-Mealiness-and-Internal-Breakdown.pdf)

### Persimmon
- Astringent cultivars "maintain a high content of soluble tannins, even when fully coloured"; astringency disappears only on over-softening or after de-astringency treatment (CO₂/ethanol).
- Sources:
  - [Microstructure: astringent vs non-astringent cultivars](https://www.sciencedirect.com/science/article/abs/pii/S0925521416301089)
  - [Alleviating astringency (UF/IFAS EDIS)](https://journals.flvc.org/edis/article/view/135070)

### Apple
- Early bruises (hours after impact) are masked by the epidermis and are hard or impossible to see in RGB. Hyperspectral/NIR detect them (~97% in lab). RGB-trained models perform far worse.
- Consequence: the app's "no visible damage" must never be read as "no bruise".
- Sources:
  - [Early apple bruise, NIR camera + DL](https://www.sciencedirect.com/science/article/abs/pii/S1350449522004236)
  - [Hyperspectral early bruise (PubMed)](https://pubmed.ncbi.nlm.nih.gov/37267465/)

### Grapes, pomegranate
- Table grapes: **rachis browning** is a critical visual quality disorder driven by water loss and oxidation.
- Pomegranate: bruises are mostly found with Vis-NIR/SWIR hyperspectral imaging.
- Sources:
  - [Rachis browning review (OENO One)](https://oeno-one.eu/article/view/10223)
  - [Rachis browning evaluation methods](https://www.sciencedirect.com/science/article/abs/pii/S0925521417306361)
  - [Pomegranate bruise hyperspectral (PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10160462/)

### Watermelon / melon
- Traditional external indicators (field spot, netting, slip, tendril) are "prone to subjectivity… and low accuracy". Acoustic methods via phone microphones have been studied (resonance ~100–130 Hz).
- Sources:
  - [Watermelon ripeness via mobile-phone acoustics](https://www.sciencedirect.com/science/article/abs/pii/S0889157525013122)
  - [Acoustic maturity assessment](https://www.sciencedirect.com/science/article/abs/pii/S0304423821008426)
  - [UMD Extension melon harvest indexes](https://extension.umd.edu/resource/ripening-behaviors-and-harvest-indexes-watermelons-cantaloupes-and-honeydew-melons)
  - ⚠︎ Blog claims such as "94% accuracy" (lifetips.alibaba.com) were **not** used.

## Israeli market context (for prioritisation)

- Fruit consumption is reported at about 75 kg/person/year ([israelagri, secondary](https://israelagri.com/israeli-fruit-consumption-ranks-high/)). Market-research summaries put tomatoes as the largest vegetable share (21.4%) followed by cucumbers, and bananas at 18.6% of fruit and vegetable value ([Mordor Intelligence summary, secondary](https://www.mordorintelligence.com/industry-reports/israel-fruits-and-vegetables-market)).
- Official CBS per-item data was not reachable. Treat these as provisional.
- Avocado: 62% Hass / 38% green-skinned (see above). Mango: Israeli-bred cultivars dominate.

## Consequences implemented

1. `data/label_mapping.json` gets a `ripeness_visual` field per produce (`strong`, `cultivar_dependent`, `weak`, `not_applicable`). `supported_heads_from_manifest` **refuses to enable ripeness** for `weak` or `not_applicable` produce even if labels exist, and for `cultivar_dependent` produce counts only rows that carry a `cultivar` field (test: `test_ripeness_visual_vetoes_ripeness`). Kiwi, plum and guava were classified too: kiwi is `not_applicable` (softness is tactile), and plum and guava are `cultivar_dependent`.
2. Grading guide: citrus, cucumber, apple, grapes and pomegranate are freshness-only (already the case), and avocado grading must record cultivar (Hass vs green-skinned).
3. Priority for ripeness data collection: **banana → tomato → strawberry → Hass avocado**. These are the fruits where the science says a photo can work.
