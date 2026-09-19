"""Streaming ridge calibration of causal pre-attention estimates; validation only."""
import argparse,json,hashlib,sys
from pathlib import Path
import numpy as np
import mlx.core as mx
sys.path.insert(0,str(Path('experiments/dsv41_mlx').resolve()))
from storage import Storage
ROOT=Path('artifacts/dsv41-l2-preattn-v4-20260916')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();args.output.mkdir(exist_ok=False,parents=True)
 plan=json.loads((ROOT/'plan.json').read_text());rows=[r for r in plan['samples'] if (ROOT/'data'/r['id']/'verified.json').exists()];train=[r for r in rows if r['split']=='train'];val=[r for r in rows if r['split']=='validation'];assert train and val
 (args.output/'cohort.json').write_text(json.dumps(dict(samples=rows),indent=2));(args.output/'training-source.py').write_bytes(Path(__file__).read_bytes())
 s=Storage('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD');w=mx.stack([s.weight(f'layers.{l}.ffn.gate.weight',mx.float32) for l in range(40)]).transpose(0,2,1);bias=mx.stack([s.weight(f'layers.{l}.ffn.gate.bias',mx.float32) for l in range(40)]);norm=mx.stack([s.weight(f'layers.{l}.ffn_norm.weight',mx.float32) for l in range(40)]);mx.eval(w,bias,norm);s.close()
 moments={mode:{k:np.zeros((40,5120),np.float64) for k in ['x','delta','xx','xd','n']} for mode in ['uniform','miss_weighted']}
 for row in train:
  with np.load(ROOT/'data'/row['id']/'supervision.npz') as z:
   x=z['preattn'];y=z['actual_ffn'];miss=(np.take_along_axis(z['resident'],z['top6'].astype(int),axis=-1)==0).sum(-1)
   for i in range(0,len(x),32):
    xx=x[i:i+32].astype(np.float64);delta=y[i:i+32].astype(np.float64)-xx
    for mode,m in moments.items():
     weights=np.ones((len(xx),40,1)) if mode=='uniform' else (1+miss[i:i+32])[...,None]
     m['n']+=weights.sum(0);m['x']+=(xx*weights).sum(0);m['delta']+=(delta*weights).sum(0);m['xx']+=(xx*xx*weights).sum(0);m['xd']+=(xx*delta*weights).sum(0)
 def evaluate(a,b,renormalize):
  a=mx.array(a.astype(np.float32));b=mx.array(b.astype(np.float32));correct=0;reads=0;misses=0;count=0
  for row in val:
   with np.load(ROOT/'data'/row['id']/'supervision.npz') as z:
    x=z['preattn'];r=z['resident'];t=np.zeros(r.shape,bool);np.put_along_axis(t,z['top6'].astype(int),True,axis=-1);misses+=int((t&(r==0)).sum());count+=len(x)
    for i in range(0,len(x),32):
     pred=mx.array(x[i:i+32])*a+b
     if renormalize:
      unit=pred/mx.where(mx.abs(norm)>1e-6,norm,mx.ones_like(norm));pred=unit*mx.rsqrt(mx.mean(unit*unit,axis=-1,keepdims=True)+1e-6)*norm
     raw=mx.matmul(pred.transpose(1,0,2),w).transpose(1,0,2);score=np.array(mx.sqrt(mx.maximum(mx.logaddexp(raw,0),1e-20))+bias);ix=np.argsort(score,axis=-1)[...,-6:][...,::-1];eligible=(np.take_along_axis(r[i:i+32],ix,axis=-1)==0).reshape(len(pred),-1);good=np.take_along_axis(t[i:i+32],ix,axis=-1).reshape(len(pred),-1);take=eligible&(np.cumsum(eligible,axis=-1)<=64);correct+=int((take&good).sum());reads+=int(take.sum())
  return dict(coverage=correct/misses,precision=correct/max(reads,1),reads_per_token=reads/count,useful_per_token=correct/count,wasted_MB_per_token=(reads-correct)*18.800640/count,rows=count)
 results=[];best=-1
 # Include true zero-update and mean-only controls alongside regularized affine fits.
 candidates=[('identity',0.,np.ones((40,5120)),np.zeros((40,5120)))]
 for mode,m in moments.items():
  mean=m['x']/m['n'];delta=m['delta']/m['n'];variance=np.maximum(m['xx']/m['n']-mean*mean,1e-12);cov=m['xd']/m['n']-mean*delta
  candidates.append((mode+'-mean',0.,np.ones_like(mean),delta))
  for ridge in [.01,.1,1.,10.]:
   correction=cov/(variance+ridge*variance.mean(-1,keepdims=True));a=1+correction;b=delta-correction*mean;candidates.append((mode,ridge,a,b))
 for mode,ridge,a,b in candidates:
  for renorm in [False,True]:
   ev=evaluate(a,b,renorm);row=dict(mode=mode,ridge=ridge,renormalize=renorm,validation=ev);results.append(row)
   if ev['coverage']>best:
    best=ev['coverage'];best_row=row;mx.save_safetensors(str(args.output/'affine.safetensors'),{'scale':mx.array(a.astype(np.float32)),'bias':mx.array(b.astype(np.float32))})
   (args.output/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps(dict(mode=mode,ridge=ridge,renorm=renorm,coverage=ev['coverage'])),flush=True)
 manifest=dict(best=best_row,train_sequences=[r['id'] for r in train],validation_sequences=[r['id'] for r in val],test_opened=False,scope='cap64 chronological Top6 proposals; all40 miss denominator; same-layer attention lead, deployment unverified');(args.output/'result.json').write_text(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
