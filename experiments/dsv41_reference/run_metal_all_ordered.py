#!/usr/bin/env python3
"""Test ordered Metal FP8 at final projection boundaries as well as inner GEMMs."""
import hashlib,json,sys
from pathlib import Path
import cpu_kernel
import metal_dense_ordered
import run_reference
import run_metal_moe
import batched_routed
from cached_store import CachedStore
from lru_metal_bank import LRUMetalBank

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1]);stores=[];banks=[]
    def store(root):
        s=CachedStore(root,experts_per_layer=0,dense_bytes=12*2**30,row_bytes=8*2**20);stores.append(s);return s
    def bank(*args,**kwargs):
        b=LRUMetalBank(*args,**kwargs);banks.append(b);return b
    run_reference.Store=store;run_metal_moe.MetalBank=bank
    run_metal_moe.prefill_executor=batched_routed.forward
    cpu_kernel.fp8_gemm=metal_dense_ordered.fp8_gemm
    try:run_metal_moe.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['metal_moe']['l0_slots_per_layer']=24
            r['metal_dense']={'scope':'ALL FP8 GEMMs ordered Metal, including attention wo_b and shared w2','statistics':metal_dense_ordered.stats}
            r['all_ordered_fp8']={'stores':[s.summary() for s in stores],'batched_prefill':batched_routed.stats,
                'l0_slots':24,'cache_payload_bytes':sum(b.capacity*b.info['record_bytes'] for b in banks),
                'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(metal_dense_ordered.__file__),Path(batched_routed.__file__),Path(__file__).with_name('cached_store.py'),Path(__file__).with_name('lru_metal_bank.py')]}}
            path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
