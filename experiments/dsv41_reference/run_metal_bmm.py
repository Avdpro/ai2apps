#!/usr/bin/env python3
import hashlib,json,sys
from pathlib import Path
import batched_projection
import run_metal_resident
import run_metal_batched

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1])
    run_metal_resident.ProjectionCache=batched_projection.BatchedProjectionCache
    try:run_metal_batched.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['batched_projection']={'scope':'independent group GEMMs batched on CPU cache hits; sequential accumulation',
                'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(batched_projection.__file__)]}}
            path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
