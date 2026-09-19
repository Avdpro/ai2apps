#!/usr/bin/env python3
"""Resident dense path with a 24-slot LRU working set per layer."""
import hashlib,json,sys,time
from pathlib import Path
import cpu_kernel
import metal_dense
import run_metal_moe
import run_metal_resident
from lru_metal_bank import LRUMetalBank

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1]);banks=[];steps=[]
    def bank(*args,**kwargs):
        b=LRUMetalBank(*args,**kwargs);banks.append(b);return b
    run_metal_moe.MetalBank=bank
    cpu_kernel.fp8_gemm=metal_dense.fp8_gemm
    sys.modules['kernel']=cpu_kernel
    sys.path.insert(0,str(Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/inference').resolve()))
    import model
    original_forward=model.Transformer.forward
    def snapshot():
        return {key:sum(getattr(b,key) for b in banks) for key in ['bytes','loads','io_seconds','hits','misses','evictions']}
    def forward(self,*args,**kwargs):
        before=snapshot();start=time.perf_counter()
        result=original_forward(self,*args,**kwargs)
        after=snapshot();steps.append(dict(seconds=time.perf_counter()-start,**{key:after[key]-before[key] for key in before}))
        return result
    model.Transformer.forward=forward
    try:run_metal_resident.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text())
            r['metal_moe']['l0_slots_per_layer']=24
            r['lru_hot_cache']={'l1_slots':8,'l0_slots':24,'policy':'free slots then least recently used non-requested slot',
                'steps':steps,'totals':snapshot(),'payload_bytes':sum(b.capacity*b.info['record_bytes'] for b in banks),
                'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('lru_metal_bank.py')]}}
            path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
