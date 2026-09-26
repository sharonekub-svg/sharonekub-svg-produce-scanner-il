"""Cheap, model-free image-quality gate run before the classifier.

Thresholds are placeholders to be tuned on the real-world validation set
(Phase 5); they must be mirrored exactly in the app's native implementation.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

DEFAULTS = {"min_mean_luma": 40.0, "max_mean_luma": 235.0, "min_laplacian_var": 60.0,
            "max_clipped_frac": 0.35, "analysis_size": 256}


@dataclass(frozen=True)
class QualityResult:
    ok: bool
    reason: str | None       # too_dark | too_bright | blurry | overexposed | None
    mean_luma: float
    laplacian_var: float
    clipped_frac: float


def _luma(img: Image.Image, size: int) -> np.ndarray:
    im = img.convert("L")
    im.thumbnail((size, size))
    return np.asarray(im, dtype=np.float64)


def laplacian_variance(g: np.ndarray) -> float:
    lap = (-4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:])
    return float(lap.var())


def assess(img: Image.Image, cfg: dict | None = None) -> QualityResult:
    c = {**DEFAULTS, **(cfg or {})}
    g = _luma(img, int(c["analysis_size"]))
    mean = float(g.mean())
    lv = laplacian_variance(g)
    clipped = float(((g <= 3) | (g >= 252)).mean())
    reason = None
    if mean < c["min_mean_luma"]:
        reason = "too_dark"
    elif mean > c["max_mean_luma"]:
        reason = "too_bright"
    elif clipped > c["max_clipped_frac"]:
        reason = "overexposed"
    elif lv < c["min_laplacian_var"]:
        reason = "blurry"
    return QualityResult(reason is None, reason, mean, lv, clipped)
