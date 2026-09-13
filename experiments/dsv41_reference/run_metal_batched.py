#!/usr/bin/env python3
import hashlib,json,sys
from pathlib import Path
import batched_routed
import run_metal_moe
import run_metal_gpu_resident

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1])
    run_metal_moe.prefill_executor=batched_routed.forward
    try:run_metal_gpu_resident.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['batched_prefill']={'statistics':batched_routed.stats,
                'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(batched_routed.__file__)]}}
            path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
