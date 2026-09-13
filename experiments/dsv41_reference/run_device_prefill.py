"""65 GB text budget with resident-first device-side Prefill accumulation."""
import hashlib,json,sys
from pathlib import Path
import batched_routed,device_prefill,run_text_budget

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1]);batched_routed.forward=device_prefill.forward
    try:run_text_budget.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['device_prefill']={'statistics':device_prefill.stats,'scope':'resident-first grouped gather_qmm; one GPU-to-CPU MoE result per layer; original ascending-expert route sum retained','source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(device_prefill.__file__)]}};path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
