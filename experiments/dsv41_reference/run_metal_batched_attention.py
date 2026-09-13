#!/usr/bin/env python3
"""All-FP8 Metal path with query-batched, numerically unchanged CPU attention."""
import hashlib,json,sys,time
from pathlib import Path
import cpu_kernel
import batched_attention
import run_metal_cpu_order

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1]);stats=dict(calls=0,seconds=0.)
    def attention(*args,**kwargs):
        start=time.perf_counter()
        try:return batched_attention.sparse_attn(*args,**kwargs)
        finally:stats['calls']+=1;stats['seconds']+=time.perf_counter()-start
    cpu_kernel.sparse_attn=attention
    try:run_metal_cpu_order.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['batched_cpu_attention']={'query_chunk':32,'block_size':64,'statistics':stats,
                'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(batched_attention.__file__)]}}
            path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
