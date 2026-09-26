"""Evaluate a checkpoint on a manifest split; optional OOD, stress variants and threshold tuning.

  python -m ml.evaluation.evaluate --ckpt runs/X/best.pt --processed data/processed_commercial \
      --splits test --out runs/X/eval_test.json
  # unseen-produce OOD: classes held out of training via exclude_source_regex
  python -m ml.evaluation.evaluate ... --ood-source-regex "Asparagus|Leek" --splits test
  # tune abstention thresholds on val (writes thresholds.json next to the checkpoint)
  python -m ml.evaluation.evaluate ... --splits val --tune --target-accuracy 0.95
  # synthetic stress proxy (NOT a substitute for the real-world set)
  python -m ml.evaluation.evaluate ... --stress dark

Only produce-head metrics are reported for heads without exact labels in the rows.
"""
from __future__ import annotations

import argparse
import zlib
import json
import re
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from torch.utils.data import DataLoader

from ml.common.taxonomy import HEADS, load_taxonomy
from ml.evaluation import calibration, metrics, ood
from ml.inference.decision import DEFAULT_THRESHOLDS, decide
from ml.training import augment, dataset
from ml.training.train import _produce_condition


UX_MIN_SHOWN_CONFIDENCE = 0.70


class Stress:
    """Deterministic (seeded per image) degradations approximating phone failure modes."""
    def __init__(self, kind: str):
        self.kind = kind

    def __call__(self, img: Image.Image) -> Image.Image:
        rng = np.random.default_rng(zlib.crc32(img.tobytes()[:4096]))  # deterministic across processes
        k = self.kind
        if k == "dark":  # underexposure + sensor noise, as in an evening kitchen
            arr = np.asarray(img, dtype=np.float32) / 255.0
            arr = (arr ** 1.8) * 0.45 + rng.normal(0, 0.03, arr.shape)
            return Image.fromarray((arr.clip(0, 1) * 255).astype(np.uint8))
        if k == "blur":
            return img.filter(ImageFilter.GaussianBlur(radius=max(img.size) / 150))
        if k == "jpeg":
            import io
            b = io.BytesIO(); img.save(b, "JPEG", quality=20); b.seek(0)
            return Image.open(b).convert("RGB")
        if k == "warm_light":  # tungsten white-balance error
            r, g, b = img.split()
            return Image.merge("RGB", (r.point(lambda v: min(255, int(v * 1.15))), g, b.point(lambda v: int(v * 0.75))))
        if k == "occlusion":  # a finger/hand covering ~25% of the frame
            img = img.copy(); w, h = img.size; d = ImageDraw.Draw(img)
            x0 = int(rng.uniform(0, 0.5) * w); y0 = int(rng.uniform(0.3, 0.6) * h)
            d.ellipse((x0, y0, x0 + w // 2, y0 + h), fill=(224, 172, 140))
            return img
        return img


def load_ckpt(path: Path):
    from ml.export.export import load
    net, cfg, tax = load(path)
    run = path.parent
    temps = json.loads((run / "temperature.json").read_text()) if (run / "temperature.json").exists() else {}
    sup = json.loads((run / "supported_heads.json").read_text()) if (run / "supported_heads.json").exists() else {}
    return net, cfg, tax, temps, sup


@torch.no_grad()
def infer(net, rows, root, tax, cfg, stress: str | None, bs=64, workers=4):
    tf = augment.build_eval_transform(cfg)
    if stress:
        st = Stress(stress)
        tf0 = tf
        tf = lambda im: tf0(st(im))  # noqa: E731
    dl = DataLoader(dataset.ManifestDataset(rows, root, tax, tf), bs, num_workers=workers, collate_fn=dataset.collate)
    logits = {h: [] for h in HEADS}
    masks = {h: [] for h in HEADS}
    for x, y in dl:
        o = net(x)  # inference path: ripeness conditioned on predicted produce
        for h in HEADS:
            logits[h].append(o[h].numpy()); masks[h].append(y[h].numpy())
    return {h: np.concatenate(v) for h, v in logits.items()}, {h: np.concatenate(v) for h, v in masks.items()}


def confusion_png(cm: np.ndarray, names: list[str], path: Path) -> None:
    n, c = len(names), 26
    img = Image.new("RGB", (140 + n * c, 140 + n * c), "white")
    d = ImageDraw.Draw(img)
    norm = cm / np.maximum(cm.sum(1, keepdims=True), 1)
    for i in range(n):
        d.text((2, 140 + i * c + 8), names[i][:18], fill="black")
        d.text((140 + i * c + 2, 2 + (i % 6) * 20), names[i][:6], fill="black")
        for j in range(n):
            v = norm[i, j]
            col = (int(255 - 200 * v), int(255 - 120 * v), 255) if i == j else (255, int(255 - 200 * v), int(255 - 200 * v))
            d.rectangle((140 + j * c, 140 + i * c, 140 + (j + 1) * c - 1, 140 + (i + 1) * c - 1), fill=col)
            if cm[i, j]:
                d.text((140 + j * c + 3, 140 + i * c + 8), str(int(cm[i, j])), fill="black")
    img.save(path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--processed", type=Path, required=True)
    ap.add_argument("--splits", nargs="+", default=["test"])
    ap.add_argument("--datasets", nargs="*")
    ap.add_argument("--exclude-source-regex")
    ap.add_argument("--ood-source-regex", help="rows matching are treated as OOD (unseen produce)")
    ap.add_argument("--stress", choices=["dark", "blur", "jpeg", "warm_light", "occlusion"])
    ap.add_argument("--save-preds", action="store_true", help="write per-image predictions (<out>.preds.jsonl)")
    ap.add_argument("--quality-gate", action="store_true", help="run the model-free quality gate first, as the app does")
    ap.add_argument("--tune", action="store_true")
    ap.add_argument("--target-accuracy", type=float, default=0.95)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    net, cfg, tax, temps, sup = load_ckpt(args.ckpt)
    rows = dataset.read_manifest(args.processed / "manifest.jsonl", set(args.splits),
                                 set(args.datasets) if args.datasets else None)
    if args.exclude_source_regex:
        rows = [r for r in rows if not re.search(args.exclude_source_regex, r["source_path"])]
    is_ood = np.array([bool(args.ood_source_regex and re.search(args.ood_source_regex, r["source_path"])) for r in rows])
    logits, masks = infer(net, rows, args.processed, tax, cfg, args.stress, workers=args.workers)
    probs = {h: calibration.softmax(logits[h], temps.get(h, 1.0)) for h in HEADS}

    res: dict = {"ckpt": str(args.ckpt), "processed": str(args.processed), "splits": args.splits,
                 "datasets": args.datasets, "stress": args.stress, "n_rows": len(rows), "n_ood": int(is_ood.sum()),
                 "temperatures": temps, "heads": {}}
    ind = ~is_ood
    for h in HEADS:
        exact = (masks[h].sum(1) == 1) & ind
        if exact.sum():
            res["heads"][h] = metrics.summarize(probs[h][exact], masks[h][exact].argmax(1), list(tax.classes(h)))
    # System-level behaviour through the real decision policy (abstention included).
    thr = dict(DEFAULT_THRESHOLDS)
    tpath = args.ckpt.parent / "thresholds.json"
    if tpath.exists() and not args.tune:
        thr.update({k: v for k, v in json.loads(tpath.read_text()).items() if k != "tuned_on"})
    energy = ood.energy(logits["produce"])
    qreasons = [None] * len(rows)
    if args.quality_gate:
        from ml.inference import quality
        from ml.preprocessing.image_io import load_rgb
        st = Stress(args.stress) if args.stress else (lambda im: im)
        qreasons = [quality.assess(st(load_rgb(args.processed / r["image"]))).reason for r in rows]
        res["quality_gate_reasons"] = {str(k): qreasons.count(k) for k in set(qreasons)}
    statuses, correct_ok = [], []
    for i in range(len(rows)):
        r = decide(tax, {h: probs[h][i] for h in HEADS}, sup, quality_reason=qreasons[i],
                   energy_score=float(energy[i]), thresholds=thr)
        statuses.append(r.status)
        if r.status == "ok" and ind[i] and masks["produce"][i].sum() == 1:
            correct_ok.append(r.produce == tax.produce[int(masks["produce"][i].argmax())])
    st = np.array(statuses)
    res["decision"] = {"thresholds": thr,
                       "in_dist_coverage_ok": float((st[ind] == "ok").mean()) if ind.any() else None,
                       "in_dist_accuracy_when_ok": float(np.mean(correct_ok)) if correct_ok else None,
                       "status_counts_in_dist": {k: int((st[ind] == k).sum()) for k in set(st[ind])} if ind.any() else {}}
    if is_ood.any():
        msp, ent = ood.max_softmax(probs["produce"]), ood.neg_entropy(probs["produce"])
        res["ood"] = {"n_in": int(ind.sum()), "n_ood": int(is_ood.sum()),
                      "auroc": {"msp": ood.auroc(msp[ind], msp[is_ood]), "energy": ood.auroc(energy[ind], energy[is_ood]),
                                "neg_entropy": ood.auroc(ent[ind], ent[is_ood])},
                      "fpr_at_95tpr": {"msp": ood.fpr_at_tpr(msp[ind], msp[is_ood]), "energy": ood.fpr_at_tpr(energy[ind], energy[is_ood])},
                      "ood_abstention_rate": float(np.isin(st[is_ood], ["unsure", "not_produce", "retake"]).mean()),
                      "ood_predicted_other_rate": float((st[is_ood] == "not_produce").mean())}
    if args.tune:
        # Smallest produce-confidence threshold whose accepted set reaches the target accuracy on val,
        # and the energy threshold keeping 95% of in-distribution val images.
        p = probs["produce"][ind]; y = masks["produce"][ind]
        exact = y.sum(1) == 1
        conf = p[exact].max(1); corr = p[exact].argmax(1) == y[exact].argmax(1)
        chosen = 0.99
        for t in np.arange(0.30, 0.99, 0.01):
            m = conf >= t
            if m.sum() >= 30 and corr[m].mean() >= args.target_accuracy:
                chosen = float(round(t, 2)); break
        # Product floor (docs/ux-principles.md #4-5): never show an answer the UI would call
        # "low confidence" (< 0.70), even if validation accuracy would allow a lower threshold.
        chosen = max(chosen, UX_MIN_SHOWN_CONFIDENCE)
        tuned = {"produce_min_prob": chosen, "ood_min_energy": float(np.quantile(energy[ind], 0.05)),
                 "tuned_on": {"processed": str(args.processed), "splits": args.splits, "target_accuracy": args.target_accuracy,
                              "coverage_at_threshold": float((conf >= chosen).mean()),
                              "accuracy_at_threshold": float(corr[conf >= chosen].mean()) if (conf >= chosen).any() else None}}
        tpath.write_text(json.dumps(tuned, indent=2))
        res["tuned_thresholds"] = tuned
    out_path_preds = None
    out = args.out or args.ckpt.parent / f"eval_{'_'.join(args.splits)}{'_' + args.stress if args.stress else ''}.json"
    out.write_text(json.dumps(res, indent=2))
    if args.save_preds:
        with open(out.with_suffix(".preds.jsonl"), "w", encoding="utf-8") as f:
            for i, r in enumerate(rows):
                p = probs["produce"][i]
                top = np.argsort(-p)[:3]
                f.write(json.dumps({"image": r["image"], "source_path": r["source_path"], "label": r["labels"]["produce"],
                                    "pred": tax.produce[int(top[0])], "conf": round(float(p[top[0]]), 4),
                                    "top3": [[tax.produce[int(j)], round(float(p[j]), 4)] for j in top],
                                    "status": statuses[i], "ood": bool(is_ood[i])}, ensure_ascii=False) + "\n")
    if "produce" in res["heads"]:
        confusion_png(np.array(res["heads"]["produce"]["confusion_matrix"]), list(tax.produce), out.with_suffix(".confusion.png"))
    brief = {k: res["heads"]["produce"][k] for k in ("n", "top1", "macro_f1", "balanced_accuracy", "worst_class_recall", "ece")} if "produce" in res["heads"] else {}
    print(json.dumps({"produce": brief, "decision": res["decision"], "ood": res.get("ood"), "tuned": res.get("tuned_thresholds")}, indent=2))


if __name__ == "__main__":
    main()
