"""Per-module immutable CPU projection cache for one checkpoint/run."""
import time
import torch

class ProjectionCache:
    def __init__(self, limit_bytes=24*2**30):
        self.limit_bytes=limit_bytes
        self.entries={}
        self.stats=dict(payload_bytes=0,hits=0,misses=0,pack_seconds=0.,gemm_seconds=0.)

    def gemm(self,key,a,sa,b,sb):
        shape=a.shape[:-1]; k=a.shape[-1]; n=b.shape[0]
        if k%32:raise ValueError('group32 required')
        a=a.float().reshape(-1,k);sa=sa.float().reshape(a.shape[0],-1)
        if key in self.entries:
            packed,scales=self.entries[key]
            if packed.shape!=(k//32,n,32):raise ValueError('projection identity/shape changed')
            self.stats['hits']+=1
        else:
            start=time.perf_counter()
            packed=b.float().reshape(n,k//32,32).permute(1,0,2).contiguous()
            scales=sb.float()[torch.arange(n)//32].T.contiguous()
            size=packed.numel()*4+scales.numel()*4
            if self.stats['payload_bytes']+size<=self.limit_bytes:
                self.entries[key]=(packed,scales)
                self.stats['payload_bytes']+=size
            self.stats['pack_seconds']+=time.perf_counter()-start
            self.stats['misses']+=1
        start=time.perf_counter()
        out=torch.zeros(a.shape[0],n,dtype=torch.float32)
        for g in range(k//32):
            part=a[:,g*32:(g+1)*32] @ packed[g].T
            out+=part*sa[:,g,None]*scales[g,None,:]
        self.stats['gemm_seconds']+=time.perf_counter()-start
        return out.reshape(*shape,n).to(torch.get_default_dtype())
