"""Bounded, model-wide double scratch; native reads overlap disjoint GPU consumers."""
import time
import mlx.core as mx
from metal_bank import native

class Prefill:
    def __init__(self,slots,top=None):
        self.slots=slots;self.top=top;self.buffers=None;self.pending=[None,None]
        self.report=dict(layers=[],read_bytes=0,io_seconds=0)
    def dispatch(self,model,layer,flat,ids,weights,bank,scores):
        mx.eval(ids,weights)
        host=ids.tolist();k=ids.shape[-1];resident=set(bank.main)|set(bank.hot)
        required=set()
        if self.top:
            ranked=mx.argsort(scores+model.w(f'layers.{layer}.ffn.gate.bias'),axis=-1)[:,-self.top:]
            mx.eval(ranked);required={e for row in ranked.tolist() for e in row}
        else:required={e for row in host for e in row}
        keep=resident|required;pairs={}
        for row,es in enumerate(host):
            for rank,e in enumerate(es):
                if e in keep:pairs.setdefault(e,[]).append((row,rank))
        main=[e for e in sorted(pairs) if e in bank.main]
        cold=[e for e in sorted(pairs) if e not in bank.main]
        if self.buffers is None:
            self.buffers=[type('Scratch',(),{'arrays':tuple(mx.zeros((self.slots,*shape),dtype=mx.uint8) for shape in bank.info['shapes'])})() for _ in range(2)]
            mx.eval(*(a for b in self.buffers for a in b.arrays))
        values=[];positions=[]
        def compute(es,target,slotmap):
            rows=[];ranks=[];ss=[];segments=[]
            for e in es:
                segments.append((slotmap[e],len(pairs[e])))
                for row,rank in pairs[e]:rows.append(row);ranks.append(rank);ss.append(slotmap[e])
            ir=mx.array(rows,dtype=mx.int32);ik=mx.array(ranks,dtype=mx.int32)
            y=model.expert(flat[ir],target,mx.array(ss,dtype=mx.int32),weights[ir,ik],segments)
            mx.async_eval(y);values.append(y);positions.extend(r*k+s for r,s in zip(rows,ranks))
            return y
        if main:compute(main,bank,bank.main)
        groups=[cold[i:i+self.slots] for i in range(0,len(cold),self.slots)]
        for i,es in enumerate(groups):
            j=i%2;target=self.buffers[j]
            # Only this scratch's consumers must finish. Other scratch and Main
            # remain read-only and can execute while native preadv fills target.
            if self.pending[j] is not None:mx.eval(self.pending[j])
            t=time.perf_counter()
            count=native.preadv_fused_experts(bank.fd,0,bank.info['record_bytes'],[bank.records[e] for e in es],list(range(len(es))),*target.arrays,bank.workers)
            if count!=len(es)*bank.info['record_bytes']:raise IOError('prefill native byte count')
            self.report['read_bytes']+=count;self.report['io_seconds']+=time.perf_counter()-t
            self.pending[j]=compute(es,target,{e:s for s,e in enumerate(es)})
        mx.eval(*values)
        out=mx.zeros((flat.shape[0]*k,model.c.dim),dtype=mx.bfloat16)
        out[mx.array(positions,dtype=mx.int32)]=mx.concatenate(values)
        mx.eval(out)
        # Preserve the complete legacy final Hot working set, including survivors
        # from the penultimate group when the final group is shorter than Hot8.
        if cold:bank.prepare(cold[-model.hot_slots:])
        self.report['layers'].append(dict(layer=layer,required_unique=len(required),loaded_unique=len(cold),retained_routes=len(positions),total_routes=flat.shape[0]*k,groups=len(groups)+bool(main)))
        return out.reshape(flat.shape[0],k,model.c.dim)
    def release(self):
        for y in self.pending:
            if y is not None:mx.eval(y)
        self.pending=[None,None];self.buffers=None
