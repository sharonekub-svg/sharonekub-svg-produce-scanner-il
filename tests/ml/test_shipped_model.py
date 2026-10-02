"""The model shipped with the API (server/model/) must match its bundle and load in ONNX Runtime."""
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "server" / "model"


def test_bundle_hash_matches_model():
    b = json.loads((MODEL / "bundle.json").read_text(encoding="utf-8"))
    assert b["files"], "bundle must list its files"
    for name, meta in b["files"].items():
        assert hashlib.sha256((MODEL / name).read_bytes()).hexdigest() == meta["sha256"], name
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
    assert c.get("/healthz").json()["model_id"].startswith("siglip2_v0.13")
    rng = np.random.default_rng(0)
    buf = io.BytesIO()
    Image.fromarray(rng.integers(0, 255, (320, 320, 3), dtype=np.uint8)).save(buf, "JPEG")
    r = c.post("/v1/scan", files={"image": ("x.jpg", buf.getvalue(), "image/jpeg")}).json()
    assert r["status"] in {"ok", "unsure", "not_produce", "retake"}


def test_shipped_model_identifies_samples():
    """The three bundled sample photos (also in the app): the right fruit is the model's first guess. The heavily
    rotten apple may stay just under the answer threshold (the app then offers its top guesses, apple first)."""
    pytest.importorskip("onnxruntime")
    from fastapi.testclient import TestClient

    from server import app as srv
    srv.engine.cache_clear()
    c = TestClient(srv.app)
    for f, want in (("banana.jpg", "banana"), ("apple_rotten.jpg", "apple"), ("pomegranate.jpg", "pomegranate")):
        r = c.post("/v1/scan", files={"image": (f, (ROOT / "server/web/samples" / f).read_bytes(), "image/jpeg")}).json()
        assert r["top3"][0]["produce"] == want, (f, r["top3"])
        assert r["status"] == "ok" or (f == "apple_rotten.jpg" and r["status"] == "unsure"), (f, r["status"])


def test_analyze_many_matches_single_analyze():
    """The "short video" endpoint (several frames, one encoder pass) returns the same logits as one-by-one."""
    pytest.importorskip("onnxruntime")
    import numpy as np
    from fastapi.testclient import TestClient

    from server import app as srv
    srv.engine.cache_clear()
    c = TestClient(srv.app)
    names = ("banana.jpg", "apple_rotten.jpg", "pomegranate.jpg")
    blobs = [(ROOT / "server/web/samples" / f).read_bytes() for f in names]
    many = c.post("/v1/analyze_many", files=[("images", (f, b, "image/jpeg")) for f, b in zip(names, blobs)]).json()
    assert many["model_id"].startswith("siglip2_v0.13") and len(many["items"]) == 3
    for (f, b), item in zip(zip(names, blobs), many["items"]):
        one = c.post("/v1/analyze", files={"image": (f, b, "image/jpeg")}).json()
        assert item["quality"] == one["quality"]
        for h, v in one["logits"].items():
            np.testing.assert_allclose(item["logits"][h], v, rtol=1e-4, atol=1e-4)
    assert c.post("/v1/analyze_many", files=[("images", ("x.jpg", blobs[0], "image/jpeg"))] * 7).status_code == 400
