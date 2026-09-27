#!/usr/bin/env bash
# C3 (no lookalike negatives) and C4 (white-balance augmentation) vs C1. Commercial data only.
set -uo pipefail
cd "$(dirname "$0")/.."
LOOK='(^|/)(Lime|Red-Grapefruit|Zucchini|Potato|Passion-Fruit)/'
P=data/processed_commercial
for cfg in p4_c3_no_lookalike_other p4_c4_white_balance; do
  log="runs_${cfg}.log"
  python3 -m ml.training.train --config "ml/configs/${cfg}.yaml" > "$log" 2>&1 || { echo "FAIL $cfg"; continue; }
  run=$(grep '^RUN_DIR' "$log" | cut -d' ' -f2)
  python3 -m ml.evaluation.evaluate --ckpt "$run/best.pt" --processed $P --splits val --tune --exclude-source-regex "$LOOK" --out "$run/eval_val_tune.json" >> "$log" 2>&1
  # in-distribution test subset (lookalikes removed) + lookalikes as "should abstain"
  python3 -m ml.evaluation.evaluate --ckpt "$run/best.pt" --processed $P --splits test --quality-gate --save-preds --ood-source-regex "$LOOK" --out "$run/eval_test_look.json" >> "$log" 2>&1
  python3 -m ml.evaluation.evaluate --ckpt "$run/best.pt" --processed $P --splits test --quality-gate --out "$run/eval_test.json" >> "$log" 2>&1
  python3 -m ml.evaluation.evaluate --ckpt "$run/best.pt" --processed $P --splits test --stress warm_light --quality-gate --out "$run/eval_test_warm.json" >> "$log" 2>&1
  echo "DONE $cfg $run"
done
echo ALLDONE
