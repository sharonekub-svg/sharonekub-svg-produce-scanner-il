"""Image validation and standardisation."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
MIN_SIDE = 64


@dataclass(frozen=True)
class ImageCheck:
    ok: bool
    reason: str = ""
    width: int = 0
    height: int = 0
    sha256: str = ""


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_rgb(path: Path) -> Image.Image:
    """Decode fully, apply EXIF orientation, convert to RGB (alpha -> white)."""
    img = Image.open(path)
    img.load()
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    return img.convert("RGB")


def check_image(path: Path, min_side: int = MIN_SIDE) -> ImageCheck:
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        return ImageCheck(False, "not_an_image_extension")
    try:
        with Image.open(path) as im:
            im.verify()  # structural check
        img = load_rgb(path)  # full decode catches truncation
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as e:
        return ImageCheck(False, f"corrupt:{type(e).__name__}")
    w, h = img.size
    if min(w, h) < min_side:
        return ImageCheck(False, "too_small", w, h)
    arr = np.asarray(img)
    if arr.std() < 2.0:
        return ImageCheck(False, "blank_or_constant", w, h)
    return ImageCheck(True, "", w, h, file_sha256(path))


def standardize(img: Image.Image, max_side: int = 512) -> Image.Image:
    """Downscale so the longest side <= max_side. Never upscales, keeps aspect."""
    w, h = img.size
    scale = max_side / max(w, h)
    if scale < 1:
        img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.LANCZOS)
    return img


def save_standard(img: Image.Image, out_path: Path, quality: int = 95) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="JPEG", quality=quality, subsampling=0, optimize=True)
