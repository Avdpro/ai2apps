"""Bounded dynamic L1 policy; the underlying tensor forward is unchanged."""
import mlx.core as mx
from model import Model

class AdaptiveModel(Model):
    def __init__(self,*args,**kwargs):
        self.reuse_hot_promotions=kwargs.pop('reuse_hot_promotions',True)
        self.l1_policy="eviction_dual"
        self.slot_swap_promotions=True
        self.fast={};self.slow={};self.recent={};self.protected={};self.role_swaps=0
        self.dynamic=True
        self.frequency={};self.decode_step=0;self.promotions=[];self.decode_io={}
        super().__init__(*args,**kwargs)
    def observe(self,layer,ids):
        if self.l1_policy!='eviction_dual':self.frequency[layer][ids]=self.frequency[layer][ids]+1
        if self.l1_policy!='baseline':
            self.fast[layer]=self.fast[layer]*(2**(-1/8))
            self.slow[layer]=self.slow[layer]*(2**(-1/64))
            self.fast[layer][ids]=self.fast[layer][ids]+1
            self.slow[layer][ids]=self.slow[layer][ids]+1
            if self.l1_policy=='probation32_8':
                self.recent[layer][(self.decode_step-1)%32]=ids
    def emit(self,name,x):
        if name.endswith('.gate'):
            layer=int(name.split('.')[1])
            if self.decode_step:self.observe(layer,x[0])
            else:
                self.frequency[layer]=mx.sum(x[...,None]==mx.arange(self.c.n_routed_experts),axis=(0,1)).astype(mx.float32)*(12/x.shape[0])
                if self.l1_policy!='baseline':
                    self.fast[layer]=self.frequency[layer]/(32*(1-2**(-1/8)))
                    self.slow[layer]=self.frequency[layer]/(32*(1-2**(-1/64)))
                    self.recent[layer]=mx.full((32,self.c.n_activated_experts),-1,dtype=mx.int32)
        return super().emit(name,x)
    def miss_metadata(self,l,ids):
        if self.l1_policy!='eviction_dual':return super().miss_metadata(l,ids)
        if self.ticks[l]+self.c.n_activated_experts>=2**24:raise RuntimeError('packed cache ages exceed exact float32 integer range')
        # Replace the existing IDs and ages readbacks with ONE packed readback.
        rank=.75*self.fast[l]*(32*(1-2**(-1/8)))+.25*self.slow[l]*(32*(1-2**(-1/64)))
        packed=mx.concatenate([ids.astype(mx.float32),self.ages[l].astype(mx.float32),rank]).tolist()
        n=ids.size;k=self.banks[l].capacity
        return [int(v) for v in packed[:n]],[int(v) for v in packed[n:n+k]],packed[n+k:]
    def prepare_miss(self,l,bank,host,scores):
        if self.l1_policy!='eviction_dual':return super().prepare_miss(l,bank,host,scores)
        slots=bank.prepare(host,promotion_scores=scores,slot_swap=self.slot_swap_promotions)
        self.refresh_slot_roles(l,bank)
        pairs=getattr(bank,'last_eviction_promotions',[])
        if pairs:self.promotions.append(dict(step=self.decode_step,layer=l,pairs=pairs))
        return slots
    def maintain(self,layer,bank):
        if self.l1_policy=='eviction_dual':return
        interval=16 if self.l1_policy=='baseline' else 8
        if not self.dynamic or self.decode_step<=1 or (self.decode_step-1)%interval:return
        main=dict(bank.main)
        if self.l1_policy=='baseline':scores=self.frequency[layer].tolist()
        else:scores=(.75*self.fast[layer]*(32*(1-2**(-1/8)))+.25*self.slow[layer]*(32*(1-2**(-1/64)))).tolist()
        threshold=2
        if self.l1_policy=='probation32_8':
            protected=self.protected.setdefault(layer,set(list(main)[:-8]))
            trial=sorted(set(main)-protected,key=lambda e:(-scores[e],e))
            old=sorted(protected,key=lambda e:(scores[e],e))
            for new,victim in zip(trial[:4],old[:4]):
                if scores[new]>scores[victim]+2:
                    protected.remove(victim);protected.add(new);self.role_swaps+=1
            recent=mx.sum(self.recent[layer][...,None]==mx.arange(self.c.n_routed_experts),axis=(0,1)).tolist()
            candidates=sorted((e for e in bank.hot if recent[e]>=2),key=lambda e:(-scores[e],e))
            victims=sorted(set(main)-protected,key=lambda e:(scores[e],e));threshold=1
        else:
            candidates=sorted((e for e in range(self.c.n_routed_experts) if e not in main),key=lambda e:(-scores[e],e))
            victims=sorted(main,key=lambda e:(scores[e],e))
        pairs=[(new,old,main[old]) for new,old in zip(candidates[:4],victims[:4]) if scores[new]>=3 and scores[new]>scores[old]+threshold]
        if pairs:
            self.promote_payload(bank,pairs)
            for new,old,slot in pairs:
                del bank.main[old];bank.main[new]=slot;bank.hot.pop(new,None)
            mapping=[-1]*self.c.n_routed_experts
            for e,slot in {**bank.main,**bank.hot}.items():mapping[e]=slot
            self.lookups[layer]=mx.array(mapping,dtype=mx.int32)
            self.promotions.append(dict(step=self.decode_step,layer=layer,pairs=pairs))
        if self.l1_policy=='baseline':self.frequency[layer]=self.frequency[layer]*.5
    def promote_payload(self,bank,pairs):
        if self.reuse_hot_promotions:
            return bank.load_promotions([p[0] for p in pairs],[p[2] for p in pairs])
        bank._load([p[0] for p in pairs],[p[2] for p in pairs])
    def moe(self,layer,x,start):
        bank=self.banks.get(layer);before=bank.io_seconds if bank else 0
        self.maintain(layer,bank)
        y=super().moe(layer,x,start)
        if start:
            self.decode_io[layer]=self.decode_io.get(layer,0)+self.banks[layer].io_seconds-before
        return y
    def __call__(self,ids,start=0):
        if start:self.decode_step+=1
        y=super().__call__(ids,start)
        mx.eval(*self.frequency.values(),*self.fast.values(),*self.slow.values(),*self.recent.values())
        return y
    def close(self):
        mx.eval(self.cache_counters)
        self.adaptive_report=dict(enabled=True,interval=16,max_promotions_per_layer=4,decay=.5,hysteresis=2,per_layer_counts=self.cache_counters.tolist(),decode_io_seconds=self.decode_io,promotions=self.promotions)
        self.adaptive_report.update(policy=self.l1_policy,interval=16 if self.l1_policy=='baseline' else 8,role_swaps=self.role_swaps)
        if self.l1_policy!='baseline':
            self.adaptive_report.update(decay=None,half_lives=[8,64],fast_weight=.75,hysteresis=1 if self.l1_policy=='probation32_8' else 2,trial_slots=8 if self.l1_policy=='probation32_8' else 0)
        if self.l1_policy=='eviction_dual':self.adaptive_report.update(interval=None,trigger='L0 eviction',trial_slots=0,maintenance_readbacks=0,promotion_extra_fences=0)
        self.adaptive_report['slot_swap_promotions']={'enabled':self.l1_policy=='eviction_dual' and self.slot_swap_promotions,'experts':sum(b.slot_swaps for b in self.banks.values())}
        self.adaptive_report['bank_fence_calls']=sum(b.fence_calls for b in self.banks.values())
        self.adaptive_report['promotion_reuse']={'enabled':self.reuse_hot_promotions,'copied_experts':sum(b.copy_experts for b in self.banks.values()),'copied_bytes':sum(b.copy_bytes for b in self.banks.values()),'copy_seconds':sum(b.copy_seconds for b in self.banks.values()),'per_layer':{str(l):{'copied_experts':b.copy_experts,'copied_bytes':b.copy_bytes,'copy_seconds':b.copy_seconds} for l,b in self.banks.items()}}
        super().close()
