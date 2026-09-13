"""Resident-first expert grouping with GPU scatter/reduction and one host result."""
import time
import numpy as np
import torch
import mlx.core as mx
import batched_routed
expert_executor=None
stats=dict(layers=0,dispatches=0,host_results=0,pairs=0)

def forward(x,weights,indices,bank):
    order=torch.argsort(indices,dim=-1)
    ids=torch.gather(indices,1,order);rw=torch.gather(weights,1,order)
    pairs={};topk=ids.shape[1]
    for row,experts in enumerate(ids.tolist()):
        for rank,e in enumerate(experts):pairs.setdefault(e,[]).append((row,rank))
    resident=[e for e in sorted(pairs) if e in bank.main]
    cold=[e for e in sorted(pairs) if e not in bank.main]
    groups=([resident] if resident else [])+[cold[i:i+bank.l0_slots] for i in range(0,len(cold),bank.l0_slots)]
    inp=mx.array(x.contiguous().view(torch.uint16).numpy()).view(mx.bfloat16) if x.dtype==torch.bfloat16 else mx.array(x.float().numpy()).astype(mx.bfloat16)
    routing=mx.array(rw.float().numpy());values=[];positions=[];elapsed=0.
    for experts in groups:
        unique_slots=bank.prepare(experts);rows=[];ranks=[];slot_indices=[]
        for slot_index,e in enumerate(experts):
            for row,rank in pairs[e]:rows.append(row);ranks.append(rank);slot_indices.append(slot_index)
        ir=mx.array(rows,dtype=mx.int32);ik=mx.array(ranks,dtype=mx.int32)
        slots=unique_slots[mx.array(slot_indices,dtype=mx.int32)]
        start=time.perf_counter()
        out=batched_routed.expert(inp[ir],bank.arrays,slots,routing[ir,ik]) if expert_executor is None else expert_executor(inp[ir],bank,experts,[len(pairs[e]) for e in experts],routing[ir,ik])
        bank.track(out);mx.eval(out)
        elapsed+=time.perf_counter()-start;values.append(out);positions.extend(row*topk+rank for row,rank in zip(rows,ranks))
    start=time.perf_counter()
    restore=mx.argsort(mx.array(positions,dtype=mx.int32))
    contributions=mx.concatenate(values,axis=0)[restore].reshape(x.shape[0],topk,x.shape[1]).astype(mx.float32)
    y=mx.zeros((x.shape[0],x.shape[1]),dtype=mx.float32)
    for rank in range(topk):y=y+contributions[:,rank,:]
    mx.eval(y);result=torch.from_numpy(np.array(y));elapsed+=time.perf_counter()-start
    stats['layers']+=1;stats['dispatches']+=len(groups);stats['host_results']+=1;stats['pairs']+=indices.numel()
    return result,elapsed,len(groups)
