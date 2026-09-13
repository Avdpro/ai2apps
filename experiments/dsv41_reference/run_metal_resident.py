#!/usr/bin/env python3
"""Bounded ordinary-weight and immutable final-projection residency plus profiling."""
import hashlib,json,sys,time,types
from collections import defaultdict
from pathlib import Path
import torch
import cpu_kernel
import metal_dense
import run_reference
import run_metal_moe
from cached_store import CachedStore
from resident_projection import ProjectionCache

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1])
    stores=[]; packed=ProjectionCache(); profile=defaultdict(lambda:dict(calls=0,inclusive_seconds=0.,exclusive_seconds=0.))
    stack=[];steps=[];trace_stats=dict(calls=0,seconds=0.)
    def store(root):
        result=CachedStore(root,experts_per_layer=0,dense_bytes=12*2**30,row_bytes=8*2**20)
        stores.append(result);return result
    run_reference.Store=store
    cpu_kernel.fp8_gemm=metal_dense.fp8_gemm
    sys.modules['kernel']=cpu_kernel
    sys.path.insert(0,str(Path('artifacts/dsv41-download/DeepSeek-V4.1-Flash/inference').resolve()))
    import model
    original_init=model.Block.__init__
    def init(self,*args,**kwargs):
        original_init(self,*args,**kwargs)
        for label,projection in [('wo_b',self.attn.wo_b),('shared_w2',self.ffn.shared_experts.w2)]:
            key=(self.layer_id,label)
            def forward(module,x,_key=key):
                qa,sa=cpu_kernel.act_quant(x,32,'ue8m0',torch.float8_e8m0fnu)
                return packed.gemm(_key,qa,sa,module.weight,module.scale)
            projection.forward=types.MethodType(forward,projection)
    model.Block.__init__=init
    original_call=torch.nn.Module._call_impl
    original_save=torch.save
    def call(module,*args,**kwargs):
        start=time.perf_counter();frame=[0.];stack.append(frame)
        try:return original_call(module,*args,**kwargs)
        finally:
            elapsed=time.perf_counter()-start;stack.pop()
            if stack:stack[-1][0]+=elapsed
            label=type(module).__name__;row=profile[label]
            row['calls']+=1;row['inclusive_seconds']+=elapsed;row['exclusive_seconds']+=elapsed-frame[0]
            if isinstance(module,model.Transformer):steps.append(elapsed)
    def save(*args,**kwargs):
        start=time.perf_counter()
        try:return original_save(*args,**kwargs)
        finally:trace_stats['calls']+=1;trace_stats['seconds']+=time.perf_counter()-start
    torch.nn.Module._call_impl=call;torch.save=save
    try:run_metal_moe.main()
    finally:
        torch.nn.Module._call_impl=original_call;torch.save=original_save
        manifest=output/'manifest.json'
        if manifest.exists():
            r=json.loads(manifest.read_text())
            r['metal_dense']={'scope':'inner Metal FP8, cached CPU final projections','statistics':metal_dense.stats,
                'sources':{str(Path(metal_dense.__file__)):hashlib.sha256(Path(metal_dense.__file__).read_bytes()).hexdigest()}}
            r['resident_optimization']={'stores':[s.summary() for s in stores],
                'packed':dict(packed.stats,limit_bytes=packed.limit_bytes),'module_profile':dict(profile),
                'model_call_seconds':steps,'trace_save':trace_stats,
                'timing_note':'module times include hooks and nested trace; exclusive excludes child module calls; save includes serialization only, not trace preparation',
                'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('resident_projection.py'),Path(__file__).with_name('cached_store.py')]}}
            manifest.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
