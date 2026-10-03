"""Measured visual signs on the fruit's skin (no learning): the defect cues machine-vision literature uses.

Defects and decay show up as regions whose colour / lightness departs from the sound skin of the same fruit
(Cubero et al. 2011, Food Bioprocess Technol 4:487); banana ripening is tracked by the share of brown-spotted
area (Mendoza & Aguilera 2004, J Food Sci); grey mould is a pale, low-chroma fuzzy growth (strawberry Botrytis);
shrivelling raises fine texture. Everything here is RELATIVE to the fruit's own median colour, so a yellow kitchen
lamp or a dark photo does not by itself look like a defect.

measure(img) -> dict with:
  fruit_frac        share of the photo that is the fruit (segmentation sanity check)
  dark_frac         share of the fruit at least 25 L* darker than its median skin
  very_dark_frac    ... at least 45 L* darker (deep black / rot)
  largest_dark      largest connected dark patch / fruit area (one big soft lesion vs. sugar-spot freckles)
  spots_per_100     number of separate dark spots per 100 cm^2-equivalent (per 10% of the fruit area)
  brown_frac        dark AND brownish (a*, b* > 0) share
  pale_frac         low-chroma, lighter-than-skin share (whitish / grey growth) on colourful fruit
  texture           mean |Laplacian| of L* on the fruit / median L* (wrinkling / shrivelling)
  L, a, b, chroma   median skin colour in CIE L*a*b*
"""
from __future__ import annotations

import numpy as np
from PIL import Image
from scipy import ndimage

SIZE = 256


def _lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB (0-255) -> CIE L*a*b* (D65)."""
    c = rgb.astype(np.float32) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]], np.float32)
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883], np.float32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], -1)


def fruit_mask(lab: np.ndarray) -> np.ndarray:
    """Foreground = far (in L*a*b*) from the border colour; largest component, holes filled.
    Falls back to a central ellipse when the photo has no clean background."""
    h, w, _ = lab.shape
    k = max(4, min(h, w) // 16)
    border = np.concatenate([lab[:k].reshape(-1, 3), lab[-k:].reshape(-1, 3), lab[:, :k].reshape(-1, 3), lab[:, -k:].reshape(-1, 3)])
    bg = np.median(border, 0)
    spread = np.median(np.abs(border - bg), 0).sum() + 1e-3
    d = np.sqrt(((lab - bg) ** 2).sum(-1))
    thr = max(18.0, 4.0 * spread)
    m = d > thr
    m = ndimage.binary_opening(m, iterations=2)
    lbl, n = ndimage.label(m)
    if n:
        sizes = ndimage.sum(m, lbl, range(1, n + 1))
        m = lbl == (1 + int(np.argmax(sizes)))
        m = ndimage.binary_fill_holes(m)
    frac = m.mean()
    if not (0.05 <= frac <= 0.92):
        yy, xx = np.mgrid[:h, :w]
        m = ((yy - h / 2) / (0.35 * h)) ** 2 + ((xx - w / 2) / (0.35 * w)) ** 2 <= 1
    return m


def measure(img: Image.Image) -> dict:
    im = img.convert("RGB")
    im.thumbnail((SIZE, SIZE))
    lab = _lab(np.asarray(im))
    m = fruit_mask(lab)
    # skin pixels away from the outline (shading at the rim is not a defect)
    inner = ndimage.binary_erosion(m, iterations=3)
    if inner.sum() < 50:
        inner = m
    L, A, B = lab[..., 0], lab[..., 1], lab[..., 2]
    Lm, Am, Bm = (float(np.median(x[inner])) for x in (L, A, B))
    chroma = np.sqrt(A ** 2 + B ** 2)
    Cm = float(np.median(chroma[inner]))
    area = float(inner.sum())
    dark = inner & (L < Lm - 25)
    vdark = inner & (L < Lm - 45)
    lbl, n = ndimage.label(dark)
    sizes = ndimage.sum(dark, lbl, range(1, n + 1)) if n else np.array([0.0])
    spots = int((sizes >= max(4, area * 0.0015)).sum())
    brown = dark & (A > 2) & (B > 4)
    # lighter and greyer than the skin, but not a specular highlight (L* >= 88)
    pale = inner & (chroma < 0.45 * Cm) & (L > Lm + 5) & (L < 88) if Cm > 18 else np.zeros_like(inner)
    lap = np.abs(ndimage.laplace(ndimage.gaussian_filter(L, 1.0)))
    return {
        "fruit_frac": round(float(m.mean()), 4),
        "dark_frac": round(float(dark.sum() / area), 4),
        "very_dark_frac": round(float(vdark.sum() / area), 4),
        "largest_dark": round(float(sizes.max() / area), 4),
        "spots_per_100": round(spots / max(area / (0.1 * SIZE * SIZE), 1e-3), 3),
        "brown_frac": round(float(brown.sum() / area), 4),
        "pale_frac": round(float(pale.sum() / area), 4),
        "texture": round(float(lap[inner].mean() / max(Lm, 1.0)), 4),
        "L": round(Lm, 2), "a": round(Am, 2), "b": round(Bm, 2), "chroma": round(Cm, 2),
    }
