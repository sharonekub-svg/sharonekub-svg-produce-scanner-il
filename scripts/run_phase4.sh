#!/usr/bin/env bash
# Phase 4 benchmark matrix (sequential; CPU). Each run: train -> tune thresholds on val ->
# evaluate test (+ unseen-produce OOD) -> cross-dataset where applicable.
set -uo pipefail
cd "$(dirname "$0")/.."
OOD='(Asparagus|Leek|Red-Beet|Passion-Fruit|Brown-Cap-Mushroom|Common_fig|Radish|Mushroom|Quince|Cherimoya|Pitahaya|Carambola)'
for cfg in "$@"; do
  log="runs_${cfg}.log"
  python3 -m ml.training.train --config "ml/configs/${cfg}.yaml" > "$log" 2>&1 || { echo "FAIL train $cfg"; continue; }
  run=$(grep '^RUN_DIR' "$log" | cut -d' ' -f2)
  ds=$(python3 -c "import yaml;d=yaml.safe_load(open('ml/configs/${cfg}.yaml'))['data'].get('datasets');print(' '.join(d) if d else '')")
  dsarg=${ds:+--datasets $ds}
  python3 -m ml.evaluation.evaluate --ckpt "$run/best.pt" --processed data/processed_research --splits val $dsarg \
      --exclude-source-regex "$OOD" --tune --out "$run/eval_val_tune.json" >> "$log" 2>&1
  python3 -m ml.evaluation.evaluate --ckpt "$run/best.pt" --processed data/processed_research --splits test $dsarg \
      --ood-source-regex "$OOD" --out "$run/eval_test.json" >> "$log" 2>&1
  python3 -m ml.evaluation.evaluate --ckpt "$run/best.pt" --processed data/processed_research --splits test \
      --datasets grocery_store_klasson --ood-source-regex "$OOD" --out "$run/eval_test_grocery.json" >> "$log" 2>&1
  echo "DONE $cfg $run"
done
