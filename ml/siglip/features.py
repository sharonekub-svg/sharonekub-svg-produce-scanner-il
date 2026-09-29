"""SigLIP2 image features (google/siglip2-base-patch16-224, Apache-2.0) — the v0.8 backbone.

One ONNX vision encoder (weight-only 8-bit, same accuracy as fp32 on real photos) gives an L2-normalised
768-d embedding; every head (produce, ripeness, freshness, visual_spoilage) is a small linear layer on it
(heads.npz). Identification starts from text embeddings of the class names (zero-shot) and is then fitted
on our licensed training photos. Measured on held-out real web photos (Open Images, never trained on):
top-1 0.29 (v0.7 CNN) -> 0.86 zero-shot (docs/results.md, round 6).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

HF_ID = "google/siglip2-base-patch16-224"
SIZE = 224

# Class names used in the text prompts (taxonomy produce id -> English names).
NAMES = {"banana": ["banana"], "apple": ["apple"], "orange": ["orange"], "mandarin": ["mandarin", "clementine"],
         "avocado": ["avocado"], "tomato": ["tomato"], "cucumber": ["cucumber"], "mango": ["mango"], "peach": ["peach"],
         "nectarine": ["nectarine"], "watermelon": ["watermelon"], "melon": ["melon", "cantaloupe"], "grape": ["grapes"],
         "strawberry": ["strawberry"], "pomegranate": ["pomegranate"], "pear": ["pear"], "kiwi": ["kiwi fruit"],
         "plum": ["plum"], "persimmon": ["persimmon"], "lemon": ["lemon"], "guava": ["guava"], "pepper": ["bell pepper"],
         "lime": ["lime"], "grapefruit": ["grapefruit"], "zucchini": ["zucchini"], "potato": ["potato"],
         "passion_fruit": ["passion fruit"]}
TEMPLATES = ["a photo of a {}.", "a close-up photo of a {}.", "a photo of a fresh {}.", "a photo of a rotten {}."]
# "Not a supported produce" prompts: their probability mass becomes the taxonomy's `other` class.
NEGATIVES = ["a photo of a person", "a photo of a hand", "a photo of a room", "a photo of a table", "a photo of a plate of food",
             "a photo of bread", "a photo of meat", "a photo of a vegetable", "a photo of a pineapple", "a photo of broccoli",
             "a photo of a carrot", "a photo of a pumpkin", "a photo of a cabbage", "a photo of an onion", "a photo of garlic",
             "a photo of a coconut", "a photo of a fig", "a photo of cherries", "a photo of dates", "a photo of a radish",
             "a photo of a squash", "a photo of a phone", "a photo of a cat", "a photo of a dog", "a photo of text",
             "a photo of a cake", "a photo of juice", "a photo of a drawing of fruit", "a photo of a plant with leaves",
             "a photo of a flower"]


def preprocess(img: Image.Image) -> np.ndarray:
    """Exactly the SigLIP2 processor: squash-resize to 224x224 (bilinear), scale to [-1, 1], CHW."""
    a = np.asarray(img.convert("RGB").resize((SIZE, SIZE), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
    return ((a - 0.5) / 0.5).transpose(2, 0, 1)


class Encoder:
    """ONNX vision encoder -> L2-normalised embeddings."""

    def __init__(self, onnx_path: Path | str, threads: int = 2):
        import onnxruntime as ort
        o = ort.SessionOptions()
        o.intra_op_num_threads = threads
        p = Path(onnx_path)
        if p.exists():
            model: str | bytes = str(p)
        else:  # shipped in parts (<100 MB each for git hosting): vision.onnx.00, vision.onnx.01, ...
            parts = sorted(p.parent.glob(p.name + ".[0-9][0-9]"))
            if not parts:
                raise FileNotFoundError(p)
            model = b"".join(x.read_bytes() for x in parts)
        self.sess = ort.InferenceSession(model, o, providers=["CPUExecutionProvider"])

    def __call__(self, images: list[Image.Image], batch: int = 16) -> np.ndarray:
        out = [self.sess.run(None, {"pixel_values": np.stack([preprocess(x) for x in images[i:i + batch]])})[0]
               for i in range(0, len(images), batch)]
        return np.concatenate(out) if out else np.zeros((0, 768), np.float32)


def text_embeddings() -> tuple[dict[str, np.ndarray], np.ndarray]:
    """(class -> mean prompt embedding, negatives matrix). Needs torch + transformers (build time only)."""
    import torch
    from transformers import AutoModel, AutoProcessor
    m, p = AutoModel.from_pretrained(HF_ID).eval(), AutoProcessor.from_pretrained(HF_ID)

    def enc(texts: list[str]) -> np.ndarray:
        with torch.no_grad():
            e = m.get_text_features(**p(text=texts, padding="max_length", max_length=64, return_tensors="pt"))
            e = getattr(e, "pooler_output", e)
            return (e / e.norm(dim=-1, keepdim=True)).numpy()

    cls = {}
    for c, names in NAMES.items():
        e = enc([t.format(n) for n in names for t in TEMPLATES]).mean(0)
        cls[c] = e / np.linalg.norm(e)
    return cls, enc(NEGATIVES)


def export_onnx(out_dir: Path) -> Path:
    """Export the vision tower (fp32) and a weight-only 8-bit copy; returns the 8-bit path."""
    import onnx
    import torch
    from onnxruntime.quantization.matmul_nbits_quantizer import DefaultWeightOnlyQuantConfig, MatMulNBitsQuantizer
    from transformers import AutoModel
    out_dir.mkdir(parents=True, exist_ok=True)
    m = AutoModel.from_pretrained(HF_ID).eval()

    class V(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, x):
            f = self.m.get_image_features(pixel_values=x)
            f = getattr(f, "pooler_output", f)
            return f / f.norm(dim=-1, keepdim=True)

    fp32 = out_dir / "vision.fp32.onnx"
    torch.onnx.export(V(m).eval(), (torch.randn(1, 3, SIZE, SIZE),), str(fp32), input_names=["pixel_values"],
                      output_names=["embedding"], dynamic_axes={"pixel_values": {0: "n"}, "embedding": {0: "n"}},
                      opset_version=17, dynamo=False)
    cfg = DefaultWeightOnlyQuantConfig(block_size=32, is_symmetric=True, bits=8)
    q = MatMulNBitsQuantizer(onnx.load(str(fp32)), block_size=32, is_symmetric=True, algo_config=cfg)
    q.process()
    w8 = out_dir / "vision.onnx"
    q.model.save_model_to_file(str(w8), use_external_data_format=False)
    return w8
