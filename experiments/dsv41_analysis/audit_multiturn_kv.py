"""Numerical audit: append-only single-token KV reuse against fresh full replay.
New images start a new segment; this does not claim incremental image prefill.
"""
import argparse,sys,json,time,hashlib
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from safetensors.numpy import load_file
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dsv41_mlx'))
import mlx.core as mx
from tokenizers import Tokenizer
from run import Budget
from storage import Storage
from adaptive import AdaptiveModel
from vision import Vision
from chat import prepare_chat
ap=argparse.ArgumentParser();ap.add_argument('--case',choices=['text','text-long','vision'],required=True);ap.add_argument('--first',type=int,required=True);ap.add_argument('--last',type=int,required=True);a=ap.parse_args()
base=Path('artifacts/dsv41-multiturn-20260913');out=base/f'kv-{a.case}-{a.first}-{a.last}';out.mkdir(exist_ok=False)
root=Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD');config=json.load(open(root/'inference/config.json'));config.update(dspark_block_size=0,max_batch_size=1,temperature=0,vision_max_n_token=256)
tokenizer=Tokenizer.from_file(str(root/'tokenizer.json'));turns=[]
for i in range(a.first,a.last+1):
 ref=base/f'{a.case}-{i}';m=json.load(open(ref/'manifest.json'));messages=json.load(open(base/f'{a.case}-{i}-messages.json'))
 _,ids,types,images,paths=prepare_chat(messages,root,tokenizer,SimpleNamespace(**config));assert ids==m['input_ids']
 turns.append((i,ref,m,ids,types,images))
config['max_seq_len']=max(256,max(len(t[3])+len(t[2]['generated_ids']) for t in turns)+1)
if a.case.startswith('text'):config['vision_n_layers']=0
budget=Budget();mx.set_cache_limit(2*2**30);mx.set_memory_limit(60_000_000_000)
s=Storage(root);model=AdaptiveModel(config,s,tokenizer,Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/experts'),config['max_seq_len'],40,prefill_slots=64)
if a.case=='vision':
 model.vision=Vision(s,model.c);model.vision.load();model.vision_images=turns[0][5];model.vision_types=mx.array([turns[0][4]],dtype=mx.int32)
consumed=[];results=[]
def compare(y,ref,m,step):
 path=ref/f'{step:02d}_logits.safetensors';assert hashlib.sha256(path.read_bytes()).hexdigest()==m['trace_files'][path.name]
 x=load_file(str(path))['logits'].astype(np.float64).reshape(-1);z=np.array(y.astype(mx.float32)).astype(np.float64).reshape(-1);assert np.isfinite(z).all()
 lx=x-x.max();lx-=np.log(np.exp(lx).sum());lz=z-z.max();lz-=np.log(np.exp(lz).sum())
 return dict(step=step,max_abs=float(abs(x-z).max()),kl=float(np.sum(np.exp(lx)*(lx-lz))),top1_equal=int(x.argmax())==int(z.argmax()))
try:
 for i,ref,m,ids,types,images in turns:
  started=time.perf_counter()
  if consumed:
   if ids[:len(consumed)]!=consumed:raise ValueError(f'turn {i}: canonical history is not append-only')
   # This segment may reuse old images but must never append a new image span.
   if any(t>=0 for t in types[len(consumed):]):raise ValueError('new image requires full replay fallback')
   appended=len(ids)-len(consumed)
   for token in ids[len(consumed):]:
    y=model(mx.array([[token]],dtype=mx.int32),len(consumed));mx.eval(y);consumed.append(token);budget.check()
  else:
   appended=len(ids);y=model(mx.array([ids],dtype=mx.int32),0);mx.eval(y);consumed=list(ids);model.prefill_executor.release();budget.check()
  checks=[compare(y,ref,m,0)]
  for step in range(1,min(8,len(m['generated_ids'])-1)+1):
   token=m['generated_ids'][step-1];y=model(mx.array([[token]],dtype=mx.int32),len(consumed));mx.eval(y);consumed.append(token);budget.check();checks.append(compare(y,ref,m,step))
  row=dict(turn=i,appended_tokens=appended,checks=checks,elapsed=time.perf_counter()-started);results.append(row);print(json.dumps(row),flush=True)
finally:
 model.close();budget.close();(out/'audit.json').write_text(json.dumps(dict(mode='teacher-forced append-only KV audit; fresh replay reference; new images require fallback',peak_bytes=budget.peak,turns=results),indent=2))
