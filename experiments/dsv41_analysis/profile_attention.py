"""Nested synchronized attention/indexer attribution for Prefill and Decode.

Diagnostic timings change evaluation boundaries and must not be treated as TPS.
"""
import sys,time,json,functools
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dsv41_mlx'))
import mlx.core as mx
import run,model,kernels
active=False;phase='';stack=[];rows={}
def arrays(v):
 if isinstance(v,mx.array):return [v]
 if isinstance(v,(tuple,list)):return [a for x in v for a in arrays(x)]
 if isinstance(v,dict):return [a for x in v.values() for a in arrays(x)]
 return []
def wrapper(fn,label):
 @functools.wraps(fn)
 def call(*a,**kw):
  if not active:return fn(*a,**kw)
  mx.eval(*arrays(a),*arrays(kw));mx.synchronize()
  stack.append([0.]);t=time.perf_counter()
  try:
   y=fn(*a,**kw);mx.eval(*arrays(y));return y
  finally:
   dt=time.perf_counter()-t;child=stack.pop()[0]
   if stack:stack[-1][0]+=dt
   r=rows.setdefault(phase+':'+label,dict(calls=0,inclusive=0.,exclusive=0.));r['calls']+=1;r['inclusive']+=dt;r['exclusive']+=dt-child
 return call
for n in ['attention','index','compress','linear','moe']:
 setattr(model.Model,n,wrapper(getattr(model.Model,n),n))
for n in ['index_scores','index_topk','sparse']:
 setattr(model,n,wrapper(getattr(model,n),n))
for n in ['sparse_gather','sparse_sdpa']:
 setattr(kernels,n,wrapper(getattr(kernels,n),n))
original=model.Model.__call__
def forward(self,ids,start=0):
 global active,phase
 active=True;phase='prefill' if start==0 else 'decode'
 try:return wrapper(original,'forward')(self,ids,start)
 finally:active=False
model.Model.__call__=forward
run.main()
out=Path(sys.argv[sys.argv.index('--output')+1]);(out/'attention-profile.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows),flush=True)
