#!/usr/bin/env python3
"""Native MX kernels plus MLX attention and a resident FP32 output head."""
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
import torch
import mlx.core as mx
import cpu_kernel
import native_mx
import mlx_attention
import batched_attention
import run_reference
import run_native_mx
from cached_store import CachedStore
import run_metal_cpu_order

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1]);stores=[];head_stats=dict(calls=0,seconds=0.,payload_bytes=0)
    # The downstream factory uses this class; capture its instance without
    # changing its cache limits or ordinary storage behavior.
    class Store(CachedStore):
        def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);stores.append(self)
    run_metal_cpu_order.CachedStore=Store
    batched_attention.sparse_attn=mlx_attention.sparse_attn
    cpu_kernel.sparse_attn=mlx_attention.sparse_attn
    cpu_kernel.fp8_gemm=native_mx.fp8_gemm
    sys.modules['kernel']=cpu_kernel
    sys.path.insert(0,str(Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/inference').resolve()))
    import model
    original_init=model.ParallelHead.__init__
    def init(self,*args,**kwargs):
        original_init(self,*args,**kwargs)
        # Explicitly own checkpoint loading here; avoids allocating/casting a
        # 2.7-GB CPU parameter on every head call in the reference hooks.
        del self._parameters['weight'];self._mlx_weight=None
    def forward(self,x,full_logits=False):
        if model.world_size!=1:raise ValueError('single-device prototype')
        start=time.perf_counter()
        if self._mlx_weight is None:
            raw=stores[-1].read('head.weight')
            if raw.dtype!=torch.bfloat16:raise ValueError('expected original BF16 head')
            self._mlx_weight=mx.array(raw.view(torch.uint16).numpy()).view(mx.bfloat16).astype(mx.float32)
            mx.eval(self._mlx_weight);head_stats['payload_bytes']=self._mlx_weight.size*4
        if not full_logits:x=x[:,-1]
        y=mx.array(x.float().numpy())@self._mlx_weight.T;mx.eval(y)
        result=torch.from_numpy(np.array(y));head_stats['calls']+=1;head_stats['seconds']+=time.perf_counter()-start
        return result
    model.ParallelHead.__init__=init;model.ParallelHead.forward=forward
    try:run_native_mx.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['native_gpu']={'attention':mlx_attention.stats,'head':head_stats,
                'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(mlx_attention.__file__)]}}
            r['batched_cpu_attention']['scope']='overridden by MLX block64 attention'
            path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
