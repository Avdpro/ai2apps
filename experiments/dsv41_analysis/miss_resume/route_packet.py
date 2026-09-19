"""Replace only the old host boundary, preserving the selected model's forward.

Works with StaticModel, AdaptiveModel and sequential BurstModel. Observations,
periodic maintenance, tail policies, diagnostics and vision stay in those models.
"""
import mlx.core as mx
import _miss_resume as native

if not hasattr(native,'probe') or not hasattr(native.Session,'begin_packet'):
    raise RuntimeError('Rebuild the native packet backend: .venv/bin/python experiments/dsv41_analysis/miss_resume/build.py')

class RoutePacketMixin:
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        if self.c.n_routed_experts!=384 or self.c.n_activated_experts!=6:raise ValueError('DS4.1F 384/Top6 required')
        self.packet_session=native.Session();self.packet_metadata={}
        self.resume_stats=dict(submissions=0,misses=0,completed_layers=0,attention_replays=0,
                               packet_checks=0,packet_misses=0,packet_tokens=0,guarded_tokens=0)
    def __call__(self,ids,start=0):
        y=super().__call__(ids,start)
        if start:self.resume_stats['packet_tokens']+=1
        return y
    def routes_all_hit(self,l,ids,mapped,required=None):
        bank=self.banks[l]
        if self.ticks[l]+6>=2**24:raise RuntimeError('packed cache ages exceed float32 range')
        rank=(.75*self.fast[l]*(32*(1-2**(-1/8)))+.25*self.slow[l]*(32*(1-2**(-1/64)))) if getattr(self,'l1_policy',None)=='eviction_dual' else mx.zeros((384,),dtype=mx.float32)
        if required is None:required=mx.ones((6,),dtype=mx.int32)
        session=self.packet_session;session.begin_packet()
        try:
            slots=native.probe(session,ids.astype(mx.int32),self.lookups[l],l,self.ages[l],rank,required.astype(mx.int32))
            mx.eval(slots)
        except BaseException:
            mx.synchronize();session.finish();raise
        status=session.finish();self.packet_metadata.pop(l,None)
        for key in ('submissions','completed_layers','packet_checks'):self.resume_stats[key]+=1
        if status[2]<0:return True
        if status[2]!=l:raise RuntimeError('wrong miss packet layer')
        self.resume_stats['misses']+=1;self.resume_stats['packet_misses']+=1
        meta=session.metadata(bank.capacity)
        scores=meta[bank.capacity:bank.capacity+384] if getattr(self,'l1_policy',None)=='eviction_dual' else None
        self.packet_metadata[l]=(status[4:10],[bool(v) for v in meta[bank.capacity+384:bank.capacity+390]],
                                 [int(v) for v in meta[bank.capacity+390:bank.capacity+396]],
                                 [int(v) for v in meta[:bank.capacity]],scores)
        return False
    def miss_metadata(self,l,ids):
        host,required,mapped,ages,scores=self.packet_metadata.pop(l)
        return host,ages,scores
    def burst_miss_metadata(self,l,ids,required,mapped):
        return self.packet_metadata.pop(l)
