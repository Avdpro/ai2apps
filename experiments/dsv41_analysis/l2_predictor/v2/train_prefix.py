"""Predict future layers from an already-computed current-token prefix, never future states."""
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from optimize import Head,objective
ROOT=Path('artifacts/dsv41-l2-state-v3-20260916')

class PrefixHead(Head):
 def __init__(self,rank,channels):
  super().__init__(rank,False);self.channels=channels;self.down=nn.Linear(5120*channels,rank)
 def __call__(self,x,r,p):
  x=x.reshape(-1,self.channels,5120);x=x*mx.rsqrt(mx.mean(x*x,axis=-1,keepdims=True)+1e-6)
  return self.up(nn.gelu(self.down(x.reshape(-1,self.channels*5120)))).reshape(-1,40,384)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--prefix',type=int,default=0);ap.add_argument('--feature',choices=['current-prefix','previous-final','combined'],default='current-prefix');ap.add_argument('--rank',type=int,default=512);ap.add_argument('--cohort',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();args.output.mkdir(exist_ok=False,parents=True)
 cohort=json.loads(args.cohort.read_text())
 def load(split):
  parts=[];names=[]
  for row in cohort['samples']:
   if row['split']!=split:continue
   with np.load(ROOT/'data'/row['id']/'supervision.npz') as z:
    n=len(z['hidden'])-1
    if n<=0:continue
    # Only ONE current-prefix layer is exposed. The later layer states are not model inputs.
    state=z['previous_ffn'][1:,args.prefix].copy() if args.feature!='previous-final' else z['hidden'][:-1].copy()
    inputs=[state,z['embedding'][:-1]]
    if args.feature=='combined':inputs.append(z['hidden'][:-1])
    features=np.concatenate(inputs,axis=-1);resident=z['resident'][:-1].copy();y=np.zeros(resident.shape,np.float32);np.put_along_axis(y,z['top6'][:-1].astype(int),1,axis=-1)
    parts.append((features,y,np.zeros_like(y),resident));names.append(row['id'])
  return tuple(np.concatenate([p[i] for p in parts]) for i in range(4)),names
 tr,trids=load('train');va,vaids=load('validation')
 def loss(m,x,t,p,r):
  z=m(x,r,p);w=(1+3*(r==0))*(1+15*t);w[:,:args.prefix+1]=0
  return mx.mean((mx.logaddexp(z,0)-t*z)*w)
 def evaluate(m,d):
  hits={k:0 for k in [32,48,64,96]};miss=0;past=0
  for i in range(0,len(d[0]),64):
   x,t,p,r=[mx.array(a[i:i+64]) for a in d];score=np.array(m(x,r,p));eligible=d[3][i:i+64]==0;truth=d[1][i:i+64].astype(bool)&eligible;miss+=truth.sum();past+=truth[:,:args.prefix+1].sum();eligible[:,:args.prefix+1]=False
   rank=np.where(eligible,score,-np.inf).reshape(len(x),-1);ix=np.argsort(rank,axis=-1)[:,-96:][:,::-1];good=np.take_along_axis(truth.reshape(len(x),-1),ix,axis=-1)
   for k in hits:hits[k]+=int(good[:,:k].sum())
  return dict(rows=len(d[0]),all_layer_misses_per_token=float(miss)/len(d[0]),uncoverable_prefix_fraction=float(past)/int(miss),budgets={k:dict(coverage=v/int(miss),useful_per_token=v/len(d[0]),precision=v/(len(d[0])*k)) for k,v in hits.items()})
 mx.random.seed(29);rng=np.random.default_rng(29);m=PrefixHead(args.rank,3 if args.feature=='combined' else 2);opt=optim.AdamW(learning_rate=2e-4,weight_decay=.01);vg=nn.value_and_grad(m,loss);best=-1;hist=[];stale=0
 manifest=dict(feature=args.feature,prefix=args.prefix,rank=args.rank,train_sequences=trids,validation_sequences=vaids,train_rows=len(tr[0]),validation_rows=len(va[0]),selection='validation ALL-40-layer miss coverage at global64 budget',availability='current prefix FFN normalized input before its routed MoE; only subsequent layers may be prefetched',test_opened=False,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest());(args.output/'manifest.json').write_text(json.dumps(manifest,indent=2))
 for epoch in range(30):
  order=rng.permutation(len(tr[0]));total=0
  for i in range(0,len(order),32):
   ix=order[i:i+32];v,g=vg(m,*[mx.array(a[ix]) for a in tr]);opt.update(m,g);mx.eval(m.parameters(),opt.state,v);total+=v.item()*len(ix)
  ev=evaluate(m,va);score=ev['budgets'][64]['coverage'];hist.append(dict(epoch=epoch+1,train_loss=total/len(order),validation=ev))
  if score>best:best=score;best_ev=ev;best_epoch=epoch+1;stale=0;m.save_weights(str(args.output/'model.safetensors'))
  else:stale+=1
  (args.output/'history.json').write_text(json.dumps(hist,indent=2));print(json.dumps(dict(epoch=epoch+1,coverage48=ev['budgets'][48]['coverage'],coverage64=score)),flush=True)
  if stale>=5:break
 (args.output/'result.json').write_text(json.dumps(dict(best_epoch=best_epoch,validation=best_ev,**manifest),indent=2))
if __name__=='__main__':main()
