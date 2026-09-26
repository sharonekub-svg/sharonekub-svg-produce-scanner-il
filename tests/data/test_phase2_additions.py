import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from ml.common.taxonomy import load_taxonomy
from ml.evaluation.agreement import cohen_kappa, pairwise_from_rows
from ml.preprocessing import registry, splits
from ml.preprocessing.labels import iter_dataset, map_path

ROOT = Path(__file__).resolve().parents[2]
TAX = load_taxonomy()
sys.path.insert(0, str(ROOT / "scripts"))
import merge_annotations  # noqa: E402
import validate_collection  # noqa: E402


def test_split_hints_most_held_out_wins():
    groups = ["a", "a", "b", "c"]
    out, conflicts = splits.apply_split_hints(groups, ["train"] * 4, ["train", "test", None, "val"])
    assert out == ["test", "test", "train", "val"] and conflicts == 1


def test_grocery_store_real_layout():
    lab = map_path(TAX, "grocery_store_klasson", "dataset/train/Fruit/Melon/Watermelon/Watermelon_001.jpg")
    assert TAX.decode("produce", lab["produce"]) == "watermelon"
    assert TAX.decode("produce", map_path(TAX, "grocery_store_klasson", "dataset/test/Vegetables/Pepper/Red-Bell-Pepper/x.jpg")["produce"]) == "pepper"
    assert TAX.decode("produce", map_path(TAX, "grocery_store_klasson", "dataset/val/Fruit/Satsumas/x.jpg")["produce"]) == "mandarin"
    assert TAX.decode("produce", map_path(TAX, "grocery_store_klasson", "dataset/val/Fruit/Lime/x.jpg")["produce"]) == "other"
    assert map_path(TAX, "grocery_store_klasson", "dataset/train/Packages/Milk/Arla/x.jpg") is None
    assert map_path(TAX, "grocery_store_klasson", "sample_images/natural/x.jpg") is None


def test_fruits360_real_names():
    m = lambda c: map_path(TAX, "fruits360_original", f"Training/{c}/r0_1.jpg")
    assert m("Avocado Black 1")["ripeness"] is None  # skin colour is cultivar-dependent -> no ripeness label
    assert m("Orange peeled 1") is None
    assert TAX.decode("produce", m("apple_granny_smith_1")["produce"]) == "apple"
    assert TAX.decode("produce", m("Tomato Cherry Red 2")["produce"]) == "tomato"
    assert TAX.decode("produce", m("Quince 2")["produce"]) == "other"


def test_max_per_group_and_force_split(tmp_path):
    root = tmp_path / "f360"
    for cls in ("Banana 3", "Peach 3"):
        d = root / "Training" / cls
        d.mkdir(parents=True)
        for k in range(100):
            (d / f"r0_{k}.jpg").write_bytes(b"x")
    samples = list(iter_dataset(TAX, "fruits360_original", root))
    assert len(samples) == 160 and all(s.split_hint == "train" for s in samples)
    again = [s.rel_path for s in iter_dataset(TAX, "fruits360_original", root)]
    assert again == [s.rel_path for s in samples]  # deterministic


def test_open_images_real_class_names():
    vm = TAX.datasets["open_images_v7"]["value_maps"]["produce"]
    assert vm["Orange (fruit)"] == "orange" and vm["Lemon (plant)"] == "lemon"
    for v in vm.values():
        TAX.encode("produce", v)


def test_signoff_rejected_blocks_everything():
    e = registry.load_registry()["grocery_store_klasson"]
    s = {"grocery_store_klasson": {"dataset_id": "grocery_store_klasson", "reviewer": "x", "date": "d",
                                   "evidence_url": "u", "decision": "rejected"}}
    for p in registry.PURPOSES:
        assert not registry.is_allowed(e, p, s)[0]


def test_signoff_file_schema():
    registry.load_signoffs()  # raises on malformed entries


def test_kappa():
    cats = ["unripe", "partially_ripe", "ripe", "overripe"]
    a = ["unripe", "ripe", "ripe", "overripe", "partially_ripe"] * 10
    assert cohen_kappa(a, a, cats) == 1.0
    assert cohen_kappa(a, a, cats, "quadratic") == 1.0
    near = ["partially_ripe" if x == "unripe" else x for x in a]
    far = ["overripe" if x == "unripe" else x for x in a]
    assert cohen_kappa(a, near, cats, "quadratic") > cohen_kappa(a, far, cats, "quadratic")


def test_pairwise_from_rows():
    rows = [{"i": "1", "annotator": "b", "ripeness": "ripe"}, {"i": "1", "annotator": "a", "ripeness": "unripe"},
            {"i": "2", "annotator": "a", "ripeness": "ripe"}]
    assert pairwise_from_rows(rows, "i", "ripeness") == (["unripe"], ["ripe"])


def test_merge_consensus_ties_become_sets(tmp_path):
    cols = ["path", "fruit_instance_id", "produce", "ripeness", "freshness", "visual_spoilage", "annotator", "notes"]
    def write(name, rows):
        with open(tmp_path / name, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    base = {"path": "p1", "fruit_instance_id": "banana-B1-1", "produce": "banana", "visual_spoilage": "", "notes": ""}
    write("a.csv", [{**base, "ripeness": "ripe", "freshness": "fresh", "annotator": "a"}])
    write("b.csv", [{**base, "ripeness": "partially_ripe", "freshness": "fresh", "annotator": "b"}])
    _, labels, errors = merge_annotations.merge([tmp_path / "a.csv", tmp_path / "b.csv"])
    assert not errors
    assert labels[0]["ripeness"] == "partially_ripe|ripe" and labels[0]["freshness"] == "fresh"
    assert labels[0]["visual_spoilage"] == ""


def _collection(root: Path, rows: list[dict]):
    (root / "images").mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    for r in rows:
        p = root / r["path"]
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(rng.integers(0, 255, (96, 96, 3), dtype=np.uint8)).save(p)
    with open(root / "labels.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def _row(**kw):
    r = {"path": "images/banana-B1-1/20260901_1.jpg", "fruit_instance_id": "banana-B1-1", "produce": "banana",
         "variety": "Cavendish", "capture_date": "2026-09-01", "day": "0", "device": "iPhone 12", "lighting": "daylight",
         "background": "counter", "distance_cm": "40", "ripeness": "unripe", "freshness": "fresh", "visual_spoilage": "none",
         "storage": "counter", "cut_check": "n/a"}
    r.update(kw)
    return r


def test_validate_collection_ok_and_errors(tmp_path):
    good = tmp_path / "good"
    _collection(good, [_row(), _row(path="images/banana-B1-1/20260903_1.jpg", capture_date="2026-09-03", day="2", ripeness="partially_ripe|ripe")])
    assert validate_collection.validate(good) == []
    bad = tmp_path / "bad"
    _collection(bad, [_row(), _row(path="images/banana-B1-1/20260903_1.jpg", capture_date="2026-09-03", day="5",
                                   produce="apple", ripeness="ripe", lighting="neon", freshness="rotten")])
    errs = "\n".join(validate_collection.validate(bad))
    for needle in ("inconsistent with capture_date", "no ripeness grading guide", "lighting", "'rotten'", "multiple produce"):
        assert needle in errs, needle


def test_verify_licenses_script_runs():
    out = subprocess.run([sys.executable, "scripts/verify_licenses.py"], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0 and "grocery_store_klasson" in out.stdout
