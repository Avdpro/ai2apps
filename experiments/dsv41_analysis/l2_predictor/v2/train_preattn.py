"""Train pre-attention Router state corrections; does not validate I/O timing."""
import argparse,json,hashlib,sys
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from train_router_lookahead import Correction
sys.path.insert(0,str(Path('experiments/dsv41_mlx').resolve()))
from storage import Storage
ROOT=Path('artifacts/dsv41-l2-preattn-v4-20260916')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();args.output.mkdir(exist_ok=False,parents=True);plan=json.loads((ROOT/'plan.json').read_text())
 def load(split):
  parts=[];names=[]
  for row in plan['samples']:
   if row['split']!=split:continue
   p=ROOT/'data'/row['id']
   if not (p/'verified.json').exists():continue
   with np.load(p/'supervision.npz') as z:
    r=z['resident'].copy();t=np.zeros(r.shape,np.float32);np.put_along_axis(t,z['top6'].astype(int),1,axis=-1);parts.append((z['preattn'].copy(),z['embedding'].copy(),z['hidden'].copy(),z['actual_ffn'].copy(),t,r));names.append(row['id'])
  return tuple(np.concatenate([p[i] for p in parts]) for i in range(6)),names
 tr,trids=load('train');va,vaids=load('validation');mean=np.mean(tr[3]-tr[0],axis=0);mx.save_safetensors(str(args.output/'mean.safetensors'),{'mean':mx.array(mean)});tr=(tr[0]+mean,*tr[1:]);va=(va[0]+mean,*va[1:])
 s=Storage('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD');w=mx.stack([s.weight(f'layers.{l}.ffn.gate.weight',mx.float32) for l in range(40)]).transpose(0,2,1);bias=mx.stack([s.weight(f'layers.{l}.ffn.gate.bias',mx.float32) for l in range(40)]);mx.eval(w,bias);s.close()
 def rank(x):return mx.sqrt(mx.maximum(mx.logaddexp(mx.matmul(x.transpose(1,0,2),w).transpose(1,0,2),0),1e-20))+bias
 def loss(m,x,e,h,target,t,r):
  pred=m(x,e,h,1.);score=rank(pred);z=(score-mx.mean(score,axis=-1,keepdims=True))*mx.exp(mx.clip(m.log_scale,-2,5))[None,:,None]+m.offset[None,:,None];weight=(1+3*(r==0))*(1+15*t);return mx.mean((mx.logaddexp(z,0)-t*z)*weight)+.2*mx.mean(mx.mean((pred-target)**2,axis=-1)/(mx.mean(target**2,axis=-1)+1e-6))
 def proposals(m,data):
  result=[]
  for i in range(0,len(data[0]),32):
   x,e,h=[mx.array(a[i:i+32]) for a in data[:3]];score=np.array(rank(m(x,e,h,1.)));ix=np.argsort(score,axis=-1)[...,-8:][...,::-1];ordered=np.take_along_axis(score,ix,axis=-1);eligible=np.take_along_axis(data[5][i:i+32],ix,axis=-1)==0;correct=np.take_along_axis(data[4][i:i+32],ix,axis=-1).astype(bool);result.append((ordered,eligible,correct))
  return tuple(np.concatenate([r[i] for r in result]) for i in range(3))
 def evaluate(m,data):
  training=proposals(m,tr);mean_reads=training[1][...,:6].sum(-1).mean(0);reserve=np.cumsum(mean_reads[::-1])[::-1]-mean_reads
  scores,eligible,correct=proposals(m,data);n=len(scores);misses=int((data[4].astype(bool)&(data[5]==0)).sum());policies={}
  for margin in [None,.025,.05,.1]:
   spent=np.zeros(n,int);useful=np.zeros(n,int)
   for layer in range(40):
    for k in range(6 if margin is None else 8):
     take=eligible[:,layer,k]&(spent<64)
     if k>=6:take&=(scores[:,layer,k]>=scores[:,layer,5]-margin)&(64-spent>reserve[layer])
     useful+=take&correct[:,layer,k];spent+=take
   policies[str(margin)]=dict(coverage=int(useful.sum())/misses,useful_per_token=float(useful.mean()),reads_per_token=float(spent.mean()),precision=int(useful.sum())/max(1,int(spent.sum())),wasted_MB_per_token=float((spent-useful).mean())*18.800640,rows=n)
  chosen=max(policies,key=lambda k:policies[k]['coverage'])
  return dict(**policies[chosen],selected_policy=chosen,policies=policies,training_future_reserve=reserve.tolist())
 mx.random.seed(47);rng=np.random.default_rng(47);m=Correction(40);initial=evaluate(m,va);best=initial['coverage'];best_ev=initial;best_epoch=0;stale=0;hist=[dict(epoch=0,validation=initial)];m.save_weights(str(args.output/'model.safetensors'));opt=optim.AdamW(learning_rate=1e-4,weight_decay=.01);vg=nn.value_and_grad(m,loss)
 manifest=dict(train_sequences=trids,validation_sequences=vaids,train_rows=len(tr[0]),validation_rows=len(va[0]),causality='Only residual estimate before attention, input token embedding and previous final state; actual FFN target never input',deployment_unverified='Requires asynchronous prediction-to-SSD handoff before attention without new blocking GPU readback; not implemented',test_opened=False);(args.output/'manifest.json').write_text(json.dumps(manifest,indent=2));(args.output/'training-source.py').write_bytes(Path(__file__).read_bytes());print(json.dumps(dict(epoch=0,coverage=initial['coverage'],reads=initial['reads_per_token'],policy=initial['selected_policy'])),flush=True)
 for epoch in range(30):
  ix=rng.permutation(len(tr[0]));total=0
  for i in range(0,len(ix),32):
   j=ix[i:i+32];v,g=vg(m,*[mx.array(a[j]) for a in tr]);opt.update(m,g);mx.eval(m.parameters(),opt.state,v);total+=v.item()*len(j)
  ev=evaluate(m,va);score=ev['coverage'];hist.append(dict(epoch=epoch+1,train_loss=total/len(ix),validation=ev))
  if score>best:best=score;best_ev=ev;best_epoch=epoch+1;stale=0;m.save_weights(str(args.output/'model.safetensors'))
  else:stale+=1
  (args.output/'history.json').write_text(json.dumps(hist,indent=2));print(json.dumps(dict(epoch=epoch+1,coverage=ev['coverage'],reads=ev['reads_per_token'],policy=ev['selected_policy'])),flush=True)
  if stale>=5:break
 (args.output/'result.json').write_text(json.dumps(dict(best_epoch=best_epoch,validation=best_ev,baseline=initial,**manifest),indent=2))
if __name__=='__main__':main()
