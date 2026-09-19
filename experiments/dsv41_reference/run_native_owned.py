"""Single-owner MLX FP8 weights; avoid CPU cache and per-step parameter loads."""
import hashlib,json,sys,time,types
from pathlib import Path
import numpy as np
import torch
import mlx.core as mx
import cached_store,cpu_kernel,run_reference,run_native_benchmark

stats=dict(modules=0,loads=0,calls=0,payload_bytes=0,seconds=0.,cpu_bypass_reads=0)
def main():
    output=Path(sys.argv[sys.argv.index('--output')+1]);owned=set();stores=[]
    original_store=cached_store.CachedStore
    raw_read=run_reference.Store.read
    class Store(original_store):
        def __init__(self,*a,**kw):super().__init__(*a,**kw);stores.append(self)
        def read(self,name,rows=None):
            if rows is None and (name in owned or name=='head.weight' or '.attn.wo_a.' in name):
                stats['cpu_bypass_reads']+=1
                return raw_read(self,name)
            return super().read(name,rows)
    cached_store.CachedStore=Store
    sys.modules['kernel']=cpu_kernel
    sys.path.insert(0,str(Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/inference').resolve()))
    import model
    import mlx_sdpa_attention
    model.sparse_attn=mlx_sdpa_attention.sparse_attn
    original_init=model.Transformer.__init__
    def forward(self,x):
        if model.world_size!=1:raise ValueError('single-device ownership prototype')
        start=time.perf_counter();k=self.in_features;n=self.out_features
        if self._mlx_owned is None:
            b=stores[-1].read(self._owned_name+'.weight');sb=stores[-1].read(self._owned_name+'.scale')
            raw=b.view(torch.uint8).contiguous().numpy().view(np.uint32).reshape(n,k//4)
            scales=sb.view(torch.uint8).repeat_interleave(32,dim=0)[:n].contiguous().numpy()
            w=mx.array(raw);sw=mx.array(scales);mx.eval(w,sw)
            self._mlx_owned=(w,sw);stats['loads']+=1;stats['payload_bytes']+=raw.nbytes+scales.nbytes
        w,sw=self._mlx_owned
        a,sa=cpu_kernel.act_quant(x,model.fp8_block_size,model.scale_fmt,model.scale_dtype)
        z=a.float().reshape(-1,k)*sa.float().reshape(-1,k//32).repeat_interleave(32,dim=1)
        y=mx.quantized_matmul(mx.array(z.numpy()).astype(mx.bfloat16),w,sw,group_size=32,bits=8,mode='mxfp8');mx.eval(y)
        result=torch.from_numpy(np.array(y.astype(mx.float32))).bfloat16().reshape(*x.shape[:-1],n)
        stats['calls']+=1;stats['seconds']+=time.perf_counter()-start
        return result.to(x.dtype) if isinstance(self,model.RowParallelLinear) else result
    def init(self,*a,**kw):
        original_init(self,*a,**kw)
        for name,m in self.named_modules():
            if isinstance(m,model.Linear) and isinstance(m._parameters.get('weight'),torch.Tensor) and m.weight.dtype==torch.float8_e4m3fn:
                if m.bias is not None:raise ValueError('unexpected FP8 bias')
                owned.update([name+'.weight',name+'.scale'])
                m._parameters.clear();m._owned_name=name;m._mlx_owned=None
                m.forward=types.MethodType(forward,m);stats['modules']+=1
    model.Transformer.__init__=init
    try:run_native_benchmark.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['native_owned']={'statistics':stats,'scope':'FP8 linears owned solely by MLX; head and wo_a bypass CPU cache; remaining CPU operations unchanged','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
            path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
