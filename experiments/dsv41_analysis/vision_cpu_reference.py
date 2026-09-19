"""Independent official CPU vision/aligner reference; never imported by the MLX runner."""
import json,importlib.util
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import torch
from safetensors import safe_open
from safetensors.torch import save_file
root=Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD');out=Path('artifacts/dsv41-vision-cpu-reference-20260913');out.mkdir(exist_ok=False)
torch.set_num_threads(4);torch.set_default_dtype(torch.bfloat16)
spec=importlib.util.spec_from_file_location('official_vit',root/'inference/vision.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
c=SimpleNamespace(**json.load(open(root/'inference/config.json')))
with torch.device('meta'):vit=v.ViT(c);aligner=v.Aligner(c)
index=json.load(open(root/'model.safetensors.index.json'))['weight_map'];weights={}
for file in sorted({file for name,file in index.items() if name.startswith(('vision.','aligner.'))}):
 with safe_open(root/file,framework='pt',device='cpu') as f:
  for name in f.keys():
   if name.startswith(('vision.','aligner.')):weights[name]=f.get_tensor(name)
vit.load_state_dict({k[len('vision.'):]:x for k,x in weights.items() if k.startswith('vision.')},assign=True)
aligner.load_state_dict({k[len('aligner.'):]:x for k,x in weights.items() if k.startswith('aligner.')},assign=True)
nh,nw=6,7
patches=torch.from_numpy(np.random.default_rng(19).normal(size=(nh*nw,3,14,14)).astype(np.float32)).to(torch.bfloat16)
with torch.inference_mode():features=vit(patches,nh,nw);aligned=aligner(features,nh,nw)
save_file({'patches':patches.float(),'features':features.float(),'aligned':aligned.float()},str(out/'reference.safetensors'))
(out/'config.json').write_text(json.dumps(dict(nh=nh,nw=nw,source=str(root/'inference/vision.py'))))
print('CPU vision reference complete',aligned.shape,flush=True)
