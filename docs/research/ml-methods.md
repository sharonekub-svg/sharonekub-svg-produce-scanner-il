# ML methods: what the literature says, and what we measured

Companion to [produce-science.md](produce-science.md), which covers what a photo can and cannot tell about each fruit. This page covers the model side. For every open problem from the "what's left" list, it gives the evidence from the literature, the experiment we ran here, and the decision taken. All numbers come from this repo's runs on commercial-licence data (Grocery Store dataset, MIT). They are on identical test rows unless stated otherwise.

## 1. Out-of-distribution detection ("is this something we know?")

| Method | Idea | Source |
|---|---|---|
| MSP | max softmax probability is lower on unknown inputs | Hendrycks & Gimpel, ICLR 2017, [arXiv 1610.02136](https://arxiv.org/abs/1610.02136) |
| Energy | `T·logsumexp(logits/T)`; aligned with input density, beats MSP | Liu et al., NeurIPS 2020, [arXiv 2010.03759](https://arxiv.org/abs/2010.03759) |
| Mahalanobis | class-conditional Gaussians with a tied covariance on the penultimate features; distance to the nearest class mean | Lee et al., NeurIPS 2018, [arXiv 1807.03888](https://arxiv.org/abs/1807.03888) |
| KNN | k-th nearest-neighbour distance of the L2-normalised feature to the training set; non-parametric, no Gaussian assumption | Sun et al., ICML 2022 (PMLR v162), [arXiv 2204.06507](https://arxiv.org/abs/2204.06507) |

The literature shows that feature-space scores (Mahalanobis, KNN) usually beat logit scores on **near-OOD** inputs, where objects look like a known class. That is exactly our case: a lime looks like an unripe lemon or mandarin, and a zucchini looks like a cucumber. The mechanism is that softmax is confident on anything near a decision boundary it has learned, whereas distance to the training data is not. The costs differ. Mahalanobis on device needs the class means plus a 1280×1280 precision matrix, about 1.7 M floats. KNN needs a feature bank, which is too big for the app unless it is subsampled or quantised.

**Experiment** (`ml/evaluation/feature_ood.py`): C1 release model, test split, lookalike produce (lime, grapefruit, zucchini, potato, passion fruit) as OOD. The scores were fitted on train features with the lookalikes excluded. Results are in §6.

## 2. Calibration and abstention

- **Temperature scaling** (Guo et al., ICML 2017, [arXiv 1706.04599](https://arxiv.org/abs/1706.04599)): one scalar per head, fitted on val. It is what we ship, in `ml/evaluation/calibration.py`.
- **Calibration degrades under dataset shift** (Ovadia et al., NeurIPS 2019, [arXiv 1906.02530](https://arxiv.org/abs/1906.02530)). Temperatures fitted on val do not hold on phone photos. This is why the product floor is fixed at a minimum shown confidence of 0.70 rather than tuned down to whatever val allows. It is also why the real-world test set (docs/beta-and-production.md) must re-fit the temperatures before launch.
- **Selective classification** (Geifman & El-Yaniv, NeurIPS 2017, [arXiv 1705.08500](https://arxiv.org/abs/1705.08500)). Picking a confidence threshold to hit a target risk is exactly `evaluate.py --tune`: the smallest threshold whose accepted set reaches 95% accuracy on val.

## 3. Lighting and colour ("warm light")

- Colour-constancy errors are a known failure mode of CNNs. Afifi & Brown (ICCV 2019, [arXiv 1912.06960](https://arxiv.org/abs/1912.06960)) show that plain colour jitter does not model real camera white-balance errors, and that white-balance-aware augmentation fixes much of the drop.
- For produce this matters more than for most objects, because hue is the cue for ripeness itself (produce-science.md: banana, tomato, strawberry). An augmentation that shifts hue freely would teach the ripeness head to ignore the one signal that works. Our `WhiteBalanceShift` (`ml/training/augment.py`) therefore applies only the physically plausible illuminant axis: a warm tungsten cast or a mild cool daylight cast, with per-channel gains and no hue rotation. It is off by default (`white_balance_p: 0`). It must be re-measured on the ripeness head before it is enabled for ripeness training.
- **Experiment:** C4 is C1 plus white-balance shift with p=0.3. Results are in §6.

## 4. Blur gate

- The variance of the Laplacian is the standard cheap focus measure (Pech-Pacheco et al., ICPR 2000). Pertuz et al. (Pattern Recognition 46(5), 2013) compared 36 focus operators and found Laplacian-based ones among the best for this purpose.
- The absolute threshold is image- and resolution-dependent, so it has to be picked from data. Our gate always computes it on a 256-px long side (Python `quality.py` and Swift `ProduceCore.swift`, parity-tested).
- **Experiment** (`ml/evaluation/blur_sweep.py`): blur each test image at nine Gaussian radii, relative to its long side. For each candidate threshold, record how many sharp photos it rejects and how accurate the model is on everything that passes. Results are in §6.

## 5. Fine-grained citrus and the "other" class

- Published fine-grained citrus work is almost entirely about **disease** (canker, greening, black spot), not cultivar or species identification from consumer photos. There is no ready-made benchmark for lemon vs lime vs mandarin vs orange under kitchen lighting.
- The fruit-ripeness survey (arXiv [2212.14441](https://arxiv.org/abs/2212.14441)) and the review in *Artificial Intelligence in Agriculture* (2023, [S2589721723000065](https://www.sciencedirect.com/science/article/pii/S2589721723000065)) report the same pattern. Most ripeness datasets are single-cultivar lab captures on plain backgrounds. Reported accuracies above 95% do not transfer to consumer photos. That supports our decision to ship identify-only until real, graded Israeli data exists.
- Negatives: the model needs to say "not something I know" for lookalikes. We tried three designs:
  - C1: lookalikes inside a single "other" class.
  - C3: no lookalikes in training at all, so the score has to catch them.
  - C5: each lookalike as its own named negative class (`is_negative_class: true`), shown to the user as "not something I know".

  The named-class design follows the outlier-exposure idea (Hendrycks et al., ICLR 2019, [arXiv 1812.04606](https://arxiv.org/abs/1812.04606)): known negatives in training sharpen the boundary. Naming them keeps "other" from becoming an incoherent class that pulls in real citrus.

## 6. Results and decisions

### 6.1 OOD scores (`feature_ood.py`, 1280-d pooled features, fit on train)

| Setting | n in / OOD | MSP | Energy | Mahalanobis | KNN (k=50) |
|---|---|---|---|---|---|
| C1 (release), lookalikes (lime, grapefruit, zucchini, potato, passion fruit) | 1514 / 190 | 0.687 | 0.700 | **0.828** | 0.683 |
| R1, 12 produce types never seen in training | 4633 / 227 | 0.646 | 0.690 | 0.713 | **0.741** |

AUROC; higher is better. FPR at 95% TPR stays between 0.79 and 0.98 for every score, so no single score is a usable gate on its own.

**Decision:** keep the energy score in the shipped app for now. Mahalanobis is the better score in both settings (+0.13 and +0.02 AUROC). But shipping it means changing the model contract: the ONNX and Core ML graphs would output features, the bundle would carry about 1.7 M parameters, and the Python, TS and Swift ports would all need it. Its gain on truly unseen produce (+0.02) is too small to justify that before we have a real-phone OOD set. What protects users today is layered: named or "other" negatives, then the 0.70 shown-confidence floor, then the energy threshold. In C1, 96.8% of lookalikes end as "not sure" or "not produce" (§6.3). Revisit this when the real-world set exists. The tooling is in place.

### 6.2 Blur gate (`blur_sweep.py`, C1, 800 test images × 9 blur levels)

| Blur radius (fraction of long side) | 0 | 0.002 | 0.004 | 0.006 | 0.008 | 0.011 | 0.015 |
|---|---|---|---|---|---|---|---|
| Model top-1 | 0.898 | 0.891 | 0.888 | 0.859 | 0.799 | 0.721 | 0.536 |
| Median Laplacian variance | 333 | 174 | 49 | 20 | 10 | 5 | 3 |

| `min_laplacian_var` | Sharp photos rejected | Accuracy of what passes | Harmless blur (0.004) passed | Harmful blur (0.008) passed |
|---|---|---|---|---|
| 20 | 0.0% | 0.890 | 95% | 1% |
| **30** | 0.3% | 0.891 | 84% | 0% |
| 60 (old) | 0.6% | 0.893 | 33% | 0% |
| 100 | 4.0% | 0.896 | 8% | 0% |

**Decision:** 30. Accuracy on what passes is the same as with 60, but blur the model still handles (0.888 top-1) now passes 84% of the time instead of 33%. Unnecessary retake requests fall from 67% to 16% of those photos. Changed in `quality.py` and `ProduceCore.swift`; Swift parity still passes 9/9. Caveat: the Grocery images are 348 px. Re-check the threshold on 12 MP phone photos from the real-world set.

### 6.3 Negatives and lighting (C3–C6)

Full table and decisions: [results.md → Follow-ups after v0.1-dev](../results.md). In short:
- Named negative classes (C5) beat both "one big other class" (C1) and "no negatives, rely on the OOD score" (C3). C3 caught only 69% of lookalikes.
- White-balance augmentation fixes most of the synthetic warm-light drop but costs in-distribution macro-F1 on one seed. It is held back until the real-world set can decide.

