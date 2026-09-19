"""Diagnostic only: projection time with packed weights already resident, no SSD/packing."""
import sys,time,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dsv41_mlx'))
import mlx.core as mx
from model import LRUMetalBank
from expert_dispatch import Dispatch
from kernels import quant
bank=LRUMetalBank('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/experts/layer-0.bin',list(range(8)),l0_slots=0)
a=bank.arrays;w=mx.concatenate([a[0],a[4]],axis=1);s=mx.concatenate([a[1],a[5]],axis=1);mx.eval(w,s)
reports=[]
for n in [16,128,256]:
 segments=[(i,n) for i in range(8)];slots=mx.array([i for i in range(8) for _ in range(n)],dtype=mx.int32)
 mx.random.seed(28);z=quant(mx.random.normal((8*n,5120)).astype(mx.bfloat16)).astype(mx.bfloat16);mx.eval(z)
 plan=Dispatch(slots,segments,True)
 def separate():return mx.concatenate([plan.project(z,a[0],a[1]),plan.project(z,a[4],a[5])],axis=-1)
 def fused():return plan.project(z,w,s)
 x=separate();y=fused();mx.eval(x,y);diff=float(mx.max(mx.abs(x.astype(mx.float32)-y.astype(mx.float32))).item());assert diff==0
 samples={'separate':[],'fused':[]}
 for rep in range(12):
  for name,fn in ([('separate',separate),('fused',fused)] if rep%2==0 else [('fused',fused),('separate',separate)]):
   t=time.perf_counter();result=fn();mx.eval(result)
   if rep>=2:samples[name].append(time.perf_counter()-t)
 row=dict(rows_per_expert=n,max_abs=diff,seconds={k:sum(v)/len(v) for k,v in samples.items()},samples=samples);reports.append(row);print(json.dumps({k:v for k,v in row.items() if k!='samples'}),flush=True)
bank.close();Path('artifacts/dsv41-fused-projection-diagnostic-20260913.json').write_text(json.dumps(reports,indent=2))
