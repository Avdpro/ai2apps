"""Fixed L1 plus bounded LRU L0; native loader and lazy-consumer fence unchanged."""
import mlx.core as mx
from metal_bank import MetalBank

class LRUMetalBank(MetalBank):
    def __init__(self,path,l1_ids,l0_slots=24,io_workers=4):
        super().__init__(path,l1_ids,l0_slots,io_workers)
        self.hits=self.misses=self.evictions=0

    def prepare(self,ids):
        ids=list(dict.fromkeys(ids))
        if any(i not in self.records for i in ids):raise KeyError('unknown expert')
        requested=set(ids)
        if len(requested-self.main.keys())>self.l0_slots:raise ValueError('route exceeds L0 capacity')
        missing=[i for i in ids if i not in self.main and i not in self.hot]
        self.hits+=len(ids)-len(missing);self.misses+=len(missing)
        occupied=set(self.hot.values())
        free=[s for s in range(len(self.main),self.capacity) if s not in occupied]
        victims=[(e,s) for e,s in self.hot.items() if e not in requested]
        slots=free[:len(missing)]
        for e,s in victims[:len(missing)-len(slots)]:
            del self.hot[e];slots.append(s);self.evictions+=1
        # _load materializes lazy consumers before any write. Failed destinations
        # stay unpublished; evicted tags are already invalid.
        self._load(missing,slots)
        self.hot.update(zip(missing,slots))
        for e in ids:
            if e in self.hot:self.hot[e]=self.hot.pop(e)
        return mx.array([self.main[e] if e in self.main else self.hot[e] for e in ids],dtype=mx.int32)
