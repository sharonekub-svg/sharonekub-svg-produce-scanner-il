#!/usr/bin/env bash
# Release checklist (docs/beta-and-production.md) as one command. Stops at the first failure.
#   scripts/release_model.sh <run_dir> <processed_dir> <version> [--allow-gate-failures]
# Steps: licence gate on the training manifest -> export (ONNX + Core ML fp16) -> ONNX/PyTorch
# parity -> test evaluation with quality gate -> acceptance gates -> sync into the app.
set -euo pipefail
RUN="${1:?run dir}"; PROC="${2:?processed dir}"; VER="${3:?version}"; ALLOW="${4:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
OUT="exports/$VER"

echo "[1/6] licence gate (commercial)"
python3 scripts/verify_licenses.py --manifest "$PROC/manifest.jsonl" --purpose commercial_training | tail -1

echo "[2/6] export"
python3 -m ml.export.export --ckpt "$RUN/best.pt" --out "$OUT" --coreml --fp16 > "$OUT.export.log" 2>&1 || { tail "$OUT.export.log"; exit 1; }

echo "[3/6] ONNX == PyTorch"
python3 -m ml.export.verify_onnx --ckpt "$RUN/best.pt" --export "$OUT" --processed "$PROC" --splits test > /dev/null 2>&1
python3 - "$OUT" <<'EOF'
import json, sys
r = json.load(open(f"{sys.argv[1]}/verify_report.json"))["variants"]["model.onnx"]
assert r["top1_agreement_with_torch"] == 1.0, r
print("  agreement 100%, size", r["size_mb"], "MB")
EOF

echo "[4/6] test evaluation (quality gate on)"
python3 -m ml.evaluation.evaluate --ckpt "$RUN/best.pt" --processed "$PROC" --splits test --quality-gate --save-preds \
  --out "$OUT/eval_test.json" > /dev/null 2>&1

echo "[5/6] acceptance gates"
python3 - "$RUN" "$OUT" "$ALLOW" <<'EOF'
import json, sys, yaml
from ml.evaluation.gates import check_gates
run, out, allow = sys.argv[1:4]
cfg = yaml.safe_load(open(f"{run}/config.yaml"))
res = json.load(open(f"{out}/eval_test.json"))
fails = check_gates(res["heads"], cfg.get("gates", {}))
json.dump({"passed": not fails, "failures": fails}, open(f"{out}/release_gates.json", "w"), indent=2)
print("  PASS" if not fails else "  FAIL:\n   - " + "\n   - ".join(fails))
if fails and allow != "--allow-gate-failures":
    sys.exit("gates failed: not releasing (use --allow-gate-failures only for internal/dev builds)")
EOF

echo "[6/6] sync into app"
scripts/sync_model_to_app.sh "$OUT"
echo "released $VER"
