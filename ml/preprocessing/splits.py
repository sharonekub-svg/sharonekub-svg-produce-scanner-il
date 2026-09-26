"""Leakage-safe, deterministic, group-aware stratified splits.

Unit of assignment is the *group* (duplicate cluster ∪ metadata group ∪
augmentation family). Every image of a group lands in the same split.
Whole datasets can be held out as cross-dataset test sets.
"""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from typing import Hashable, Sequence

SPLITS = ("train", "val", "test")


def _stable_rank(key: Hashable, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()


def group_split(groups: Sequence[Hashable], strata: Sequence[Hashable],
                ratios: dict[str, float] | None = None, seed: int = 1337) -> list[str]:
    """Assign each group to a split so that, within each stratum, the image counts
    approximate `ratios`. A group's stratum is its majority stratum.

    Greedy: groups sorted by (size desc, stable hash) are assigned to the split with
    the largest deficit relative to its target. Deterministic for fixed inputs+seed.
    """
    ratios = ratios or {"train": 0.8, "val": 0.1, "test": 0.1}
    if abs(sum(ratios.values()) - 1.0) > 1e-6:
        raise ValueError("ratios must sum to 1")
    members: dict[Hashable, list[int]] = defaultdict(list)
    for i, g in enumerate(groups):
        members[g].append(i)
    group_stratum = {g: Counter(strata[i] for i in idx).most_common(1)[0][0] for g, idx in members.items()}

    by_stratum: dict[Hashable, list[Hashable]] = defaultdict(list)
    for g, s in group_stratum.items():
        by_stratum[s].append(g)

    assignment: dict[Hashable, str] = {}
    for s in sorted(by_stratum, key=str):
        gs = sorted(by_stratum[s], key=lambda g: (-len(members[g]), _stable_rank(g, seed)))
        total = sum(len(members[g]) for g in gs)
        filled = {k: 0 for k in ratios}
        for g in gs:
            deficit = {k: ratios[k] * total - filled[k] for k in ratios}
            k = max(deficit, key=lambda k: (deficit[k], ratios[k]))
            assignment[g] = k
            filled[k] += len(members[g])
    return [assignment[g] for g in groups]


def check_no_leakage(groups: Sequence[Hashable], splits: Sequence[str]) -> list[Hashable]:
    """Return the groups that appear in more than one split (should be empty)."""
    seen: dict[Hashable, set[str]] = defaultdict(set)
    for g, s in zip(groups, splits):
        seen[g].add(s)
    return [g for g, ss in seen.items() if len(ss) > 1]


def apply_dataset_holdout(dataset_ids: Sequence[str], splits: list[str], holdout: set[str],
                          groups: Sequence[Hashable] | None = None) -> list[str]:
    """Move whole datasets to 'cross_dataset_test'. If a holdout image shares a group
    with a non-holdout image (cross-dataset duplicate), that whole group moves too."""
    out = list(splits)
    tainted = set()
    if groups is not None:
        tainted = {g for g, d in zip(groups, dataset_ids) if d in holdout}
    for i, d in enumerate(dataset_ids):
        if d in holdout or (groups is not None and groups[i] in tainted):
            out[i] = "cross_dataset_test"
    return out


_HELD_OUT_ORDER = {"test": 0, "val": 1, "train": 2}


def apply_split_hints(groups: Sequence[Hashable], splits: list[str], hints: Sequence[str | None]) -> tuple[list[str], int]:
    """Honour official/forced splits. A cluster containing any hinted member takes the
    most held-out hint among its members (test > val > train), so an image that is
    duplicated across an official train/test boundary can never train the model.
    Returns (splits, number of clusters whose official split had to be overridden)."""
    best: dict[Hashable, str] = {}
    conflicted: dict[Hashable, set[str]] = defaultdict(set)
    for g, h in zip(groups, hints):
        if h is None:
            continue
        conflicted[g].add(h)
        if g not in best or _HELD_OUT_ORDER[h] < _HELD_OUT_ORDER[best[g]]:
            best[g] = h
    out = [best.get(g, s) for g, s in zip(groups, splits)]
    return out, sum(len(v) > 1 for v in conflicted.values())


def carve_val_from_train(groups: Sequence[Hashable], splits_: list[str], strata: Sequence[Hashable],
                         frac: float, seed: int = 1337, frozen: Sequence[bool] | None = None) -> list[str]:
    """Move a group-stratified `frac` of TRAIN clusters to 'val' (for datasets whose official
    val split is too small to gate on). Clusters with any `frozen` member (e.g. force_split
    datasets such as Fruits-360, never used for evaluation) are left untouched."""
    frozen_groups = {g for g, f in zip(groups, frozen or [False] * len(groups)) if f}
    idx = [i for i, (g, s) in enumerate(zip(groups, splits_)) if s == "train" and g not in frozen_groups]
    if not idx:
        return list(splits_)
    sub = group_split([groups[i] for i in idx], [strata[i] for i in idx],
                      {"train": 1 - frac, "val": frac, "test": 0.0}, seed=seed + 1)
    out = list(splits_)
    for i, s in zip(idx, sub):
        out[i] = s
    return out
