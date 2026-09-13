#!/usr/bin/env python3
"""Module-owned native MXFP8 weights and grouped wo_a residency."""
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
import torch
import mlx.core as mx
import native_mx,cpu_kernel,mlx_attention,run_native_gpu
import native_mx_bf16

stats=dict(fp8_hits=0,fp8_misses=0,fp8_payload_bytes=0,wo_a_payload_bytes=0,wo_a_calls=0,wo_a_seconds=0.)
def main():
    output=Path(sys.argv[sys.argv.index('--output')+1]);active=[];cache={};stores=[]
    native_mx.expert=native_mx_bf16.expert
    from cached_store import CachedStore
    # run_native_gpu subclasses this symbol before passing it to the harness.
    class Store(CachedStore):
        def __init__(self,*a,**kw):super().__init__(*a,**kw);stores.append(self)
    run_native_gpu.CachedStore=Store
    def gemm(a,sa,b,sb,scale_dtype=torch.float32,block_size=128):
        if block_size!=32 or not active:raise ValueError('named group32 FP8 required')
        start=time.perf_counter();owner=active[-1];k=a.shape[-1];n=b.shape[0]
        if owner in cache:w,sw=cache[owner];stats['fp8_hits']+=1
        else:
            raw=b.view(torch.uint8).contiguous().numpy().view(np.uint32).reshape(n,k//4)
            scales=sb.view(torch.uint8).repeat_interleave(32,dim=0)[:n].contiguous().numpy()
            w=mx.array(raw);sw=mx.array(scales);size=raw.nbytes+scales.nbytes
            if stats['fp8_payload_bytes']+size>8*2**30:raise RuntimeError('FP8 GPU cache budget exceeded')
            cache[owner]=(w,sw);stats['fp8_payload_bytes']+=size;stats['fp8_misses']+=1;native_mx.stats['fp8_upload_bytes']+=size
        x=a.float().reshape(-1,k)*sa.float().reshape(-1,k//32).repeat_interleave(32,dim=1)
        out=mx.quantized_matmul(mx.array(x.numpy()).astype(mx.bfloat16),w,sw,group_size=32,bits=8,mode='mxfp8');mx.eval(out)
        result=torch.from_numpy(np.array(out.astype(mx.float32))).bfloat16().reshape(*a.shape[:-1],n)
        native_mx.stats['fp8_calls']+=1;native_mx.stats['fp8_seconds']+=time.perf_counter()-start
        return result
    native_mx.fp8_gemm=gemm;cpu_kernel.fp8_gemm=gemm;cpu_kernel.sparse_attn=mlx_attention.sparse_attn
    sys.modules['kernel']=cpu_kernel
    sys.path.insert(0,str(Path('artifacts/dsv41-download/DeepSeek-V4.1-Flash/inference').resolve()))
    import model
    linear_init=model.Linear.__init__
    def init(self,*a,**kw):
        linear_init(self,*a,**kw)
        if self.weight.dtype==torch.float8_e4m3fn:
            def before(m,args):active.append(m)
            def after(m,args,result):active.pop()
            self.register_forward_pre_hook(before);self.register_forward_hook(after,always_call=True)
    model.Linear.__init__=init
    class GroupedWeight:
        def __init__(self,layer):self.layer=layer;self.value=None
        def view(self,*shape):
            if self.value is None:
                key=f'layers.{self.layer}.attn.wo_a';b=stores[-1].read(key+'.weight');sb=stores[-1].read(key+'.scale')
                n,k=b.shape;w=mx.array(b.view(torch.uint8).numpy().view(np.uint32).reshape(n,k//4))
                sw=mx.array(sb.view(torch.uint8).repeat_interleave(32,dim=0)[:n].numpy())
                self.value=mx.dequantize(w,sw,group_size=32,bits=8,mode='mxfp8').astype(mx.bfloat16);mx.eval(self.value)
                stats['wo_a_payload_bytes']+=self.value.size*2
                if stats['wo_a_payload_bytes']>8*2**30:raise RuntimeError('wo_a cache budget exceeded')
            return self.value.reshape(shape)
    attention_init=model.Attention.__init__
    def attn_init(self,*a,**kw):
        attention_init(self,*a,**kw)
        self.wo_a._parameters.clear();self.wo_a.weight=GroupedWeight(self.layer_id)
    model.Attention.__init__=attn_init
    old_einsum=torch.einsum
    def einsum(equation,*operands):
        if equation=='bsgd,grd->bsgr' and isinstance(operands[1],mx.array):
            start=time.perf_counter();x,w=operands
            a=mx.array(x.float().numpy()).astype(mx.bfloat16)
            y=mx.transpose(mx.transpose(a,(0,2,1,3))@mx.swapaxes(w,-1,-2),(0,2,1,3));mx.eval(y)
            result=torch.from_numpy(np.array(y.astype(mx.float32))).to(x.dtype)
            stats['wo_a_calls']+=1;stats['wo_a_seconds']+=time.perf_counter()-start;return result
        return old_einsum(equation,*operands)
    torch.einsum=einsum
    try:run_native_gpu.main()
    finally:
        torch.einsum=old_einsum
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['native_cached']={'compute_dtype':'BF16 dequantized FP8 activation (no additional mantissa loss on normal-range values)','expert_source_sha256':hashlib.sha256(Path(native_mx_bf16.__file__).read_bytes()).hexdigest(),'expert_statistics':native_mx_bf16.stats,'statistics':stats,'key':'module identity; immutable checkpoint per run',
                'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
