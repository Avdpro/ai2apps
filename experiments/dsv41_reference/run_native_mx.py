#!/usr/bin/env python3
"""Use native MX kernels; accept ordinary FP32 reduction differences, no requantization."""
import hashlib,json,sys
from pathlib import Path
import native_mx
import metal_dense_cpu_order
import run_metal_moe
import batched_routed
import run_metal_batched_attention

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1])
    metal_dense_cpu_order.fp8_gemm=native_mx.fp8_gemm
    run_metal_moe.expert=native_mx.expert;batched_routed.expert=native_mx.expert
    try:run_metal_batched_attention.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['metal_dense']['scope']='native MLX MXFP8, original packed bytes'
            r['native_mx']={'statistics':native_mx.stats,'policy':'original quantized weights; normal floating reduction differences accepted; evaluate logits/top-k/generation',
                'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(native_mx.__file__)]}}
            path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
