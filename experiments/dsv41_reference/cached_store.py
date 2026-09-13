"""Bounded original-byte caches; no changes to model arithmetic or execution order."""
from collections import OrderedDict
import re
import torch
from run_reference import Store

class CachedStore(Store):
    def __init__(self, root, experts_per_layer=8, dense_bytes=2*2**30, row_bytes=8*2**20):
        super().__init__(root)
        self.experts_per_layer=experts_per_layer
        self.dense_limit=dense_bytes; self.row_limit=row_bytes
        self.layers={}; self.dense={}; self.rows=OrderedDict()
        self.expert_bytes=self.dense_bytes=self.row_bytes=0
        self.stats=dict(expert_hits=0,expert_misses=0,expert_evictions=0,dense_hits=0,row_hits=0,row_misses=0,row_evictions=0)
        self.peak_bytes=0
    def _peak(self):
        self.peak_bytes=max(self.peak_bytes,self.expert_bytes+self.dense_bytes+self.row_bytes)
    @staticmethod
    def size(x): return x.numel()*x.element_size()
    def read(self,name,rows=None):
        if rows is not None:
            shape=self.entries[name][2]['shape']
            ids=rows.flatten().tolist()
            if any(i<0 or i>=shape[0] for i in ids): raise IndexError(name)
            result=[]
            for i in ids:
                key=(name,i)
                if key in self.rows:
                    self.stats['row_hits']+=1
                    value=self.rows.pop(key); self.rows[key]=value
                else:
                    self.stats['row_misses']+=1
                    value=super().read(name,torch.tensor([i],dtype=torch.long))[0]
                    size=self.size(value)
                    if size<=self.row_limit:
                        while self.rows and self.row_bytes+size>self.row_limit:
                            _,old=self.rows.popitem(last=False); self.row_bytes-=self.size(old); self.stats['row_evictions']+=1
                        self.rows[key]=value; self.row_bytes+=size; self._peak()
                result.append(value.view(torch.uint8))
            return torch.stack(result).view(value.dtype).reshape(*rows.shape,*shape[1:])
        match=re.fullmatch(r'(layers\.\d+\.ffn\.experts)\.(\d+)\.(w[123])\.(weight|scale)',name)
        if match and self.experts_per_layer:
            layer,expert=match.group(1),match.group(2)
            bank=self.layers.setdefault(layer,OrderedDict())
            if expert in bank:
                self.stats['expert_hits']+=1
                record=bank.pop(expert); bank[expert]=record
            else:
                self.stats['expert_misses']+=1
                if len(bank)>=self.experts_per_layer:
                    _,old=bank.popitem(last=False)
                    self.expert_bytes-=sum(self.size(v) for v in old.values()); self.stats['expert_evictions']+=1
                # Publish a complete six-segment expert only after all reads succeed.
                record={}
                for projection in ('w1','w2','w3'):
                    for part in ('weight','scale'):
                        key=f'{layer}.{expert}.{projection}.{part}'
                        record[key]=super().read(key)
                bank[expert]=record
                self.expert_bytes+=sum(self.size(v) for v in record.values()); self._peak()
            return record[name]
        if not match:
            if name in self.dense:
                self.stats['dense_hits']+=1; return self.dense[name]
            value=super().read(name)
            size=self.size(value)
            # Admission-only dense cache avoids cyclic layer-order LRU thrashing.
            if self.dense_bytes+size<=self.dense_limit:
                self.dense[name]=value; self.dense_bytes+=size; self._peak()
            return value
        return super().read(name)
    def summary(self):
        return dict(self.stats,expert_cache_bytes=self.expert_bytes,dense_cache_bytes=self.dense_bytes,
                    row_cache_bytes=self.row_bytes,peak_cache_payload_bytes=self.peak_bytes,
                    experts_per_layer=self.experts_per_layer,dense_limit=self.dense_limit,row_limit=self.row_limit,
                    read_bytes=self.bytes,read_calls=self.reads)
