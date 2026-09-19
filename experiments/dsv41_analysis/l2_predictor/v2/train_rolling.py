"""Causal one/two-layer lookahead with sequential, capped prefetch decisions."""
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
ROOT=Path('artifacts/dsv41-l2-state-v3-20260916')
class Rolling(nn.Module):
 def __init__(self,distance,rank):
  super().__init__();layers=40-distance
  self.down=mx.random.normal((layers,5120,rank))*(5120**-.5);self.bias=mx.zeros((layers,rank));self.up=mx.random.normal((layers,rank,384))*(rank**-.5);self.offset=mx.zeros((layers,384));self.token=nn.Linear(5120,rank,bias=False);self.previous=nn.Linear(5120,rank,bias=False)
 def __call__(self,x,e,h):
  def norm(a):return a*mx.rsqrt(mx.mean(a*a,axis=-1,keepdims=True)+1e-6)
  hidden=mx.matmul(norm(x).transpose(1,0,2),self.down).transpose(1,0,2)+self.token(norm(e))[:,None]+self.previous(norm(h))[:,None]+self.bias
  return mx.matmul(nn.gelu(hidden).transpose(1,0,2),self.up).transpose(1,0,2)+self.offset

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--distance',type=int,choices=[1,2],default=2);ap.add_argument('--rank',type=int,default=64);ap.add_argument('--cohort',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();args.output.mkdir(exist_ok=False,parents=True);d=args.distance;plan=json.loads(args.cohort.read_text())
 def load(split):
  parts=[];names=[]
  for row in plan['samples']:
   if row['split']!=split:continue
   with np.load(ROOT/'data'/row['id']/'supervision.npz') as z:
    n=len(z['hidden'])-1
    if n<=0:continue
    r=z['resident'][:-1,d:].copy();t=np.zeros(r.shape,np.float32);np.put_along_axis(t,z['top6'][:-1,d:].astype(int),1,axis=-1)
    miss=(np.take_along_axis(z['resident'][:-1],z['top6'][:-1].astype(int),axis=-1)==0).sum(axis=(1,2))
    parts.append((z['previous_ffn'][1:,:40-d].copy(),z['embedding'][:-1].copy(),z['hidden'][:-1].copy(),t,r,miss));names.append(row['id'])
  return tuple(np.concatenate([p[i] for p in parts]) for i in range(6)),names
 tr,trids=load('train');va,vaids=load('validation');layer_misses=(tr[3].astype(bool)&(tr[4]==0)).sum(-1);quota=np.zeros(40-d,int)
 for _ in range(64):
  _,l=max((float((layer_misses[:,l]>quota[l]).mean()),l) for l in range(40-d) if quota[l]<6);quota[l]+=1
 thresholds=[-2.,-1.,0.,1.,2.,3.]
 def loss(m,x,e,h,t,r,unused):
  z=m(x,e,h);w=(1+3*(r==0))*(1+15*t);return mx.mean((mx.logaddexp(z,0)-z*t)*w)
 def evaluate(m,data):
  stats={str(v):[0,0] for v in thresholds};static=0;total=int(data[5].sum());nrows=len(data[0])
  for i in range(0,nrows,32):
   x,e,h,t,r,unused=[mx.array(a[i:i+32]) for a in data];z=np.array(m(x,e,h));eligible=data[4][i:i+32]==0;truth=data[3][i:i+32].astype(bool);score=np.where(eligible,z,-np.inf);order=np.argsort(score,axis=-1)[...,-6:][...,::-1];top=np.take_along_axis(score,order,axis=-1);correct=np.take_along_axis(truth,order,axis=-1)
   static+=int((correct&(np.arange(6)[None,None,:]<quota[None,:,None])).sum())
   # Layer-major order is the actual chronological decision order. Never sort
   # across future layer predictions that are not yet available.
   for threshold in thresholds:
    candidate=(top>=threshold).reshape(len(x),-1);accepted=candidate&(np.cumsum(candidate,axis=-1)<=64);good=correct.reshape(len(x),-1)&accepted;stats[str(threshold)][0]+=int(good.sum());stats[str(threshold)][1]+=int(accepted.sum())
  policies={k:dict(coverage=v[0]/total,useful_per_token=v[0]/nrows,reads_per_token=v[1]/nrows,precision=v[0]/max(1,v[1]),wasted_MB_per_token=(v[1]-v[0])*18.800640/nrows) for k,v in stats.items()}
  best=max(policies,key=lambda k:policies[k]['coverage'])
  return dict(rows=nrows,misses_per_token=total/nrows,static_quota_coverage=static/total,threshold_policies=policies,best_threshold=best,best_coverage=policies[best]['coverage'])
 mx.random.seed(31);rng=np.random.default_rng(31);m=Rolling(d,args.rank);opt=optim.AdamW(learning_rate=3e-4,weight_decay=.01);vg=nn.value_and_grad(m,loss);history=[];best=-1;stale=0
 manifest=dict(distance=d,rank=args.rank,train_sequences=trids,validation_sequences=vaids,train_rows=len(tr[0]),validation_rows=len(va[0]),static_quota=quota.tolist(),test_opened=False,causality='Current layer FFN input predicts layer+distance; layer-major decisions with remaining budget, maximum64/token. Future states used only as labels.',deadline_assumption='Offline ready upper bound, real SSD deadline not yet verified',source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest());(args.output/'manifest.json').write_text(json.dumps(manifest,indent=2));(args.output/'training-source.py').write_bytes(Path(__file__).read_bytes())
 for epoch in range(30):
  ix=rng.permutation(len(tr[0]));total=0
  for i in range(0,len(ix),32):
   j=ix[i:i+32];v,g=vg(m,*[mx.array(a[j]) for a in tr]);opt.update(m,g);mx.eval(m.parameters(),opt.state,v);total+=v.item()*len(j)
  ev=evaluate(m,va);score=ev['best_coverage'];history.append(dict(epoch=epoch+1,train_loss=total/len(ix),validation=ev))
  if score>best:best=score;best_epoch=epoch+1;best_ev=ev;stale=0;m.save_weights(str(args.output/'model.safetensors'))
  else:stale+=1
  (args.output/'history.json').write_text(json.dumps(history,indent=2));print(json.dumps(dict(epoch=epoch+1,coverage=score,threshold=ev['best_threshold'],static=ev['static_quota_coverage'])),flush=True)
  if stale>=5:break
 (args.output/'result.json').write_text(json.dumps(dict(best_epoch=best_epoch,validation=best_ev,**manifest),indent=2))
if __name__=='__main__':main()
