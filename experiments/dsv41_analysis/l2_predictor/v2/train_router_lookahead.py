"""Learn causal adjacent-layer state correction around frozen official routers."""
import argparse,json,hashlib,sys
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
sys.path.insert(0,str(Path('experiments/dsv41_mlx').resolve()))
from storage import Storage
ROOT=Path('artifacts/dsv41-l2-state-v3-20260916')
class Correction(nn.Module):
 def __init__(self,layers):
  super().__init__();self.local=nn.Linear(5120,128);self.token=nn.Linear(5120,128,bias=False);self.previous=nn.Linear(5120,128,bias=False);self.layer=mx.zeros((layers,128));self.out=nn.Linear(128,5120);self.out.weight=mx.zeros_like(self.out.weight);self.out.bias=mx.zeros_like(self.out.bias);self.log_scale=mx.full((layers,),2.);self.offset=mx.full((layers,),-3.)
 def __call__(self,x,e,h,ratio):
  def norm(a):return a*mx.rsqrt(mx.mean(a*a,axis=-1,keepdims=True)+1e-6)
  base=x*ratio;hidden=self.local(norm(x))+self.token(norm(e))[:,None]+self.previous(norm(h))[:,None]+self.layer
  return base+self.out(nn.gelu(hidden))*mx.sqrt(mx.mean(base*base,axis=-1,keepdims=True)+1e-6)

class PerLayerCorrection(nn.Module):
 def __init__(self,layers,rank=64):
  super().__init__();self.local=mx.random.normal((layers,5120,rank))*(5120**-.5);self.token=nn.Linear(5120,rank,bias=False);self.previous=nn.Linear(5120,rank,bias=False);self.layer=mx.zeros((layers,rank));self.out=mx.zeros((layers,rank,5120));self.bias=mx.zeros((layers,5120));self.log_scale=mx.full((layers,),2.);self.offset=mx.full((layers,),-3.)
 def __call__(self,x,e,h,ratio):
  def norm(a):return a*mx.rsqrt(mx.mean(a*a,axis=-1,keepdims=True)+1e-6)
  base=x*ratio;local=mx.matmul(norm(x).transpose(1,0,2),self.local).transpose(1,0,2);hidden=nn.gelu(local+self.token(norm(e))[:,None]+self.previous(norm(h))[:,None]+self.layer);delta=mx.matmul(hidden.transpose(1,0,2),self.out).transpose(1,0,2)+self.bias
  return base+delta*mx.sqrt(mx.mean(base*base,axis=-1,keepdims=True)+1e-6)

class RoutedCorrection(PerLayerCorrection):
 def __init__(self,layers,rank=64):
  super().__init__(layers,rank);self.experts=mx.zeros((layers,384,rank))
 def __call__(self,x,e,h,ratio,ids):
  def norm(a):return a*mx.rsqrt(mx.mean(a*a,axis=-1,keepdims=True)+1e-6)
  base=x*ratio;local=mx.matmul(norm(x).transpose(1,0,2),self.local).transpose(1,0,2)
  routed=mx.mean(self.experts[mx.arange(self.experts.shape[0])[None,:,None],ids],axis=2)
  hidden=nn.gelu(local+self.token(norm(e))[:,None]+self.previous(norm(h))[:,None]+self.layer+routed)
  delta=mx.matmul(hidden.transpose(1,0,2),self.out).transpose(1,0,2)+self.bias
  return base+delta*mx.sqrt(mx.mean(base*base,axis=-1,keepdims=True)+1e-6)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cohort',type=Path,required=True);ap.add_argument('--distance',type=int,default=1,choices=[1,2]);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--per-layer-rank',type=int,default=0);ap.add_argument('--route-features',action='store_true');ap.add_argument('--warm-start',type=Path);ap.add_argument('--route-only',action='store_true');ap.add_argument('--learning-rate',type=float,default=1e-4);ap.add_argument('--loss',choices=['bce','rank'],default='bce');args=ap.parse_args();args.output.mkdir(exist_ok=False,parents=True);d=args.distance;plan=json.loads(args.cohort.read_text())
 def load(split):
  parts=[];names=[]
  for row in plan['samples']:
   if row['split']!=split:continue
   with np.load(ROOT/'data'/row['id']/'supervision.npz') as z:
    current=z['previous_ffn'][1:];resident=z['resident'][:-1,d:];truth=np.zeros(resident.shape,np.float32);np.put_along_axis(truth,z['top6'][:-1,d:].astype(int),1,axis=-1);misses=(np.take_along_axis(z['resident'][:-1],z['top6'][:-1].astype(int),axis=-1)==0).sum((1,2))
    parts.append((current[:,:-d].copy(),z['embedding'][:-1].copy(),z['hidden'][:-1].copy(),current[:,d:].copy(),truth,resident.copy(),misses,z['top6'][:-1,:-d].astype(np.int32)));names.append(row['id'])
  return tuple(np.concatenate([p[i] for p in parts]) for i in range(8)),names
 tr,trids=load('train');va,vaids=load('validation')
 s=Storage('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD');w=mx.stack([s.weight(f'layers.{l}.ffn.gate.weight',mx.float32) for l in range(d,40)]).transpose(0,2,1);bias=mx.stack([s.weight(f'layers.{l}.ffn.gate.bias',mx.float32) for l in range(d,40)]);norm=mx.stack([s.weight(f'layers.{l}.ffn_norm.weight',mx.float32) for l in range(40)]);ratio=norm[d:]/mx.where(mx.abs(norm[:-d])>1e-6,norm[:-d],mx.ones_like(norm[:-d]));mx.eval(w,bias,ratio);s.close()
 def router(x):return mx.sqrt(mx.maximum(mx.logaddexp(mx.matmul(x.transpose(1,0,2),w).transpose(1,0,2),0),1e-20))+bias
 def predict(m,x,e,h,ids):return m(x,e,h,ratio,ids) if args.route_features else m(x,e,h,ratio)
 def loss(m,x,e,h,target,t,r,unused,ids):
  pred=predict(m,x,e,h,ids);rank=router(pred);z=(rank-mx.mean(rank,axis=-1,keepdims=True))*mx.exp(mx.clip(m.log_scale,-2,5))[None,:,None]+m.offset[None,:,None]
  weight=(1+3*(r==0))*(1+15*t);classification=mx.mean((mx.logaddexp(z,0)-t*z)*weight);regression=mx.mean(mx.mean((pred-target)**2,axis=-1)/(mx.mean(target**2,axis=-1)+1e-6))
  if args.loss=='rank':
   labels=t*(1+3*(r==0));labels=labels/mx.maximum(mx.sum(labels,axis=-1,keepdims=True),1);logits=rank/.1;classification=-mx.mean(mx.sum(labels*(logits-mx.logsumexp(logits,axis=-1,keepdims=True)),axis=-1));return classification+.02*regression
  return classification+.2*regression
 def evaluate(m,data):
  useful=0;reads=0;misses=int(data[6].sum());nrows=len(data[0])
  for i in range(0,nrows,32):
   x,e,h=[mx.array(a[i:i+32]) for a in data[:3]];score=np.array(router(predict(m,x,e,h,mx.array(data[7][i:i+32]))));ix=np.argsort(score,axis=-1)[...,-6:][...,::-1];candidate=(np.take_along_axis(data[5][i:i+32],ix,axis=-1)==0).reshape(len(x),-1);correct=np.take_along_axis(data[4][i:i+32],ix,axis=-1).astype(bool).reshape(len(x),-1);take=candidate&(np.cumsum(candidate,axis=-1)<=64);reads+=int(take.sum());useful+=int((take&correct).sum())
  return dict(coverage=useful/misses,useful_per_token=useful/nrows,reads_per_token=reads/nrows,precision=useful/max(reads,1),wasted_MB_per_token=(reads-useful)*18.800640/nrows,rows=nrows)
 mx.random.seed(43);rng=np.random.default_rng(43);m=(RoutedCorrection if args.route_features else PerLayerCorrection)(40-d,args.per_layer_rank) if args.per_layer_rank else Correction(40-d)
 if args.route_features:assert args.per_layer_rank>0
 if args.warm_start:m.load_weights(str(args.warm_start),strict=False)
 if args.route_only:
  assert args.route_features and args.warm_start
  m.freeze();m.unfreeze(keys=['experts'])
 initial=evaluate(m,va);best=initial['coverage'];best_ev=initial;best_epoch=0;stale=0;history=[dict(epoch=0,validation=initial)];opt=optim.AdamW(learning_rate=args.learning_rate,weight_decay=.01);vg=nn.value_and_grad(m,loss);m.save_weights(str(args.output/'model.safetensors'))
 manifest=dict(distance=d,loss=args.loss,route_only=args.route_only,learning_rate=args.learning_rate,route_features=args.route_features,warm_start=str(args.warm_start) if args.warm_start else None,per_layer_rank=args.per_layer_rank,train_sequences=trids,validation_sequences=vaids,train_rows=len(tr[0]),validation_rows=len(va[0]),causality='source layer current FFN input + current token embedding + previous final state; target future FFN only enters loss',selection='validation sequential Top6 proposals filtered by cache, capped64/token; all40 miss denominator',test_opened=False,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest());(args.output/'manifest.json').write_text(json.dumps(manifest,indent=2));(args.output/'training-source.py').write_bytes(Path(__file__).read_bytes());print(json.dumps(dict(epoch=0,validation=initial)),flush=True)
 for epoch in range(30):
  ix=rng.permutation(len(tr[0]));total=0
  for i in range(0,len(ix),32):
   j=ix[i:i+32];v,g=vg(m,*[mx.array(a[j]) for a in tr]);opt.update(m,g);mx.eval(m.parameters(),opt.state,v);total+=v.item()*len(j)
  ev=evaluate(m,va);history.append(dict(epoch=epoch+1,train_loss=total/len(ix),validation=ev));score=ev['coverage']
  if score>best:best=score;best_ev=ev;best_epoch=epoch+1;stale=0;m.save_weights(str(args.output/'model.safetensors'))
  else:stale+=1
  (args.output/'history.json').write_text(json.dumps(history,indent=2));print(json.dumps(dict(epoch=epoch+1,validation=ev)),flush=True)
  if stale>=5:break
 (args.output/'result.json').write_text(json.dumps(dict(best_epoch=best_epoch,validation=best_ev,baseline=initial,**manifest),indent=2))
if __name__=='__main__':main()
