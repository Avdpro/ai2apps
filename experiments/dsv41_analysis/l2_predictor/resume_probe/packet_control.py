"""Native-dispatch miss boundary for the frequent-miss regime.

One packet read per layer, including IDs/ages/ranks only when loading is needed.
No speculative suffix, state snapshots, donation restriction or ICB dispatch.
"""
import os
import mlx.core as mx
from adaptive import AdaptiveModel
import _l2_resume as native


class PacketMixin:
    def __init__(self,*args,resume_mode='auto',**kw):
        if resume_mode not in ('auto','packet','guarded','window','resume'):raise ValueError('invalid resume mode')
        self.force_window=os.environ.get('DSV41_WINDOW_FORCE','0')=='1'
        self.window_ready=False
        self.resume_mode=resume_mode
        super().__init__(*args,**kw)
        self.resume_stats.update(packet_tokens=0,guarded_tokens=0,window_tokens=0,packet_checks=0,packet_misses=0,native_tail_tokens=0)

    def __call__(self,ids,start=0):
        if not start:return super().__call__(ids,start)
        if ids.shape!=(1,1) or self.l1_policy!='eviction_dual':raise ValueError('single-token eviction_dual required')
        # Guarded dispatch has not passed the high-hit performance gate. Auto
        # keeps native packets; explicit guarded and transition tests remain.
        before_misses=self.resume_stats['misses']
        if self.choose_guarded(start):
            y=super().__call__(ids,start)
            self.resume_stats['window_tokens' if self.native_window else 'guarded_tokens']+=1
        else:
            y=self.packet_forward(ids,start) if self.scheduler else AdaptiveModel.__call__(self,ids,start)
            self.resume_stats['packet_tokens']+=1
        if self.resume_mode=='window':
            # Admission uses observed required-miss layers, never a stress flag.
            # Cold/low-hit requests pay only the native packet boundary.
            self.window_ready=(self.resume_stats['misses']-before_misses)<=2
        return y

    def choose_guarded(self,start):
        if os.environ.get('L2_DIAGNOSTIC_WINDOW_ONCE')=='1' and not getattr(self,'diagnostic_window_done',False):
            self.diagnostic_window_done=True
            return True
        return self.resume_mode in ('guarded','resume') or (self.resume_mode=='window' and (self.force_window or self.window_ready))

    def native_tail(self,first,h,pre,hashes,start):
        # Reuse the original layer forward, with this mixin's packet MoE. The
        # failed layer's attention is already committed and is not visited here.
        from burst import BurstModel
        for l in range(first,self.c.n_layers):
            if self.scheduler:self.packet_layer_begin(l,h,pre,hashes,start)
            h,pre=BurstModel.layer(self,l,h,pre,hashes,start)
        logits=self.norm('norm',self.hc_pre(h,pre))[:,-1].astype(mx.float32)@self.w('head.weight',mx.float32).T
        mx.eval(*self.frequency.values(),*self.fast.values(),*self.slow.values(),*self.recent.values())
        return logits

    def moe(self,l,x,start):
        if not start:return AdaptiveModel.moe(self,l,x,start)
        c=self.c;bank=self.banks[l];p=f'layers.{l}.ffn.gate';flat=x.reshape(-1,c.dim)
        scores=(flat.astype(mx.float32)@self.w(p+'.weight',mx.float32).T)/c.gate_temp
        scores=mx.sqrt(mx.logaddexp(scores,mx.array(0.,dtype=mx.float32)))
        ranked=mx.argsort(scores+self.w(p+'.bias'),axis=-1)[...,-6:][...,::-1]
        weights=mx.take_along_axis(scores,ranked,axis=-1)
        weights=weights/(mx.sum(weights,axis=-1,keepdims=True)+1e-20)*c.route_scale
        order=mx.argsort(ranked,axis=-1)
        ids=mx.take_along_axis(ranked,order,axis=-1)[0]
        weights=mx.take_along_axis(weights,order,axis=-1)[0]
        if l not in self.lookups:
            mapping=[-1]*c.n_routed_experts
            for e,s in {**bank.main,**bank.hot}.items():mapping[e]=s
            self.lookups[l]=mx.array(mapping,dtype=mx.int32)
            ages=[0]*bank.capacity
            for age,slot in enumerate(bank.hot.values()):ages[slot]=age+1
            self.ages[l]=mx.array(ages,dtype=mx.int32);self.ticks[l]=bank.capacity
        # Natural promotes after observing the route; Burst uses the previous rank.
        if not self.resume_burst:self.observe(l,ids)
        rank=.75*self.fast[l]*(32*(1-2**(-1/8)))+.25*self.slow[l]*(32*(1-2**(-1/64)))
        required=(order[0]<self.resume_burst).astype(mx.int32) if self.resume_burst else mx.array([1]*6,dtype=mx.int32)
        if self.ticks[l]+6>=2**24:raise RuntimeError('packed cache ages exceed float32 range')
        if self.scheduler and self.predictor=='lookahead':
            self.packet_prediction=True
            try:self.predict_lookahead(l,x.reshape(-1,c.dim)[-1]) if l<39 else None
            finally:self.packet_prediction=False
        self.session.begin_packet()
        try:
            mapped=native.probe(self.session,ids.astype(mx.int32),self.lookups[l],l,self.ages[l],rank,required)
            mx.eval(mapped,*self.token_dependencies) if self.scheduler else mx.eval(mapped)
        except BaseException:
            mx.synchronize();self.session.finish();raise
        status=self.session.finish()
        if self.scheduler:self.l2_window_end(l,l+1,status,self.session.used_staging())
        self.resume_stats['packet_checks']+=1;self.resume_stats['submissions']+=1
        self.cache_counters[l]=self.cache_counters[l]+self.route_cache_counts(l,mapped)
        before_io=bank.io_seconds
        if status[2]>=0:
            if status[2]!=l:raise RuntimeError('wrong packet layer')
            self.resume_stats['packet_misses']+=1;self.resume_stats['misses']+=1
            host=status[4:10];meta=self.session.metadata(bank.capacity)
            ages=meta[:bank.capacity];rank_host=meta[bank.capacity:bank.capacity+384]
            needed=meta[bank.capacity+384:bank.capacity+390];before=meta[bank.capacity+390:bank.capacity+396]
            requested=[e for e,must,s in zip(host,needed,before) if must or s>=0]
            bank.hot=dict(sorted(bank.hot.items(),key=lambda pair:ages[pair[1]]))
            self.prepare_miss(l,bank,requested,rank_host)
            mapping=[-1]*c.n_routed_experts
            for e,s in {**bank.main,**bank.hot}.items():mapping[e]=s
            self.l2_augment(l,mapping)
            self.lookups[l]=mx.array(mapping,dtype=mx.int32)
            slots=mx.array([mapping[e] for e in host],dtype=mx.int32)
            self.stats['decode_host_ids']+=6
        else:
            slots=mapped;self.stats['all_hit_steps']+=1
        self.decode_io[l]=self.decode_io.get(l,0)+bank.io_seconds-before_io
        if self.resume_burst:self.observe(l,ids)
        valid=slots>=0;safe=mx.maximum(slots,0) if self.resume_burst else slots
        out=self.expert(mx.broadcast_to(flat,(6,c.dim)),bank,safe,weights)[None]
        if self.resume_burst:out=mx.where(valid[None,:,None],out,mx.zeros_like(out))
        bank.track(out)
        self.ticks[l]+=6;updates=self.ticks[l]+mx.arange(6,dtype=mx.int32)
        if self.resume_burst:
            mask=(mx.arange(bank.capacity)[:,None]==slots[None,:])&valid[None,:]
            self.ages[l]=mx.max(mx.where(mask,updates[None,:],self.ages[l][:,None]),axis=1)
        else:self.ages[l][slots]=updates
        self.stats['route_requests']+=6;self.resume_stats['completed_layers']+=1
        y=mx.zeros((1,c.dim),dtype=mx.float32)
        for i in range(6):y=y+out[:,i,:].astype(mx.float32)
        return (y.reshape(x.shape)+self.shared_expert(l,x)).astype(x.dtype)
