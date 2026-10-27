"""Bounded, model-wide double scratch; native reads overlap disjoint GPU consumers."""
import time
from types import SimpleNamespace
import mlx.core as mx
from omlx.custom_kernels.glm_moe_dsa import fast as native

class Prefill:
    def __init__(self,slots,top=None,hot_direct=True,reuse_hot=False,retain_routes=False,lazy_scratch=False,defer_completion=False,overlap_hot=False):
        self.overlap_hot=overlap_hot
        self.defer_completion=defer_completion
        self.lazy_scratch=lazy_scratch
        self.retain_routes=retain_routes
        self.reuse_hot=reuse_hot
        self.hot_direct=hot_direct;self.slots=slots;self.top=top;self.buffers=None;self.pending=[None,None]
        self.report=dict(layers=[],read_bytes=0,io_seconds=0)
    def dispatch(self,model,layer,flat,ids,weights,bank,scores,on_io_ready=None):
        dispatch_started=time.perf_counter()
        timing=dict(submit_seconds=0.,scratch_wait_seconds=0.,drain_wait_seconds=0.,hot_handoff_seconds=0.,assembly_seconds=0.)
        if getattr(self,'profile_route_input',False):
            waited=time.perf_counter();mx.eval(flat)
            timing['route_input_wait_seconds']=time.perf_counter()-waited
        waited=time.perf_counter();mx.eval(ids,weights)
        timing['route_ready_seconds']=time.perf_counter()-waited
        timing['scratch_read_seconds']=0.
        bank_io_before=getattr(bank,'io_seconds',0.)
        waited=time.perf_counter();host=ids.tolist()
        timing['route_host_seconds']=time.perf_counter()-waited
        independent_pending=on_io_ready
        def launch_independent():
            nonlocal independent_pending
            if independent_pending is not None:
                submitted=time.perf_counter();independent_pending()
                timing['independent_submit_seconds']=time.perf_counter()-submitted
                independent_pending=None
        planned=time.perf_counter()
        k=ids.shape[-1];resident=set(bank.main)|set(bank.hot)
        required=set()
        if self.top:
            ranked=mx.argsort(scores+model.w(f'layers.{layer}.ffn.gate.bias'),axis=-1)[:,-self.top:]
            mx.eval(ranked);required={e for row in ranked.tolist() for e in row}
        else:required={e for row in host for e in row}
        keep=resident|required;pairs={}
        for row,es in enumerate(host):
            for rank,e in enumerate(es):
                if e in keep:pairs.setdefault(e,[]).append((row,rank))
        resident_map={**bank.main,**bank.hot} if self.reuse_hot else bank.main
        main=[e for e in sorted(pairs) if e in resident_map]
        cold=[e for e in sorted(pairs) if e not in resident_map]
        if self.buffers is None:
            self.buffers=[None,None]
            if not self.lazy_scratch:
                for j in range(2):self.allocate_scratch(j,bank)
        values=[];positions=[]
        def compute(es,target,slotmap):
            submitted=time.perf_counter()
            rows=[];ranks=[];ss=[];segments=[]
            for e in es:
                segments.append((slotmap[e],len(pairs[e])))
                for row,rank in pairs[e]:rows.append(row);ranks.append(rank);ss.append(slotmap[e])
            ir=mx.array(rows,dtype=mx.int32);ik=mx.array(ranks,dtype=mx.int32)
            y=model.expert(flat[ir],target,mx.array(ss,dtype=mx.int32),weights[ir,ik],segments)
            if self.defer_completion and target is bank:bank.track(y)
            mx.async_eval(y);values.append(y);positions.extend(r*k+s for r,s in zip(rows,ranks))
            timing['submit_seconds']+=time.perf_counter()-submitted
            return y
        tail=cold[-model.hot_slots:] if self.hot_direct else []
        streamed=cold[:-len(tail)] if tail else cold
        retained=None
        if self.retain_routes and self.reuse_hot and self.hot_direct:
            # Early candidate rows survive rejection more often. Retain useful
            # existing Hot entries too, rather than evicting them for every miss.
            ranked=sorted((e for e in pairs if e not in bank.main),
                          key=lambda e:(-sum(.7**row for row,_ in pairs[e]),e))
            retained=ranked[:model.hot_slots]
            tail=[e for e in retained if e not in resident_map]
            streamed=[e for e in cold if e not in set(tail)]
        # Only Main and explicitly retained Hot slots are immutable during the
        # upcoming load. Consume evictable Hot before the bank fence; launch
        # immutable consumers after that fence, alongside disjoint native writes.
        overlap=[e for e in main if e in bank.main or e in (retained or [])] if self.overlap_hot and tail else []
        early=[e for e in main if e not in set(overlap)]
        timing['route_plan_seconds']=time.perf_counter()-planned
        if early:compute(early,bank,resident_map)
        groups=[streamed[i:i+self.slots] for i in range(0,len(streamed),self.slots)]
        for i,es in enumerate(groups):
            j=i%2
            if self.buffers[j] is None:self.allocate_scratch(j,bank)
            target=self.buffers[j]
            # Only this scratch's consumers must finish. Other scratch and Main
            # remain read-only and can execute while native preadv fills target.
            waited=time.perf_counter()
            if self.pending[j] is not None:mx.eval(self.pending[j])
            timing['scratch_wait_seconds']+=time.perf_counter()-waited
            launch_independent()
            t=time.perf_counter()
            count=native.preadv_fused_experts(bank.fd,0,bank.info['record_bytes'],[bank.records[e] for e in es],list(range(len(es))),*target.arrays,bank.workers)
            if count!=len(es)*bank.info['record_bytes']:raise IOError('prefill native byte count')
            elapsed=time.perf_counter()-t
            self.report['read_bytes']+=count;self.report['io_seconds']+=elapsed
            timing['scratch_read_seconds']+=elapsed
            self.pending[j]=compute(es,target,{e:s for s,e in enumerate(es)})
        waited=time.perf_counter()
        if tail or not self.defer_completion:mx.eval(*values)
        timing['drain_wait_seconds']+=time.perf_counter()-waited
        if tail:
            # All Main/scratch consumers are complete before writing legacy Hot.
            # Load these experts once, and calculate their contributions in Hot.
            handed=time.perf_counter()
            if overlap or independent_pending is not None:
                def launch_immutable(write_slots):
                    if set(write_slots)&{resident_map[e] for e in overlap}:
                        raise RuntimeError('overlap would read overwritten expert slots')
                    launch_independent()
                    if overlap:compute(overlap,bank,resident_map)
                bank.prepare(retained if retained is not None else tail,on_read_ready=launch_immutable)
            else:bank.prepare(retained if retained is not None else tail)
            timing['hot_handoff_seconds']+=time.perf_counter()-handed
            compute(tail,bank,bank.hot)
            waited=time.perf_counter()
            if not self.defer_completion:mx.eval(values[-1])
            timing['drain_wait_seconds']+=time.perf_counter()-waited
        assembled=time.perf_counter()
        out=mx.zeros((flat.shape[0]*k,model.c.dim),dtype=mx.bfloat16)
        out[mx.array(positions,dtype=mx.int32)]=mx.concatenate(values)
        if self.defer_completion:mx.async_eval(out)
        else:mx.eval(out)
        timing['assembly_seconds']=time.perf_counter()-assembled
        # Preserve the complete legacy final Hot working set, including survivors
        # from the penultimate group when the final group is shorter than Hot8.
        if cold and not self.hot_direct:
            handed=time.perf_counter();bank.prepare(cold[-model.hot_slots:])
            timing['hot_handoff_seconds']+=time.perf_counter()-handed
        timing['dispatch_wall_seconds']=time.perf_counter()-dispatch_started
        timing['hot_read_seconds']=getattr(bank,'io_seconds',0.)-bank_io_before
        self.report['layers'].append(dict(layer=layer,required_unique=len(required),loaded_unique=len(cold),retained_routes=len(positions),total_routes=flat.shape[0]*k,groups=len(groups)+bool(main)+bool(tail),hot_direct=self.hot_direct,hot_experts=list(bank.hot),timing=timing))
        return out.reshape(flat.shape[0],k,model.c.dim)
    def allocate_scratch(self,j,bank):
        # Instance-owned arrays avoid a dynamic class/MRO cycle retaining GPU
        # buffers until Python's cyclic collector happens to run.
        self.buffers[j]=SimpleNamespace(arrays=tuple(mx.zeros((self.slots,*shape),dtype=mx.uint8) for shape in bank.info['shapes']))
        mx.eval(*self.buffers[j].arrays)
    def release(self):
        for y in self.pending:
            if y is not None:mx.eval(y)
        self.pending=[None,None];self.buffers=None
