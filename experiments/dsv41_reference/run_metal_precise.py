#!/usr/bin/env python3
"""Compensated SIMD dots, resident CPU projections, LRU experts, batched prefill."""
import hashlib,json,sys
from pathlib import Path
import metal_dense
import metal_dense_precise
import batched_routed
import run_metal_moe
import run_metal_hot

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1])
    metal_dense.kernel=metal_dense_precise.kernel
    run_metal_moe.prefill_executor=batched_routed.forward
    try:run_metal_hot.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['compensated_fp8']={'scope':'two-part SIMD reduction; contraction/reassociation disabled',
                'batched_prefill':batched_routed.stats,
                'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(metal_dense_precise.__file__),Path(batched_routed.__file__)]}}
            path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
