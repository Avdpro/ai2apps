"""Validation-only miss-aware ablations. Never loads the held-out test split."""
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_flatten
from train import ROOT,load
OUT=ROOT/'optimization-v2'
BUDGETS=[16,32,48,64,96]

class Head(nn.Module):
 def __init__(self,rank,context):
  super().__init__();self.context=context;self.down=nn.Linear(10240,rank)
  if context:self.cache=nn.Linear(15360,rank,bias=False);self.prev=nn.Linear(15360,rank,bias=False)
  self.up=nn.Linear(rank,15360)
 def __call__(self,x,r,p):
  x=x.reshape(-1,2,5120);x=x*mx.rsqrt(mx.mean(x*x,axis=-1,keepdims=True)+1e-6);h=self.down(x.reshape(-1,10240))
  if self.context:h=h+self.cache((r>0).astype(mx.float32).reshape(-1,15360))+self.prev(p.reshape(-1,15360))
  return self.up(nn.gelu(h)).reshape(-1,40,384)

def unpack(data):
 x,y,p,r=data;t=np.zeros(r.shape,np.float32);q=np.zeros_like(t);np.put_along_axis(t,y,1,axis=-1);np.put_along_axis(q,p,1,axis=-1)
 return x,t,q,r

def objective(model,x,t,p,r):
 z=model(x,r,p);eligible=(r==0).astype(mx.float32)
 # Positive weighting counteracts 6/384 sparsity. Cache misses receive 4x
 # weight, but resident routing remains an auxiliary supervision signal.
 weight=(1+3*eligible)*(1+15*t)
 return mx.mean((mx.logaddexp(z,0)-t*z)*weight)

def evaluate(model,data):
 x,t,p,r=data;hits={k:0 for k in BUDGETS};miss=0;loss=0;layers=np.zeros(40);lm=np.zeros(40)
 for i in range(0,len(x),64):
  xx,tt,pp,rr=[mx.array(a[i:i+64]) for a in data];z=model(xx,rr,pp);v=objective(model,xx,tt,pp,rr);mx.eval(z,v);loss+=v.item()*len(xx)
  eligible=r[i:i+64]==0;truth=t[i:i+64].astype(bool)&eligible;miss+=truth.sum();lm+=truth.sum(axis=(0,2))
  score=np.where(eligible,np.array(z),-np.inf).reshape(len(xx),-1);order=np.argsort(score,axis=-1)[:,-max(BUDGETS):][:,::-1]
  good=np.take_along_axis(truth.reshape(len(xx),-1),order,axis=-1)
  for k in BUDGETS:hits[k]+=int(good[:,:k].sum())
  for j in range(len(xx)):
   selected=order[j,:48][good[j,:48]];layers+=np.bincount(selected//384,minlength=40)
 return dict(loss=loss/len(x),misses_per_token=float(miss)/len(x),budgets={k:dict(coverage=v/int(miss),useful_per_token=v/len(x),precision=v/(len(x)*k)) for k,v in hits.items()},layer_coverage48=np.divide(layers,lm,out=np.zeros_like(layers),where=lm>0).tolist())

def main():
 global OUT
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=OUT);parser.add_argument('--configs',default='128:0,256:0,256:1,512:1');args=parser.parse_args();OUT=args.output
 OUT.mkdir(exist_ok=False);plan=json.loads((ROOT/'plan.json').read_text());train=unpack(load(plan,'train'));val=unpack(load(plan,'validation'))
 (OUT/'protocol.json').write_text(json.dumps(dict(target='70% of ALL 40-layer actual misses',primary_budget=48,secondary_budget=64,diagnostic_budget=96,test_opened=False,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2))
 results=[]
 for rank,context in [(int(item.split(':')[0]),bool(int(item.split(':')[1]))) for item in args.configs.split(',')]:
  name=f'r{rank}-context{int(context)}';out=OUT/name;out.mkdir();mx.random.seed(20260917);rng=np.random.default_rng(20260917);model=Head(rank,context);opt=optim.AdamW(learning_rate=2e-4,weight_decay=.01);vg=nn.value_and_grad(model,objective);best=-1;history=[];start=time.time();stale=0
  for epoch in range(30):
   order=rng.permutation(len(train[0]));total=0
   for j in range(0,len(order),32):
    idx=order[j:j+32];xx,tt,pp,rr=[mx.array(a[idx]) for a in train];v,g=vg(model,xx,tt,pp,rr);opt.update(model,g);mx.eval(model.parameters(),opt.state,v);total+=v.item()*len(idx)
   ev=evaluate(model,val);score=ev['budgets'][48]['coverage'];row=dict(epoch=epoch+1,train_loss=total/len(order),validation=ev,seconds=time.time()-start);history.append(row)
   if score>best:
    best=score;best_epoch=epoch+1;best_ev=ev;stale=0;model.save_weights(str(out/'model.safetensors'))
   else:stale+=1
   (out/'history.json').write_text(json.dumps(history,indent=2));print(json.dumps(dict(model=name,epoch=epoch+1,coverage48=score,coverage64=ev['budgets'][64]['coverage'],best=best)),flush=True)
   if stale>=5:break
  result=dict(name=name,rank=rank,context=context,best_epoch=best_epoch,validation=best_ev,parameters=sum(v.size for _,v in tree_flatten(model.parameters())),seconds=time.time()-start)
  (out/'result.json').write_text(json.dumps(result,indent=2));results.append(result);(OUT/'results.json').write_text(json.dumps(results,indent=2))
if __name__=='__main__':main()
