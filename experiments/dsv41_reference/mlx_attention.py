"""MLX block64 online attention, retaining BF16 probabilities and FP32 state."""
import time
import mlx.core as mx
import numpy as np
import torch

stats=dict(calls=0,seconds=0.)
def sparse_attn(q,kv,attn_sink,topk_idxs,softmax_scale,query_chunk=64):
    start=time.perf_counter()
    qx=mx.array(q.float().numpy());kx=mx.array(kv.float().numpy())
    sink=mx.array(attn_sink.float().numpy());indices=mx.array(topk_idxs.numpy())
    batches=[]
    for b in range(q.shape[0]):
        chunks=[]
        for begin in range(0,q.shape[1],query_chunk):
            end=min(begin+query_chunk,q.shape[1]);queries=qx[b,begin:end]
            m=mx.full((end-begin,q.shape[2]),-1e30,dtype=mx.float32)
            sums=mx.zeros_like(m);acc=mx.zeros((end-begin,q.shape[2],q.shape[3]),dtype=mx.float32)
            for offset in range(0,topk_idxs.shape[-1],64):
                idx=indices[b,begin:end,offset:offset+64];valid=idx!=-1
                v=mx.where(valid[:,:,None],kx[b,mx.maximum(idx,0)],0)
                scores=mx.where(valid[:,None,:],queries@mx.swapaxes(v,1,2),-mx.inf)*softmax_scale
                new_m=mx.maximum(m,mx.max(scores,axis=-1));correction=mx.exp(m-new_m)
                p=mx.exp(scores-new_m[:,:,None]);sums=sums*correction+mx.sum(p,axis=-1)
                acc=acc*correction[:,:,None]+p.astype(mx.bfloat16).astype(mx.float32)@v;m=new_m
            sums+=mx.exp(sink[None,:]-m)
            chunks.append((acc/sums[:,:,None]).astype(mx.bfloat16))
        batches.append(mx.concatenate(chunks,axis=0))
    out=mx.stack(batches);mx.eval(out)
    result=torch.from_numpy(np.array(out.astype(mx.float32))).to(q.dtype)
    stats['calls']+=1;stats['seconds']+=time.perf_counter()-start
    return result
