"""Batch independent group GEMMs, retaining sequential FP32 group accumulation."""
import time
import torch
from resident_projection import ProjectionCache

class BatchedProjectionCache(ProjectionCache):
    def gemm(self,key,a,sa,b,sb):
        if key not in self.entries:
            return super().gemm(key,a,sa,b,sb)
        start=time.perf_counter()
        shape=a.shape[:-1];k=a.shape[-1];n=b.shape[0];g=k//32
        packed,scales=self.entries[key]
        if k%32 or packed.shape!=(g,n,32):raise ValueError('projection identity/shape changed')
        a=a.float().reshape(-1,k);m=a.shape[0];sa=sa.float().reshape(m,g)
        parts=torch.bmm(a.reshape(m,g,32).permute(1,0,2),packed.transpose(1,2))
        parts=parts*sa.T[:,:,None]
        parts=parts*scales[:,None,:]
        out=torch.zeros(m,n,dtype=torch.float32)
        for group in range(g):out+=parts[group]
        self.stats['hits']+=1;self.stats['gemm_seconds']+=time.perf_counter()-start
        return out.reshape(*shape,n).to(torch.get_default_dtype())
