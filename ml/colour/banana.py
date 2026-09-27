"""Banana peel colour grading from pixels (no learned model).

Industry banana colour index (CI) 1-7: 1 all green, 2 green with a trace of yellow, 3 more green than
yellow, 4 more yellow than green, 5 yellow with a trace of green, 6 all yellow, 7 yellow with brown
flecks (docs/research/produce-science.md). We measure the fractions of visible peel that are green,
yellow and brown and map them to our ripeness taxonomy. Validated on psolymos/bananas (MIT, 11 fruits x
21 days, human labels) with leave-one-fruit-out: ml/colour/eval_bananas.py.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class PeelColour:
    green: float
    yellow: float
    brown: float
    n_pixels: int


def peel_fractions(img: Image.Image, mask: np.ndarray | None = None, size: int = 256) -> PeelColour:
    """Fractions of peel pixels per colour family. `mask` marks fruit pixels (same size as img);
    default: every pixel that is not near-white background."""
    im = img.convert("RGB")
    scale = size / max(im.size)
    if scale < 1:
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.Resampling.BILINEAR)
        if mask is not None:
            mask = np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).resize(im.size)) > 127
    hsv = np.asarray(im.convert("HSV"), dtype=np.float32)
    h, s, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    if mask is None:
        mask = ~((s < 0.12) & (v > 0.80))  # near-white background
    brown = mask & ((v < 0.38) | ((h < 40) & (s > 0.25)) | ((s < 0.30) & (v < 0.60)))
    green = mask & ~brown & (h >= 62) & (h < 150)
    yellow = mask & ~brown & ~green & (h >= 40) & (h < 62)
    n = int(brown.sum() + green.sum() + yellow.sum())
    if n == 0:
        return PeelColour(0.0, 0.0, 0.0, 0)
    return PeelColour(float(green.sum() / n), float(yellow.sum() / n), float(brown.sum() / n), n)
