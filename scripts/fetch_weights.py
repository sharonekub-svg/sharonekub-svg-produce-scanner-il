#!/usr/bin/env python3
"""Download pinned ImageNet-pretrained timm weights (GitHub releases) into weights/ and verify SHA-256.

  python scripts/fetch_weights.py [names...]

Licence note (docs/licensing.md): these weights were trained on ImageNet-1k, whose terms are
non-commercial research. Using them in a shipped model requires the legal sign-off described there.
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

REL = "https://github.com/huggingface/pytorch-image-models/releases/download/v0.1-weights/"
WEIGHTS = {
    "mobilenetv3_large_100": ("mobilenetv3_large_100_ra-f55367f5.pth",
                              "f55367f56f62fa6115a03033835fd60ef3094a1e0fdce6f38a5c97cbab27295f"),
    "efficientnet_b0": ("efficientnet_b0_ra-3dd342df.pth",
                        "3dd342dfa1fee25ae65e7bbdf8998cad6e45d6e77e69d580f0bd14d3eeb0b3f3"),
    "mobilenetv3_small_100": ("mobilenetv3_small_100_lamb-266a294c.pth",
                              "266a294cbf3d119000a760bf5664a4d80a9674d0616b5cc0836b093d20c38249"),
}
OUT = Path(__file__).resolve().parents[1] / "weights"


def main() -> int:
    OUT.mkdir(exist_ok=True)
    for name in sys.argv[1:] or WEIGHTS:
        fname, sha = WEIGHTS[name]
        dest = OUT / fname
        if not dest.exists():
            urllib.request.urlretrieve(REL + fname, dest)
        got = hashlib.sha256(dest.read_bytes()).hexdigest()
        if got != sha:
            dest.unlink()
            raise SystemExit(f"{fname}: sha256 mismatch {got}")
        print(f"ok {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
