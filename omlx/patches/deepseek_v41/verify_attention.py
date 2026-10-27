"""Experimental batched projections with unchanged per-query attention kernels."""
import mlx.core as mx
from .kernels import quant,rope,rope_selected,sparse

def projected_attention(model,l,x,start,shared,prefix):
    c=model.c;p=f'layers.{l}.attn';st=model.states[l];n=x.shape[1]
    ratio=c.compress_ratios[l];freq=model.freqs[bool(ratio)];rd=c.rope_head_dim
    qr=model.norm(p+'.q_norm',model.linear(p+'.wq_a',x))
    q=rope(model.linear(p+'.wq_b',qr).reshape(1,n,c.n_heads,c.head_dim),freq,start,rd)
    kv=quant(rope(model.norm(p+'.kv_norm',model.linear(p+'.wkv',x)),freq,start,rd))
    parts=[]
    for i in range(n):
        position=start+i;model.shared=shared[i]
        st['window'][:,position%c.window_size]=kv[:,i];window=st['window']
        oldest=position%c.window_size+1
        idx=mx.concatenate([mx.arange(oldest,c.window_size),mx.arange(oldest)])[None,None,:]
        idx=mx.where(idx>position,-1,idx).astype(mx.int32)
        if ratio:
            clen=(position+1)//ratio;latent=None
            if l in c.kv_source_layers:
                latent=model.compress(l,x[:,i:i+1],position);model.shared['compressed']=st['compressed']
            if l in c.index_source_layers:
                ci=mx.zeros((1,1,0),dtype=mx.int32) if clen==0 else model.index(l,x[:,i:i+1],qr[:,i:i+1],latent,position,window.shape[1])
                model.shared['indices']=ci
            else:ci=model.shared['indices']
            if latent is not None:
                latent=quant(rope_selected(latent,freq,mx.array([position+1-ratio]),rd),16,True,True)
                st['compressed'][:,position//ratio:position//ratio+latent.shape[1]]=latent
                model.shared['compressed']=st['compressed']
            window=mx.concatenate([window,model.shared['compressed'][:,:clen]],axis=1)
            idx=mx.concatenate([idx,ci],axis=-1)
        out=sparse(q[:,i:i+1],window,model.w(p+'.attn_sink'),idx,c.head_dim**-.5,model.attention_chunk)
        out=rope(out,freq,position,rd,True).reshape(1,1,c.o_groups,-1)
        # Keep the grouped BF16 contraction shape identical to scalar Decode.
        w=model.s.grouped(p+'.wo_a').reshape(c.o_groups,c.o_lora_rank,-1)
        out=mx.transpose(mx.transpose(out,(0,2,1,3))@mx.swapaxes(w,-1,-2),(0,2,1,3)).reshape(1,1,-1)
        parts.append(out)
        prefix[i][l]={k:mx.array(v) for k,v in st.items()}
    return model.linear(p+'.wo_b',mx.concatenate(parts,axis=1))
