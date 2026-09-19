"""Synchronized, nested Prefill attribution. Diagnostic timings are not throughput gates."""
import sys,time,json,functools,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dsv41_mlx'))
import mlx.core as mx
import run
from model import Model
from storage import Storage
from prefill import Prefill
from metal_bank import MetalBank
active=False;stack=[];rows={}
def arrays(value):
    if isinstance(value,mx.array):return [value]
    if isinstance(value,(list,tuple)):return [a for v in value for a in arrays(v)]
    if isinstance(value,dict):return [a for v in value.values() for a in arrays(v)]
    return []
def wrap(cls,name,label=None):
    original=getattr(cls,name);label=label or name
    @functools.wraps(original)
    def measured(self,*args,**kwargs):
        if not active:return original(self,*args,**kwargs)
        # Pending input evaluation is charged to the parent, before child timing.
        mx.eval(*arrays(args),*arrays(kwargs));mx.synchronize()
        layer=stack[-1]['layer'] if stack else -1
        if name in ('engram','attention','moe') and args:layer=int(args[0])
        node=dict(layer=layer,children=0.);stack.append(node);t=time.perf_counter()
        try:
            result=original(self,*args,**kwargs);mx.eval(*arrays(result));return result
        finally:
            elapsed=time.perf_counter()-t;stack.pop()
            if stack:stack[-1]['children']+=elapsed
            key=f'{layer}:{label}';r=rows.setdefault(key,dict(layer=layer,operation=label,calls=0,inclusive_seconds=0.,exclusive_seconds=0.))
            r['calls']+=1;r['inclusive_seconds']+=elapsed;r['exclusive_seconds']+=elapsed-node['children']
    setattr(cls,name,measured)
for name in ['engram','attention','moe','shared_expert','expert','expert_linear','linear','hc_pre','hc_post','hc_mixes','norm','compress','index']:
    wrap(Model,name)
wrap(Storage,'embedding','embedding_rows')
for name in ['raw','weight','fp8','grouped']:wrap(Storage,name,'storage_'+name)
wrap(Prefill,'dispatch','prefill_dispatch');wrap(MetalBank,'_load','bank_load_and_fence')
original=Model.__call__
def forward(self,ids,start=0):
    global active
    if start:return original(self,ids,start)
    active=True;stack.append(dict(layer=-1,children=0.));t=time.perf_counter()
    try:
        y=original(self,ids,start);mx.eval(y);return y
    finally:
        elapsed=time.perf_counter()-t;node=stack.pop();active=False
        rows['-1:forward']=dict(layer=-1,operation='forward',calls=1,inclusive_seconds=elapsed,exclusive_seconds=elapsed-node['children'])
Model.__call__=forward
run.main()
out=Path(sys.argv[sys.argv.index('--output')+1]);m=json.loads((out/'manifest.json').read_text())
summary={}
for r in rows.values():
    s=summary.setdefault(r['operation'],dict(calls=0,inclusive_seconds=0.,exclusive_seconds=0.))
    for key in s:s[key]+=r[key]
report=dict(profiler_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),mode='synchronized nested Prefill attribution; no timing comparison with unprofiled TPS',status=m['status'],operations=summary,layers=list(rows.values()),prefill_wall_seconds=m['step_seconds'][0],native_expert_io_seconds=m.get('expert_total_io_seconds'),note='Exclusive times are disjoint; inclusive parents contain children. Input materialization is charged to parent. Synchronization removes normal overlap; SSD counters are logical API reads, not physical cold reads.')
(out/'profile.json').write_text(json.dumps(report,indent=2));print(json.dumps(summary),flush=True)
