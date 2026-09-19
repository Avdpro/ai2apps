"""Validation tuning of a causal reserve policy; total reads never exceed64."""
import json,sys
from pathlib import Path
import numpy as np
import mlx.core as mx
from train_router_lookahead import Correction,ROOT
sys.path.insert(0,str(Path('experiments/dsv41_mlx').resolve()))
from storage import Storage
out=ROOT/'router-lookahead-d1-correction-pilot';meta=json.loads((out/'manifest.json').read_text());model=Correction(39);model.load_weights(str(out/'model.safetensors'));s=Storage('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD');w=mx.stack([s.weight(f'layers.{l}.ffn.gate.weight',mx.float32) for l in range(1,40)]).transpose(0,2,1);b=mx.stack([s.weight(f'layers.{l}.ffn.gate.bias',mx.float32) for l in range(1,40)]);norm=mx.stack([s.weight(f'layers.{l}.ffn_norm.weight',mx.float32) for l in range(40)]);ratio=norm[1:]/mx.where(mx.abs(norm[:-1])>1e-6,norm[:-1],mx.ones_like(norm[:-1]));mx.eval(w,b,ratio);s.close()
def gather(names):
 arrays=[];miss=0
 for name in names:
  with np.load(ROOT/'data'/name/'supervision.npz') as z:
   x=z['previous_ffn'][1:,:-1];e=z['embedding'][:-1];h=z['hidden'][:-1];r=z['resident'][:-1,1:];truth=np.zeros(r.shape,bool);np.put_along_axis(truth,z['top6'][:-1,1:].astype(int),True,axis=-1);miss+=int((np.take_along_axis(z['resident'][:-1],z['top6'][:-1].astype(int),axis=-1)==0).sum())
   for i in range(0,len(x),32):
    pred=model(mx.array(x[i:i+32]),mx.array(e[i:i+32]),mx.array(h[i:i+32]),ratio);raw=mx.matmul(pred.transpose(1,0,2),w).transpose(1,0,2);scores=np.array(mx.sqrt(mx.maximum(mx.logaddexp(raw,0),1e-20))+b);ix=np.argsort(scores,axis=-1)[...,-8:][...,::-1];rank=np.take_along_axis(scores,ix,axis=-1);eligible=np.take_along_axis(r[i:i+32],ix,axis=-1)==0;correct=np.take_along_axis(truth[i:i+32],ix,axis=-1);arrays.append((rank,eligible,correct))
 return tuple(np.concatenate([a[i] for a in arrays]) for i in range(3)),miss
train,_=gather(meta['train_sequences']);val,miss=gather(meta['validation_sequences']);mean=train[1][...,:6].sum(-1).mean(0);reserve=np.cumsum(mean[::-1])[::-1]-mean;scores,eligible,correct=val;n=len(scores);rows=[]
for alpha in [.5,.8,1.]:
 for margin in [.01,.05,.1,.2,100.]:
  spent=np.zeros(n,int);hits=np.zeros(n,int)
  for layer in range(39):
   for k in range(8):
    take=eligible[:,layer,k]&(spent<64)
    if k>=6:take&=(scores[:,layer,k]>=scores[:,layer,5]-margin)&(64-spent>reserve[layer]*alpha)
    hits+=take&correct[:,layer,k];spent+=take
  rows.append(dict(reserve_multiplier=alpha,extra_rank_margin=margin,coverage=int(hits.sum())/miss,reads_per_token=float(spent.mean()),useful_per_token=float(hits.mean()),precision=int(hits.sum())/int(spent.sum()),wasted_MB_per_token=float((spent-hits).mean())*18.800640))
rows.sort(key=lambda r:r['coverage'],reverse=True);(out/'policy-tuning.json').write_text(json.dumps(dict(reserve_from_training=reserve.tolist(),validation_rows=n,results=rows,causality='layer-major, training-only future reserve, cap64; no future current-token prediction available to an earlier decision'),indent=2));print(json.dumps(rows[:4],indent=2))
