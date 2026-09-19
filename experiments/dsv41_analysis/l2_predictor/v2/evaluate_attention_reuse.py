"""Offline same-layer early-router pilot; no claim of SSD deadline readiness."""
import json,sys
from pathlib import Path
import numpy as np
import mlx.core as mx
sys.path.insert(0,str(Path('experiments/dsv41_mlx').resolve()))
from storage import Storage
root=Path('artifacts/dsv41-l2-attn-reuse-v5-20260916');plan=json.loads((root/'plan.json').read_text());assert (root/'pilot-verified.json').exists()
s=Storage('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD');w=mx.stack([s.weight(f'layers.{l}.ffn.gate.weight',mx.float32) for l in range(40)]).transpose(0,2,1);bias=mx.stack([s.weight(f'layers.{l}.ffn.gate.bias',mx.float32) for l in range(40)]);mx.eval(w,bias);s.close()
def router(x):return mx.sqrt(mx.logaddexp(mx.matmul(x.transpose(1,0,2),w).transpose(1,0,2),0))+bias
sums=np.zeros((40,5120),np.float64);count=0
for row in plan['samples']:
 if row['split']=='train':
  with np.load(root/'data'/row['id']/'supervision.npz') as z:sums+=(z['actual_ffn']-z['attention_reuse']).sum(0);count+=len(z['hidden'])
delta=(sums/count).astype(np.float32);results={};audit=[]
for weight in [0.,.25,.5,1.]:
 stats={k:[0,0] for k in [6,7,8]};misses=0;n=0
 for row in plan['samples']:
  if row['split']!='validation':continue
  with np.load(root/'data'/row['id']/'supervision.npz') as z:
   if weight==0:
    exact=router(mx.array(z['actual_ffn'][:1]));error=float(mx.max(mx.abs(exact-mx.array(z['router_rank'][:1]))).item());assert error<1e-3,error;audit.append(dict(id=row['id'],target_rank_max_abs=error))
   for i in range(0,len(z['hidden']),32):
    scores=np.array(router(mx.array(z['attention_reuse'][i:i+32]+weight*delta)));order=np.argsort(scores,axis=-1)[...,-8:][...,::-1];resident=z['resident'][i:i+32];truth=np.zeros(resident.shape,bool);np.put_along_axis(truth,z['top6'][i:i+32].astype(int),True,axis=-1);eligible=np.take_along_axis(resident,order,axis=-1)==0;correct=np.take_along_axis(truth,order,axis=-1);misses+=int((truth&(resident==0)).sum());n+=len(scores)
    for k in stats:
     candidates=eligible[...,:k].reshape(len(scores),-1);take=candidates&(np.cumsum(candidates,axis=-1)<=64);stats[k][0]+=int((take&correct[...,:k].reshape(len(scores),-1)).sum());stats[k][1]+=int(take.sum())
 results[str(weight)]={k:dict(coverage=a/misses,reads_per_token=b/n,useful_per_token=a/n,precision=a/max(1,b),wasted_MB_per_token=(b-a)*18.800640/n) for k,(a,b) in stats.items()};print(json.dumps(dict(mean_correction=weight,results=results[str(weight)])),flush=True)
(root/'attention-reuse-pilot.json').write_text(json.dumps(dict(status='pilot_only',target_alignment=audit,results=results,scope='one train and one validation family, no independent test; prefetch window only attention computation; sequential max64 budget'),indent=2))
