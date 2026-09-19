"""Validation diagnostic: frozen future Router on current normalized residual estimate."""
import json,sys
from pathlib import Path
import numpy as np
import mlx.core as mx
sys.path.insert(0,str(Path('experiments/dsv41_mlx').resolve()))
from storage import Storage
root=Path('artifacts/dsv41-l2-state-v3-20260916');plan=json.loads((root/'prefix-cohort-1.json').read_text());s=Storage('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD')
w=mx.stack([s.weight(f'layers.{l}.ffn.gate.weight',mx.float32) for l in range(40)]);bias=mx.stack([s.weight(f'layers.{l}.ffn.gate.bias',mx.float32) for l in range(40)]);norm=mx.stack([s.weight(f'layers.{l}.ffn_norm.weight',mx.float32) for l in range(40)]);mx.eval(w,bias,norm);s.close()
results={}
for distance in [1,2]:
 for renorm in [False,True]:
  stats={k:[0,0] for k in [6,8,12]};total=0;count=0
  for row in plan['samples']:
   if row['split']!='validation':continue
   with np.load(root/'data'/row['id']/'supervision.npz') as z:
    n=len(z['hidden'])-1;xall=z['previous_ffn'][1:];yy=z['top6'][:-1].astype(int);rr=z['resident'][:-1]
    for i in range(0,n,32):
     x=mx.array(xall[i:i+32,:40-distance])
     if renorm:x=x/mx.where(mx.abs(norm[:-distance])>1e-6,norm[:-distance],mx.ones_like(norm[:-distance]))*norm[distance:]
     raw=mx.matmul(x.transpose(1,0,2),w[distance:].transpose(0,2,1)).transpose(1,0,2);score=np.array(mx.sqrt(mx.logaddexp(raw,0))+bias[distance:]);order=np.argsort(score,axis=-1)[...,-12:][...,::-1]
     cache=rr[i:i+32,distance:];truth=np.zeros(cache.shape,bool);np.put_along_axis(truth,yy[i:i+32,distance:],True,axis=-1)
     eligible=np.take_along_axis(cache,order,axis=-1)==0;correct=np.take_along_axis(truth,order,axis=-1);total+=int((np.take_along_axis(rr[i:i+32],yy[i:i+32],axis=-1)==0).sum());count+=len(x)
     for k in stats:
      candidate=eligible[...,:k].reshape(len(x),-1);take=candidate&(np.cumsum(candidate,axis=-1)<=64);good=correct[...,:k].reshape(len(x),-1)&take;stats[k][0]+=int(good.sum());stats[k][1]+=int(take.sum())
  result={k:dict(coverage=a/total,reads_per_token=b/count,precision=a/max(b,1)) for k,(a,b) in stats.items()};results[f'd{distance}-norm{int(renorm)}']=result;print(json.dumps({f'd{distance}-norm{int(renorm)}':result}),flush=True)
(root/'router-lookahead-probe.json').write_text(json.dumps(dict(scope='validation only; sequential cap64; same-token source layer known before future target layer; no SSD timing',results=results),indent=2))
