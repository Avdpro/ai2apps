import sys,json
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dsv41_mlx'))
import mlx.core as mx
import numpy as np
from safetensors.numpy import load_file
from storage import Storage
from vision import Vision
root=Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD');ref=Path('artifacts/dsv41-vision-cpu-reference-20260913')
a=load_file(str(ref/'reference.safetensors'));grid=json.load(open(ref/'config.json'))
s=Storage(root);v=Vision(s,SimpleNamespace(**json.load(open(root/'inference/config.json'))));weight_bytes=v.load()
y=v(mx.array(a['patches']).astype(mx.bfloat16),grid['nh'],grid['nw']);mx.eval(y)
x=a['aligned'].astype(np.float64);z=np.array(y.astype(mx.float32)).astype(np.float64)
assert np.isfinite(z).all()
report=dict(weight_bytes=weight_bytes,shape=list(z.shape),max_abs=float(abs(x-z).max()),rmse=float(np.sqrt(np.mean((x-z)**2))),reference_rms=float(np.sqrt(np.mean(x*x))),cosine=float(np.vdot(x,z)/(np.linalg.norm(x)*np.linalg.norm(z))))
(ref/'mlx-comparison.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));s.close()
