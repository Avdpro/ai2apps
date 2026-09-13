"""Single-layer fixed L1 + mutable L0, using original GLM/Qwen C++ preadv.
Replay prototype takes host routing IDs; a production device-only hit path is pending.
"""
import json
import os
from pathlib import Path
import sys
import time
import numpy as np
import mlx.core as mx
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'artifacts/dsv41-native-build'))
import _dsv41_loader as native

class MetalBank:
    def __init__(self,path,l1_ids,l0_slots=6,io_workers=4):
        self.info=json.loads(Path(str(path)+'.json').read_text())
        self.fd=os.open(path,os.O_RDONLY)
        self.records={int(k):v for k,v in self.info['expert_to_record'].items()}
        if len(l1_ids)!=len(set(l1_ids)): raise ValueError('duplicate L1 ids')
        self.main={e:i for i,e in enumerate(l1_ids)}; self.hot={}; self.l0_slots=l0_slots
        self.workers=io_workers; self.pending=[]; self.loads=self.bytes=0; self.io_seconds=0
        self.capacity=len(l1_ids)+l0_slots
        self.arrays=tuple(mx.zeros((self.capacity,*shape),dtype=mx.uint8) for shape in self.info['shapes'])
        mx.eval(*self.arrays);mx.synchronize()
        if native.abi_probe(self.arrays[0])!=self.arrays[0].size: raise RuntimeError('native ABI')
        self._load(l1_ids,list(range(len(l1_ids))))
    def _load(self,ids,slots):
        if not ids:return
        if len(set(slots))!=len(slots): raise ValueError('duplicate native destinations')
        # Materialize every lazy consumer before waiting; synchronize alone is insufficient.
        if self.pending: mx.eval(*self.pending)
        mx.synchronize(); self.pending.clear()
        start=time.perf_counter()
        count=native.preadv_fused_experts(self.fd,0,self.info['record_bytes'],[self.records[i] for i in ids],slots,*self.arrays,self.workers)
        self.io_seconds+=time.perf_counter()-start
        if count!=len(ids)*self.info['record_bytes']: raise IOError('native byte count mismatch')
        self.loads+=1; self.bytes+=count
    def prepare(self,ids):
        ids=list(dict.fromkeys(ids)); missing=[i for i in ids if i not in self.main and i not in self.hot]
        if len([i for i in ids if i not in self.main])>self.l0_slots:raise ValueError('route exceeds L0 capacity')
        used={self.hot[i] for i in ids if i in self.hot}
        free=[s for s in range(len(self.main),self.capacity) if s not in used]
        slots=free[:len(missing)]
        # Invalidate overwritten tags before I/O, and publish new IDs only on success.
        for e,s in list(self.hot.items()):
            if s in slots:del self.hot[e]
        self._load(missing,slots)
        self.hot.update(zip(missing,slots))
        return mx.array([self.main[i] if i in self.main else self.hot[i] for i in ids],dtype=mx.int32)
    def track(self,value):self.pending.append(value)
    def close(self):
        if self.pending:mx.eval(*self.pending)
        mx.synchronize();os.close(self.fd)
    def verify_bytes(self,store,layer):
        # Validation only: independent CPU extraction; not the runtime loading path.
        for e,s in {**self.main,**self.hot}.items():
            for array,(projection,part) in zip(self.arrays,[(w,p) for w in ('w1','w2','w3') for p in ('weight','scale')]):
                expected=store.read(f'layers.{layer}.ffn.experts.{e}.{projection}.{part}').view(__import__('torch').uint8).numpy()
                if not np.array_equal(np.array(array[s]),expected):raise AssertionError((e,projection,part))
