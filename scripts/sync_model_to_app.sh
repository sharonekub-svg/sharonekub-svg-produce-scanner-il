#!/usr/bin/env bash
# Copy an exported model bundle into the app (bundle.json, credits, Core ML package).
#   scripts/sync_model_to_app.sh exports/v1
set -euo pipefail
EXP="${1:?usage: sync_model_to_app.sh <export dir>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cp "$EXP/bundle.json" "$ROOT/app/assets/model/bundle.json"
python3 "$ROOT/scripts/gen_credits.py" --bundle "$EXP/bundle.json" --out "$ROOT/app/assets/model/credits.json"
rm -rf "$ROOT/app/modules/produce-model/models/ProduceScanner.mlpackage"
if [ -d "$EXP/ProduceScanner.mlpackage" ]; then
  cp -R "$EXP/ProduceScanner.mlpackage" "$ROOT/app/modules/produce-model/models/"
else
  echo "warning: no ProduceScanner.mlpackage in $EXP (export with --coreml); app will use remote mode" >&2
fi
echo "synced $(python3 -c "import json;print(json.load(open('$EXP/bundle.json'))['model_id'])")"
