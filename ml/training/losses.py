"""Partial-label (set-valued) cross-entropy.

For a sample whose truth is known only to lie in a set S (e.g. 'bad quality'
-> {declining, spoiled}) we minimise -log sum_{c in S} p(c). For |S| = 1 this
is ordinary cross-entropy; for an empty mask (unknown) the sample is ignored.
This lets coarse datasets train fine heads without fabricating labels.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F


def set_valued_ce(logits: torch.Tensor, allowed: torch.Tensor, label_smoothing: float = 0.0,
                  class_weights: torch.Tensor | None = None) -> torch.Tensor:
    """logits: [B, C]; allowed: [B, C] bool mask. Returns mean over known samples (0 if none)."""
    known = allowed.any(dim=1)
    if not known.any():
        return logits.sum() * 0.0
    logits, allowed = logits[known], allowed[known]
    logp = F.log_softmax(logits, dim=1)
    masked = logp.masked_fill(~allowed, float("-inf"))
    nll = -torch.logsumexp(masked, dim=1)
    if label_smoothing > 0:
        nll = (1 - label_smoothing) * nll - label_smoothing * logp.mean(dim=1)
    if class_weights is not None:
        # weight of a set label = mean weight of its members
        w = (allowed.float() * class_weights).sum(1) / allowed.float().sum(1)
        return (nll * w).sum() / w.sum()
    return nll.mean()


def multitask_loss(outputs: dict[str, torch.Tensor], targets: dict[str, torch.Tensor],
                   head_weights: dict[str, float], label_smoothing: float = 0.0,
                   class_weights: dict[str, torch.Tensor] | None = None) -> tuple[torch.Tensor, dict[str, float]]:
    total = 0.0
    parts = {}
    for head, w in head_weights.items():
        if w == 0 or head not in outputs:
            continue
        cw = class_weights.get(head) if class_weights else None
        l = set_valued_ce(outputs[head], targets[head], label_smoothing, cw)
        parts[head] = float(l.detach())
        total = total + w * l
    return total, parts
