"""The model shipped with the API (server/model/) must match its bundle and load in ONNX Runtime."""
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "server" / "model"


def test_bundle_hash_matches_model():
    b = json.loads((MODEL / "bundle.json").read_text(encoding="utf-8"))
    sha = hashlib.sha256((MODEL / "model.onnx").read_bytes()).hexdigest()
    assert b["files"]["model.onnx"]["sha256"] == sha
    assert b["model_id"] and b["outputs"]["produce"][-1] == "other"


def test_shipped_model_serves(monkeypatch):
    pytest.importorskip("onnxruntime")
    pytest.importorskip("fastapi")
    import io

    import numpy as np
    from fastapi.testclient import TestClient
    from PIL import Image

    monkeypatch.delenv("PRODUCE_BUNDLE", raising=False)
    from server import app as srv
    srv.engine.cache_clear()
    c = TestClient(srv.app)
    assert c.get("/healthz").json()["model_id"].startswith("p5_c8")
    rng = np.random.default_rng(0)
    buf = io.BytesIO()
    Image.fromarray(rng.integers(0, 255, (320, 320, 3), dtype=np.uint8)).save(buf, "JPEG")
    r = c.post("/v1/scan", files={"image": ("x.jpg", buf.getvalue(), "image/jpeg")}).json()
    assert r["status"] in {"ok", "unsure", "not_produce", "retake"}
