"""One graph and one encoding per token; resume after the actual missing Gate."""
import time
import mlx.core as mx
from guarded_model import arrays

def execute(self,h,pre,hashes,start):
    if self.predictor!='none' or self.resume_burst:
        raise ValueError('Capture validation initially requires exact Top6 without L2')
    self.records={};self.before_layers={};missed=set()
    self.resume_stats.setdefault('capture_replays',0)
    began=time.perf_counter();self.session.begin_replay()
    try:
        for j in range(self.c.n_layers):
            h,pre=self._layer(j,h,pre,hashes,start)
            if self.async_window:mx.async_eval(h,pre)
        logits=self.norm('norm',self.hc_pre(h,pre))[:,-1].astype(mx.float32)@self.w('head.weight',mx.float32).T
        roots=arrays((logits,self.states,self.shared,self.fast,self.slow,self.frequency,self.ages,self.cache_counters))
        roots += [v for bank in self.banks.values() for v in bank.pending]
        self.resume_stats['constructed_layers']+=self.c.n_layers
        self.resume_stats['build_seconds']+=time.perf_counter()-began
        mx.eval(*roots)
        self.session.seal_replay()
        status=self.session.finish()
        # Pending consumers are already captured; no bank operation may evaluate
        # the stopped suffix or drop the capture-owned buffer allocations.
        for bank in self.banks.values():bank.pending.clear()
        while True:
            self.resume_stats['submissions']+=1
            visits=self.session.visits()
            self.resume_stats['gpu_router_visits']+=sum(visits)
            if self.audit_gpu:
                phases=self.session.phases()
                self.resume_stats['gpu_layer_starts']+=sum(phases[:40])
                self.resume_stats['gpu_moe_completions']+=sum(phases[40:])
            failed=status[2]
            if failed<0:break
            if failed in missed:raise RuntimeError('repeated unresolved replay miss')
            missed.add(failed);self.resume_stats['misses']+=1
            bank=self.banks[failed];metadata=self.session.metadata(bank.capacity)
            host=status[4:10];age=metadata[:bank.capacity];rank=metadata[bank.capacity:bank.capacity+384]
            needed=metadata[bank.capacity+384:bank.capacity+390];before=metadata[bank.capacity+390:bank.capacity+396]
            requested=[e for e,must,slot in zip(host,needed,before) if must or slot>=0]
            bank.hot=dict(sorted(bank.hot.items(),key=lambda pair:age[pair[1]]))
            before_io=bank.io_seconds
            self.prepare_miss(failed,bank,requested,rank)
            self.decode_io[failed]=self.decode_io.get(failed,0)+bank.io_seconds-before_io
            self.stats['decode_host_ids']+=len(host)
            mapping=[-1]*self.c.n_routed_experts
            for e,slot in {**bank.main,**bank.hot}.items():mapping[e]=slot
            # Future tokens see the replacement map. The already encoded current
            # MoE reads the six shared slot integers patched by continue_replay.
            self.lookups[failed]=mx.array(mapping,dtype=mx.int32)
            status=self.session.continue_replay(failed,[mapping[e] for e in host])
            self.resume_stats['capture_replays']+=1
        self.resume_stats['replay_seconds']=sum(self.session.replay_times())
        self.resume_stats['completed_layers']+=self.c.n_layers
        self.stats['route_requests']+=self.c.n_layers*6
        self.stats['all_hit_steps']+=self.c.n_layers-len(missed)
        return logits
    finally:
        cleanup_began=time.perf_counter()
        self.session.release_replay()
        self.resume_stats['capture_cleanup_seconds']=self.resume_stats.get('capture_cleanup_seconds',0.)+time.perf_counter()-cleanup_began
