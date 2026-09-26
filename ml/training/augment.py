"""Realistic phone-photo augmentations.

Design constraint: colour IS the label for ripeness (green vs yellow banana,
dark vs green Hass skin). Hue jitter is therefore tiny and saturation/brightness
changes are bounded to what white-balance/exposure errors produce. Anything that
could turn a 'ripe' image into a plausible 'unripe' one is forbidden.
"""
from __future__ import annotations

import io
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


class RandomShadow:
    """Soft polygonal shadow, e.g. a hand or kitchen cabinet."""
    def __init__(self, p: float = 0.3, strength: tuple[float, float] = (0.45, 0.8)):
        self.p, self.strength = p, strength

    def __call__(self, img: Image.Image) -> Image.Image:
        if random.random() > self.p:
            return img
        w, h = img.size
        mask = Image.new("L", (w, h), 0)
        pts = [(random.randint(-w // 4, w + w // 4), random.randint(-h // 4, h + h // 4)) for _ in range(random.randint(3, 6))]
        ImageDraw.Draw(mask).polygon(pts, fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=max(w, h) / 20))
        k = random.uniform(*self.strength)
        arr = np.asarray(img, dtype=np.float32)
        m = np.asarray(mask, dtype=np.float32)[..., None] / 255.0
        arr = arr * (1 - m * (1 - k))
        return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


class JpegCompression:
    def __init__(self, p: float = 0.5, quality: tuple[int, int] = (35, 95)):
        self.p, self.quality = p, quality

    def __call__(self, img: Image.Image) -> Image.Image:
        if random.random() > self.p:
            return img
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=random.randint(*self.quality))
        buf.seek(0)
        return Image.open(buf).convert("RGB")


class SensorNoise:
    def __init__(self, p: float = 0.3, sigma: tuple[float, float] = (2.0, 10.0)):
        self.p, self.sigma = p, sigma

    def __call__(self, img: Image.Image) -> Image.Image:
        if random.random() > self.p:
            return img
        arr = np.asarray(img, dtype=np.float32)
        arr += np.random.normal(0, random.uniform(*self.sigma), arr.shape)
        return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


class BackgroundReplace:
    """For studio datasets (white background): composite the fruit onto a random
    real background so the model cannot learn 'white background => class X'.
    Foreground mask = pixels not near-white, then feathered."""
    def __init__(self, backgrounds: list[str], p: float = 0.5, white_thresh: int = 235):
        self.backgrounds, self.p, self.t = backgrounds, p, white_thresh

    def __call__(self, img: Image.Image, is_studio: bool = True) -> Image.Image:
        if not self.backgrounds or not is_studio or random.random() > self.p:
            return img
        arr = np.asarray(img)
        fg = (arr.min(axis=2) < self.t).astype(np.uint8) * 255
        mask = Image.fromarray(fg).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(2))
        bg = Image.open(random.choice(self.backgrounds)).convert("RGB").resize(img.size)
        return Image.composite(img, bg, mask)


def build_train_transform(cfg: dict):
    from torchvision import transforms as T
    a = cfg["augment"]
    size = cfg["data"]["image_size"]
    return T.Compose([
        T.RandomResizedCrop(size, scale=tuple(a.get("crop_scale", (0.35, 1.0))), ratio=(0.75, 1.33)),
        T.RandomHorizontalFlip(),
        T.RandomVerticalFlip(p=0.2),
        T.RandomRotation(a.get("rotation_deg", 30)),
        T.RandomApply([T.ColorJitter(brightness=a.get("brightness", 0.35), contrast=a.get("contrast", 0.3),
                                     saturation=a.get("saturation", 0.15), hue=a.get("hue", 0.01))], p=0.8),
        RandomShadow(p=a.get("shadow_p", 0.3)),
        T.RandomApply([T.GaussianBlur(kernel_size=7, sigma=(0.1, 2.0))], p=a.get("blur_p", 0.2)),
        SensorNoise(p=a.get("noise_p", 0.3)),
        JpegCompression(p=a.get("jpeg_p", 0.5)),
        T.ToTensor(),
        T.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    ])


def build_eval_transform(cfg: dict):
    from torchvision import transforms as T
    size = cfg["data"]["image_size"]
    return T.Compose([
        T.Resize(int(size * 1.14)), T.CenterCrop(size), T.ToTensor(),
        T.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    ])
