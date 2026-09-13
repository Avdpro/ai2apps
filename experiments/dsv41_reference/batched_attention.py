"""Batch independent queries in the CPU reference's block64 online attention."""
import torch

def sparse_attn(q,kv,attn_sink,topk_idxs,softmax_scale,query_chunk=32):
    out=torch.empty_like(q)
    for b in range(q.shape[0]):
        for begin in range(0,q.shape[1],query_chunk):
            end=min(begin+query_chunk,q.shape[1]);queries=q[b,begin:end].float()
            m=torch.full((end-begin,q.shape[2]),-1e30,dtype=torch.float32)
            sums=torch.zeros_like(m)
            acc=torch.zeros(end-begin,q.shape[2],q.shape[3],dtype=torch.float32)
            for start in range(0,topk_idxs.shape[-1],64):
                idx=topk_idxs[b,begin:end,start:start+64].long();valid=idx!=-1
                v=kv[b,idx.clamp_min(0)].float().masked_fill(~valid[:,:,None],0)
                scores=torch.bmm(queries,v.transpose(1,2)).masked_fill(~valid[:,None,:],-torch.inf)*softmax_scale
                new_m=torch.maximum(m,scores.amax(-1));correction=(m-new_m).exp()
                p=(scores-new_m[:,:,None]).exp()
                sums=sums*correction+p.sum(-1)
                acc=acc*correction[:,:,None]+torch.bmm(p.bfloat16().float(),v)
                m=new_m
            sums+=(attn_sink[None,:]-m).exp()
            out[b,begin:end]=(acc/sums[:,:,None]).to(q.dtype)
    return out
