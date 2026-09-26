#!/usr/bin/env python3
"""Fixtures for the Swift core parity test (scripts/test_swift_core.sh).

For each image: raw RGB bytes (as decoded by Pillow), the model tensor from server/app.py
Engine.preprocess, and ml/inference/quality.assess results. Swift must reproduce them.

  python scripts/gen_swift_fixtures.py --out /tmp/swift_fixtures [--images a.jpg b.jpg ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.inference import quality  # noqa: E402


def preprocess(img: Image.Image, inp: dict) -> np.ndarray:
    # Same code path as server/app.py Engine.preprocess (kept importable without onnxruntime).
    size, ratio = inp["size"], inp["resize_ratio"]
    w, h = img.size
    s = int(size * ratio) / min(w, h)
    img = img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.Resampling.BILINEAR)
    w, h = img.size
    left, top = (w - size) // 2, (h - size) // 2
    img = img.crop((left, top, left + size, top + size))
    x = np.asarray(img, dtype=np.float32) / 255.0
    x = (x - np.array(inp["mean"], dtype=np.float32)) / np.array(inp["std"], dtype=np.float32)
    return x.transpose(2, 0, 1).astype(np.float32)


def synthetic() -> dict[str, Image.Image]:
    rng = np.random.default_rng(0)
    base = Image.fromarray(rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)).filter(ImageFilter.GaussianBlur(1))
    return {
        "syn_texture_640x480": base,
        "syn_dark": Image.fromarray((np.asarray(base) * 0.1).astype(np.uint8)),
        "syn_bright": Image.fromarray(np.clip(np.asarray(base).astype(int) + 200, 0, 255).astype(np.uint8)),
        "syn_blurry": base.filter(ImageFilter.GaussianBlur(10)),
        "syn_portrait_300x533": base.resize((300, 533)),
        "syn_small_250x250": base.resize((250, 250)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--images", nargs="*", type=Path, default=[])
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    inp = json.loads((ROOT / "server/model/bundle.json").read_text(encoding="utf-8"))["input"]
    cases = synthetic()
    for p in args.images:
        cases[p.stem] = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
    index = []
    for name, img in cases.items():
        img = img.convert("RGB")
        (args.out / f"{name}.rgb").write_bytes(np.asarray(img, dtype=np.uint8).tobytes())
        preprocess(img, inp).tofile(args.out / f"{name}.tensor.f32")
        q = quality.assess(img)
        index.append({"name": name, "width": img.width, "height": img.height,
                      "quality": {"reason": q.reason, "mean_luma": q.mean_luma,
                                  "laplacian_var": q.laplacian_var, "clipped_frac": q.clipped_frac}})
    (args.out / "index.json").write_text(json.dumps({"input": inp, "cases": index}, indent=1))
    print(f"{len(index)} cases -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
