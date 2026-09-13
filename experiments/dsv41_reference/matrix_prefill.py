"""Use matrix GEMM for experts with >=128 tokens, gather for small groups."""
import mlx.core as mx
from metal_expert import act_quant,swiglu_kernel,silu_table
from native_mx_bf16 import linear as gather_linear
stats=dict(matrix_experts=0,matrix_rows=0,gather_rows=0)
def linear(x,weight,scale,slots,counts):
    chunks=[];positions=[];small=[];offset=0
    q,sa=act_quant(x);k=x.shape[-1]
    z=(q.reshape(-1,k//32,32)*sa[:,:,None]).reshape(-1,k).astype(mx.bfloat16)
    for slot,count in zip(slots,counts):
        rows=list(range(offset,offset+count))
        if count>=128:
            chunks.append(mx.quantized_matmul(z[offset:offset+count],weight[slot].view(mx.uint32),scale[slot],group_size=32,bits=4,mode='mxfp4'))
            positions.extend(rows);stats['matrix_experts']+=1;stats['matrix_rows']+=count
        else:small.extend((r,slot) for r in rows)
        offset+=count
    if small:
        rows=mx.array([r for r,s in small],dtype=mx.int32);ss=mx.array([s for r,s in small],dtype=mx.int32)
        chunks.append(gather_linear(x[rows],weight,scale,ss));positions.extend(r for r,s in small);stats['gather_rows']+=len(small)
    restore=mx.argsort(mx.array(positions,dtype=mx.int32))
    return mx.concatenate(chunks,axis=0)[restore].astype(mx.bfloat16)

def expert(x,bank,experts,counts,weights):
    slots=[bank.main[e] if e in bank.main else bank.hot[e] for e in experts]
    gate=linear(x,bank.arrays[0],bank.arrays[1],slots,counts)
    up=linear(x,bank.arrays[4],bank.arrays[5],slots,counts)
    hidden=swiglu_kernel()(inputs=[gate,up,weights,silu_table()],template=[('D',gate.shape[-1]),('T',mx.bfloat16)],grid=(gate.size,1,1),threadgroup=(128,1,1),output_shapes=[gate.shape],output_dtypes=[mx.bfloat16])[0]
    return linear(hidden,bank.arrays[2],bank.arrays[3],slots,counts)
