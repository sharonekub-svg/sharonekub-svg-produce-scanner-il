"""Classification, calibration and selective-prediction metrics (numpy only).

All functions take probs [N, C] and integer targets [N] for samples with an
exact label. Set-valued / unknown targets are filtered by the caller.
"""
from __future__ import annotations

import numpy as np


def confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, n: int) -> np.ndarray:
    cm = np.zeros((n, n), dtype=np.int64)
    np.add.at(cm, (y_true, y_pred), 1)
    return cm


def per_class_prf(cm: np.ndarray) -> dict[str, np.ndarray]:
    tp = np.diag(cm).astype(float)
    support = cm.sum(1).astype(float)
    predicted = cm.sum(0).astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        precision = np.where(predicted > 0, tp / predicted, np.nan)
        recall = np.where(support > 0, tp / support, np.nan)
        f1 = np.where((precision + recall) > 0, 2 * precision * recall / (precision + recall), 0.0)
    f1 = np.where(support > 0, f1, np.nan)
    return {"precision": precision, "recall": recall, "f1": f1, "support": support}


def topk_accuracy(probs: np.ndarray, y: np.ndarray, k: int) -> float:
    k = min(k, probs.shape[1])
    topk = np.argsort(-probs, axis=1)[:, :k]
    return float((topk == y[:, None]).any(1).mean())


def expected_calibration_error(probs: np.ndarray, y: np.ndarray, n_bins: int = 15) -> float:
    conf = probs.max(1)
    correct = probs.argmax(1) == y
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            ece += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def brier(probs: np.ndarray, y: np.ndarray) -> float:
    onehot = np.eye(probs.shape[1])[y]
    return float(((probs - onehot) ** 2).sum(1).mean())


def nll(probs: np.ndarray, y: np.ndarray) -> float:
    return float(-np.log(np.clip(probs[np.arange(len(y)), y], 1e-12, 1)).mean())


def selective_risk_curve(conf: np.ndarray, correct: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Coverage vs risk when abstaining on lowest-confidence samples first."""
    order = np.argsort(-conf)
    c = correct[order].astype(float)
    n = np.arange(1, len(c) + 1)
    return n / len(c), 1 - np.cumsum(c) / n


def aurc(conf: np.ndarray, correct: np.ndarray) -> float:
    _, risk = selective_risk_curve(conf, correct)
    return float(risk.mean())


def risk_at_coverage(conf: np.ndarray, correct: np.ndarray, coverage: float) -> float:
    cov, risk = selective_risk_curve(conf, correct)
    return float(risk[min(len(risk) - 1, int(np.ceil(coverage * len(risk))) - 1)])


def summarize(probs: np.ndarray, y: np.ndarray, class_names: list[str]) -> dict:
    n = len(class_names)
    pred = probs.argmax(1)
    cm = confusion_matrix(y, pred, n)
    prf = per_class_prf(cm)
    conf = probs.max(1)
    correct = pred == y
    present = prf["support"] > 0
    return {
        "n": int(len(y)),
        "top1": float(correct.mean()) if len(y) else float("nan"),
        "top5": topk_accuracy(probs, y, 5) if len(y) else float("nan"),
        "macro_f1": float(np.nanmean(prf["f1"][present])) if present.any() else float("nan"),
        "balanced_accuracy": float(np.nanmean(prf["recall"][present])) if present.any() else float("nan"),
        "worst_class_recall": float(np.nanmin(prf["recall"][present])) if present.any() else float("nan"),
        "ece": expected_calibration_error(probs, y),
        "brier": brier(probs, y),
        "nll": nll(probs, y),
        "aurc": aurc(conf, correct),
        "per_class": {c: {k: (None if np.isnan(prf[k][i]) else float(prf[k][i])) for k in prf}
                      for i, c in enumerate(class_names)},
        "confusion_matrix": cm.tolist(),
    }
