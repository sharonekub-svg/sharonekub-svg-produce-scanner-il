import io
import random

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from ml.preprocessing import dedup, hashing, image_io, splits


def synthetic(seed: int, size=160) -> Image.Image:
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 255, (8, 8, 3), dtype=np.uint8)
    img = Image.fromarray(base).resize((size, size), Image.Resampling.BICUBIC)
    return img.filter(ImageFilter.GaussianBlur(2))


def rec(img):
    return dedup.DupRecord(sha256=str(id(img)), pixel_digest=hashing.pixel_digest(img),
                           phash=hashing.dihedral_phash(img))


def jpeg(img, q):
    b = io.BytesIO()
    img.save(b, "JPEG", quality=q)
    return Image.open(io.BytesIO(b.getvalue())).convert("RGB")


def test_augmented_copies_cluster_with_original():
    orig = synthetic(1)
    variants = [orig.rotate(90, expand=True), orig.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
                jpeg(orig, 40), ImageEnhance.Brightness(orig).enhance(1.15),
                orig.resize((120, 120)), orig.filter(ImageFilter.GaussianBlur(1))]
    others = [synthetic(s) for s in range(10, 30)]
    ids, stats = dedup.cluster([rec(i) for i in [orig, *variants, *others]])
    assert len(set(ids[:7])) == 1, stats
    assert ids[0] not in ids[7:]
    assert len(set(ids[7:])) == 20


def test_metadata_groups_link_different_images():
    a, b = synthetic(100), synthetic(101)
    r = [dedup.DupRecord("a", "pa", hashing.phash(a), "hass:17"),
         dedup.DupRecord("b", "pb", hashing.phash(b), "hass:17")]
    ids, _ = dedup.cluster(r)
    assert ids[0] == ids[1]


def test_group_split_no_leakage_and_deterministic():
    rnd = random.Random(0)
    groups = [f"g{rnd.randint(0, 300)}" for _ in range(3000)]
    strata = [f"ds|{hash(g) % 5}" for g in groups]
    s1 = splits.group_split(groups, strata, seed=7)
    s2 = splits.group_split(groups, strata, seed=7)
    assert s1 == s2
    assert splits.check_no_leakage(groups, s1) == []
    frac = {k: s1.count(k) / len(s1) for k in splits.SPLITS}
    assert abs(frac["train"] - 0.8) < 0.05 and frac["val"] > 0.05 and frac["test"] > 0.05


def test_holdout_pulls_cross_dataset_duplicates():
    ds = ["a", "a", "b", "b"]
    groups = ["g1", "g2", "g2", "g3"]  # g2 spans datasets a and b
    out = splits.apply_dataset_holdout(ds, ["train"] * 4, {"b"}, groups)
    assert out == ["train", "cross_dataset_test", "cross_dataset_test", "cross_dataset_test"]


def test_image_checks(tmp_path):
    good = tmp_path / "good.jpg"
    synthetic(3).save(good)
    assert image_io.check_image(good).ok
    trunc = tmp_path / "trunc.jpg"
    trunc.write_bytes(good.read_bytes()[:200])
    assert not image_io.check_image(trunc).ok
    blank = tmp_path / "blank.png"
    Image.new("RGB", (200, 200), (10, 10, 10)).save(blank)
    assert image_io.check_image(blank).reason == "blank_or_constant"
    tiny = tmp_path / "tiny.png"
    synthetic(4, size=32).save(tiny)
    assert image_io.check_image(tiny).reason == "too_small"
    txt = tmp_path / "x.txt"
    txt.write_text("hi")
    assert not image_io.check_image(txt).ok


def _blob(color, bg=(255, 255, 255)):
    from PIL import ImageDraw
    img = Image.new("RGB", (160, 160), bg)
    ImageDraw.Draw(img).ellipse((30, 25, 130, 135), fill=color)
    return img.filter(ImageFilter.GaussianBlur(2))


def _vrec(img, key):
    return dedup.DupRecord(sha256=key, pixel_digest=key, phash=hashing.dihedral_phash(img),
                           chroma=hashing.chroma_hist(img),
                           studio=hashing.white_fraction(img) >= dedup.STUDIO_WHITE_FRACTION)


def test_studio_same_shape_different_colour_not_linked():
    """Regression (real data): pHash linked plum<->tomato on white background and chained
    all of Fruits-360 into one cluster."""
    plum, tomato = _blob((70, 20, 60)), _blob((200, 40, 25))
    assert hashing.hamming(hashing.dihedral_phash(plum), hashing.dihedral_phash(tomato)) <= 6
    ids, stats = dedup.cluster([_vrec(plum, "a"), _vrec(tomato, "b")])
    assert ids[0] != ids[1] and stats["near_duplicate_rejected_by_verification"] == 1


def test_studio_brightness_copy_still_linked():
    t = _blob((200, 40, 25))
    brighter = ImageEnhance.Brightness(t).enhance(1.1)
    ids, _ = dedup.cluster([_vrec(t, "a"), _vrec(brighter, "b")])
    assert ids[0] == ids[1]
