"""Size / latency benchmark for candidate backbones (host CPU; NOT a phone number).

  python -m ml.export.benchmark --backbones mobilenetv3_large_100 efficientnet_b0 --size 224

Host-CPU latency is only a relative ranking signal. Release decisions use
on-device measurements (Xcode Instruments / Core ML Performance Report) recorded
in docs/evaluation.md.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time

import torch

from ml.training.model import MultiTaskProduceNet


def bench(backbone: str, size: int, runs: int = 30, threads: int = 1) -> dict:
    torch.set_num_threads(threads)
    net = MultiTaskProduceNet(backbone, 23, 4, 3, 3, pretrained=False).eval()
    params = sum(p.numel() for p in net.parameters())
    x = torch.randn(1, 3, size, size)
    with torch.inference_mode():
        for _ in range(5):
            net(x)
        ts = []
        for _ in range(runs):
            t0 = time.perf_counter()
            net(x)
            ts.append((time.perf_counter() - t0) * 1000)
    return {"backbone": backbone, "params_m": round(params / 1e6, 2), "fp32_mb": round(params * 4 / 2**20, 1),
            "int8_mb_est": round(params / 2**20, 1), "cpu_ms_median": round(statistics.median(ts), 1),
            "cpu_ms_p90": round(sorted(ts)[int(0.9 * len(ts)) - 1], 1), "threads": threads, "size": size}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backbones", nargs="+", default=[
        "mobilenetv3_large_100", "mobilenetv4_conv_medium", "efficientnet_b0",
        "convnext_nano", "fastvit_t8", "efficientvit_b1.r224_in1k", "vit_small_patch16_224"])
    ap.add_argument("--size", type=int, default=224)
    ap.add_argument("--runs", type=int, default=30)
    args = ap.parse_args()
    for b in args.backbones:
        try:
            print(json.dumps(bench(b, args.size, args.runs)))
        except Exception as e:  # unknown model name in installed timm, etc.
            print(json.dumps({"backbone": b, "error": str(e)[:200]}))


if __name__ == "__main__":
    main()
