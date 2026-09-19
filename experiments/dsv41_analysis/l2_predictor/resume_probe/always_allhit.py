"""One-token all-hit executor diagnostic; preparation excluded from timing."""
import os,sys,json,time,statistics
from pathlib import Path
repo=Path(__file__).resolve().parents[4]
frozen=repo/os.environ.get('L2_ALLHIT_SOURCE','artifacts/dsv41-l2-always-resume-v1-20260917/source/resume_probe')
sys.path[:0]=[str(frozen),str(repo/"experiments/dsv41_mlx")]
import run_driver as run
original_main=run.main;run.main=lambda:None
import entry
run.main=original_main
import mlx.core as mx
import numpy as np
from guarded_model import snapshot_tree,arrays
os.environ['L2_WINDOW_PREDICTOR']='none'
os.environ.pop('L2_DIAGNOSTIC_WINDOW_ONCE',None)
os.environ['DSV41_WINDOW_FORCE']='0'
class Probe(entry.L2WindowModel):
    testing=False
    def prepare_miss(self,*a,**kw):
        if self.testing:raise RuntimeError('unexpected all-hit miss')
        return super().prepare_miss(*a,**kw)
    def __call__(self,ids,start=0):
        if not start:return super().__call__(ids,start)
        mx.eval(*arrays((self.states,self.shared,self.fast,self.slow,self.frequency,self.hash.cache)))
        core=snapshot_tree((self.states,self.shared,self.fast,self.slow,self.frequency,self.hash.cache))
        self.resume_mode='packet'
        ref=super().__call__(ids,start)
        mx.eval(ref,*arrays((self.states,self.shared,self.fast,self.slow,self.ages,self.cache_counters)))
        expected=np.array(ref)
        cache=snapshot_tree((self.ages,self.ticks));step=self.decode_step
        banks={l:(dict(b.main),dict(b.hot)) for l,b in self.banks.items()}
        self.testing=True;records=[]
        def restore():
            self.states,self.shared,self.fast,self.slow,self.frequency,self.hash.cache=snapshot_tree(core)
            self.ages,self.ticks=snapshot_tree(cache);self.decode_step=step
            self.cache_counters=mx.zeros((40,3),mx.uint32)
            for bank in self.banks.values():bank.pending.clear()
            mx.eval(*arrays((self.states,self.shared,self.fast,self.slow,self.frequency,self.hash.cache,self.ages,self.cache_counters)))
        for round_ in range(6):
            for block in ([1,2,4,40] if round_%2==0 else [40,4,2,1]):
                restore();self.resume_block=block;self.resume_mode='packet' if block==1 else 'resume';self.window_ready=True
                before=self.resume_stats['submissions'];before_packet=self.resume_stats['packet_checks'];before_io=sum(b.bytes for b in self.banks.values())
                t=time.perf_counter();y=super().__call__(ids,start)
                mx.eval(y,self.cache_counters,*self.ages.values(),*arrays((self.states,self.shared)))
                finite=bool(mx.all(mx.isfinite(y)).item());token=int(mx.argmax(y,axis=-1).item())
                elapsed=time.perf_counter()-t
                if block>1:assert self.resume_stats['packet_checks']==before_packet
                assert finite and np.array_equal(np.array(y),expected)
                assert int(mx.sum(self.cache_counters[:,2]).item())==0
                assert sum(b.bytes for b in self.banks.values())==before_io
                assert banks=={l:(dict(b.main),dict(b.hot)) for l,b in self.banks.items()}
                records.append(dict(round=round_,block=block,seconds=elapsed,submissions=self.resume_stats['submissions']-before,exact=True,ssd_bytes=0))
        result={str(b):dict(median_ms=1000*statistics.median(v['seconds'] for v in records if v['block']==b and v['round']>=2),samples=4) for b in (1,2,4,40)}
        Path(os.environ['L2_WINDOW_OUTPUT'],'allhit.json').write_text(json.dumps(dict(scope='Same token replay, preparation excluded, not generation TPS',results=result,records=records),indent=2))
        restore();self.testing=False;self.resume_mode='packet';return super().__call__(ids,start)
def factory(args):
    os.environ['L2_WINDOW_OUTPUT']=str(args.output)
    return Probe,dict(resume_mode='packet',resume_block=2,resume_burst=0)
run.model_factory=factory
run.main()
p=Path(os.environ['L2_WINDOW_OUTPUT'],'manifest.json');d=json.loads(p.read_text());d['step_seconds_not_generation_tps']=True;p.write_text(json.dumps(d,indent=2))
