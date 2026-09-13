"""Compose context Main24/Hot8, GPU activation and bounded idle allocator."""
import hashlib,json,sys
from pathlib import Path
import run_native_owned,run_owned_gpu_activation,run_context_main,run_gpu_act_memory,run_bounded_allocator

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1])
    gpu_main=run_owned_gpu_activation.main
    run_native_owned.main=gpu_main
    run_gpu_act_memory.run_owned_gpu_activation.main=run_context_main.main
    try:run_bounded_allocator.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['context_bounded']={'scope':'Main24/Hot8 with current-prefill selection, GPU activation, 2 GiB idle allocator cap','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
