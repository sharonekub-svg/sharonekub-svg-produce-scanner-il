"""Banana peel colour fractions (ml/colour/banana.py) on synthetic peels."""
import numpy as np
from PIL import Image

from ml.colour.banana import peel_fractions


def _peel(rgb, brown_frac=0.0):
    a = np.full((100, 200, 3), 255, np.uint8)          # white background
    a[25:75, 20:180] = rgb                               # peel
    n = int(brown_frac * 50)
    a[25:25 + n, 20:180] = (92, 54, 31)                  # brown flecks band
    return Image.fromarray(a)


def test_green_yellow_brown_are_separated():
    g = peel_fractions(_peel((110, 150, 40)))
    y = peel_fractions(_peel((230, 200, 70)))
    b = peel_fractions(_peel((230, 200, 70), brown_frac=0.4))
    assert g.green > 0.95 and y.yellow > 0.95
    assert abs(b.brown - 0.4) < 0.05 and b.n_pixels > 0


def test_background_only_is_empty():
    assert peel_fractions(Image.new("RGB", (64, 64), "white")).n_pixels == 0
