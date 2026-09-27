#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
LOOK='(^|/)(Lime|Red-Grapefruit|Zucchini|Potato|Passion-Fruit)/'
P=data/processed_commercial_v2
cfg=${1:-p4_c5_named_negatives}; log="runs_${cfg}.log"
python3 -m ml.training.train --config "ml/configs/${cfg}.yaml" > "$log" 2>&1 || { echo "FAIL"; exit 1; }
run=$(grep '^RUN_DIR' "$log" | cut -d' ' -f2)
python3 -m ml.evaluation.evaluate --ckpt "$run/best.pt" --processed $P --splits val --tune --out "$run/eval_val_tune.json" >> "$log" 2>&1
python3 -m ml.evaluation.evaluate --ckpt "$run/best.pt" --processed $P --splits test --quality-gate --save-preds --ood-source-regex "$LOOK" --out "$run/eval_test_look.json" >> "$log" 2>&1
python3 -m ml.evaluation.evaluate --ckpt "$run/best.pt" --processed $P --splits test --quality-gate --out "$run/eval_test.json" >> "$log" 2>&1
python3 -m ml.evaluation.evaluate --ckpt "$run/best.pt" --processed $P --splits test --stress warm_light --quality-gate --out "$run/eval_test_warm.json" >> "$log" 2>&1
echo "DONE $cfg $run"
