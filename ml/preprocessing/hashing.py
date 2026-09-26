"""Perceptual hashing for near-duplicate and augmented-copy detection.

`dihedral_phash` returns the minimum pHash over the 8 rotations/flips of the
image, so a 90-degree-rotated or mirrored augmentation hashes to (almost) the
same value as its original. Colour jitter, mild blur and JPEG re-encoding are
handled by pHash itself operating on low DCT frequencies of luminance.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

_HASH = 8          # 8x8 low-frequency block -> 64-bit hash
_SIZE = 32         # image downscaled to 32x32 before DCT


def _dct_matrix(n: int) -> np.ndarray:
    k = np.arange(n)[:, None]
    i = np.arange(n)[None, :]
    m = np.sqrt(2.0 / n) * np.cos(np.pi * (2 * i + 1) * k / (2 * n))
    m[0, :] = np.sqrt(1.0 / n)
    return m


_D = _dct_matrix(_SIZE)


def _gray(img: Image.Image, size: int) -> np.ndarray:
    return np.asarray(img.convert("L").resize((size, size), Image.Resampling.LANCZOS), dtype=np.float64)


def _phash_array(g: np.ndarray) -> int:
    dct = _D @ g @ _D.T
    block = dct[:_HASH, :_HASH].flatten()
    med = np.median(block[1:])  # exclude DC term
    bits = block > med
    return int("".join("1" if b else "0" for b in bits), 2)


def phash(img: Image.Image) -> int:
    return _phash_array(_gray(img, _SIZE))


def dhash(img: Image.Image) -> int:
    g = np.asarray(img.convert("L").resize((9, 8), Image.Resampling.LANCZOS), dtype=np.float64)  # 8 rows x 9 cols
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def dihedral_phash(img: Image.Image) -> int:
    g = _gray(img, _SIZE)
    variants = []
    for k in range(4):
        r = np.rot90(g, k)
        variants.append(_phash_array(r))
        variants.append(_phash_array(np.fliplr(r)))
    return min(variants)


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def pixel_digest(img: Image.Image) -> str:
    """Hash of decoded pixels at 64x64: catches identical images re-encoded to another format."""
    import hashlib
    arr = np.asarray(img.convert("RGB").resize((64, 64), Image.Resampling.BILINEAR))
    return hashlib.sha1((arr // 8).tobytes()).hexdigest()


def chroma_hist(img: Image.Image, bins: int = 8) -> np.ndarray:
    """Brightness- and orientation-invariant colour signature: normalised rg-chromaticity
    histogram of foreground pixels (near-white background and near-black pixels ignored).
    Separates shape-alike but differently coloured objects (plum vs tomato) that pHash
    alone links on studio backgrounds."""
    a = np.asarray(img.convert("RGB").resize((64, 64)), dtype=np.float64)
    s = a.sum(2)
    mx, mn = a.max(2), a.min(2)
    fg = ((mx < 235) | (mx - mn > 25)) & (s > 60)
    if fg.sum() < 50:
        fg = np.ones_like(fg)
    r = (a[..., 0] / np.maximum(s, 1))[fg]
    g = (a[..., 1] / np.maximum(s, 1))[fg]
    h, _, _ = np.histogram2d(r, g, bins=bins, range=[[0, 1], [0, 1]])
    return (h.ravel() / h.sum()).astype(np.float32)


def white_fraction(img: Image.Image) -> float:
    """Share of near-white pixels; >= 0.1 marks a studio / white-background image."""
    a = np.asarray(img.convert("RGB").resize((64, 64)))
    return float((a.min(2) > 235).mean())
