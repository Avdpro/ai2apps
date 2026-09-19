"""Frozen backbone, small MLX multi-label route predictor; family-held-out eval."""
import argparse,json,time
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_flatten
p=argparse.ArgumentParser();p.add_argument('--full',action='store_true');p.add_argument('--epochs',type=int,default=10);a=p.parse_args()
root=Path('artifacts/dsv41-l2-predictor-20260915');meta=json.loads((root/('collection-full.json' if a.full else 'collection-pilot.json')).read_text());mode='full' if a.full else 'pilot';out=root/('training-'+mode);out.mkdir(exist_ok=True)
assert not (out/'model.safetensors').exists(),'Do not overwrite a trained artifact'
trainfamilies={r['family_id'] for r in meta if r['split']=='train'};valfamilies={r['family_id'] for r in meta if r['split']=='validation'};assert not trainfamilies&valfamilies
# Test split is intentionally never opened during model fitting or selection.
def load(split):
 records=[]
 for r in meta:
  if r['split']==split:
   with np.load(root/'data'/r['id']/'supervision.npz') as z:records.append(tuple(z[k].copy() for k in ['features','top6','previous_top6']))
 return tuple(np.concatenate([r[j] for r in records]) for j in range(3))
xf,yf,pf=load('train');xv,yv,pv=load('validation')
class Predictor(nn.Module):
 def __init__(self):
  super().__init__();self.input=nn.Linear(10240,256);self.output=nn.Linear(256,35*384)
 def __call__(self,x):
  x=x.astype(mx.float32).reshape(-1,2,5120);x=x*mx.rsqrt(mx.mean(x*x,axis=-1,keepdims=True)+1e-6)
  return self.output(nn.gelu(self.input(x.reshape(-1,10240)))).reshape(-1,35,384)
mx.random.seed(20260915);rng=np.random.default_rng(20260915);model=Predictor();optimizer=optim.AdamW(learning_rate=3e-4,weight_decay=1e-3)
def loss(m,x,y):
 logits=m(x);return mx.mean(mx.logsumexp(logits,axis=-1)-mx.mean(mx.take_along_axis(logits,y.astype(mx.int32),axis=-1),axis=-1))
vg=nn.value_and_grad(model,loss)
def recall(indices,targets):return float((indices[...,None]==targets[...,None,:]).any(axis=-2).mean())
def evaluate(x,y):
 hits={k:0 for k in [6,12,24,48]};total=0;ls=0
 for i in range(0,len(x),64):
  xx=mx.array(x[i:i+64]);yy=mx.array(y[i:i+64]);pred=model(xx);v=loss(model,xx,yy);mx.eval(pred,v);rank=np.argsort(np.array(pred),axis=-1);n=len(xx);total+=n;ls+=float(v.item())*n
  for k in hits:hits[k]+=recall(rank[...,-k:],y[i:i+64])*n
 return dict(loss=ls/total,recall={str(k):v/total for k,v in hits.items()})
counts=np.zeros((35,384),dtype=np.int64)
for l in range(35):counts[l]=np.bincount(yf[:,l].ravel(),minlength=384)
rank=np.argsort(counts,axis=-1)
baselines={'previous_top6_recall6':recall(pv,yv),'train_frequency':{str(k):recall(np.broadcast_to(rank[None,:,-k:],(len(yv),35,k)),yv) for k in [6,12,24,48]}}
start=time.time();history=[];best=float('inf')
for epoch in range(a.epochs):
 indices=rng.permutation(len(xf));s=0
 for i in range(0,len(indices),32):
  batch=indices[i:i+32];v,g=vg(model,mx.array(xf[batch]),mx.array(yf[batch]));optimizer.update(model,g);mx.eval(model.parameters(),optimizer.state,v);s+=float(v.item())*len(batch)
 val=evaluate(xv,yv);row=dict(epoch=epoch+1,train_loss=s/len(xf),validation=val,elapsed_s=time.time()-start);history.append(row)
 if val['loss']<best:
  best=val['loss'];model.save_weights(str(out/'model.safetensors'))
 (out/'history.json').write_text(json.dumps(history,indent=2));print(json.dumps(row),flush=True)
model.load_weights(str(out/'model.safetensors'));result=dict(mode=mode,train_rows=len(xf),validation_rows=len(xv),epochs=a.epochs,seconds=time.time()-start,parameters=sum(v.size for _,v in tree_flatten(model.parameters())),matrix_shapes={k:list(v.shape) for k,v in tree_flatten(model.parameters())},validation=evaluate(xv,yv),baselines=baselines,train_families=sorted(trainfamilies),validation_families=sorted(valfamilies),precision='float32 training weights; deployment quantization not evaluated',limitations=['pilot is a data-path check, not a generalization claim','router recall is not deadline-aware L2 cache hit rate','no inference prefetch integration or TPS measurement'])
(out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
