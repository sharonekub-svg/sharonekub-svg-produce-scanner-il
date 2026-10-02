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
        self.siglip = self.bundle.get("backbone") == "siglip2"
        if self.siglip:  # v0.8+: SigLIP2 encoder + linear heads (ml/siglip/features.py, scripts/siglip_train_heads.py)
            from ml.siglip.features import Encoder
            self.encoder = Encoder(bundle_dir / "vision.onnx", threads=int(os.environ.get("PRODUCE_THREADS", "2")))
            self.heads = dict(np.load(bundle_dir / "heads.npz"))
            self.onnx_file = "vision.onnx"
            self.tax = restrict_produce(load_taxonomy(), self.bundle["outputs"]["produce"])
            return
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
        return self.logits_many([img])[0]

    def logits_many(self, imgs: list[Image.Image]) -> list[dict[str, np.ndarray]]:
        """One encoder pass for several photos (the app's 2-second "short video" frames)."""
        if self.siglip:
            return [self._heads(e) for e in self.encoder(imgs)]
        return [self._logits_cnn(img) for img in imgs]

    def _heads(self, e: np.ndarray) -> dict[str, np.ndarray]:
        hd = self.heads
        neg = e @ hd["neg_W"].T
        other = float(neg.max() + np.log(np.exp(neg - neg.max()).sum()) + hd["produce_b"][-1])
        out = {"produce": np.concatenate([e @ hd["produce_W"].T + hd["produce_b"][:-1], [other]]).astype(np.float32)}
        for h in ("ripeness", "freshness", "visual_spoilage"):
            out[h] = (e @ hd[f"{h}_W"].T + hd[f"{h}_b"]).astype(np.float32)
        if "general_ab" in hd:  # general rotten-vs-fresh logit per produce type (types without a verified head)
            a, b = hd["general_ab"]
            out["freshness_general"] = (a * (hd["general_bad_W"] @ e - hd["general_fresh_W"] @ e) + b).astype(np.float32)
        if "condition_W" in hd:  # condition head: logit of P(good condition), one per produce output
            out["condition"] = (float(e @ hd["condition_W"]) + hd["condition_b"]).astype(np.float32)
            if "condition_g_W" in hd:  # v0.14 graded types: own P(good) head + P(rotten | not good)
                g = (float(e @ hd["condition_g_W"]) + hd["condition_g_b"]).astype(np.float32)
                out["condition"] = np.where(hd["condition_graded"] > 0, g, out["condition"]).astype(np.float32)
                out["condition_rot"] = (float(e @ hd["condition_r_W"]) + hd["condition_r_b"]).astype(np.float32)
        return out

    def _logits_cnn(self, img: Image.Image) -> dict[str, np.ndarray]:
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
    """Skin appearance in words, derived only from the freshness/spoilage/condition heads (no new claims)."""
    c = d.get("condition") or {}
    if c.get("available"):
        if d.get("low_confidence"):
            return None
        return {"good": "קליפה נקייה, בלי פגמים נראים", "early": "סימנים ראשונים: כתמים, ריכוך או פגמים קטנים"}.get(
            c.get("label"), "פגמים או סימני ריקבון נראים בקליפה")
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


# The phone app is the product. Browsers get the app's own web build (scripts/build_app_preview.sh) as a
# preview of the phone screens; scans from it go to /v1/analyze here. The older hand-made page stays at /web/index.html.
PREVIEW = WEB / "preview"
APP_ROUTES = ("history", "info", "result", "welcome", "signin", "credits", "auth-callback", "landing", "profile")


def _preview_page() -> HTMLResponse:
    return HTMLResponse((PREVIEW / "index.html").read_text(encoding="utf-8"), headers={"Cache-Control": "no-cache"})


@app.get("/")
def root(request: Request):
    # Browsers get the app preview; programs get JSON.
    if "text/html" in request.headers.get("accept", ""):
        return _preview_page()
    return {"service": "produce-scanner inference API", "endpoints": ["/healthz", "/v1/bundle", "POST /v1/analyze", "POST /v1/scan"],
            "note": "Visual assessment only; not a food-safety guarantee."}


for _r in APP_ROUTES:  # client-side routes of the app (expo-router, single-page web output)
    app.add_api_route(f"/{_r}", lambda: _preview_page(), methods=["GET"], include_in_schema=False)


@app.get("/privacy", include_in_schema=False)
def privacy():
    # Privacy policy (Google Play listing links here): server/web/privacy.html
    return HTMLResponse((WEB / "privacy.html").read_text(encoding="utf-8"))


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response((PREVIEW / "favicon.ico").read_bytes(), media_type="image/x-icon")


# The old page registered a service worker; this version removes it and its cache from returning browsers.
SW_JS = """self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.map(k => caches.delete(k))))
  .then(() => self.registration.unregister()).then(() => self.clients.matchAll()).then(cs => cs.forEach(c => c.navigate(c.url)))));
"""


@app.get("/sw.js")
def service_worker():
    return Response(SW_JS, media_type="application/javascript", headers={"Cache-Control": "no-cache"})


app.mount("/_expo", StaticFiles(directory=PREVIEW / "_expo"), name="preview_js")
app.mount("/assets", StaticFiles(directory=PREVIEW / "assets"), name="preview_assets")
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


MAX_FRAMES = 6


@app.post("/v1/analyze_many")
async def analyze_many(images: list[UploadFile] = File(...)):
    """Same as /v1/analyze for up to MAX_FRAMES photos in one request (one encoder pass)."""
    if not 1 <= len(images) <= MAX_FRAMES:
        raise HTTPException(400, f"send 1-{MAX_FRAMES} images")
    imgs = [await _read_image(f) for f in images]
    e = engine()
    items = []
    for img, lg in zip(imgs, e.logits_many(imgs)):
        q = quality.assess(img, e.bundle.get("quality"))
        items.append({"logits": {h: v.tolist() for h, v in lg.items()},
                      "quality": {"ok": q.ok, "reason": q.reason, "mean_luma": q.mean_luma,
                                  "laplacian_var": q.laplacian_var, "clipped_frac": q.clipped_frac}})
    return {"model_id": e.bundle["model_id"], "items": items}


def _probs(e, img) -> tuple[dict, float, str | None]:
    q = quality.assess(img, e.bundle.get("quality"))
    lg = e.logits(img)
    temps = e.bundle.get("temperatures", {})
    probs = {h: softmax(lg[h][None], temps.get(h, 1.0))[0] for h in HEADS}
    if "freshness_general" in lg:
        probs["freshness_general"] = 1.0 / (1.0 + np.exp(-lg["freshness_general"]))
    if "condition" in lg:
        probs["condition"] = 1.0 / (1.0 + np.exp(-lg["condition"] / temps.get("condition", 1.0)))
    if "condition_rot" in lg:
        probs["condition_rot"] = 1.0 / (1.0 + np.exp(-lg["condition_rot"]))
    return probs, float(energy(lg["produce"][None])[0]), q.reason


def _combine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Two photos of the same fruit: normalised geometric mean per head (same as app/src/model/advice.ts)."""
    g = np.sqrt(np.maximum(a, 1e-12) * np.maximum(b, 1e-12))
    return g / g.sum()


def _combine_binary(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Per-type probabilities (freshness_general, condition): the same geometric mean over {p, 1-p}."""
    g1 = np.sqrt(np.maximum(a, 1e-12) * np.maximum(b, 1e-12))
    g0 = np.sqrt(np.maximum(1 - a, 1e-12) * np.maximum(1 - b, 1e-12))
    return g1 / (g1 + g0)


@app.post("/v1/scan")
async def scan(image: UploadFile = File(...), image2: UploadFile | None = File(None)):
    """One photo, or two angles of the same fruit ("צלם מזווית נוספת": evidence of both is combined)."""
    e = engine()
    probs, en, qreason = _probs(e, await _read_image(image))
    angles = 1
    if image2 is not None:
        p2, en2, q2 = _probs(e, await _read_image(image2))
        if q2 is None and qreason is None:  # two good photos: combine the evidence
            probs, en, angles = ({h: _combine(probs[h], p2[h]) for h in HEADS}
                                 | {k: _combine_binary(probs[k], p2[k]) for k in ("freshness_general", "condition", "condition_rot")
                                    if k in probs and k in p2}), max(en, en2), 2
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
