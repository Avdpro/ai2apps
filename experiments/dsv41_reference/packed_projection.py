"""CPU strict group32 GEMM with K-group-major weights; arithmetic order unchanged."""
import time
import torch
stats={'calls':0,'pack_seconds':0.,'gemm_seconds':0.}

def fp8_gemm(a,a_s,b,b_s,scale_dtype=torch.float32,block_size=128):
    if block_size!=32:raise ValueError('group32 required')
    shape=a.shape[:-1];k=a.shape[-1];n=b.shape[0]
    a=a.float().reshape(-1,k);sa=a_s.float().reshape(a.shape[0],-1)
    start=time.perf_counter()
    # The original slices have row stride K; each group now has row stride 32.
    packed=b.float().reshape(n,k//32,32).permute(1,0,2).contiguous()
    sb=b_s.float()[torch.arange(n)//32].T.contiguous()
    stats['pack_seconds']+=time.perf_counter()-start
    out=torch.zeros(a.shape[0],n,dtype=torch.float32)
    start=time.perf_counter()
    for g in range(k//32):
        part=a[:,g*32:(g+1)*32] @ packed[g].T
        out+=part*sa[:,g,None]*sb[g,None,:]
    stats['gemm_seconds']+=time.perf_counter()-start;stats['calls']+=1
    return out.reshape(*shape,n).to(torch.get_default_dtype())
