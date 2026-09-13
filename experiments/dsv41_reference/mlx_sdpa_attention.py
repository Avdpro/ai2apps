"""Native SDPA over official sparse indices; query chunks bound gathered KV."""
import time
import mlx.core as mx
import numpy as np
import torch
stats=dict(calls=0,seconds=0.)
def sparse_attn(q,kv,attn_sink,topk_idxs,softmax_scale,query_chunk=64):
    start=time.perf_counter();batches=[]
    qx=mx.array(q.float().numpy()).astype(mx.bfloat16)
    kx=mx.array(kv.float().numpy()).astype(mx.bfloat16)
    sink=mx.array(attn_sink.float().numpy()).astype(mx.bfloat16);indices=mx.array(topk_idxs.numpy())
    for b in range(q.shape[0]):
        chunks=[]
        for begin in range(0,q.shape[1],query_chunk):
            end=min(begin+query_chunk,q.shape[1]);idx=indices[b,begin:end];valid=idx>=0
            v=kx[b,mx.maximum(idx,0)][:,None,:,:]
            queries=qx[b,begin:end][:,:,None,:]
            y=mx.fast.scaled_dot_product_attention(queries,v,v,scale=softmax_scale,
                mask=valid[:,None,None,:],sinks=sink)
            chunks.append(y[:,:,0,:])
        batches.append(mx.concatenate(chunks,axis=0))
    out=mx.stack(batches);mx.eval(out)
    result=torch.from_numpy(np.array(out.astype(mx.float32))).to(q.dtype)
    stats['calls']+=1;stats['seconds']+=time.perf_counter()-start
    return result
