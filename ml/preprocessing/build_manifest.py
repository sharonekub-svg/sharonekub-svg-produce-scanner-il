"""Build the unified, deduplicated, leakage-safe manifest.

  python -m ml.preprocessing.build_manifest --purpose commercial_training \
      --datasets grocery_store_klasson own_il_collection \
      --holdout grocery_store_klasson --out data/processed

Steps: licence gate -> adapter labels -> validate/decode -> hash -> cluster
-> group-aware split -> standardised JPEGs + manifest.jsonl + report.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ml.common.taxonomy import HEADS, REPO_ROOT, load_taxonomy
from ml.preprocessing import dedup, hashing, image_io, labels, registry, splits


def build(dataset_ids: list[str], purpose: str, raw_root: Path, out_dir: Path,
          holdout: set[str], seed: int = 1337, max_side: int = 512, max_distance: int = 6,
          write_images: bool = True, val_frac_from_train: float = 0.0) -> dict:
    tax = load_taxonomy()
    reg = registry.load_registry()
    signoffs = registry.load_signoffs()
    report: dict = {"purpose": purpose, "datasets": {}, "rejected_files": Counter()}

    samples, recs = [], []
    for ds in dataset_ids:
        if ds not in reg:
            raise KeyError(f"{ds} not in registry")
        ok, why = registry.is_allowed(reg[ds], purpose, signoffs)
        report["datasets"][ds] = {"allowed": ok, "reason": why}
        if not ok:
            raise PermissionError(f"licence gate refused {ds} for {purpose}: {why}")
        root = raw_root / ds
        n = 0
        for s in labels.iter_dataset(tax, ds, root):
            path = root / s.rel_path
            chk = image_io.check_image(path)
            if not chk.ok:
                report["rejected_files"][chk.reason] += 1
                continue
            img = image_io.load_rgb(path)
            recs.append(dedup.DupRecord(chk.sha256, hashing.pixel_digest(img),
                                        hashing.dihedral_phash(img), s.group_key, hashing.chroma_hist(img),
                                        hashing.white_fraction(img) >= dedup.STUDIO_WHITE_FRACTION))
            samples.append((s, chk, path))  # re-decoded at write time; keeps memory flat
            n += 1
        report["datasets"][ds]["n_valid"] = n

    cluster_ids, stats = dedup.cluster(recs, max_distance=max_distance)
    report["dedup"] = stats
    strata = [f"{s.dataset_id}|{s.labels['produce']}" for s, _, _ in samples]
    split = splits.group_split(cluster_ids, strata, seed=seed)
    split, n_conflict = splits.apply_split_hints(cluster_ids, split, [s.split_hint for s, _, _ in samples])
    report["official_split_conflicts"] = n_conflict
    if val_frac_from_train > 0:
        frozen = ["force_split" in tax.datasets[s.dataset_id] for s, _, _ in samples]
        split = splits.carve_val_from_train(cluster_ids, split, strata, val_frac_from_train, seed, frozen)
    split = splits.apply_dataset_holdout([s.dataset_id for s, _, _ in samples], split, holdout, cluster_ids)
    # Label conflicts: clusters whose members carry different produce labels (same scene,
    # different class). Reported for review; multi-object source images (Open Images) are expected here.
    by_cluster: dict[int, set] = {}
    for (s, _, _), cid in zip(samples, cluster_ids):
        by_cluster.setdefault(cid, set()).add((s.dataset_id, s.labels["produce"]))
    report["clusters_with_conflicting_produce"] = sum(len({p for _, p in v}) > 1 for v in by_cluster.values())
    report["cross_dataset_clusters"] = sum(len({d for d, _ in v}) > 1 for v in by_cluster.values())
    leaks = splits.check_no_leakage(cluster_ids, split)
    if leaks:
        raise AssertionError(f"{len(leaks)} groups leak across splits")

    out_dir.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    with open(out_dir / "manifest.jsonl", "w", encoding="utf-8") as f:
        for (s, chk, path), cid, sp in zip(samples, cluster_ids, split):
            rel_out = f"images/{s.dataset_id}/{chk.sha256[:2]}/{chk.sha256}.jpg"
            if write_images:
                image_io.save_standard(image_io.standardize(image_io.load_rgb(path), max_side), out_dir / rel_out)
            row = {"image": rel_out, "dataset_id": s.dataset_id, "source_path": s.rel_path,
                   "sha256": chk.sha256, "group": f"g{cid}", "split": sp,
                   "labels": {h: tax.decode(h, s.labels[h]) for h in HEADS}}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            counts[(sp, tax.decode("produce", s.labels["produce"]))] += 1
    report["split_counts"] = {f"{k[0]}/{k[1]}": v for k, v in sorted(counts.items())}
    report["rejected_files"] = dict(report["rejected_files"])
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", nargs="+", required=True)
    ap.add_argument("--purpose", choices=registry.PURPOSES, required=True)
    ap.add_argument("--raw-root", type=Path, default=REPO_ROOT / "data" / "raw")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "processed")
    ap.add_argument("--holdout", nargs="*", default=[])
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--max-distance", type=int, default=6)
    ap.add_argument("--val-frac-from-train", type=float, default=0.0,
                    help="move this fraction of train clusters to val (group-aware, stratified)")
    args = ap.parse_args()
    rep = build(args.datasets, args.purpose, args.raw_root, args.out, set(args.holdout),
                seed=args.seed, max_distance=args.max_distance, val_frac_from_train=args.val_frac_from_train)
    print(json.dumps({k: rep[k] for k in ("datasets", "dedup", "rejected_files")}, indent=2))


if __name__ == "__main__":
    main()
