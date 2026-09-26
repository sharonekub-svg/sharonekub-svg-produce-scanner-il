"""Self-hosted inference server — the fallback path in docs/architecture.md.

Runs OUR exported ONNX model (no third-party AI API). Stateless: the uploaded photo is
processed in memory and never written to disk or logged.

  PRODUCE_BUNDLE=exports/v1 uvicorn server.app:app --host 0.0.0.0 --port 8080

Endpoints
  GET  /healthz           -> {"ok": true, "model_id": ...}
  GET  /v1/bundle         -> bundle.json (the app reads classes/thresholds from here)
  POST /v1/analyze        -> raw logits + quality stats; the app runs decide() itself
  POST /v1/scan           -> full ScanResult (Hebrew) via ml.inference.decision
"""
from __future__ import annotations

import io
import json
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from ml.common.taxonomy import HEADS, load_taxonomy
from ml.evaluation.calibration import softmax
from ml.evaluation.ood import energy
from ml.inference import decision, quality

MAX_BYTES = 12 * 1024 * 1024
app = FastAPI(title="Produce Scanner inference", version="1")


class Engine:
    def __init__(self, bundle_dir: Path):
        import onnxruntime as ort
        self.bundle = json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))
        onnx_file = "model.int8.onnx" if (bundle_dir / "model.int8.onnx").exists() else "model.onnx"
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = int(os.environ.get("PRODUCE_THREADS", "2"))
        self.sess = ort.InferenceSession(str(bundle_dir / onnx_file), opts, providers=["CPUExecutionProvider"])
        self.onnx_file = onnx_file
        self.tax = load_taxonomy()

    def preprocess(self, img: Image.Image) -> np.ndarray:
        """Must match ml.training.augment.build_eval_transform and the app's native path:
        resize short side to size*ratio, centre-crop size x size, ImageNet normalisation."""
        inp = self.bundle["input"]
        size, ratio = inp["size"], inp["resize_ratio"]
        w, h = img.size
        s = int(size * ratio) / min(w, h)
        img = img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.Resampling.BILINEAR)
        w, h = img.size
        left, top = (w - size) // 2, (h - size) // 2
        img = img.crop((left, top, left + size, top + size))
        x = np.asarray(img, dtype=np.float32) / 255.0
        x = (x - np.array(inp["mean"], dtype=np.float32)) / np.array(inp["std"], dtype=np.float32)
        return x.transpose(2, 0, 1)[None]

    def logits(self, img: Image.Image) -> dict[str, np.ndarray]:
        outs = self.sess.run(None, {"image": self.preprocess(img)})
        return {h: o[0] for h, o in zip(self.bundle["outputs"].keys(), outs)}


@lru_cache(maxsize=1)
def engine() -> Engine:
    return Engine(Path(os.environ.get("PRODUCE_BUNDLE", "exports/latest")))


async def _read_image(file: UploadFile) -> Image.Image:
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "image too large")
    try:
        from PIL import ImageOps
        img = Image.open(io.BytesIO(data))
        img.load()
        return ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "not a decodable image")


@app.get("/healthz")
def healthz():
    e = engine()
    return {"ok": True, "model_id": e.bundle["model_id"], "onnx": e.onnx_file}


@app.get("/v1/bundle")
def bundle():
    return engine().bundle


@app.post("/v1/analyze")
async def analyze(image: UploadFile = File(...)):
    img = await _read_image(image)
    e = engine()
    q = quality.assess(img, e.bundle.get("quality"))
    return {"model_id": e.bundle["model_id"],
            "logits": {h: v.tolist() for h, v in e.logits(img).items()},
            "quality": {"ok": q.ok, "reason": q.reason, "mean_luma": q.mean_luma,
                        "laplacian_var": q.laplacian_var, "clipped_frac": q.clipped_frac}}


@app.post("/v1/scan")
async def scan(image: UploadFile = File(...)):
    img = await _read_image(image)
    e = engine()
    q = quality.assess(img, e.bundle.get("quality"))
    lg = e.logits(img)
    temps = e.bundle.get("temperatures", {})
    probs = {h: softmax(lg[h][None], temps.get(h, 1.0))[0] for h in HEADS}
    res = decision.decide(e.tax, probs, e.bundle.get("supported_heads", {}), quality_reason=q.reason,
                          energy_score=float(energy(lg["produce"][None])[0]), thresholds=e.bundle.get("thresholds"))
    return {"model_id": e.bundle["model_id"], **res.to_dict()}
