"""Verify exported ONNX models against PyTorch: accuracy on a split, top-1 agreement,
max logit deviation, file size and host-CPU latency. Gates must hold AFTER quantisation.

  python -m ml.export.verify_onnx --ckpt runs/X/best.pt --export exports/v1 \
      --processed data/processed_commercial --splits test
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import numpy as np
import torch

from ml.evaluation import calibration, metrics
from ml.export.export import load
from ml.preprocessing.image_io import load_rgb
from ml.training.augment import build_eval_transform
from ml.training.dataset import read_manifest


def latency(sess, size: int, threads_note: str, runs: int = 50) -> dict:
    x = np.random.rand(1, 3, size, size).astype(np.float32)
    for _ in range(5):
        sess.run(None, {"image": x})
    ts = []
    for _ in range(runs):
        t0 = time.perf_counter()
        sess.run(None, {"image": x})
        ts.append((time.perf_counter() - t0) * 1000)
    ts.sort()
    return {"ms_p50": round(statistics.median(ts), 2), "ms_p90": round(ts[int(0.9 * runs) - 1], 2), "threads": threads_note}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--export", type=Path, required=True)
    ap.add_argument("--processed", type=Path, required=True)
    ap.add_argument("--splits", nargs="+", default=["test"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--threads", type=int, default=1)
    args = ap.parse_args()
    import onnxruntime as ort

    net, cfg, tax = load(args.ckpt)
    size = cfg["data"]["image_size"]
    temps = json.loads((args.ckpt.parent / "temperature.json").read_text())
    rows = read_manifest(args.processed / "manifest.jsonl", set(args.splits))
    rows = [r for r in rows if isinstance(r["labels"]["produce"], str)]
    if args.limit:
        rows = sorted(rows, key=lambda r: r["sha256"])[: args.limit]
    tf = build_eval_transform(cfg)
    X = np.stack([tf(load_rgb(args.processed / r["image"])).numpy() for r in rows])
    y = np.array([tax.produce.index(r["labels"]["produce"]) for r in rows])
    torch.set_num_threads(args.threads)
    with torch.inference_mode():
        ref = np.concatenate([net(torch.from_numpy(X[i:i + 64]))["produce"].numpy() for i in range(0, len(X), 64)])
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = args.threads
    report = {"n": len(rows), "splits": args.splits, "variants": {}}
    for name in ("model.onnx", "model.int8.onnx"):
        p = args.export / name
        if not p.exists():
            continue
        sess = ort.InferenceSession(str(p), opts, providers=["CPUExecutionProvider"])
        out = np.concatenate([sess.run(None, {"image": X[i:i + 1]})[0] for i in range(len(X))])
        probs = calibration.softmax(out, temps.get("produce", 1.0))
        s = metrics.summarize(probs, y, list(tax.produce))
        report["variants"][name] = {
            "size_mb": round(p.stat().st_size / 2**20, 2),
            "top1": round(s["top1"], 4), "macro_f1": round(s["macro_f1"], 4),
            "worst_class_recall": round(s["worst_class_recall"], 4), "ece": round(s["ece"], 4),
            "top1_agreement_with_torch": round(float((out.argmax(1) == ref.argmax(1)).mean()), 4),
            "max_abs_logit_diff": round(float(np.abs(out - ref).max()), 4),
            "host_cpu_latency": latency(sess, size, f"{args.threads} thread(s)"),
        }
    ts = calibration.softmax(ref, temps.get("produce", 1.0))
    report["torch_reference_top1"] = round(float((ts.argmax(1) == y).mean()), 4)
    for d in ("ProduceScanner.mlpackage",):
        p = args.export / d
        if p.exists():
            report[d] = {"size_mb": round(sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 2**20, 2)}
    out_path = args.export / "verify_report.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
