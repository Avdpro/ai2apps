"""Experimental direct-index Metal attention; never enabled by the model default.

Avoids materializing gathered KV. Scalar/SIMD arithmetic (not tensor units),
so benchmark before integration. Float32 accumulation need not be bitwise
identical to MLX SDPA. Invalid indices are masked; sink has no value vector.
"""
from functools import lru_cache
import mlx.core as mx

@lru_cache(None)
def _kernel():
    return mx.fast.metal_kernel(name='dsv41_indexed_attention_probe',
        input_names=['q','kv','sink','indices','scale'],output_names=['out'],source=r'''
        uint tid=thread_position_in_grid.x%256;
        uint group=thread_position_in_grid.x/256;
        uint query=group/H,head=group%H,lane=tid%32,warp=tid/32;
        threadgroup float logits[K];
        threadgroup float partial[8];
        for(uint j=warp;j<K;j+=8){
            int row=indices[query*K+j];
            float dot=0.0f;
            if(row>=0 && row<L){
                for(uint d=lane;d<D;d+=32)
                    dot+=float(q[(query*H+head)*D+d])*float(kv[row*D+d]);
            }
            dot=simd_sum(dot);
            if(lane==0)logits[j]=(row>=0 && row<L)?dot*scale[0]:-INFINITY;
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
        float top=float(sink[head]);
        for(uint j=tid;j<K;j+=256)top=max(top,logits[j]);
        top=simd_max(top);
        if(lane==0)partial[warp]=top;
        threadgroup_barrier(mem_flags::mem_threadgroup);
        top=simd_max(lane<8?partial[lane]:-INFINITY);
        threadgroup_barrier(mem_flags::mem_threadgroup);
        float total=0.0f;
        for(uint j=tid;j<K;j+=256){
            float v=exp(logits[j]-top);logits[j]=v;total+=v;
        }
        total=simd_sum(total);
        if(lane==0)partial[warp]=total;
        threadgroup_barrier(mem_flags::mem_threadgroup);
        total=simd_sum(lane<8?partial[lane]:0.0f)+exp(float(sink[head])-top);
        for(uint d=tid;d<D;d+=256){
            float v=0.0f;
            for(uint j=0;j<K;j++){
                int row=indices[query*K+j];
                if(row>=0 && row<L)v+=logits[j]*float(kv[row*D+d]);
            }
            out[(query*H+head)*D+d]=T(v/total);
        }
        ''')

def indexed_attention(q,kv,sink,indices,scale):
    if q.ndim!=4 or q.shape[0]!=1 or kv.shape[0]!=1 or indices.shape[:2]!=q.shape[:2]:
        raise ValueError('single-sequence query/index shapes required')
    n,h,d=q.shape[1:];k=indices.shape[-1]
    if not 0<k<=1024 or d!=kv.shape[-1] or kv.dtype!=q.dtype:
        raise ValueError('unsupported indexed attention shape/dtype')
    return _kernel()(inputs=[q,kv,sink.astype(q.dtype),indices,mx.array([scale],dtype=mx.float32)],
        template=[('H',h),('D',d),('K',k),('L',kv.shape[1]),('T',q.dtype)],
        grid=(n*h*256,1,1),threadgroup=(256,1,1),output_shapes=[q.shape],output_dtypes=[q.dtype])[0]
