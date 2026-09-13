"""Native MLX MXFP8/MXFP4 over original packed bytes; keep activation quantization."""
import time
import mlx.core as mx
import numpy as np
import torch
from metal_expert import act_quant,swiglu_kernel,silu_table

stats=dict(fp8_calls=0,fp8_seconds=0.,fp8_upload_bytes=0,expert_calls=0)

def fp8_gemm(a,sa,b,sb,scale_dtype=torch.float32,block_size=128):
    if block_size!=32 or sb.dtype!=torch.float8_e8m0fnu:raise ValueError('group32 UE8M0 required')
    start=time.perf_counter();k=a.shape[-1];n=b.shape[0]
    raw=b.view(torch.uint8).contiguous().numpy().view(np.uint32).reshape(n,k//4)
    scales=sb.view(torch.uint8).repeat_interleave(32,dim=0)[:n].contiguous().numpy()
    w=mx.array(raw);sw=mx.array(scales)
    x=a.float().reshape(-1,k)*sa.float().reshape(-1,k//32).repeat_interleave(32,dim=1)
    out=mx.quantized_matmul(mx.array(x.numpy()).astype(mx.bfloat16),w,sw,group_size=32,bits=8,mode='mxfp8')
    mx.eval(out)
    result=torch.from_numpy(np.array(out.astype(mx.float32))).bfloat16().reshape(*a.shape[:-1],n)
    stats['fp8_calls']+=1;stats['fp8_upload_bytes']+=b.numel()+scales.size;stats['fp8_seconds']+=time.perf_counter()-start
    return result

def linear(x,weight,scale,slots):
    m,k=x.shape
    q,sa=act_quant(x)
    dequant=(q.reshape(m,k//32,32)*sa[:,:,None]).reshape(m,1,k).astype(mx.bfloat16)
    # Sorting enables native gathered-QMM grouping without claiming arbitrary
    # expert IDs are physically ordered in the mutable slot bank.
    order=mx.argsort(slots);inverse=mx.argsort(order)
    out=mx.gather_qmm(dequant[order],weight.view(mx.uint32),scale,
        lhs_indices=mx.arange(m,dtype=mx.uint32),rhs_indices=slots[order].astype(mx.uint32),
        group_size=32,bits=4,mode='mxfp4',sorted_indices=True)
    return out[inverse,0,:].astype(mx.bfloat16)

def expert(x,bank,slots,route_weights):
    gate=linear(x,bank[0],bank[1],slots)
    up=linear(x,bank[4],bank[5],slots)
    hidden=swiglu_kernel()(inputs=[gate,up,route_weights,silu_table()],template=[('D',gate.shape[-1]),('T',mx.bfloat16)],
        grid=(gate.size,1,1),threadgroup=(128,1,1),output_shapes=[gate.shape],output_dtypes=[mx.bfloat16])[0]
    stats['expert_calls']+=1
    return linear(hidden,bank[2],bank[3],slots)
