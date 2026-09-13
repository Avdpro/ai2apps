#!/usr/bin/env python3
import hashlib,json,sys
from pathlib import Path
import cpu_kernel
import packed_projection
import run_metal_dense

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1])
    cpu_kernel.fp8_gemm=packed_projection.fp8_gemm
    try:run_metal_dense.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['packed_projection']={'statistics':packed_projection.stats,
                'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(packed_projection.__file__)]}}
            path.write_text(json.dumps(r,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
