"""Train-only per-feature two-input ridge correction for one-layer lookahead."""
import json,sys
from pathlib import Path
import numpy as np
import mlx.core as mx
sys.path.insert(0,str(Path('experiments/dsv41_mlx').resolve()))
from storage import Storage
root=Path('artifacts/dsv41-l2-state-v3-20260916');out=root/'lookahead-affine-fit';out.mkdir(exist_ok=False)
meta=json.loads((root/'router-lookahead-d1-correction-pilot/manifest.json').read_text());s=Storage('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD')
norm=np.stack([np.array(s.weight(f'layers.{l}.ffn_norm.weight',mx.float32)) for l in range(40)]);s.close();ratio=norm[1:]/np.where(np.abs(norm[:-1])>1e-6,norm[:-1],1)
sums=np.zeros((8,39,5120),np.float64);count=0
for name in meta['train_sequences']:
 with np.load(root/'data'/name/'supervision.npz') as z:states=z['previous_ffn'].astype(np.float32)
 for start in range(0,len(states)-1,32):
  end=min(start+32,len(states)-1);x=states[start+1:end+1,:-1]*ratio;r=states[start:end,1:]-states[start:end,:-1]*ratio;y=states[start+1:end+1,1:]-x
  for i,v in enumerate([x,r,y,x*x,r*r,x*r,x*y,r*y]):sums[i]+=v.sum(0,dtype=np.float64)
  count+=len(x)
x,r,y,xx,rr,xr,xy,ry=sums/count
vx=np.maximum(xx-x*x,1e-12);vr=np.maximum(rr-r*r,1e-12);cov=xr-x*r;cx=xy-x*y;cr=ry-r*y
for ridge in [.01,.1,1.,10.]:
 ax=vx*(1+ridge);ar=vr*(1+ridge);det=np.maximum(ax*ar-cov*cov,1e-24);a=(cx*ar-cr*cov)/det;b=(cr*ax-cx*cov)/det;c=y-a*x-b*r
 assert all(np.isfinite(v).all() for v in [a,b,c])
 np.savez_compressed(out/f'ridge-{ridge}.npz',a=a.astype(np.float32),b=b.astype(np.float32),c=c.astype(np.float32))
(out/'manifest.json').write_text(json.dumps(dict(train_sequences=meta['train_sequences'],train_rows=count,test_opened=False,scope='Current source FFN and previous-token layer residual; target-current next FFN only used in fitting'),indent=2));print('fitted',count)
