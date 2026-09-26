"""Out-of-distribution scores. Higher score = more likely in-distribution."""
from __future__ import annotations

import numpy as np


def max_softmax(probs: np.ndarray) -> np.ndarray:
    return probs.max(1)


def neg_entropy(probs: np.ndarray) -> np.ndarray:
    return (probs * np.log(np.clip(probs, 1e-12, 1))).sum(1)


def energy(logits: np.ndarray, t: float = 1.0) -> np.ndarray:
    """Negative free energy (Liu et al. 2020): t * logsumexp(logits / t)."""
    z = logits / t
    m = z.max(1, keepdims=True)
    return t * (m[:, 0] + np.log(np.exp(z - m).sum(1)))


def auroc(scores_in: np.ndarray, scores_out: np.ndarray) -> float:
    """P(score_in > score_out), ties count half (Mann-Whitney U)."""
    s = np.concatenate([scores_in, scores_out])
    order = s.argsort(kind="mergesort")
    ranks = np.empty(len(s))
    ranks[order] = np.arange(1, len(s) + 1)
    # average ranks for ties
    _, inv, counts = np.unique(s, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, weights=ranks)
    ranks = (sums / counts)[inv]
    n1, n2 = len(scores_in), len(scores_out)
    return float((ranks[:n1].sum() - n1 * (n1 + 1) / 2) / (n1 * n2))


def fpr_at_tpr(scores_in: np.ndarray, scores_out: np.ndarray, tpr: float = 0.95) -> float:
    thr = np.quantile(scores_in, 1 - tpr)
    return float((scores_out >= thr).mean())
