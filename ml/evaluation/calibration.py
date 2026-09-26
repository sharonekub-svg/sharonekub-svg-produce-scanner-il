"""Temperature scaling (Guo et al. 2017), fit on the validation split only."""
from __future__ import annotations

import numpy as np


def softmax(logits: np.ndarray, t: float = 1.0) -> np.ndarray:
    z = logits / t
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


def _nll(logits: np.ndarray, y: np.ndarray, t: float) -> float:
    p = softmax(logits, t)
    return float(-np.log(np.clip(p[np.arange(len(y)), y], 1e-12, 1)).mean())


def fit_temperature(logits: np.ndarray, y: np.ndarray, lo: float = 0.05, hi: float = 20.0, iters: int = 80) -> float:
    """Golden-section search on log T (NLL is unimodal in T for a fixed model)."""
    a, b = np.log(lo), np.log(hi)
    g = (np.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = _nll(logits, y, np.exp(c)), _nll(logits, y, np.exp(d))
    for _ in range(iters):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = _nll(logits, y, np.exp(c))
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = _nll(logits, y, np.exp(d))
    return float(np.exp((a + b) / 2))
