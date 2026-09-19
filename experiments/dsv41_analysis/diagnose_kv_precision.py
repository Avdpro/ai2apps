"""Locate replay/incremental divergence and isolate same-input batch/row linear arithmetic."""
import sys,json,gc,argparse
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dsv41_mlx'))
import mlx.core as mx
from tokenizers import Tokenizer
from storage import Storage
from adaptive import AdaptiveModel
from run import Budget
ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
out=Path(args.out);out.mkdir(exist_ok=False)
root=Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD');base=Path('artifacts/dsv41-multiturn-20260913')
ids=json.load(open(base/'text-3/manifest.json'))['input_ids'];prefix=json.load(open(base/'text-1/manifest.json'))['input_ids'];assert ids[:len(prefix)]==prefix
config=json.load(open(root/'inference/config.json'));config.update(dspark_block_size=0,max_batch_size=1,max_seq_len=256,temperature=0,vision_n_layers=0)
tok=Tokenizer.from_file(str(root/'tokenizer.json'));mx.set_cache_limit(2*2**30);mx.set_memory_limit(60_000_000_000)
def arr(x):return np.array(x.astype(mx.float32))
def diff(a,b):
 a=a.astype(np.float64);b=b.astype(np.float64);d=a-b
 return dict(max_abs=float(abs(d).max()),rmse=float(np.sqrt(np.mean(d*d))),unequal=int(np.count_nonzero(d)),size=d.size)
refs={};isolated=[];comparison=[]
for mode in ['replay','incremental']:
 budget=Budget();s=Storage(root);model=AdaptiveModel(config,s,tok,Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/experts'),256,40,prefill_slots=64)
 active=False
 def capture(name,x):
  if not active:return
  if name.endswith('.gate'):x=x[-1:]
  elif x.ndim>=3:x=x[:,-1:]
  a=arr(x)
  if mode=='replay':refs[name]=a
  else:comparison.append(dict(name=name,**diff(refs[name],a)))
 original=model.linear
 def linear(name,x,force_f32=False):
  y=original(name,x,force_f32)
  if active:
   capture(name+'.input',x);capture(name+'.output',y)
   if mode=='replay' and x.ndim==3 and x.shape[1]>1:
    single=original(name,x[:,-1:],force_f32);isolated.append(dict(name=name,dtype=s.entries[name+'.weight'][2]['dtype'],**diff(arr(y[:,-1:]),arr(single))))
  return y
 model.linear=linear;model.trace=capture
 try:
  if mode=='replay':active=True;y=model(mx.array([ids],dtype=mx.int32),0);mx.eval(y)
  else:
   y=model(mx.array([prefix],dtype=mx.int32),0);mx.eval(y);model.prefill_executor.release()
   for pos in range(len(prefix),len(ids)):
    active=pos==len(ids)-1;y=model(mx.array([[ids[pos]]],dtype=mx.int32),pos);mx.eval(y);budget.check()
    if pos%10==0:print(json.dumps(dict(mode=mode,pos=pos)),flush=True)
  capture('logits',y)
  np.savez(out/f'{mode}.npz',**(refs if mode=='replay' else {'logits':arr(y)}))
 finally:model.close();budget.close()
 print(json.dumps(dict(mode=mode,peak_bytes=budget.peak)),flush=True)
 del model,s,original;gc.collect();mx.clear_cache()
(out/'report.json').write_text(json.dumps(dict(prefix_tokens=len(prefix),total_tokens=len(ids),isolated_same_input=isolated,replay_vs_incremental=comparison),indent=2))
print(json.dumps(dict(first_differences=[r for r in comparison if r['unequal']][:15],isolated_nonzero=[r for r in isolated if r['unequal']][:15])),flush=True)
