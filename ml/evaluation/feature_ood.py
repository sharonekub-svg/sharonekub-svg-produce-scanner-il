"""Feature-space OOD scores vs logit scores, on the same rows (docs/research/ml-methods.md).

Fits on TRAIN-split penultimate features (the pooled 1280-d MobileNetV3 embedding), scores the
test split, and reports AUROC / FPR@95%TPR for:
  msp, energy                      - logit-based (what the app uses today)
  mahalanobis                      - class-conditional Gaussians, tied covariance (Lee et al. 2018)
  knn                              - k-th nearest-neighbour distance, L2-normalised (Sun et al. 2022)

  python -m ml.evaluation.feature_ood --ckpt runs/X/best.pt --processed data/processed_commercial \
      --ood-source-regex '(^|/)(Lime|Red-Grapefruit|Zucchini|Potato|Passion-Fruit)/' --out runs/X/feature_ood.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from ml.evaluation import ood
from ml.evaluation.evaluate import load_ckpt
from ml.training import augment, dataset


@torch.no_grad()
def features(net, rows, root, tax, cfg, workers=2, bs=64):
    dl = DataLoader(dataset.ManifestDataset(rows, root, tax, augment.build_eval_transform(cfg)), bs,
                    num_workers=workers, collate_fn=dataset.collate)
    f, lg = [], []
    for x, _ in dl:
        o = net(x)  # eval mode: dropout is identity, so o["features"] is the pooled embedding
        f.append(o["features"].numpy()); lg.append(o["produce"].numpy())
    return np.concatenate(f), np.concatenate(lg)


def fit_mahalanobis(f: np.ndarray, y: np.ndarray, shrink: float = 1e-3):
    classes = np.unique(y)
    mu = np.stack([f[y == c].mean(0) for c in classes])
    xc = f - mu[np.searchsorted(classes, y)]
    cov = xc.T @ xc / len(f)
    cov += shrink * np.trace(cov) / cov.shape[0] * np.eye(cov.shape[0])
    return mu, np.linalg.inv(cov)


def mahalanobis_score(f: np.ndarray, mu: np.ndarray, prec: np.ndarray) -> np.ndarray:
    d = np.stack([np.einsum("ij,jk,ik->i", f - m, prec, f - m) for m in mu], 1)
    return -d.min(1)


def knn_score(f: np.ndarray, bank: np.ndarray, k: int = 50) -> np.ndarray:
    def norm(a):
        return a / np.linalg.norm(a, axis=1, keepdims=True).clip(1e-12)
    q, b = norm(f), norm(bank)
    out = np.empty(len(q))
    for i in range(0, len(q), 512):
        d = 2 - 2 * q[i:i + 512] @ b.T
        out[i:i + 512] = -np.sqrt(np.partition(d, k - 1, axis=1)[:, k - 1].clip(0))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--processed", type=Path, required=True)
    ap.add_argument("--ood-source-regex", required=True)
    ap.add_argument("--exclude-source-regex", help="drop rows entirely (e.g. classes held out of training)")
    ap.add_argument("--max-train", type=int, default=8000)
    ap.add_argument("--k", type=int, default=50)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    net, cfg, tax, temps, _ = load_ckpt(args.ckpt)
    rx = re.compile(args.ood_source_regex)
    drop = re.compile(args.exclude_source_regex) if args.exclude_source_regex else None

    def keep(r):
        return not (drop and drop.search(r["source_path"]))
    train = [r for r in dataset.read_manifest(args.processed / "manifest.jsonl", {"train"})
             if keep(r) and not rx.search(r["source_path"]) and isinstance(r["labels"]["produce"], str)]
    rng = np.random.default_rng(0)
    if len(train) > args.max_train:
        train = [train[i] for i in sorted(rng.choice(len(train), args.max_train, replace=False))]
    test = [r for r in dataset.read_manifest(args.processed / "manifest.jsonl", {"test"}) if keep(r)]
    is_ood = np.array([bool(rx.search(r["source_path"])) for r in test])

    ftr, _ = features(net, train, args.processed, tax, cfg, args.workers)
    ytr = np.array([tax.produce.index(r["labels"]["produce"]) for r in train])
    fte, lte = features(net, test, args.processed, tax, cfg, args.workers)

    probs = np.exp(lte / temps.get("produce", 1.0) - (lte / temps.get("produce", 1.0)).max(1, keepdims=True))
    probs /= probs.sum(1, keepdims=True)
    mu, prec = fit_mahalanobis(ftr, ytr)
    scores = {"msp": ood.max_softmax(probs), "energy": ood.energy(lte),
              "mahalanobis": mahalanobis_score(fte, mu, prec), "knn": knn_score(fte, ftr, args.k)}
    ind = ~is_ood
    res = {"ckpt": str(args.ckpt), "processed": str(args.processed), "ood_source_regex": args.ood_source_regex,
           "n_train_fit": len(train), "n_in": int(ind.sum()), "n_ood": int(is_ood.sum()), "k": args.k,
           "auroc": {k: ood.auroc(v[ind], v[is_ood]) for k, v in scores.items()},
           "fpr_at_95tpr": {k: ood.fpr_at_tpr(v[ind], v[is_ood]) for k, v in scores.items()},
           "on_device_cost": {"mahalanobis_floats": int(mu.size + prec.size), "knn_floats": int(ftr.size)}}
    out = args.out or args.ckpt.parent / "feature_ood.json"
    out.write_text(json.dumps(res, indent=2))
    print(json.dumps({k: res[k] for k in ("n_in", "n_ood", "auroc", "fpr_at_95tpr")}, indent=2))


if __name__ == "__main__":
    main()
