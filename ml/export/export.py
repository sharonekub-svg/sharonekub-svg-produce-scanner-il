"""Export a trained checkpoint to ONNX and (optionally) Core ML, plus a model bundle.

  python -m ml.export.export --ckpt runs/.../best.pt --out exports/v0 [--coreml] [--fp16]

The bundle (bundle.json) is the ONLY contract the app depends on:
class lists, input spec, temperatures, thresholds, supported_heads, version.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch

from ml.common.taxonomy import HEADS, load_taxonomy
from ml.inference.decision import DEFAULT_THRESHOLDS
from ml.training.model import build_model

OUTPUT_NAMES = ["produce", "ripeness", "freshness", "visual_spoilage"]


class ExportWrapper(torch.nn.Module):
    """Fixed-signature wrapper: image -> 4 logit tensors (no features, no conditioning input)."""
    def __init__(self, net, normalize_inside: bool = False):
        super().__init__()
        self.net = net
        self.normalize_inside = normalize_inside
        self.register_buffer("mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))

    def forward(self, x):
        if self.normalize_inside:  # x in [0, 1]
            x = (x - self.mean) / self.std
        o = self.net(x)
        return tuple(o[h] for h in OUTPUT_NAMES)


def load(ckpt_path: Path):
    ck = torch.load(ckpt_path, map_location="cpu")
    tax = load_taxonomy()
    cfg = ck["cfg"]
    cfg["model"]["pretrained"] = False
    net = build_model(cfg, {h: tax.num_classes(h) for h in HEADS})
    net.load_state_dict(ck["model"])
    return net.eval(), cfg, tax


def export_onnx(net, size: int, out: Path, opset: int = 17) -> Path:
    path = out / "model.onnx"
    torch.onnx.export(ExportWrapper(net), torch.randn(1, 3, size, size), path, input_names=["image"],
                      output_names=OUTPUT_NAMES, opset_version=opset, dynamic_axes={"image": {0: "batch"}},
                      external_data=False)  # single self-contained file (bundle hashes it)
    return path


def export_coreml(net, size: int, out: Path, fp16: bool = True, palettize_bits: int | None = None) -> Path:
    """Core ML ML Program. Input 'image' is the SAME normalised NCHW float tensor as the ONNX
    model (the app's Swift module does crop + normalisation, mirroring server/app.py), so there
    is one preprocessing contract across server, Core ML and training eval."""
    import coremltools as ct
    traced = torch.jit.trace(ExportWrapper(net).eval(), torch.randn(1, 3, size, size))
    mlm = ct.convert(
        traced,
        inputs=[ct.TensorType(name="image", shape=(1, 3, size, size))],
        outputs=[ct.TensorType(name=n) for n in OUTPUT_NAMES],
        compute_precision=ct.precision.FLOAT16 if fp16 else ct.precision.FLOAT32,
        minimum_deployment_target=ct.target.iOS16,
        convert_to="mlprogram",
    )
    if palettize_bits:
        from coremltools.optimize.coreml import OpPalettizerConfig, OptimizationConfig, palettize_weights
        mlm = palettize_weights(mlm, OptimizationConfig(global_config=OpPalettizerConfig(mode="kmeans", nbits=palettize_bits)))
    mlm.short_description = "Produce scanner multi-task model (visual assessment only)"
    path = out / "ProduceScanner.mlpackage"
    mlm.save(str(path))
    return path


def quantize_int8(onnx_path: Path, processed: Path, size: int, n_calib: int = 256) -> Path:
    """Static QDQ int8 quantisation (per-channel weights) calibrated on validation images.
    Conv nets need static quantisation; dynamic quantisation only covers MatMul/Gemm."""
    from onnxruntime.quantization import CalibrationDataReader, QuantFormat, QuantType, quantize_static
    from onnxruntime.quantization.shape_inference import quant_pre_process

    from ml.preprocessing.image_io import load_rgb
    from ml.training.augment import build_eval_transform
    from ml.training.dataset import read_manifest

    rows = read_manifest(processed / "manifest.jsonl", {"val"})
    rows = sorted(rows, key=lambda r: r["sha256"])[:n_calib]
    tf = build_eval_transform({"data": {"image_size": size}})

    class Reader(CalibrationDataReader):
        def __init__(self):
            self.it = iter(rows)

        def get_next(self):
            r = next(self.it, None)
            return None if r is None else {"image": tf(load_rgb(processed / r["image"]))[None].numpy()}

    pre = onnx_path.with_suffix(".pre.onnx")
    quant_pre_process(str(onnx_path), str(pre))
    out = onnx_path.with_name("model.int8.onnx")
    quantize_static(str(pre), str(out), Reader(), quant_format=QuantFormat.QDQ, per_channel=True,
                    activation_type=QuantType.QUInt8, weight_type=QuantType.QInt8)
    pre.unlink()
    return out


def _datasets_used(cfg: dict) -> list[str]:
    from ml.common.taxonomy import REPO_ROOT
    mf = REPO_ROOT / cfg["data"]["processed_dir"] / "manifest.jsonl"
    if not mf.exists():
        return []
    used = set()
    with open(mf, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["split"] == "train":
                used.add(r["dataset_id"])
    allow = cfg["data"].get("datasets")
    return sorted(u for u in used if not allow or u in allow)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--coreml", action="store_true")
    ap.add_argument("--fp16", action="store_true")
    ap.add_argument("--palettize-bits", type=int, choices=[4, 6, 8])
    ap.add_argument("--int8-calib", type=Path, help="processed dir whose val split calibrates int8 quantisation")
    ap.add_argument("--supported-heads", type=Path, help="default: <run>/supported_heads.json")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    net, cfg, tax = load(args.ckpt)
    size = cfg["data"]["image_size"]
    files = [export_onnx(net, size, args.out)]
    if args.int8_calib:
        files.append(quantize_int8(files[0], args.int8_calib, size))
    if args.coreml:
        files.append(export_coreml(net, size, args.out, args.fp16, args.palettize_bits))
    run_dir = args.ckpt.parent
    rd = lambda n: json.loads((run_dir / n).read_text()) if (run_dir / n).exists() else {}  # noqa: E731
    thresholds = {**DEFAULT_THRESHOLDS, **{k: v for k, v in rd("thresholds.json").items() if k != "tuned_on"}}
    sup_path = args.supported_heads or run_dir / "supported_heads.json"

    def digest(p: Path) -> str:
        h = hashlib.sha256()
        for f in sorted(p.rglob("*")) if p.is_dir() else [p]:
            if f.is_file():
                h.update(f.read_bytes())
        return h.hexdigest()

    bundle = {
        "bundle_version": 1,
        "model_id": f"{cfg['experiment']}@{hashlib.sha256(args.ckpt.read_bytes()).hexdigest()[:12]}",
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "input": {"size": size, "layout": "NCHW", "mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225],
                  "resize": "short_side_then_center_crop", "resize_ratio": 1.14},
        "outputs": {h: list(tax.classes(h)) for h in OUTPUT_NAMES},
        "temperatures": rd("temperature.json"),
        "thresholds": thresholds,
        "supported_heads": json.loads(sup_path.read_text()) if sup_path.exists() else {},
        "produce_meta": tax.produce_meta,
        "label_he": tax.label_he,
        "training_datasets": _datasets_used(cfg),
        "files": {p.name: {"sha256": digest(p)} for p in files},
    }
    (args.out / "bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"exported": [str(p) for p in files]}, indent=2))


if __name__ == "__main__":
    main()
