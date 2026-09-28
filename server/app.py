"""Self-hosted inference server — the fallback path in docs/architecture.md.

Runs OUR exported ONNX model (no third-party AI API). Stateless: the uploaded photo is
processed in memory and never written to disk or logged.

  uvicorn server.app:app --host 0.0.0.0 --port 8080          # uses server/model/ (shipped model)
  PRODUCE_BUNDLE=exports/v1 uvicorn server.app:app ...       # or any exported bundle
  Deployed on Vercel via pyproject.toml [tool.vercel] entrypoint.

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
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from ml.common.taxonomy import HEADS, load_taxonomy, restrict_produce
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
        self.tax = restrict_produce(load_taxonomy(), self.bundle["outputs"]["produce"])

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
    default = Path(__file__).resolve().parent / "model"
    return Engine(Path(os.environ.get("PRODUCE_BUNDLE", default)))


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


WEB = Path(__file__).resolve().parent / "web"
# Copy of app/src/model/produce_care.json (app/ is not deployed); tests/ml/test_server_and_export.py keeps them equal.
CARE = json.loads((WEB / "produce_care.json").read_text(encoding="utf-8"))


def storage_tip_he(produce: str | None) -> str | None:
    """Same text as the app's STORAGE_TIP_HE (app/src/model/advice.ts): tip + the ethylene rule."""
    c = CARE["produce"].get(produce or "")
    if not c:
        return None
    g = CARE["general_he"]
    eth = g["ethylene_producer"] if c["ethylene"]["producer"] else g["ethylene_sensitive"] if c["ethylene"]["sensitive"] else ""
    return f"{c['tip_he']} {eth}" if eth else c["tip_he"]


def touch_tip_he(produce: str | None) -> str | None:
    """General hand check for this produce type (texture can't be measured from a photo)."""
    return (CARE["produce"].get(produce or "") or {}).get("touch_he")


def surface_he(d: dict) -> str | None:
    """Skin appearance in words, derived only from the freshness/spoilage heads (no new claims)."""
    sp = d.get("visual_spoilage") or {}
    fr = d.get("freshness") or {}
    spl = sp.get("label") if sp.get("available") else None
    frl = fr.get("label") if fr.get("available") else None
    if spl is None and frl is None:
        return None
    if spl == "severe" or frl == "spoiled":
        return "סימני ריקבון נראים בקליפה"
    if spl == "defects":
        return "פגמים נראים בקליפה"
    if spl == "mild" or frl in ("declining", "not_fresh"):
        return "כתמים קלים או סימני התייבשות"
    if spl in (None, "none") and frl in (None, "fresh"):
        return "קליפה נקייה, בלי פגמים נראים"
    return None


@app.get("/")
def root(request: Request):
    # Browsers get the scan page (docs/mobile.md: web fallback until the iOS build); programs get JSON.
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse((WEB / "index.html").read_text(encoding="utf-8"))
    return {"service": "produce-scanner inference API", "endpoints": ["/healthz", "/v1/bundle", "POST /v1/analyze", "POST /v1/scan"],
            "note": "Visual assessment only; not a food-safety guarantee."}


SW_JS = """// Offline shell only: the page and its icons. Scans (/v1/*) always go to the network.
const C = 'shell-v1', SHELL = ['/web/manifest.webmanifest', '/web/icon-192.png', '/web/favicon.png'];
self.addEventListener('install', e => { e.waitUntil(caches.open(C).then(c => c.addAll(SHELL))); self.skipWaiting(); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== C).map(k => caches.delete(k))))); self.clients.claim(); });
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin || u.pathname.startsWith('/v1/')) return;
  e.respondWith(fetch(e.request).then(r => { const cp = r.clone(); caches.open(C).then(c => c.put(e.request, cp)); return r; })
    .catch(() => caches.match(e.request)));
});
"""


@app.get("/sw.js")
def service_worker():
    return Response(SW_JS, media_type="application/javascript", headers={"Cache-Control": "no-cache"})


app.mount("/web", StaticFiles(directory=WEB), name="web")


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


def _probs(e, img) -> tuple[dict, float, str | None]:
    q = quality.assess(img, e.bundle.get("quality"))
    lg = e.logits(img)
    temps = e.bundle.get("temperatures", {})
    probs = {h: softmax(lg[h][None], temps.get(h, 1.0))[0] for h in HEADS}
    return probs, float(energy(lg["produce"][None])[0]), q.reason


def _combine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Two photos of the same fruit: normalised geometric mean per head (same as app/src/model/advice.ts)."""
    g = np.sqrt(np.maximum(a, 1e-12) * np.maximum(b, 1e-12))
    return g / g.sum()


@app.post("/v1/scan")
async def scan(image: UploadFile = File(...), image2: UploadFile | None = File(None)):
    """One photo, or two angles of the same fruit ("צלם מזווית נוספת": evidence of both is combined)."""
    e = engine()
    probs, en, qreason = _probs(e, await _read_image(image))
    angles = 1
    if image2 is not None:
        p2, en2, q2 = _probs(e, await _read_image(image2))
        if q2 is None and qreason is None:  # two good photos: combine the evidence
            probs, en, angles = {h: _combine(probs[h], p2[h]) for h in HEADS}, max(en, en2), 2
        elif q2 is None:  # only the second photo is usable
            probs, en, qreason = p2, en2, None
        # a bad second photo never spoils a good first one
    res = decision.decide(e.tax, probs, e.bundle.get("supported_heads", {}), quality_reason=qreason,
                          energy_score=en, thresholds=e.bundle.get("thresholds"))
    top = np.argsort(-probs["produce"])[:3]
    top3 = [{"produce": e.tax.produce[int(i)], "he": e.tax.produce_meta[e.tax.produce[int(i)]]["he"],
             "prob": round(float(probs["produce"][i]), 4)} for i in top]
    d, ok = res.to_dict(), res.status == "ok"
    return {"model_id": e.bundle["model_id"], **d, "angles": angles, "top3": top3,
            "storage_tip_he": storage_tip_he(res.produce) if ok else None,
            "surface_he": surface_he(d) if ok else None,
            "touch_tip_he": touch_tip_he(res.produce) if ok else None}
