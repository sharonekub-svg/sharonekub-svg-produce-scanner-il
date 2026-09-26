#!/usr/bin/env bash
# Commercial-track candidates (Grocery Store only): train -> tune on val -> evaluate on official test.
set -uo pipefail
cd "$(dirname "$0")/.."
for cfg in "$@"; do
  log="runs_${cfg}.log"
  python3 -m ml.training.train --config "ml/configs/${cfg}.yaml" > "$log" 2>&1 || { echo "FAIL train $cfg"; continue; }
  run=$(grep '^RUN_DIR' "$log" | cut -d' ' -f2)
  python3 -m ml.evaluation.evaluate --ckpt "$run/best.pt" --processed data/processed_commercial --splits val --tune --out "$run/eval_val_tune.json" >> "$log" 2>&1
  python3 -m ml.evaluation.evaluate --ckpt "$run/best.pt" --processed data/processed_commercial --splits test --quality-gate --out "$run/eval_test.json" >> "$log" 2>&1
  echo "DONE $cfg $run"
done
