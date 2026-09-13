import hashlib,json,sys
from pathlib import Path
import device_prefill,matrix_prefill,run_device_moe

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1]);device_prefill.expert_executor=matrix_prefill.expert
    try:run_device_moe.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['matrix_prefill']={'statistics':matrix_prefill.stats,'scope':'native per-expert GEMM for >=128 rows, original gather for smaller batches; normal floating reduction differences evaluated','source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(matrix_prefill.__file__)]}};path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
