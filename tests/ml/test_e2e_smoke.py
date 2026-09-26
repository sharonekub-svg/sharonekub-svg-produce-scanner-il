"""End-to-end smoke test on synthetic images: manifest -> train (few steps) -> ONNX export.
Proves the pipeline wiring only; says NOTHING about model quality."""
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image, ImageFilter

pytest.importorskip("torch")
pytest.importorskip("timm")

from ml.preprocessing.build_manifest import build  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def _make_raw(raw: Path) -> None:
    d = raw / "own_il_collection"
    (d / "img").mkdir(parents=True)
    rng = np.random.default_rng(0)
    rows = []
    produce = ["banana", "apple", "tomato"]
    for fruit in range(30):  # 30 physical fruits, 3 photos each
        for shot in range(3):
            arr = rng.integers(0, 255, (6, 6, 3), dtype=np.uint8)
            img = Image.fromarray(arr).resize((128, 128), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(1))
            p = f"img/f{fruit}_{shot}.jpg"
            img.save(d / p)
            rows.append({"path": p, "fruit_instance_id": f"f{fruit}", "produce": produce[fruit % 3],
                         "ripeness": ["unripe", "ripe", ""][fruit % 3], "freshness": "fresh|declining",
                         "visual_spoilage": ""})
    with open(d / "labels.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def test_pipeline_end_to_end(tmp_path):
    raw, proc = tmp_path / "raw", tmp_path / "processed"
    _make_raw(raw)
    rep = build(["own_il_collection"], "commercial_training", raw, proc, holdout=set(), max_side=128)
    rows = [json.loads(l) for l in (proc / "manifest.jsonl").read_text().splitlines()]
    assert len(rows) == 90
    by_group = {}
    for r in rows:
        by_group.setdefault(r["group"], set()).add(r["split"])
    assert all(len(s) == 1 for s in by_group.values())  # fruit instances never straddle splits
    assert rows[0]["labels"]["freshness"] == ["fresh", "declining"]  # set-valued preserved
    assert rep["dedup"]["metadata_group"] == 60

    cfg = yaml.safe_load((ROOT / "ml/configs/baseline_mobilenetv3.yaml").read_text())
    cfg["data"].update(processed_dir=str(proc), image_size=96)
    cfg["model"].update(backbone="mobilenetv3_small_050", pretrained=False, ripeness_mode="per_produce")
    cfg["train"].update(epochs=1, batch_size=8, num_workers=0)
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))
    out = subprocess.run([sys.executable, "-m", "ml.training.train", "--config", str(cfg_path),
                          "--max-steps", "3", "--runs-dir", str(tmp_path / "runs")],
                         cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, out.stderr[-3000:]
    run_dir = Path([l for l in out.stdout.splitlines() if l.startswith("RUN_DIR")][0].split(" ", 1)[1])
    assert (run_dir / "best.pt").exists() and (run_dir / "gates.json").exists()

    pytest.importorskip("onnx")
    exp = subprocess.run([sys.executable, "-m", "ml.export.export", "--ckpt", str(run_dir / "best.pt"),
                          "--out", str(tmp_path / "export")], cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert exp.returncode == 0, exp.stderr[-3000:]
    bundle = json.loads((tmp_path / "export/bundle.json").read_text())
    assert bundle["outputs"]["ripeness"] == ["unripe", "partially_ripe", "ripe", "overripe"]

    ort = pytest.importorskip("onnxruntime")
    sess = ort.InferenceSession(str(tmp_path / "export/model.onnx"))
    outs = sess.run(None, {"image": np.random.rand(1, 3, 96, 96).astype(np.float32)})
    assert [o.shape[1] for o in outs] == [23, 4, 3, 3]
