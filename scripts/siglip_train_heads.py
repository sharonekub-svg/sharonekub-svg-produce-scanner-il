#!/usr/bin/env python3
"""Train the v0.8 heads on SigLIP2 embeddings (scripts/siglip_embed.py) and write a run directory.

  python scripts/siglip_train_heads.py --processed data/processed_commercial_v7 --emb runs/siglip/emb_v7.npz \
      --config ml/configs/p5_c12_fresh_spoiled.yaml --real runs/siglip/oi_real.npz --out runs/siglip/v08

Heads (all linear on the L2-normalised 768-d embedding):
  produce  : scale * e @ (T + D)^T + b over the 27 taxonomy produce types, where T are text embeddings of the
             class names (zero-shot start) and D is a small learned correction (L2 toward the text weights);
             `other` = logsumexp over "not supported" text prompts (+ bias). Aux (quality-only) datasets never
             train produce, as before (their studio backgrounds would become a shortcut).
  ripeness / freshness / visual_spoilage : softmax regression with set-valued targets (-log sum_{c in set} p_c).
Chosen on data we are allowed to use for choices: the produce correction strength on the real-photo calibration
half (--real, split=cal) + val; temperatures on val; produce_min_prob on the real-photo calibration half.
Reported on test (manifest) and on the real-photo test half. Per-fruit gate: scripts/gate_quality_heads.py rules.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import yaml

from ml.common.taxonomy import HEADS, load_taxonomy
from ml.evaluation import calibration, metrics
from ml.evaluation.evaluate import quality_by_produce
from ml.siglip.features import NAMES, fresh_text_embeddings, text_embeddings
from ml.training.dataset import label_mask

torch.manual_seed(0)
np.random.seed(0)
SCALE = 100.0  # SigLIP cosine -> logit scale (chosen on the real-photo calibration half, zero-shot)


def masks_for(rows, tax) -> dict[str, np.ndarray]:
    return {h: np.stack([label_mask(tax, h, r["labels"].get(h)).numpy() for r in rows]) for h in HEADS}


def fit_softmax(X, M, wd, epochs=300, init_W=None, anchor=None, scale=1.0, extra_logit=None, lr=0.05):
    """Set-valued softmax regression. M: bool (n, C) allowed-label masks. anchor: L2 toward it (else toward 0)."""
    X = torch.tensor(X, dtype=torch.float32)
    M = torch.tensor(M, dtype=torch.bool)
    C = M.shape[1]
    W = torch.nn.Parameter(torch.tensor(init_W, dtype=torch.float32).clone() if init_W is not None else torch.zeros(C, X.shape[1]))
    b = torch.nn.Parameter(torch.zeros(C))
    A = torch.tensor(anchor, dtype=torch.float32) if anchor is not None else torch.zeros_like(W)
    # class balance: rows weighted by the inverse frequency of their (first) label
    first = M.float().argmax(1)
    cnt = torch.bincount(first, minlength=C).float().clamp(min=1)
    w = (1.0 / cnt[first]) ** 0.5
    w = w / w.mean()
    opt = torch.optim.Adam([W, b], lr=lr)
    for _ in range(epochs):
        opt.zero_grad()
        L = scale * X @ W.T + b
        if extra_logit is not None:
            L = extra_logit(X, L)
        lp = torch.log_softmax(L, 1)
        nll = -(torch.logsumexp(lp.masked_fill(~M, -1e9), 1))
        loss = (w * nll).mean() + wd * ((W - A) ** 2).sum()
        loss.backward()
        opt.step()
    return W.detach().numpy(), b.detach().numpy()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--processed", type=Path, required=True)
    ap.add_argument("--emb", type=Path, required=True)
    ap.add_argument("--config", type=Path, required=True, help="for aux (quality-only) dataset ids")
    ap.add_argument("--real", type=Path, required=True, help="real-photo set: emb, true, split (cal/test)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--candidates", type=Path, default=Path("runs/p5_c12_fresh_spoiled/20260928-121025/supported_heads_ungated.json"),
                    help="candidate heads per produce (labels + vetoes) from the previous release")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    tax = load_taxonomy()
    produce = list(tax.produce)
    assert produce[:len(NAMES)] == list(NAMES) and produce[-1] == "other", produce
    aux = set((yaml.safe_load(open(args.config))["train"].get("aux_datasets") or {}))

    z = np.load(args.emb)
    emb = dict(zip(z["sha256"].tolist(), z["emb"].astype(np.float32)))
    rows = [json.loads(l) for l in open(args.processed / "manifest.jsonl", encoding="utf-8")]
    rows = [r for r in rows if r["sha256"] in emb]
    X = np.stack([emb[r["sha256"]] for r in rows])
    M = masks_for(rows, tax)
    split = np.array([r["split"] for r in rows])
    is_aux = np.array([r["dataset_id"] in aux for r in rows])
    tr, va, te = split == "train", split == "val", split == "test"

    cls_emb, NEG = text_embeddings()
    T = np.stack([cls_emb[c] for c in NAMES])
    negW = torch.tensor(SCALE * NEG, dtype=torch.float32)

    def with_other(Xt, L27):  # append `other` = logsumexp over the "not supported" prompts
        return torch.cat([L27[:, :-1], (torch.logsumexp(Xt @ negW.T, 1) + L27[:, -1])[:, None]], 1)

    def produce_logits(Xn, W27, b):
        L = SCALE * Xn @ W27.T + b[:-1]
        oth = np.log(np.exp(Xn @ (SCALE * NEG).T - 50).sum(1)) + 50 + b[-1]
        return np.concatenate([L, oth[:, None]], 1)

    real = np.load(args.real)
    RX, Ry, Rs = real["emb"].astype(np.float32), real["true"], real["split"]

    def real_top1(W27, b, part):
        m = (Rs == part) & (Ry != "other")
        P = produce_logits(RX[m], W27, b)
        return float((np.array(produce)[P.argmax(1)] == Ry[m]).mean())

    # ---- produce: text-initialised correction, strength chosen on real cal + val ----
    pm = M["produce"].copy()
    ptrain = tr & ~is_aux & (pm.sum(1) > 0)
    W0 = np.concatenate([T, np.zeros((1, T.shape[1]))])  # last row unused (other = negatives)
    best = None
    for wd in (1e-1, 1e-2, 1e-3):
        W, b = fit_softmax(X[ptrain], pm[ptrain], wd, epochs=200, init_W=W0, anchor=W0, scale=SCALE, extra_logit=with_other, lr=0.002)
        vm = va & ~is_aux & (pm.sum(1) == 1)
        vacc = float((produce_logits(X[vm], W[:-1], b).argmax(1) == pm[vm].argmax(1)).mean())
        rc = real_top1(W[:-1], b, "cal")
        print(f"produce wd={wd}: val top1 {vacc:.3f}  real-cal top1 {rc:.3f}", flush=True)
        if best is None or rc + 0.25 * vacc > best[0]:
            best = (rc + 0.25 * vacc, wd, W, b)
    zs_b = np.zeros(len(produce))
    zs = real_top1(T, zs_b, "cal")
    print(f"zero-shot real-cal top1 {zs:.3f}; best fitted wd={best[1]} real-cal {real_top1(best[2][:-1], best[3], 'cal'):.3f}")
    # Blend the zero-shot text head (best on real photos) with the fitted head (knows our labelled cases, e.g.
    # heavily rotten fruit): W = (1-a) T + a W_fit. `a` chosen on the real-photo calibration half + val.
    vm = va & ~is_aux & (pm.sum(1) == 1)
    best_a = None
    for a in (0.0, 0.25, 0.5, 0.75, 1.0):
        Wa, ba = (1 - a) * T + a * best[2][:-1], a * best[3]
        rc = real_top1(Wa, ba, "cal")
        vacc = float((produce_logits(X[vm], Wa, ba).argmax(1) == pm[vm].argmax(1)).mean())
        print(f"blend a={a}: real-cal top1 {rc:.3f}  val top1 {vacc:.3f}", flush=True)
        if best_a is None or rc + 0.25 * vacc > best_a[0]:
            best_a = (rc + 0.25 * vacc, a, Wa, ba)
    _, a, Wp, bp = best_a
    print(f"produce head: blend a={a}")
    heads = {"produce_W": (SCALE * Wp).astype(np.float32), "produce_b": bp.astype(np.float32),
             "neg_W": (SCALE * NEG).astype(np.float32)}

    # ---- quality heads ----
    for h in ("ripeness", "freshness", "visual_spoilage"):
        m = M[h]
        C = m.shape[1]
        use = tr & (m.sum(1) > 0) & (m.sum(1) < C)
        bestq = None
        for wd in (1e-3, 1e-4, 1e-5):
            W, b = fit_softmax(X[use], m[use], wd, epochs=300, scale=10.0, lr=0.02)
            vm = va & (m.sum(1) == 1)
            vacc = float(((X[vm] @ (10.0 * W).T + b).argmax(1) == m[vm].argmax(1)).mean()) if vm.sum() else 0.0
            print(f"{h} wd={wd}: val exact acc {vacc:.3f} (n={int(vm.sum())})", flush=True)
            if bestq is None or vacc > bestq[0]:
                bestq = (vacc, wd, W, b)
        heads[f"{h}_W"] = (10.0 * bestq[2]).astype(np.float32)
        heads[f"{h}_b"] = bestq[3].astype(np.float32)

    # ---- general fresh-vs-spoiled for every produce type (zero-shot prompts + one global scale/bias) ----
    ft = args.out.parent / "fresh_zs_text.npz"
    if ft.exists():
        z2 = np.load(ft)
        GF, GB = z2["fresh"], z2["bad"]
    else:
        GF, GB = fresh_text_embeddings()
        np.savez(ft, fresh=GF, bad=GB)
    fm = M["freshness"]
    fi = tax.heads["freshness"].index("fresh")
    pid = M["produce"].argmax(1)
    gl = tr & (M["produce"].sum(1) == 1) & (pid < len(NAMES)) & (fm.sum(1) > 0) & ~((fm.sum(1) > 1) & fm[:, fi])
    pc = pid.clip(max=len(NAMES) - 1)
    zsl = 50.0 * ((X * GB[pc]).sum(1) - (X * GF[pc]).sum(1))
    yb = torch.tensor(~fm[gl][:, fi], dtype=torch.float32)
    a_, b_ = torch.ones(1, requires_grad=True), torch.zeros(1, requires_grad=True)
    opt = torch.optim.Adam([a_, b_], lr=0.05)
    zt = torch.tensor(zsl[gl], dtype=torch.float32)
    for _ in range(400):
        opt.zero_grad()
        torch.nn.functional.binary_cross_entropy_with_logits(a_ * zt + b_, yb).backward()
        opt.step()
    heads["general_fresh_W"] = GF.astype(np.float32)
    heads["general_bad_W"] = GB.astype(np.float32)
    heads["general_ab"] = np.array([50.0 * float(a_), float(b_)], np.float32)
    print(f"general freshness: scale {50.0 * float(a_):.2f} bias {float(b_):.3f} (fit on {int(gl.sum())} train rows)")

    def all_logits(Xn):
        out = {"produce": produce_logits(Xn, heads["produce_W"] / SCALE, heads["produce_b"])}
        for h in ("ripeness", "freshness", "visual_spoilage"):
            out[h] = Xn @ heads[f"{h}_W"].T + heads[f"{h}_b"]
        return out

    # ---- temperatures: produce on the REAL-photo calibration half (that is where the app is used);
    #      quality heads on val (no real-photo quality labels yet) ----
    Lv = all_logits(X[va])
    temps = {}
    for h in HEADS:
        ex = M[h][va].sum(1) == 1
        temps[h] = float(calibration.fit_temperature(Lv[h][ex], M[h][va][ex].argmax(1))) if ex.sum() > 20 else 1.0
    rc = Rs == "cal"
    temps["produce"] = float(calibration.fit_temperature(
        produce_logits(RX[rc], heads["produce_W"] / SCALE, heads["produce_b"]), np.array([produce.index(v) for v in Ry[rc]])))
    print("temperatures", temps)

    # ---- test metrics + per-fruit quality ----
    Lt = all_logits(X[te])
    probs = {h: calibration.softmax(Lt[h], temps[h]) for h in HEADS}
    mt = {h: M[h][te] for h in HEADS}
    res = {"heads": {}, "n_test": int(te.sum())}
    for h in HEADS:
        ex = mt[h].sum(1) == 1
        if ex.sum():
            res["heads"][h] = metrics.summarize(probs[h][ex], mt[h][ex].argmax(1), list(tax.classes(h)))
    res["quality_heads"] = quality_by_produce(tax, probs, mt, np.ones(int(te.sum()), bool))

    # ---- identification threshold on the real-photo calibration half ----
    def real_probs(part):
        m = Rs == part
        P = calibration.softmax(produce_logits(RX[m], heads["produce_W"] / SCALE, heads["produce_b"]), temps["produce"])
        return P, Ry[m]

    def shown_stats(P, y, t, margin=0.15):
        top = P.argmax(1)
        srt = np.sort(P, 1)
        pred = np.array(produce)[top]
        show = (srt[:, -1] >= t) & (srt[:, -1] - srt[:, -2] >= margin) & (pred != "other")
        sup, neg = y != "other", y == "other"
        acc = float((pred[show & sup] == y[show & sup]).mean()) if (show & sup).sum() else float("nan")
        return {"shown": float(show[sup].mean()), "acc_when_shown": acc, "unsupported_shown": float(show[neg].mean()),
                "top1": float((pred[sup] == y[sup]).mean())}

    Pc, yc = real_probs("cal")
    choice = None
    for t in np.arange(0.30, 0.99, 0.02):
        s = shown_stats(Pc, yc, t)
        if s["acc_when_shown"] >= 0.92 and s["unsupported_shown"] <= 0.10:
            choice = round(float(t), 2)
            break
    choice = choice if choice is not None else 0.9
    Pt, yt = real_probs("test")
    res["real_photos"] = {"threshold": choice, "cal": shown_stats(Pc, yc, choice), "test": shown_stats(Pt, yt, choice),
                          "test_always_answer": shown_stats(Pt, yt, 0.0)}
    print(json.dumps(res["real_photos"], indent=1))

    np.savez(args.out / "heads.npz", **heads)
    (args.out / "temperature.json").write_text(json.dumps(temps, indent=2))
    (args.out / "eval_test.json").write_text(json.dumps(res, indent=2))
    (args.out / "thresholds.json").write_text(json.dumps({
        "produce_min_prob": choice, "produce_min_margin": 0.15, "ood_min_energy": None,
        "tuned_on": {"real_photos": "Open Images crops (never trained on), calibration half by image id",
                     "rule": "smallest threshold with accuracy-when-shown >= 0.92 and unsupported-shown <= 10% "
                             "(below it the app asks the user to pick among its top guesses)"}}, indent=2))
    # Candidate heads per produce = the previous release's candidates (enough labels + product vetoes such as
    # mango ripeness with unknown cultivar); scripts/gate_quality_heads.py then keeps only what passes on test.
    sup = json.loads(args.candidates.read_text())
    (args.out / "supported_heads.json").write_text(json.dumps(sup, indent=2))
    print("wrote", args.out)


if __name__ == "__main__":
    main()
