#!/usr/bin/env python3
"""Hard-example set (evaluation.md test set #4): confident errors + near-misses from a
predictions file (evaluate.py --save-preds). Writes <preds>.hard.json and a contact sheet.

  python scripts/mine_hard_examples.py --preds runs/X/eval_test.preds.jsonl --processed data/processed_commercial
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preds", type=Path, required=True)
    ap.add_argument("--processed", type=Path, required=True)
    ap.add_argument("--n", type=int, default=40)
    args = ap.parse_args()
    rows = [json.loads(l) for l in args.preds.read_text(encoding="utf-8").splitlines()]
    wrong = sorted((r for r in rows if not r["ood"] and r["pred"] != r["label"]), key=lambda r: -r["conf"])
    confusions = Counter((r["label"], r["pred"]) for r in wrong)
    shown_wrong = [r for r in wrong if r["status"] == "ok"]
    hard = {"n_rows": len(rows), "n_errors": len(wrong),
            "errors_shown_to_user": len(shown_wrong),
            "top_confusions": [{"true": t, "pred": p, "n": n} for (t, p), n in confusions.most_common(15)],
            "confident_errors": wrong[: args.n]}
    out = args.preds.with_suffix(".hard.json")
    out.write_text(json.dumps(hard, indent=2, ensure_ascii=False), encoding="utf-8")
    T, cols = 128, 8
    sel = wrong[: args.n]
    sheet = Image.new("RGB", (cols * T, ((len(sel) + cols - 1) // cols) * (T + 24)), "white")
    d = ImageDraw.Draw(sheet)
    for k, r in enumerate(sel):
        im = Image.open(args.processed / r["image"]).convert("RGB")
        im.thumbnail((T - 4, T - 4))
        x, y = (k % cols) * T, (k // cols) * (T + 24)
        sheet.paste(im, (x + 2, y + 2))
        d.text((x + 2, y + T), f"{r['label'][:9]}>{r['pred'][:9]} {r['conf']:.2f}", fill="black")
    sheet.save(out.with_suffix(".jpg"), quality=85)
    print(json.dumps({k: hard[k] for k in ("n_rows", "n_errors", "errors_shown_to_user", "top_confusions")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
