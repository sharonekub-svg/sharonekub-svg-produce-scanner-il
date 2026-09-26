# Inference API

FastAPI app running **our** exported model with ONNX Runtime (no third-party AI API).
The app uses it only in `remote` mode (`app/app.json → extra.inference`); the default is on-device Core ML.

| Endpoint | |
|---|---|
| `GET /` · `GET /healthz` | service info · model id |
| `GET /v1/bundle` | class lists, thresholds, temperatures (the app syncs from this) |
| `POST /v1/analyze` (multipart `image`) | raw logits + quality stats; the app runs `decide()` |
| `POST /v1/scan` (multipart `image`) | full Hebrew `ScanResult` |

Photos are processed in memory and never stored or logged.

## Deploy

- **Vercel**: `pyproject.toml` → `[tool.vercel] entrypoint = "server.app:app"`. Vercel installs the root
  `requirements.txt` (runtime only). `.vercelignore` keeps the bundle to the API code, `data/label_mapping.json`
  and the shipped model (`server/model/`). Measured locally with the same files and a clean venv: ~185 MB of
  dependencies + 17 MB model; `/healthz`, `/v1/scan` on real photos and bad-upload rejection all verified.
  Request bodies must stay under Vercel's 4.5 MB limit — the app uploads a 768-px JPEG (~150 KB).
- **Docker**: `docker build -f server/Dockerfile -t produce-scanner-api . && docker run -p 8080:8080 produce-scanner-api`
- **Local**: `uvicorn server.app:app --port 8080`

## Changing the model

`scripts/release_model.sh …` produces `exports/<version>/`; copy its `model.onnx` and `bundle.json` into
`server/model/` (the files' SHA-256 is recorded in `bundle.json` and checked by `tests/ml/test_shipped_model.py`).
