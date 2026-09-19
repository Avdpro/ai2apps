"""Diagnostic route collection; device arrays cross only at completed step boundaries."""
import json
import time
import numpy as np
import mlx.core as mx

def captured_model(base, output):
    class Captured(base):
        def __init__(self,*args,**kwargs):
            self.route_pending={};self.route_steps=[];self.capture_events=[];self.capture_initial=None
            self.capture_overhead=0.;self.read_events=[];self.copy_events=[]
            super().__init__(*args,**kwargs)
        def emit(self,name,x):
            if name.endswith('.gate'):self.route_pending[int(name.split('.')[1])]=x
            return super().emit(name,x)
        def __call__(self,ids,start=0):
            y=super().__call__(ids,start)
            mx.eval(y,self.cache_counters,*self.ages.values())
            began=time.perf_counter()
            routes=mx.stack([self.route_pending[l] for l in range(self.c.n_layers)])
            self.route_steps.append(np.array(routes).astype(np.uint16));self.route_pending.clear()
            if not start:
                self.capture_initial={str(l):{'main':list(b.main.items()),'hot':list(b.hot.items())} for l,b in self.banks.items()}
                for l,b in self.banks.items():
                    original=b._read_ready
                    def read(experts,slots,original=original,layer=l):
                        if experts:self.read_events.append({'layer':layer,'experts':list(experts),'slots':list(slots)})
                        return original(experts,slots)
                    b._read_ready=read
                    original_copy=b._copy_ready
                    def copy(sources,slots,original=original_copy,layer=l):
                        if sources:self.copy_events.append({'layer':layer,'sources':list(sources),'slots':list(slots)})
                        return original(sources,slots)
                    b._copy_ready=copy
            else:
                self.capture_events.append({'step':self.decode_step,'counts':self.cache_counters.tolist(),'reads':self.read_events,'copies':self.copy_events})
                self.read_events=[];self.copy_events=[]
            self.capture_overhead+=time.perf_counter()-began
            return y
        def close(self):
            if self.route_steps:
                np.savez_compressed(output/'routes.npz',prefill=self.route_steps[0],decode=np.stack(self.route_steps[1:]) if len(self.route_steps)>1 else np.empty((0,self.c.n_layers,1,6),dtype=np.uint16))
                (output/'routes.json').write_text(json.dumps({'initial':self.capture_initial,'events':self.capture_events,'collector_boundary_seconds':self.capture_overhead,'route_bytes':sum(a.nbytes for a in self.route_steps)},separators=(',',':')))
            super().close()
    return Captured
