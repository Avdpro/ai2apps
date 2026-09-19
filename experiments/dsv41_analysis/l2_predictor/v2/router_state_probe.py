"""Causal state regression with the frozen official Router; validation only."""
import argparse,hashlib,json,sys,time
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
sys.path.insert(0,str(Path('experiments/dsv41_mlx').resolve()))
from storage import Storage
ROOT=Path('artifacts/dsv41-l2-state-v3-20260916')

class State(nn.Module):
 def __init__(self,rank):
  super().__init__();self.global_in=nn.Linear(10240,rank);self.local_in=nn.Linear(5120,rank,bias=False);self.out=nn.Linear(rank,5120);self.out.weight=mx.zeros_like(self.out.weight);self.out.bias=mx.zeros_like(self.out.bias);self.layer=mx.zeros((40,rank));self.log_scale=mx.full((40,),2.);self.offset=mx.full((40,),-3.)
 def __call__(self,old,hidden,embedding):
  def norm(x):return x*mx.rsqrt(mx.mean(x*x,axis=-1,keepdims=True)+1e-6)
  h=self.local_in(norm(old))+self.global_in(mx.concatenate([norm(hidden),norm(embedding)],axis=-1))[:,None]+self.layer
  return old+self.out(nn.gelu(h))*mx.sqrt(mx.mean(old*old,axis=-1,keepdims=True)+1e-6)

def load(split,limit):
 plan=json.loads((ROOT/'plan.json').read_text());parts=[];ids=[]
 for row in plan['samples']:
  if row['split']!=split:continue
  d=ROOT/'data'/row['id']
  if not (d/'verified.json').exists():continue
  with np.load(d/'supervision.npz') as z:
   if len(z['hidden'])<2:continue
   target=np.zeros(z['resident'][:-1].shape,np.float32);np.put_along_axis(target,z['top6'][:-1].astype(int),1,axis=-1)
   # Current FFN is a training target only: the NEXT row's previous FFN.
   parts.append((z['previous_ffn'][:-1].copy(),z['hidden'][:-1].copy(),z['embedding'][:-1].copy(),z['resident'][:-1].copy(),target,z['previous_ffn'][1:].copy(),z['router_rank'][:-1].copy()));ids.append(row['id'])
  if len(ids)>=limit:break
 assert parts
 return tuple(np.concatenate([p[i] for p in parts]) for i in range(7)),ids

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--sequences',type=int,default=12);ap.add_argument('--epochs',type=int,default=25);args=ap.parse_args();args.output.mkdir(exist_ok=False,parents=True)
 tr,trids=load('train',args.sequences);va,vaids=load('validation',args.sequences)
 checkpoint=Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD');s=Storage(checkpoint)
 weights=mx.stack([s.weight(f'layers.{l}.ffn.gate.weight',mx.float32) for l in range(40)]).transpose(0,2,1);bias=mx.stack([s.weight(f'layers.{l}.ffn.gate.bias',mx.float32) for l in range(40)]);mx.eval(weights,bias);fingerprint=s.source_index_sha256;s.close()
 def router(x):
  raw=mx.matmul(x.transpose(1,0,2),weights).transpose(1,0,2)
  return mx.sqrt(mx.logaddexp(raw,0))+bias
 # Confirm row alignment with stored Router scores before any fitting.
 exact=router(mx.array(tr[5][:1]));difference=float(mx.max(mx.abs(exact-mx.array(tr[6][:1]))).item());assert difference<1e-3,difference
 def logits(m,pred):
  rank=router(pred);return (rank-mx.mean(rank,axis=-1,keepdims=True))*mx.exp(mx.clip(m.log_scale,-2,5))[None,:,None]+m.offset[None,:,None]
 def loss(m,old,h,e,r,t,current,unused_rank):
  pred=m(old,h,e);z=logits(m,pred);weight=(1+3*(r==0))*(1+15*t)
  route=mx.mean((mx.logaddexp(z,0)-t*z)*weight)
  regression=mx.mean(mx.mean((pred-current)**2,axis=-1)/(mx.mean(current**2,axis=-1)+1e-6))
  return route+.2*regression
 def evaluate(m,data):
  hits={k:0 for k in [48,64,96]};misses=0;total=0
  for i in range(0,len(data[0]),32):
   a=[mx.array(x[i:i+32]) for x in data];pred=m(*a[:3]);z=logits(m,pred);v=loss(m,*a);mx.eval(z,v);n=len(a[0]);total+=v.item()*n
   eligible=data[3][i:i+32]==0;truth=data[4][i:i+32].astype(bool)&eligible;misses+=truth.sum();score=np.where(eligible,np.array(z),-np.inf).reshape(n,-1);ix=np.argsort(score,axis=-1)[:,-96:][:,::-1];correct=np.take_along_axis(truth.reshape(n,-1),ix,axis=-1)
   for k in hits:hits[k]+=int(correct[:,:k].sum())
  return dict(loss=total/len(data[0]),budgets={k:dict(coverage=v/int(misses),precision=v/(len(data[0])*k),useful_per_token=v/len(data[0])) for k,v in hits.items()})
 mx.random.seed(19);rng=np.random.default_rng(19);m=State(128);opt=optim.AdamW(learning_rate=2e-4,weight_decay=.01);vg=nn.value_and_grad(m,loss);hist=[];best=-1;stale=0
 manifest=dict(train_sequences=trids,validation_sequences=vaids,train_rows=len(tr[0]),validation_rows=len(va[0]),checkpoint=fingerprint,alignment_max_abs=difference,causality='current FFN only in loss; model inputs previous FFN, previous final hidden, actual input embedding',test_opened=False,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest());(args.output/'manifest.json').write_text(json.dumps(manifest,indent=2))
 for epoch in range(args.epochs):
  ix=rng.permutation(len(tr[0]));train_loss=0
  for i in range(0,len(ix),32):
   j=ix[i:i+32];v,g=vg(m,*[mx.array(x[j]) for x in tr]);opt.update(m,g);mx.eval(m.parameters(),opt.state,v);train_loss+=v.item()*len(j)
  ev=evaluate(m,va);score=ev['budgets'][64]['coverage'];row=dict(epoch=epoch+1,train_loss=train_loss/len(ix),validation=ev);hist.append(row)
  if score>best:best=score;best_ev=ev;best_epoch=epoch+1;stale=0;m.save_weights(str(args.output/'model.safetensors'))
  else:stale+=1
  (args.output/'history.json').write_text(json.dumps(hist,indent=2));print(json.dumps(dict(epoch=epoch+1,coverage48=ev['budgets'][48]['coverage'],coverage64=score)),flush=True)
  if stale>=5:break
 (args.output/'result.json').write_text(json.dumps(dict(best_epoch=best_epoch,validation=best_ev,**manifest),indent=2))
if __name__=='__main__':main()
