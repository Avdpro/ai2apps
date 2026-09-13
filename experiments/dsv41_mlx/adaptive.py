"""Bounded dynamic L1 policy; the underlying tensor forward is unchanged."""
import mlx.core as mx
from model import Model

class AdaptiveModel(Model):
    def __init__(self,*args,**kwargs):
        self.dynamic=True
        self.frequency={};self.decode_step=0;self.promotions=[];self.decode_io={}
        super().__init__(*args,**kwargs)
    def emit(self,name,x):
        if name.endswith('.gate'):
            layer=int(name.split('.')[1])
            if self.decode_step:
                self.frequency[layer][x[0]]=self.frequency[layer][x[0]]+1
            else:
                # Modest prior; never allow a long Prefill to dominate later Decode.
                self.frequency[layer]=mx.sum(x[...,None]==mx.arange(self.c.n_routed_experts),axis=(0,1)).astype(mx.float32)*(12/x.shape[0])
        return super().emit(name,x)
    def moe(self,layer,x,start):
        bank=self.banks.get(layer);before=bank.io_seconds if bank else 0
        if self.dynamic and self.decode_step>1 and (self.decode_step-1)%16==0:
            scores=self.frequency[layer].tolist();main=dict(bank.main)
            candidates=sorted((e for e in range(self.c.n_routed_experts) if e not in main),key=lambda e:(-scores[e],e))
            victims=sorted(main,key=lambda e:(scores[e],e));pairs=[]
            for new,old in zip(candidates[:4],victims[:4]):
                if scores[new]>=3 and scores[new]>scores[old]+2:pairs.append((new,old,main[old]))
            if pairs:
                # _load fences every lazy consumer before overwriting native storage.
                bank._load([p[0] for p in pairs],[p[2] for p in pairs])
                for new,old,slot in pairs:
                    del bank.main[old];bank.main[new]=slot;bank.hot.pop(new,None)
                mapping=[-1]*self.c.n_routed_experts
                for e,s in {**bank.main,**bank.hot}.items():mapping[e]=s
                self.lookups[layer]=mx.array(mapping,dtype=mx.int32)
                self.promotions.append(dict(step=self.decode_step,layer=layer,pairs=pairs))
            self.frequency[layer]=self.frequency[layer]*.5
        y=super().moe(layer,x,start)
        if start:
            self.decode_io[layer]=self.decode_io.get(layer,0)+self.banks[layer].io_seconds-before
        return y
    def __call__(self,ids,start=0):
        if start:self.decode_step+=1
        y=super().__call__(ids,start)
        mx.eval(*self.frequency.values())
        return y
    def close(self):
        mx.eval(self.cache_counters)
        self.adaptive_report=dict(enabled=True,interval=16,max_promotions_per_layer=4,decay=.5,hysteresis=2,per_layer_counts=self.cache_counters.tolist(),decode_io_seconds=self.decode_io,promotions=self.promotions)
        super().close()

