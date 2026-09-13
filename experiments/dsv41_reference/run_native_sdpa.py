"""Native cached BF16 path with sparse-index SDPA."""
import hashlib,json,sys
from pathlib import Path
import mlx_attention,mlx_sdpa_attention,run_native_cached_bf16

def main():
    mlx_attention.sparse_attn=mlx_sdpa_attention.sparse_attn
    mlx_attention.stats=mlx_sdpa_attention.stats
    output=Path(sys.argv[sys.argv.index('--output')+1])
    try:run_native_cached_bf16.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text())
            r['native_sdpa']={'statistics':mlx_sdpa_attention.stats,'scope':'official sparse indices and sinks; native FP32 softmax, BF16 inputs/output; not block64 bitwise parity',
                'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(mlx_sdpa_attention.__file__)]}}
            r['batched_cpu_attention']['scope']='overridden by native MLX SDPA'
            path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
