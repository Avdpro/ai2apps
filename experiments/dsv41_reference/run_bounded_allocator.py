"""Bound idle MLX allocator storage; keep active inference weights unchanged."""
import hashlib,json,sys
from pathlib import Path
import mlx.core as mx
import run_gpu_act_memory

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1]);limit=2*2**30
    previous=mx.set_cache_limit(limit)
    try:run_gpu_act_memory.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['bounded_allocator']={'cache_limit_bytes':limit,'previous_cache_limit_bytes':previous,'scope':'idle MLX allocator pool bound only; not a whole-process memory enforcer','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};path.write_text(json.dumps(r,indent=2))
        mx.set_cache_limit(previous)
if __name__=='__main__':main()
