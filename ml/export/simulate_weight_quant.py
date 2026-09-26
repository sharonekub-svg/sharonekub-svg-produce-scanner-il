"""Estimate the accuracy cost of Core ML weight-only compression without a Mac: apply the same
transform to the PyTorch weights (fp16 rounding; k-means palettisation per tensor at N bits)
and re-evaluate. Activations stay fp16/fp32, as with Core ML palettised weights on ANE/GPU.

  python -m ml.export.simulate_weight_quant --ckpt runs/X/best.pt --processed data/processed_commercial --splits test
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import numpy as np
import torch

from ml.evaluation import calibration, metrics
from ml.export.export import load
from ml.preprocessing.image_io import load_rgb
from ml.training.augment import build_eval_transform
from ml.training.dataset import read_manifest


def kmeans_1d(w: np.ndarray, k: int, iters: int = 25) -> np.ndarray:
    cent = np.quantile(w, np.linspace(0, 1, k))
    for _ in range(iters):
        idx = np.abs(w[:, None] - cent[None]).argmin(1)
        for j in range(k):
            m = idx == j
            if m.any():
                cent[j] = w[m].mean()
    return cent[np.abs(w[:, None] - cent[None]).argmin(1)]


def compress(net, mode: str):
    net = copy.deepcopy(net)
    with torch.no_grad():
        for name, p in net.named_parameters():
            if p.dim() < 2:  # biases / norms stay as-is (Core ML palettises weights of conv/linear)
                continue
            if mode == "fp16":
                p.copy_(p.half().float())
            else:
                bits = int(mode.split("_")[1])
                w = p.detach().cpu().numpy().ravel()
                if w.size > 20000:  # subsample for centroid fitting, apply to all
                    rng = np.random.default_rng(0)
                    sample = rng.choice(w, 20000, replace=False)
                    cent = np.unique(kmeans_1d(sample, 2 ** bits))
                    q = cent[np.abs(w[:, None] - cent[None]).argmin(1)] if w.size < 3_000_000 else w
                else:
                    q = kmeans_1d(w, 2 ** bits)
                p.copy_(torch.from_numpy(q.reshape(p.shape).astype(np.float32)).half().float())
    return net


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--processed", type=Path, required=True)
    ap.add_argument("--splits", nargs="+", default=["test"])
    ap.add_argument("--modes", nargs="+", default=["fp32", "fp16", "palettize_8", "palettize_6", "palettize_4"])
    args = ap.parse_args()
    net, cfg, tax = load(args.ckpt)
    temps = json.loads((args.ckpt.parent / "temperature.json").read_text())
    rows = [r for r in read_manifest(args.processed / "manifest.jsonl", set(args.splits)) if isinstance(r["labels"]["produce"], str)]
    tf = build_eval_transform(cfg)
    X = torch.stack([tf(load_rgb(args.processed / r["image"])) for r in rows])
    y = np.array([tax.produce.index(r["labels"]["produce"]) for r in rows])
    res, ref = {}, None
    for mode in args.modes:
        m = net if mode == "fp32" else compress(net, mode)
        with torch.inference_mode():
            lg = torch.cat([m(X[i:i + 64])["produce"] for i in range(0, len(X), 64)]).numpy()
        ref = lg if ref is None else ref
        s = metrics.summarize(calibration.softmax(lg, temps.get("produce", 1.0)), y, list(tax.produce))
        res[mode] = {"top1": round(s["top1"], 4), "macro_f1": round(s["macro_f1"], 4),
                     "worst_class_recall": round(s["worst_class_recall"], 4),
                     "agreement_with_fp32": round(float((lg.argmax(1) == ref.argmax(1)).mean()), 4)}
        print(mode, res[mode], flush=True)
    (args.ckpt.parent / "weight_quant_sim.json").write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
