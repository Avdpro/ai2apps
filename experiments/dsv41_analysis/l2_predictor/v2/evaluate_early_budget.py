"""Fixed-cohort causal early-router budget diagnostic (validation only)."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import mlx.core as mx
sys.path.insert(0, str(Path('experiments/dsv41_mlx').resolve()))
from storage import Storage

ap = argparse.ArgumentParser()
ap.add_argument('--root', type=Path, required=True)
ap.add_argument('--reuse-blend',type=float)
ap.add_argument('--blend-coefficients',type=Path)
ap.add_argument('--mean-scale',type=float,default=1.)
ap.add_argument('--feature', choices=['preattn', 'attention_reuse'], default='preattn')
ap.add_argument('--output', type=Path, required=True)
ap.add_argument('--export-proposals', action='store_true')
a = ap.parse_args()
a.output.mkdir(parents=True, exist_ok=False)
plan = json.loads((a.root/'plan.json').read_text())
samples = [r for r in plan['samples'] if r['split'] in ['train', 'validation'] and (a.root/'data'/r['id']/'verified.json').exists()]
assert {r['split'] for r in samples} == {'train', 'validation'}
train_families = {r['family_id'] for r in samples if r['split']=='train'}
assert not train_families.intersection(r['family_id'] for r in samples if r['split']=='validation')
coefficients=(np.array(json.loads(a.blend_coefficients.read_text())['coefficients'],np.float32)[:,None] if a.blend_coefficients else a.reuse_blend)
def feature(z):
 if coefficients is not None:return z['preattn'].astype(np.float32)+coefficients*(z['attention_reuse'].astype(np.float32)-z['preattn'].astype(np.float32))
 return z[a.feature].astype(np.float32)
mean = np.zeros((40,5120), np.float64)
count = 0
for r in samples:
 if r['split'] == 'train':
  with np.load(a.root/'data'/r['id']/'supervision.npz') as z:
   mean += (z['actual_ffn'].astype(np.float32)-feature(z)).sum(0); count += len(z['hidden'])
mean = (a.mean_scale*mean/count).astype(np.float32)
s = Storage('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD')
w = mx.stack([s.weight(f'layers.{l}.ffn.gate.weight', mx.float32) for l in range(40)]).transpose(0,2,1)
bias = mx.stack([s.weight(f'layers.{l}.ffn.gate.bias', mx.float32) for l in range(40)])
mx.eval(w,bias);s.close()
proposals={'train':[], 'validation':[]}
stats = {b:dict(useful=0,reads=0,oracle=0,layer_useful=np.zeros(40,np.int64)) for b in [48,64,96]}
misses=0;rows=0;layer_misses=np.zeros(40,np.int64)
for r in samples:
 if r['split']!='validation' and not a.export_proposals:continue
 with np.load(a.root/'data'/r['id']/'supervision.npz') as z:
  features=feature(z)
  for start in range(0,len(z['hidden']),32):
   x=mx.array(features[start:start+32]+mean)
   score=np.array(mx.sqrt(mx.logaddexp(mx.matmul(x.transpose(1,0,2),w).transpose(1,0,2),0))+bias)
   ids=np.argsort(score,axis=-1)[...,-12:][...,::-1]
   ordered=np.take_along_axis(score,ids,axis=-1)
   resident=z['resident'][start:start+32]
   truth=np.zeros(resident.shape,bool);np.put_along_axis(truth,z['top6'][start:start+32].astype(int),True,axis=-1)
   target=truth&(resident==0);nm=target.sum((1,2))
   eligible=np.take_along_axis(resident,ids,axis=-1)==0
   correct=np.take_along_axis(truth,ids,axis=-1)
   if a.export_proposals:proposals[r['split']].append((ordered,eligible,correct,nm))
   if r['split']!='validation':continue
   misses+=int(nm.sum());rows+=len(nm);layer_misses+=target.sum((0,2))
   eligible=eligible[...,:6];correct=correct[...,:6]
   for budget,st in stats.items():
    take=eligible & (np.cumsum(eligible.reshape(len(nm),-1),axis=-1).reshape(eligible.shape)<=budget)
    useful=take&correct;st['useful']+=int(useful.sum());st['reads']+=int(take.sum());st['oracle']+=int(np.minimum(nm,budget).sum());st['layer_useful']+=useful.sum((0,2))
results={str(b):dict(coverage=st['useful']/misses,reads_per_token=st['reads']/rows,useful_per_token=st['useful']/rows,precision=st['useful']/max(1,st['reads']),wasted_MB_per_token=(st['reads']-st['useful'])*18.800640/rows,oracle_budget_ceiling=st['oracle']/misses,layer_coverage=(st['layer_useful']/np.maximum(layer_misses,1)).tolist()) for b,st in stats.items()}
report=dict(blend_coefficients=str(a.blend_coefficients) if a.blend_coefficients else None,reuse_blend=a.reuse_blend,feature=a.feature,mean_scale=a.mean_scale,train_rows=count,validation_rows=rows,misses=misses,results=results,samples=samples,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),test_opened=False,scope='Offline mean-corrected early router; layer-major Top6 prefetch; no deadline or asynchronous handoff proof')
(a.output/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:{kk:vv for kk,vv in v.items() if kk!='layer_coverage'} for k,v in results.items()}),flush=True)

if a.export_proposals:
 for split,parts in proposals.items():
  np.savez_compressed(a.output/f'{split}-proposals.npz',**{key:np.concatenate([p[i] for p in parts]) for i,key in enumerate(['scores','eligible','correct','misses'])})
