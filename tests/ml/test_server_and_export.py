"""Export bundle + self-hosted server contract, using a tiny random model (wiring only)."""
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("timm")
pytest.importorskip("onnxruntime")
pytest.importorskip("fastapi")

from PIL import Image  # noqa: E402

from ml.common.taxonomy import HEADS, load_taxonomy  # noqa: E402
from ml.training.model import MultiTaskProduceNet  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def bundle_dir(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("exp")
    tax = load_taxonomy()
    cfg = {"experiment": "tiny", "data": {"image_size": 96, "processed_dir": "nonexistent"},
           "model": {"backbone": "mobilenetv3_small_050", "pretrained": False, "ripeness_mode": "shared", "dropout": 0.0}}
    net = MultiTaskProduceNet("mobilenetv3_small_050", *(tax.num_classes(h) for h in HEADS), pretrained=False)
    run = tmp / "run"
    run.mkdir()
    torch.save({"model": net.state_dict(), "cfg": cfg, "epoch": 0}, run / "best.pt")
    (run / "temperature.json").write_text(json.dumps({"produce": 1.5}))
    (run / "thresholds.json").write_text(json.dumps({"produce_min_prob": 0.6, "tuned_on": {}}))
    (run / "supported_heads.json").write_text(json.dumps({}))
    out = tmp / "export"
    r = subprocess.run([sys.executable, "-m", "ml.export.export", "--ckpt", str(run / "best.pt"), "--out", str(out)],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    return out


def test_bundle_contract(bundle_dir):
    b = json.loads((bundle_dir / "bundle.json").read_text())
    assert b["thresholds"]["produce_min_prob"] == 0.6 and "tuned_on" not in b["thresholds"]
    assert b["temperatures"] == {"produce": 1.5}
    assert set(b["outputs"]) == set(HEADS) and b["input"]["size"] == 96
    assert len(b["files"]["model.onnx"]["sha256"]) == 64
    assert b["label_he"]["ripeness"]["ripe"] == "בשל"


def _jpeg(color=(200, 180, 40), noise=True):
    rng = np.random.default_rng(0)
    arr = np.full((300, 400, 3), color, np.uint8)
    if noise:
        arr = np.clip(arr + rng.integers(-60, 60, arr.shape), 0, 255).astype(np.uint8)
    b = io.BytesIO()
    Image.fromarray(arr).save(b, "JPEG")
    return b.getvalue()


def test_server_endpoints(bundle_dir, monkeypatch):
    monkeypatch.setenv("PRODUCE_BUNDLE", str(bundle_dir))
    from fastapi.testclient import TestClient

    from server import app as srv
    srv.engine.cache_clear()
    c = TestClient(srv.app)
    assert c.get("/healthz").json()["ok"]
    r = c.post("/v1/analyze", files={"image": ("a.jpg", _jpeg(), "image/jpeg")}).json()
    assert [len(r["logits"][h]) for h in HEADS] == [23, 4, 3, 3]
    s = c.post("/v1/scan", files={"image": ("a.jpg", _jpeg(), "image/jpeg")}).json()
    assert s["status"] in {"ok", "unsure", "not_produce", "retake"} and "הערכה חזותית" in s["disclaimer_he"]
    dark = c.post("/v1/scan", files={"image": ("d.jpg", _jpeg((5, 5, 5), noise=False), "image/jpeg")}).json()
    assert dark["status"] == "retake"
    assert c.post("/v1/scan", files={"image": ("x.jpg", b"not an image", "image/jpeg")}).status_code == 400


def test_server_preprocess_matches_training_eval_transform(bundle_dir, monkeypatch):
    """App/server preprocessing must equal ml.training.augment.build_eval_transform."""
    monkeypatch.setenv("PRODUCE_BUNDLE", str(bundle_dir))
    from ml.training.augment import build_eval_transform
    from server import app as srv
    srv.engine.cache_clear()
    img = Image.open(io.BytesIO(_jpeg())).convert("RGB")
    a = srv.engine().preprocess(img)[0]
    b = build_eval_transform({"data": {"image_size": 96}})(img).numpy()
    assert a.shape == b.shape and np.abs(a - b).mean() < 0.02
