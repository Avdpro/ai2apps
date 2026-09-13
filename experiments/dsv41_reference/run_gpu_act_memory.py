"""GPU activation path with per-forward MLX allocator observations."""
import hashlib,json,sys,time
from pathlib import Path
import torch
import mlx.core as mx
import run_owned_gpu_activation

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1]);old=torch.nn.Module._call_impl;steps=[]
    def memory():return {'active_bytes':mx.get_active_memory(),'cache_bytes':mx.get_cache_memory(),'peak_bytes':mx.get_peak_memory()}
    def call(self,*a,**kw):
        if type(self).__name__!='Transformer':return old(self,*a,**kw)
        before=memory();start=time.perf_counter()
        result=old(self,*a,**kw)
        row={'step':len(steps),'seconds':time.perf_counter()-start,'before':before,'after':memory()};steps.append(row);print(json.dumps({'allocator_step':row}),flush=True)
        return result
    torch.nn.Module._call_impl=call
    try:run_owned_gpu_activation.main()
    finally:
        torch.nn.Module._call_impl=old
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['allocator_steps']={'steps':steps,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
