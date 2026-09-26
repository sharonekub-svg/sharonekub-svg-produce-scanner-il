"""Reproducible multi-task training.

  python -m ml.training.train --config ml/configs/baseline_mobilenetv3.yaml

Outputs under runs/<experiment>/<timestamp>/: config snapshot, git hash,
metrics.jsonl (per epoch, per head), best.pt, last.pt, temperature.json.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import time
from pathlib import Path

import numpy as np
import torch
import yaml
from torch.utils.data import DataLoader, WeightedRandomSampler

from ml.common.taxonomy import HEADS, REPO_ROOT, load_taxonomy
from ml.evaluation import calibration, gates, metrics
from ml.inference.decision import supported_heads_from_manifest
from ml.training import augment, dataset, losses, model as model_lib


def seed_everything(seed: int, deterministic: bool) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if deterministic:
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        torch.use_deterministic_algorithms(True, warn_only=True)
        torch.backends.cudnn.benchmark = False


def _git_hash() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        return "unknown"


def _produce_condition(y_produce: torch.Tensor) -> torch.Tensor:
    """True produce index where exactly known, else -1 (model falls back to its prediction)."""
    exact = y_produce.sum(1) == 1
    return torch.where(exact, y_produce.float().argmax(1), torch.full_like(exact, -1, dtype=torch.long))


@torch.no_grad()
def collect(net, loader, device) -> dict[str, dict[str, np.ndarray]]:
    net.eval()
    out = {h: {"logits": [], "mask": []} for h in HEADS}
    for x, y in loader:
        x = x.to(device)
        o = net(x, produce_idx=_produce_condition(y["produce"].to(device)))
        for h in HEADS:
            out[h]["logits"].append(o[h].float().cpu().numpy())
            out[h]["mask"].append(y[h].numpy())
    return {h: {k: np.concatenate(v) for k, v in d.items()} for h, d in out.items()}


def summarize_heads(collected, tax, temps: dict[str, float] | None = None) -> dict[str, dict]:
    res = {}
    for h in HEADS:
        logits, mask = collected[h]["logits"], collected[h]["mask"]
        exact = mask.sum(1) == 1  # only exact labels are scored
        y = mask[exact].argmax(1)
        p = calibration.softmax(logits[exact], (temps or {}).get(h, 1.0))
        res[h] = metrics.summarize(p, y, list(tax.classes(h))) if exact.any() else {"n": 0}
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--max-steps", type=int, default=None, help="debug: stop early")
    ap.add_argument("--runs-dir", type=Path, default=REPO_ROOT / "runs")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text())
    seed_everything(cfg["seed"], cfg.get("deterministic", True))
    tax = load_taxonomy()
    device = torch.device(cfg.get("device", "cuda" if torch.cuda.is_available() else "cpu"))

    run_dir = args.runs_dir / cfg["experiment"] / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True)
    print(f"RUN_DIR {run_dir}")
    (run_dir / "config.yaml").write_text(yaml.safe_dump(cfg))
    (run_dir / "git.txt").write_text(_git_hash())

    if cfg.get("threads"):
        torch.set_num_threads(cfg["threads"])
    data_root = REPO_ROOT / cfg["data"]["processed_dir"]
    tr_rows = dataset.select_rows(cfg, {"train"}, data_root)
    va_rows = dataset.select_rows(cfg, {"val"}, data_root)
    (run_dir / "supported_heads.json").write_text(json.dumps(supported_heads_from_manifest(tr_rows), indent=2))
    tr = dataset.ManifestDataset(tr_rows, data_root, tax, augment.build_train_transform(cfg))
    va = dataset.ManifestDataset(va_rows, data_root, tax, augment.build_eval_transform(cfg))
    g = torch.Generator().manual_seed(cfg["seed"])
    bs, nw = cfg["train"]["batch_size"], cfg["train"].get("num_workers", 4)
    # Class-balanced sampling on produce: weight ~ count^-alpha (alpha=0 -> uniform, 1 -> fully balanced).
    alpha = cfg["train"].get("balance_alpha", 0.0)
    n_per_epoch = cfg["train"].get("samples_per_epoch") or len(tr)
    if alpha > 0 or cfg["train"].get("samples_per_epoch"):
        from collections import Counter
        keys = [str(r["labels"]["produce"]) for r in tr_rows]
        cnt = Counter(keys)
        w = torch.tensor([cnt[k] ** -alpha for k in keys], dtype=torch.double)
        sampler = WeightedRandomSampler(w, n_per_epoch, replacement=True, generator=g)
        tl = DataLoader(tr, bs, sampler=sampler, num_workers=nw, collate_fn=dataset.collate, drop_last=True)
    else:
        tl = DataLoader(tr, bs, shuffle=True, num_workers=nw, collate_fn=dataset.collate, generator=g, drop_last=True)
    vl = DataLoader(va, bs, shuffle=False, num_workers=nw, collate_fn=dataset.collate)
    print(f"train {len(tr_rows)} (sampled {n_per_epoch}/epoch), val {len(va_rows)}", flush=True)

    n_classes = {h: tax.num_classes(h) for h in HEADS}
    net = model_lib.build_model(cfg, n_classes).to(device)
    lr = cfg["train"]["lr"]
    bb_mult = cfg["train"].get("backbone_lr_mult", 1.0)
    bb = [p for n, p in net.named_parameters() if n.startswith("backbone.") and p.requires_grad]
    heads = [p for n, p in net.named_parameters() if not n.startswith("backbone.")]
    opt = torch.optim.AdamW([{"params": bb, "lr": lr * bb_mult}, {"params": heads, "lr": lr}],
                            weight_decay=cfg["train"].get("weight_decay", 0.05))
    epochs = cfg["train"]["epochs"]
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[lr * bb_mult, lr], total_steps=epochs * max(1, len(tl)),
                                                pct_start=cfg["train"].get("warmup_frac", 0.1))
    head_w = cfg["train"]["head_weights"]
    best, step = -1.0, 0
    for ep in range(epochs):
        t0 = time.time()
        net.train()
        for x, y in tl:
            x = x.to(device)
            y = {h: v.to(device) for h, v in y.items()}
            out = net(x, produce_idx=_produce_condition(y["produce"]))
            loss, parts = losses.multitask_loss(out, y, head_w, cfg["train"].get("label_smoothing", 0.0))
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 5.0)
            opt.step()
            sched.step()
            step += 1
            if args.max_steps and step >= args.max_steps:
                break
        summ = summarize_heads(collect(net, vl, device), tax)
        score = np.nanmean([summ[h]["macro_f1"] for h in HEADS if summ[h].get("n", 0) and head_w.get(h, 0) > 0])
        rec = {"epoch": ep, "step": step, "sec": round(time.time() - t0, 1), "loss": round(float(loss), 4),
               "val_score": float(score),
               **{f"{h}/{k}": summ[h][k] for h in HEADS if summ[h].get("n") for k in ("top1", "macro_f1", "worst_class_recall", "ece")}}
        with open(run_dir / "metrics.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(json.dumps(rec))
        torch.save({"model": net.state_dict(), "cfg": cfg, "epoch": ep}, run_dir / "last.pt")
        if score > best:
            best = score
            torch.save({"model": net.state_dict(), "cfg": cfg, "epoch": ep}, run_dir / "best.pt")
        if args.max_steps and step >= args.max_steps:
            break

    # Calibrate on val with the best checkpoint, then evaluate gates on val.
    net.load_state_dict(torch.load(run_dir / "best.pt", map_location=device)["model"])
    col = collect(net, vl, device)
    temps = {}
    for h in HEADS:
        exact = col[h]["mask"].sum(1) == 1
        if exact.sum() >= 50:
            temps[h] = calibration.fit_temperature(col[h]["logits"][exact], col[h]["mask"][exact].argmax(1))
    (run_dir / "temperature.json").write_text(json.dumps(temps, indent=2))
    summ = summarize_heads(col, tax, temps)
    (run_dir / "val_summary.json").write_text(json.dumps(summ, indent=2))
    fails = gates.check_gates(summ, cfg.get("gates", {}))
    (run_dir / "gates.json").write_text(json.dumps({"passed": not fails, "failures": fails}, indent=2))
    print("GATES:", "PASS" if not fails else fails)


if __name__ == "__main__":
    main()
