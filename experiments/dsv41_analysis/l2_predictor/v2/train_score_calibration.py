"""Fit small prediction-score corrections only; never changes the actual model router."""
import argparse,json,sys
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
sys.path.insert(0,str(Path('experiments/dsv41_mlx').resolve()))
from storage import Storage
ROOT=Path('artifacts/dsv41-l2-preattn-v4-20260916')
class Calibration(nn.Module):
 def __init__(self):super().__init__();self.delta=mx.zeros((40,384))
 def __call__(self,x):return x+self.delta

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();args.output.mkdir(exist_ok=False,parents=True);plan=json.loads((ROOT/'plan.json').read_text());rows=[r for r in plan['samples'] if (ROOT/'data'/r['id']/'verified.json').exists()];train=[r for r in rows if r['split']=='train'];val=[r for r in rows if r['split']=='validation'];(args.output/'cohort.json').write_text(json.dumps(dict(samples=rows),indent=2))
 mean=np.zeros((40,5120),np.float64);count=0
 for row in train:
  with np.load(ROOT/'data'/row['id']/'supervision.npz') as z:mean+=(z['actual_ffn']-z['preattn']).sum(0);count+=len(z['hidden'])
 mean=mx.array((mean/count).astype(np.float32));mx.save_safetensors(str(args.output/'mean.safetensors'),{'mean':mean})
 s=Storage('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD');w=mx.stack([s.weight(f'layers.{l}.ffn.gate.weight',mx.float32) for l in range(40)]).transpose(0,2,1);b=mx.stack([s.weight(f'layers.{l}.ffn.gate.bias',mx.float32) for l in range(40)]);mx.eval(w,b);s.close()
 def load(selected):
  all_scores=[];labels=[];residents=[];target_scores=[]
  for row in selected:
   with np.load(ROOT/'data'/row['id']/'supervision.npz') as z:
    x=z['preattn'];parts=[]
    for i in range(0,len(x),32):
     raw=mx.matmul((mx.array(x[i:i+32])+mean).transpose(1,0,2),w).transpose(1,0,2);parts.append(np.array(mx.sqrt(mx.maximum(mx.logaddexp(raw,0),1e-20))+b))
    all_scores.append(np.concatenate(parts));labels.append(z['top6'].astype(np.int32));residents.append(z['resident'].copy());target_scores.append(z['router_rank'].copy())
  return tuple(np.concatenate(x) for x in [all_scores,labels,residents,target_scores])
 tr=load(train);va=load(val)
 def loss(m,x,y,r):
  z=m(x)/.1;selected=mx.take_along_axis(z,y,axis=-1);full=mx.mean(mx.logsumexp(z,axis=-1)-mx.mean(selected,axis=-1));eligible=r==0;required=mx.take_along_axis(eligible,y,axis=-1).astype(mx.float32);n=mx.sum(required,axis=-1);cold=mx.logsumexp(mx.where(eligible,z,-1e9),axis=-1)-mx.sum(selected*required,axis=-1)/mx.maximum(n,1);cold=mx.sum(mx.where(n>0,cold,0))/mx.maximum(mx.sum(n>0),1);return .5*full+.5*cold+20*mx.mean(m.delta*m.delta)
 def evaluate(m,data):
  useful=0;reads=0;miss=0;n=len(data[0])
  for i in range(0,n,64):
   scores=np.array(m(mx.array(data[0][i:i+64])));ix=np.argsort(scores,axis=-1)[...,-6:][...,::-1];r=data[2][i:i+64];t=np.zeros(r.shape,bool);np.put_along_axis(t,data[1][i:i+64],True,axis=-1);miss+=int((t&(r==0)).sum());candidate=(np.take_along_axis(r,ix,axis=-1)==0).reshape(len(scores),-1);correct=np.take_along_axis(t,ix,axis=-1).reshape(len(scores),-1);take=candidate&(np.cumsum(candidate,axis=-1)<=64);useful+=int((take&correct).sum());reads+=int(take.sum())
  return dict(coverage=useful/miss,reads_per_token=reads/n,useful_per_token=useful/n,precision=useful/max(reads,1),wasted_MB_per_token=(reads-useful)*18.800640/n,rows=n)
 m=Calibration();initial=evaluate(m,va);best=initial['coverage'];best_ev=initial;best_epoch=0;m.save_weights(str(args.output/'calibration.safetensors'));opt=optim.AdamW(learning_rate=.002,weight_decay=.01);vg=nn.value_and_grad(m,loss);rng=np.random.default_rng(53);hist=[dict(epoch=0,validation=initial)];stale=0
 manifest=dict(train_sequences=[r['id'] for r in train],validation_sequences=[r['id'] for r in val],train_rows=len(tr[0]),validation_rows=len(va[0]),parameters=15360,test_opened=False,scope='Prediction-only score bias. Real main-model Router unchanged. Pre-attention deployment still unverified.');(args.output/'manifest.json').write_text(json.dumps(manifest,indent=2));(args.output/'training-source.py').write_bytes(Path(__file__).read_bytes());print(json.dumps(dict(epoch=0,validation=initial)),flush=True)
 for epoch in range(30):
  order=rng.permutation(len(tr[0]))
  for i in range(0,len(order),64):
   ix=order[i:i+64];v,g=vg(m,*[mx.array(a[ix]) for a in tr[:3]]);opt.update(m,g);mx.eval(m.parameters(),opt.state,v)
  ev=evaluate(m,va);hist.append(dict(epoch=epoch+1,validation=ev));score=ev['coverage']
  if score>best:best=score;best_ev=ev;best_epoch=epoch+1;stale=0;m.save_weights(str(args.output/'calibration.safetensors'))
  else:stale+=1
  (args.output/'history.json').write_text(json.dumps(hist,indent=2));print(json.dumps(dict(epoch=epoch+1,validation=ev)),flush=True)
  if stale>=5:break
 (args.output/'result.json').write_text(json.dumps(dict(best_epoch=best_epoch,baseline=initial,validation=best_ev,**manifest),indent=2))
if __name__=='__main__':main()
