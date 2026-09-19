"""Reuse Prefill dispatch metadata across gate/up/down; share gate/up quantization."""
import mlx.core as mx
from kernels import quant

class Dispatch:
    def __init__(self,slots,segments,matrix):
        self.large=[];small=[];positions=[];offset=0
        if matrix and any(n>=128 for _,n in segments):
            for slot,n in segments:
                rows=list(range(offset,offset+n))
                if n>=128:self.large.append((slot,offset,n));positions.extend(rows)
                else:small.extend(rows)
                offset+=n
            positions.extend(small)
            self.restore=mx.argsort(mx.array(positions,dtype=mx.int32))
            self.small=mx.array(small,dtype=mx.int32) if small else None
            selected=slots[self.small] if small else None
        else:
            self.restore=None;self.small=None;selected=slots
        self.order=self.inverse=self.lhs=self.rhs=None
        if selected is not None:
            self.order=mx.argsort(selected);self.inverse=mx.argsort(self.order)
            self.lhs=mx.arange(selected.shape[0],dtype=mx.uint32)
            self.rhs=selected[self.order].astype(mx.uint32)
    def project(self,z,w,s):
        chunks=[]
        for slot,offset,n in self.large:
            chunks.append(mx.quantized_matmul(z[offset:offset+n],w[slot].view(mx.uint32),s[slot],group_size=32,bits=4,mode='mxfp4'))
        if self.order is not None:
            a=z[self.small] if self.small is not None else z
            out=mx.gather_qmm(a[self.order,None,:],w.view(mx.uint32),s,lhs_indices=self.lhs,rhs_indices=self.rhs,group_size=32,bits=4,mode='mxfp4',sorted_indices=True)
            chunks.append(out[self.inverse,0,:].astype(mx.bfloat16))
        if self.restore is not None:return mx.concatenate(chunks)[self.restore].astype(mx.bfloat16)
        return chunks[0]

def expert(model,x,bank,slots,rw,segments):
    plan=Dispatch(slots,segments,model.matrix_prefill);a=bank.arrays
    z=quant(x).astype(mx.bfloat16)
    if getattr(model,'fused_gate_up',False):
        # Concatenate packed output rows only; original quantized bytes/scales.
        extent=max(slot for slot,n in segments if n)+1
        w=mx.concatenate([a[0][:extent],a[4][:extent]],axis=1)
        scales=mx.concatenate([a[1][:extent],a[5][:extent]],axis=1)
        both=plan.project(z,w,scales).astype(mx.float32)
        gate,up=mx.split(both,2,axis=-1)
    else:
        gate=plan.project(z,a[0],a[1]).astype(mx.float32)
        up=plan.project(z,a[4],a[5]).astype(mx.float32)
    gate=mx.minimum(gate,10);up=mx.clip(up,-10,10)
    h=(rw[:,None]*((gate*mx.sigmoid(gate))*up)).astype(mx.bfloat16)
    return plan.project(quant(h).astype(mx.bfloat16),a[2],a[3])


def decode_expert(x,arrays,slots,rw,mode):
    """Reuse the route plan and gate/up activation quantization for small Decode.

    Every output stays in the original route order. Down input quantization,
    FP32 activation/router weighting and the final BF16 conversion are unchanged.
    Unsorted mode also accepts repeated slots used by Burst's safe placeholders.
    """
    sorted_routes=mode=="shared"
    order=mx.argsort(slots) if sorted_routes else None
    inverse=mx.argsort(order) if sorted_routes else None
    rhs=(slots[order] if sorted_routes else slots).astype(mx.uint32)
    lhs=mx.arange(x.shape[0],dtype=mx.uint32)
    def project(z,w,s):
        z=z[order] if sorted_routes else z
        out=mx.gather_qmm(z[:,None,:],w.view(mx.uint32),s,
            lhs_indices=lhs,rhs_indices=rhs,group_size=32,bits=4,
            mode='mxfp4',sorted_indices=sorted_routes)
        return (out[inverse,0,:] if sorted_routes else out[:,0,:]).astype(mx.bfloat16)
    z=quant(x).astype(mx.bfloat16)
    gate=project(z,arrays[0],arrays[1]).astype(mx.float32)
    up=project(z,arrays[4],arrays[5]).astype(mx.float32)
    gate=mx.minimum(gate,10);up=mx.clip(up,-10,10)
    h=(rw[:,None]*((gate*mx.sigmoid(gate))*up)).astype(mx.bfloat16)
    return project(quant(h).astype(mx.bfloat16),arrays[2],arrays[3])
