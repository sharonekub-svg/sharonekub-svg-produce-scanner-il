import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from ml.preprocessing import splits

ROOT = Path(__file__).resolve().parents[2]


def test_carve_val_from_train_group_safe_and_respects_frozen():
    groups = [f"g{i // 3}" for i in range(600)]
    strata = ["a" if (i // 3) % 2 else "b" for i in range(600)]
    base = ["train"] * 480 + ["test"] * 120
    frozen = [i < 30 for i in range(600)]
    out = splits.carve_val_from_train(groups, base, strata, 0.15, seed=1, frozen=frozen)
    assert splits.check_no_leakage(groups, out) == []
    assert all(s == "train" for s in out[:30])            # frozen (e.g. Fruits-360) never moves
    assert out[480:] == ["test"] * 120                     # official test untouched
    assert 0.10 < out.count("val") / 480 < 0.20
    assert out == splits.carve_val_from_train(groups, base, strata, 0.15, seed=1, frozen=frozen)


def test_stress_variants_deterministic_and_change_image():
    from ml.evaluation.evaluate import Stress
    rng = np.random.default_rng(0)
    img = Image.fromarray(rng.integers(0, 255, (120, 160, 3), dtype=np.uint8))
    for kind in ("dark", "blur", "jpeg", "warm_light", "occlusion"):
        a, b = Stress(kind)(img), Stress(kind)(img)
        assert np.array_equal(np.asarray(a), np.asarray(b)), kind
        assert not np.array_equal(np.asarray(a), np.asarray(img)), kind
    assert np.asarray(Stress("dark")(img)).mean() < np.asarray(img).mean() * 0.6


def test_gen_credits(tmp_path):
    b = tmp_path / "bundle.json"
    b.write_text(json.dumps({"model_id": "m@1", "training_datasets": ["grocery_store_klasson", "open_images_v7"]}))
    out = tmp_path / "credits.json"
    r = subprocess.run([sys.executable, "scripts/gen_credits.py", "--bundle", str(b), "--out", str(out)],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    c = json.loads(out.read_text())
    assert [d["dataset_id"] for d in c["datasets"]] == ["grocery_store_klasson", "open_images_v7"]
    assert "MIT" in c["datasets"][0]["license"]


def test_decision_fixtures_cover_all_branches():
    f = json.loads((ROOT / "app/__tests__/fixtures/decision_cases.json").read_text(encoding="utf-8"))
    recs = {c["expected"]["recommendation"] for c in f["cases"]}
    assert {"discard", "wait", "wait_little", "eat_now", "eat_soon", "inspect"} <= recs
