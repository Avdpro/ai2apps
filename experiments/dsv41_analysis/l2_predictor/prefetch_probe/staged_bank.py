"""Isolated LRU bank: eight physical staging slots excluded from logical L0.
Derived from this repository frozen v4 cache bank; original prepare logic retained.
"""
"""Logical L1 plus bounded LRU L0; native loader and lazy-consumer fence unchanged."""
import mlx.core as mx
from metal_bank import MetalBank

class StagedBank(MetalBank):
    def __init__(self,path,l1_ids,l0_slots=24,io_workers=4,no_cache=False):
        super().__init__(path,l1_ids,l0_slots+8,io_workers,no_cache=no_cache)
        self.l0_slots=l0_slots
        self.reserved=set(range(self.capacity-8,self.capacity))
        self.hits=self.misses=self.evictions=0
        self.slot_swaps=0;self.dynamic_roles=False

    def prepare(self,ids,promotion_scores=None,slot_swap=False):
        ids=list(dict.fromkeys(ids))
        if any(i not in self.records for i in ids):raise KeyError('unknown expert')
        requested=set(ids)
        if len(requested-self.main.keys())>self.l0_slots:raise ValueError('route exceeds L0 capacity')
        missing=[i for i in ids if i not in self.main and i not in self.hot]
        self.hits+=len(ids)-len(missing);self.misses+=len(missing)
        occupied=set(self.hot.values())
        free=[s for s in range(self.capacity) if s not in occupied and s not in self.main.values() and s not in self.reserved]
        victims=[(e,s) for e,s in self.hot.items() if e not in requested]
        slots=free[:len(missing)]
        evicted=victims[:len(missing)-len(slots)]
        if promotion_scores is not None and missing:
            candidates=sorted(evicted,key=lambda p:(-promotion_scores[p[0]],p[0]))
            old=sorted((e for e in self.main if e not in requested),key=lambda e:(promotion_scores[e],e))
            pairs=[(e,v,self.main[v],source) for (e,source),v in zip(candidates[:4],old[:4])
                   if promotion_scores[e]>=3 and promotion_scores[e]>promotion_scores[v]+2]
            slots.extend(s for e,s in evicted)
            # Slot exchange leaves the promoted payload in place. The miss writes
            # into the evicted Main slot instead of overwriting the promoted Hot.
            if slot_swap:
                redirects={source:dest for e,v,dest,source in pairs}
                slots=[redirects.get(s,s) for s in slots]
            # The same existing miss fence protects all overwritten slots.
            self._fence()
            if pairs and not slot_swap:self._copy_ready([p[3] for p in pairs],[p[2] for p in pairs])
            self._read_ready(missing,slots)
            for e,v,dest,source in pairs:
                del self.main[v];self.main[e]=source if slot_swap else dest
            for e,s in evicted:del self.hot[e]
            self.evictions+=len(evicted)
            self.hot.update(zip(missing,slots))
            for e in ids:
                if e in self.hot:self.hot[e]=self.hot.pop(e)
            self.last_eviction_promotions=[p[:3] for p in pairs]
            if slot_swap:
                self.dynamic_roles=True;self.slot_swaps+=len(pairs)
            return mx.array([self.main[e] if e in self.main else self.hot[e] for e in ids],dtype=mx.int32)
        for e,s in evicted:
            del self.hot[e];slots.append(s);self.evictions+=1
        # _load materializes lazy consumers before any write. Failed destinations
        # stay unpublished; evicted tags are already invalid.
        self._load(missing,slots)
        self.hot.update(zip(missing,slots))
        for e in ids:
            if e in self.hot:self.hot[e]=self.hot.pop(e)
        return mx.array([self.main[e] if e in self.main else self.hot[e] for e in ids],dtype=mx.int32)
