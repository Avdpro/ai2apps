"""Diagnostic only: replay ONE real token/state with all six experts resident.

Cache preparation, snapshot restoration and verification are outside timing.
This is a submission-overhead ceiling, NOT end-to-end generation TPS or L2 TPS.
"""
import importlib.util,sys,os,json,time,hashlib
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[3];here=Path(__file__).parent
sys.path[:0]=[str(root/'experiments/dsv41_mlx'),str(here),str(root/'artifacts/dsv41-miss-resume-native-build')]
import mlx.core as mx
from adaptive import AdaptiveModel
from model import Model
from packet import PacketMixin
spec=importlib.util.spec_from_file_location('isolated_controller',here/'model.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
import run
work=Path(os.environ['DSV41_ISOLATION_OUT']);work.mkdir(parents=True,exist_ok=True)
class Probe(PacketMixin,mod.MissResumeModel):
    kind='legacy';group=40;testing=False
    def prepare_miss(self,*a,**kw):
        if self.testing:raise RuntimeError('unexpected miss in all-hit replay')
        return super().prepare_miss(*a,**kw)
    def routes_all_hit(self,l,ids,mapped,required=None):
        if self.kind in ('chain','async-chain'):return True
        return Model.routes_all_hit(self,l,ids,mapped,required)
    def moe(self,l,x,start):
        if self.kind in ('legacy','chain','async-chain'):return AdaptiveModel.moe(self,l,x,start)
        return PacketMixin.moe(self,l,x,start)
    def emit(self,name,x):
        out=super().emit(name,x)
        if self.testing and self.kind in ('chain','async-chain') and name.startswith('layers.') and name.count('.')==1:
            layer=int(name.split('.')[1])
            if (layer+1)%self.group==0 and layer+1<self.c.n_layers:
                (mx.async_eval if self.kind=='async-chain' else mx.eval)(x)
        return out
    def __call__(self,ids,start=0):
        if not start:return AdaptiveModel.__call__(self,ids,start)
        # Warm the actual token through the unmodified natural forward, loading
        # its real six experts per layer. No replacement is permitted thereafter.
        core=mod.snapshot_tree((self.states,self.shared,self.fast,self.slow,self.frequency,self.hash.cache))
        reference=AdaptiveModel.__call__(self,ids,start);mx.eval(reference,self.cache_counters,*self.ages.values())
        ref=np.array(reference.astype(mx.float32));banks={l:(dict(b.main),dict(b.hot)) for l,b in self.banks.items()}
        cache=mod.snapshot_tree((self.ages,self.ticks));base_step=self.decode_step
        self.testing=True;records=[]
        configs=[('legacy',1),('packet',1),('chain',1),('chain',2),('chain',4),('chain',40),('async-chain',1),('async-chain',2),('async-chain',4),('window',2),('window',4),('window',40),('guarded',4),('guarded',40)]
        def restore():
            self.states,self.shared,self.fast,self.slow,self.frequency,self.hash.cache=mod.snapshot_tree(core)
            self.ages,self.ticks=mod.snapshot_tree(cache);self.decode_step=base_step
            self.cache_counters=mx.zeros((self.c.n_layers,3),dtype=mx.uint32)
            for b in self.banks.values():b.pending.clear()
            mx.eval(*mod.arrays((self.states,self.shared,self.fast,self.slow,self.frequency,self.hash.cache,self.ages,self.cache_counters)))
        def once(kind,group,round_,sample):
            restore();self.kind=kind;self.group=group;self.native_window=kind=='window';self.resume_block=group
            self.local_roots=True;self.defer_counters=True;self.defer_route_stats=True;self.native_prefix=True
            before_io=sum(b.bytes for b in self.banks.values());before_sub=self.resume_stats['submissions']
            t=time.perf_counter()
            y=mod.MissResumeModel.__call__(self,ids,start) if kind in ('window','guarded') else AdaptiveModel.__call__(self,ids,start)
            mx.eval(y,self.cache_counters,*self.ages.values())
            # Match the public runner's final finite check and token readback.
            finite=bool(mx.all(mx.isfinite(y)).item());token=int(mx.argmax(y,axis=-1).item())
            elapsed=time.perf_counter()-t
            exact=np.array_equal(np.array(y.astype(mx.float32)),ref)
            misses=int(mx.sum(self.cache_counters[:,2]).item());read=sum(b.bytes for b in self.banks.values())-before_io
            assert finite and exact and misses==0 and read==0,(kind,group,exact,misses,read)
            assert banks=={l:(dict(b.main),dict(b.hot)) for l,b in self.banks.items()}
            records.append(dict(kind=kind,block=group,round=round_,sample=sample,seconds=elapsed,exact=True,misses=misses,ssd_bytes=read,submissions=self.resume_stats['submissions']-before_sub))
        # Warm each execution shape, then interleave forward/reverse orders.
        for kind,group in configs:
            for i in range(2):once(kind,group,-1,i)
        for round_ in range(4):
            for kind,group in configs if round_%2==0 else configs[::-1]:
                for i in range(3):once(kind,group,round_,i)
        result=[]
        for kind,group in configs:
            vals=[r['seconds'] for r in records if r['kind']==kind and r['block']==group and r['round']>=0]
            result.append(dict(kind=kind,block=group,samples=len(vals),median_ms=float(np.median(vals)*1000),p25_ms=float(np.percentile(vals,25)*1000),p75_ms=float(np.percentile(vals,75)*1000),mean_ms=float(np.mean(vals)*1000)))
        report=dict(diagnostic='same-token all-hit replay; cache preparation excluded; not generation TPS',position=start,token=int(ids[0,0].item()),results=result,records=records)
        (work/'isolation.json').write_text(json.dumps(report,indent=2));print(json.dumps(result,indent=2),flush=True)
        restore();self.kind='legacy';y=AdaptiveModel.__call__(self,ids,start);mx.eval(y,self.cache_counters,*self.ages.values());return y
run.model_factory=lambda args:(Probe,dict(resume_mode='packet',resume_burst=0,resume_block=4))
run.main()

# The outer runner includes the complete diagnostic sweep in its one Decode.
# Mark its receipt so no benchmark consumer mistakes that for generation TPS.
receipt_path=Path(sys.argv[sys.argv.index("--output")+1])/"manifest.json"
data=json.loads(receipt_path.read_text());data["diagnostic"]="fixed-token all-hit replay";data["step_seconds_not_generation_tps"]=True
receipt_path.write_text(json.dumps(data,indent=2))
