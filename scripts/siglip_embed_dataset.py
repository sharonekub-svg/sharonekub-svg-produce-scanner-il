#!/usr/bin/env python3
"""Embed EVERY row of one dataset (no caps), resumable; merge into emb_v7 for runs/siglip/v09:
  PYTHONPATH=. python3 scripts/siglip_embed_dataset.py hass_avocado_ripening runs/siglip/emb_hass.npz
"""
import json, sys, numpy as np
from pathlib import Path
from PIL import Image
from ml.siglip.features import Encoder
P=Path('data/processed_commercial_v7'); DS, out = sys.argv[1], Path(sys.argv[2])
rows=[json.loads(l) for l in open(P/'manifest.jsonl') if json.loads(l)['dataset_id'] == DS]
done={}
if out.exists():
    z=np.load(out); done=dict(zip(z['sha256'].tolist(), z['emb']))
enc=Encoder(Path('exports/siglip2/vision.onnx'), threads=8)
def save():
    k=[r for r in rows if r['sha256'] in done]
    np.savez(out, sha256=np.array([r['sha256'] for r in k]), split=np.array([r['split'] for r in k]),
             emb=np.stack([done[r['sha256']] for r in k]).astype(np.float16))
todo=[r for r in rows if r['sha256'] not in done]
for i in range(0,len(todo),128):
    ch=todo[i:i+128]
    e=enc([Image.open(P/r['image']) for r in ch])
    done.update({r['sha256']:v.astype(np.float16) for r,v in zip(ch,e)})
    if (i//128)%10==0: save(); print(len(done),'/',len(rows),flush=True)
save(); print('done',len(done))
