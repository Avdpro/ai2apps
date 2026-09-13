"""Group independent prefill expert/token pairs; preserve per-token sum order."""
import time
import mlx.core as mx
import numpy as np
import torch
from metal_expert import expert

stats=dict(layers=0,dispatches=0,pairs=0,unique_experts=0)

def forward(x,weights,indices,bank):
    order=torch.argsort(indices,dim=-1)
    ids=torch.gather(indices,1,order);rw=torch.gather(weights,1,order)
    pairs={}
    for row,experts in enumerate(ids.tolist()):
        for rank,e in enumerate(experts):pairs.setdefault(e,[]).append((row,rank))
    all_ids=sorted(pairs)
    values=torch.empty((x.shape[0],ids.shape[1],x.shape[1]),dtype=torch.float32)
    elapsed=0.;calls=0
    for begin in range(0,len(all_ids),bank.l0_slots):
        experts=all_ids[begin:begin+bank.l0_slots]
        unique_slots=bank.prepare(experts)
        rows=[];ranks=[];slot_indices=[]
        for slot_index,e in enumerate(experts):
            for row,rank in pairs[e]:
                rows.append(row);ranks.append(rank);slot_indices.append(slot_index)
        inp=mx.array(x[rows].float().numpy()).astype(mx.bfloat16)
        selected_weights=mx.array(rw[rows,ranks].float().numpy())
        slots=unique_slots[mx.array(slot_indices,dtype=mx.int32)]
        start=time.perf_counter()
        out=expert(inp,bank.arrays,slots,selected_weights);bank.track(out);mx.eval(out)
        elapsed+=time.perf_counter()-start;calls+=1
        values[rows,ranks]=torch.from_numpy(np.array(out.astype(mx.float32)))
    y=torch.zeros_like(x,dtype=torch.float32)
    for rank in range(ids.shape[1]):y+=values[:,rank]
    stats['layers']+=1;stats['dispatches']+=calls;stats['pairs']+=indices.numel();stats['unique_experts']+=len(all_ids)
    return y,elapsed,calls
