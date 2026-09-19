#!/usr/bin/env python3
"""Cache inner FP8 Metal weights by immutable module identity for one run."""
import hashlib,json,sys,time
from pathlib import Path
import mlx.core as mx
import numpy as np
import torch
import cpu_kernel
import metal_dense
import run_metal_hot

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1]);active=[];cache={}
    stats=dict(hits=0,misses=0,payload_bytes=0,limit_bytes=6*2**30,upload_seconds=0.,gemm_and_transfer_seconds=0.)
    def gemm(a,a_s,b,b_s,scale_dtype=torch.float32,block_size=128):
        if block_size!=32 or b_s.dtype!=torch.float8_e8m0fnu:raise ValueError('group32 UE8M0 required')
        if not active:raise RuntimeError('FP8 GEMM outside named Linear module')
        owner=active[-1];k=a.shape[-1];n=b.shape[0];m=a.numel()//k
        qa=mx.array(a.float().reshape(m,k).numpy());sa=mx.array(a_s.float().reshape(m,-1).numpy())
        if owner in cache:
            w,sw=cache[owner];stats['hits']+=1
            if w.shape!=b.shape or sw.shape!=b_s.shape:raise ValueError('immutable module shape changed')
        else:
            start=time.perf_counter()
            w=mx.array(b.view(torch.uint8).numpy());sw=mx.array(b_s.view(torch.uint8).numpy())
            mx.eval(w,sw);stats['upload_seconds']+=time.perf_counter()-start
            size=b.numel()+b_s.numel();stats['misses']+=1
            metal_dense.stats['weight_upload_bytes']+=size
            if stats['payload_bytes']+size<=stats['limit_bytes']:
                cache[owner]=(w,sw);stats['payload_bytes']+=size
        start=time.perf_counter()
        out=metal_dense.kernel()(inputs=[qa,sa,w,sw],template=[('K',k),('N',n),('T',mx.bfloat16)],grid=(n*32,m,1),threadgroup=(128,1,1),output_shapes=[(m,n)],output_dtypes=[mx.bfloat16])[0]
        mx.eval(out)
        result=torch.from_numpy(np.array(out.astype(mx.float32))).bfloat16().reshape(*a.shape[:-1],n)
        stats['gemm_and_transfer_seconds']+=time.perf_counter()-start;metal_dense.stats['calls']+=1
        return result
    metal_dense.fp8_gemm=gemm;cpu_kernel.fp8_gemm=gemm
    sys.modules['kernel']=cpu_kernel
    sys.path.insert(0,str(Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/inference').resolve()))
    import model
    original_init=model.Linear.__init__
    def init(self,*args,**kwargs):
        original_init(self,*args,**kwargs)
        if self.weight.dtype==torch.float8_e4m3fn:
            def before(module,args):active.append(module)
            def after(module,args,result):
                if not active or active[-1] is not module:raise RuntimeError('FP8 module context imbalance')
                active.pop()
            self.register_forward_pre_hook(before)
            self.register_forward_hook(after,always_call=True)
    model.Linear.__init__=init
    try:run_metal_hot.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['gpu_weight_cache']={'statistics':stats,'key':'owning Linear module, immutable checkpoint per process',
                'source_sha256':{str(Path(__file__)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
            path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
