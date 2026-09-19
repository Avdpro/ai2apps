"""Isolated L2 publication to guarded GPU windows; experimental, default off."""
import json
import os
from pathlib import Path
import sys
import time

repo=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(repo/'experiments/dsv41_mlx'))
sys.path.insert(0,str(repo/'experiments/dsv41_analysis/l2_predictor/v2'))
sys.path.insert(0,str(repo/'artifacts/dsv41-l2-async-mailbox-build'))
import mlx.core as mx
import run_driver as run
import model
from burst import BurstModel
from guarded_model import MissResumeModel,snapshot_tree
from packet_control import PacketMixin
import _l2_resume as native
from scheduler import WindowScheduler
from train_state import StateHead
from train_router_lookahead import PerLayerCorrection
import importlib.util
spec=importlib.util.spec_from_file_location('l2_staged_bank',repo/'experiments/dsv41_analysis/l2_predictor/prefetch_probe/staged_bank.py')
bank_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(bank_module)
model.LRUMetalBank=bank_module.StagedBank


class L2WindowModel(PacketMixin,MissResumeModel):
    def __init__(self,*args,**kw):
        self.predictor=os.environ.get('L2_WINDOW_PREDICTOR','none')
        self.notice_policy=os.environ.get('L2_WINDOW_NOTICE','packet')
        assert self.notice_policy in ('packet','credit')
        assert self.predictor in ('none','state','lookahead','block6')
        self.predicting=False;self.ffn={};self.final_hidden=None;self.predictions={};self.layer_outputs={}
        self.scheduler=None;self.published={};self.history=[];self.box=native.Mailbox()
        super().__init__(*args,**kw)
        self.gpu_windows=[];self.profile=os.environ.get('L2_TRACE_SCHEDULER')=='1';self.session.set_profile(self.profile)
        assert all(b.capacity==56 and b.reserved==set(range(48,56)) for b in self.banks.values())
        self.head=None
        root=repo/'artifacts/dsv41-l2-state-v3-20260916'
        if self.predictor=='state':
            self.head=StateHead(512);self.head.load_weights(str(root/'extended-r512/model.safetensors'))
        elif self.predictor=='lookahead':
            self.head=PerLayerCorrection(39,64);self.head.load_weights(str(root/'lookahead-full-extended-r64/model.safetensors'))
            self.ratios=[]
            for l in range(39):
                a=self.w(f'layers.{l}.ffn_norm.weight',mx.float32);b=self.w(f'layers.{l+1}.ffn_norm.weight',mx.float32)
                self.ratios.append(b/mx.where(mx.abs(a)>1e-6,a,mx.ones_like(a)))
            import numpy as np
            with np.load(root/'lookahead-full-extended-r64/priority/priority-policy.npz') as z:
                self.policy={k:mx.array(z[k]) for k in z.files}

    def norm(self,name,x):
        result=super().norm(name,x)
        if not self.predicting:
            if name.endswith('.ffn_norm'):self.ffn[int(name.split('.')[1])]=result.reshape(-1,self.c.dim)[-1]
            elif name=='norm':self.final_hidden=result.reshape(-1,self.c.dim)[-1]
        return result

    def moe(self,l,x,start):
        if not self.predicting:return super().moe(l,x,start)
        p=f'layers.{l}.ffn.gate';flat=x.reshape(-1,self.c.dim)
        score=mx.sqrt(mx.logaddexp((flat.astype(mx.float32)@self.w(p+'.weight',mx.float32).T)/self.c.gate_temp,0))
        rank=score+self.w(p+'.bias');self.predictions[l]=rank[0]
        ids=mx.argsort(rank,axis=-1)[0,-6:][::-1]
        weights=score[0,ids];weights=weights/(mx.sum(weights)+1e-20)*self.c.route_scale
        order=mx.argsort(ids);ids=ids[order];weights=weights[order]
        slots=self.lookups[l][ids];valid=slots>=0
        values=self.expert(mx.broadcast_to(flat,(6,self.c.dim)),self.banks[l],mx.maximum(slots,0),weights)
        values=mx.where(valid[:,None],values,mx.zeros_like(values));self.banks[l].track(values)
        y=mx.zeros((1,self.c.dim),mx.float32)
        for i in range(6):y=y+values[i:i+1].astype(mx.float32)
        return (y.reshape(x.shape)+self.shared_expert(l,x)).astype(x.dtype)

    def _compute_moe(self,l,r,slots):
        if not self.predicting:self.ffn[l]=r['x'].reshape(-1,self.c.dim)[-1]
        result=super()._compute_moe(l,r,slots)
        if os.environ.get('L2_VERIFY_LAYERS')=='1':self.layer_outputs[l]=result[0]
        if self.predictor=='lookahead' and self.scheduler and self.credits>0 and l<39:
            self.predict_lookahead(l,r['x'].reshape(-1,self.c.dim)[-1])
        return result

    def predict_lookahead(self,l,source):
        import mlx.nn as nn
        x=source.astype(mx.float32)[None];m=self.head
        def norm(a):return a*mx.rsqrt(mx.mean(a*a,axis=-1,keepdims=True)+1e-6)
        base=x*self.ratios[l]
        hidden=nn.gelu(norm(x)@m.local[l]+m.token(norm(self.embedding))[None]+m.previous(norm(self.previous_hidden))[None]+m.layer[l])
        pred=base+(hidden@m.out[l]+m.bias[l])*mx.sqrt(mx.mean(base*base,axis=-1,keepdims=True)+1e-6)
        p=f'layers.{l+1}.ffn.gate'
        score=mx.sqrt(mx.maximum(mx.logaddexp(pred@self.w(p+'.weight',mx.float32).T,0),1e-20))+self.w(p+'.bias')
        ids=mx.argsort(score[0])[-12:][::-1];rank=score[0,ids];gap=rank-rank[5]
        cells=mx.sum(gap[:,None]>self.policy['edges'][None,:],axis=-1).astype(mx.int32)
        probs=self.policy['prob'][l+1,mx.arange(12),cells]
        order=mx.argsort(probs)[::-1];ids=ids[order];probs=probs[order]
        reserve=self.policy['future_better'][l+1,mx.minimum((probs*100).astype(mx.int32),100)]
        with self.scheduler.cv:remaining=64-self.scheduler.spent
        codes=mx.where(remaining>1.25*reserve,ids+(l+1)*384,mx.array(-2,mx.int32))
        if getattr(self,"packet_prediction",False):
            self.token_dependencies=(*self.token_dependencies,native.export_proposals(self.session,codes.astype(mx.int32).reshape(-1)))
        else:self.submit(codes,source=l)

    def submit(self,codes,source=-1):
        if self.credits<1:return False
        self.credits-=1
        packet=native.notify(self.box,codes.astype(mx.int32).reshape(-1),self.decode_step,self.session,source)
        self.notices.append(packet);mx.async_eval(packet)
        self.scheduler.event('notice_submitted',count=codes.size)
        return True

    def l2_augment(self,l,mapping):
        for e,slot in self.published.get(l,{}).items():
            if mapping[e]<0:mapping[e]=slot

    def l2_window_begin(self,first,end,h,pre,hashes,start,pending):
        if not self.scheduler:return
        publish_end=max(end,min(first+6,40)) if self.predictor=="block6" and first>=self.next_predict else end
        for l,bank in self.banks.items():
            if l<first or l>=publish_end:continue
            self.published[l]=self.scheduler.snapshot(l) if self.scheduler else {}
            mapping=[-1]*384
            for e,slot in {**bank.main,**bank.hot}.items():mapping[e]=slot
            self.l2_augment(l,mapping);self.lookups[l]=mx.array(mapping,dtype=mx.int32)
        if self.scheduler:self.scheduler.event('ready_snapshot',first=first,end=end,ready=sum(len(v) for l,v in self.published.items() if l>=first))
        if not self.scheduler or first>=40:return
        if self.predictor=='state' and not self.state_sent:
            resident=mx.stack([(self.lookups[l]>=0).astype(mx.float32) for l in range(40)])[None]
            scores=self.head(self.previous_ffn[None],self.embedding[None],self.previous_hidden[None],resident)[0]
            eligible=mx.arange(40)[:,None]>=first
            scores=mx.where((resident[0]==0)&eligible,scores,-mx.inf)
            codes=mx.argsort(scores.reshape(-1))[-64:][::-1].astype(mx.int32)
            self.token_dependencies=(*self.token_dependencies,native.export_proposals(self.session,codes.astype(mx.int32).reshape(-1)))
            self.state_sent=True
        elif self.predictor=='block6' and first>=self.next_predict and (self.notice_policy=='packet' or self.credits>0):
            import copy
            probe=copy.copy(self)
            probe.states,probe.shared=snapshot_tree((self.states,self.shared))
            probe.predicting=True;probe.predictions={}
            try:
                ah,ap=h,pre
                for l in range(first,min(first+6,40)):ah,ap=BurstModel.layer(probe,l,ah,ap,hashes,start)
                codes=mx.concatenate([mx.argsort(probe.predictions[l])[-6:][::-1]+l*384 for l in sorted(probe.predictions)])
                mx.async_eval(ah,ap,*probe.predictions.values())
                if self.notice_policy=='packet':
                    self.token_dependencies=(*self.token_dependencies,native.export_proposals(self.session,codes.astype(mx.int32)))
                else:self.submit(codes)
                self.next_predict=min(first+6,40)
            finally:probe.predicting=False

    def l2_window_end(self,first,end,status,usage):
        if not self.scheduler:return
        failed=status[2];checked=(end-first) if failed<0 else (failed-first+1)
        self.credits+=max(checked-1,0);self.checked+=checked
        if self.scheduler:self.scheduler.close_layers(first,end if failed<0 else failed+1,usage)
        proposals=self.session.proposals()
        if proposals:
            self.scheduler.enqueue_packet(proposals);self.host_packets+=1
        if self.profile:self.gpu_windows.append(dict(step=self.decode_step,first=first,end=end,failed=failed,host_finished=time.perf_counter(),gpu_times=self.session.gpu_times()))

    def prepare_miss(self,l,bank,host,scores):
        # READY slots remain separate L2 capacity, never evicted or overwritten by L0.
        ready=self.published.get(l,{})
        requested=[e for e in host if e not in ready or e in bank.main or e in bank.hot]
        return super().prepare_miss(l,bank,requested,scores)

    def __call__(self,ids,start=0):
        if not start or self.predictor=="none":return super().__call__(ids,start)
        if os.environ.get('L2_VERIFY_STATE_ROOTS')=='1':
            from guarded_model import arrays
            mx.eval(*arrays((self.states,self.shared)))
        # Previous-token staging slots are about to be recycled. Global-head
        # resident features must not include their expired READY tags.
        self.published={}
        for l,bank in self.banks.items():
            mapping=[-1]*384
            for e,slot in {**bank.main,**bank.hot}.items():mapping[e]=slot
            self.lookups[l]=mx.array(mapping,dtype=mx.int32)
            if l not in self.ages:
                age=[0]*bank.capacity
                for t,slot in enumerate(bank.hot.values()):age[slot]=t+1
                self.ages[l]=mx.array(age,dtype=mx.int32);self.ticks[l]=bank.capacity
        self.token_dependencies=()
        began=time.perf_counter();self.previous_ffn=mx.stack([self.ffn[l] for l in range(40)]).astype(mx.float32)
        self.previous_hidden=self.final_hidden.astype(mx.float32)
        self.embedding=self.s.embedding('embed',ids).reshape(-1,self.c.dim)[-1].astype(mx.float32)
        self.notices=[];self.credits=0;self.checked=0;self.state_sent=False;self.host_packets=0;self.next_predict=0
        if self.scheduler is None and self.predictor!='none':
            self.scheduler=WindowScheduler(self,self.box)
            for l,bank in self.banks.items():
                original=bank._read_ready
                bank._read_ready=lambda ids,slots,l=l,original=original:self.scheduler.read(l,ids,slots,original)
        if self.scheduler:self.scheduler.begin(self.decode_step+1)
        before=self.resume_stats['submissions']
        logits=super().__call__(ids,start)
        if self.notices:mx.eval(*self.notices)
        if self.scheduler:self.scheduler.finish(len(self.notices)+self.host_packets)
        if os.environ.get('L2_VERIFY_LAYERS')=='1':
            mx.save_safetensors(str(Path(os.environ['L2_WINDOW_OUTPUT'])/f'layers-{self.decode_step}.safetensors'),{str(k):v for k,v in self.layer_outputs.items()})
        submissions=self.resume_stats['submissions']-before
        # Final head-only continuation may contribute one boundary beyond the40 routers.
        assert submissions+len(self.notices)<=41,(submissions,len(self.notices))
        self.history.append(dict(step=self.decode_step,submissions=submissions,notices=len(self.notices),host_packets=self.host_packets,checked=self.checked,seconds=time.perf_counter()-began))
        return logits

    def packet_forward(self,ids,start):
        self.decode_step+=1;self.image_mask=None
        hashes=self.hash(ids,start)
        h=mx.repeat(self.s.embedding('embed',ids)[:,:,None,:],self.c.hc_mult,axis=2)
        pre=mx.zeros(h.shape[:-1],dtype=mx.float32);pre[:,:,0]=1.
        return self.native_tail(0,h,pre,hashes,start)

    def packet_layer_begin(self,l,h,pre,hashes,start):
        # This runs only at an existing safe packet boundary, before its graph.
        self.token_dependencies=()
        self.l2_window_begin(l,l+1,h,pre,hashes,start,None)

    def close(self):
        if self.scheduler:self.scheduler.close()
        Path(os.environ['L2_WINDOW_OUTPUT'],'l2-window.json').write_text(json.dumps(dict(predictor=self.predictor,notice_policy=self.notice_policy,history=self.history,stats=self.resume_stats,tokens=self.scheduler.tokens if self.scheduler else [],events=self.scheduler.events if self.scheduler else [],reads=self.scheduler.reads if self.scheduler else [],gpu_windows=self.gpu_windows,scope='Window-boundary READY publication; L2 is separate token-local capacity; routing cache policy differs from no-L2'),indent=2))
        super().close()


def factory(args):
    os.environ['L2_WINDOW_OUTPUT']=str(args.output)
    executor=os.environ.get('L2_WINDOW_EXECUTOR','resume')
    if executor=='resume' or executor.startswith('window'):
        os.environ['DSV41_NATIVE_WINDOW']='0'
        os.environ['DSV41_NATIVE_PREFIX']='1'
        for name in ('DSV41_LOCAL_ROOTS','DSV41_DEFER_COUNTERS','DSV41_DEFER_ROUTE_STATS','DSV41_ASYNC_WINDOW'):
            os.environ.setdefault(name,'1')
        mode='resume'
    else:mode='packet' if executor=='packet' else 'guarded' if executor=='guarded' else 'window'
    cls=L2WindowModel
    if os.environ.get('DSV41_RESUME_STRESS_ALL_MISS')=='1':
        # Existing diagnostic invalidates real cache tags, not fake miss flags.
        sys.path.insert(0,str(repo/'experiments/dsv41_analysis/miss_resume'))
        from stress import AllMissStress
        class StressModel(AllMissStress,L2WindowModel):pass
        cls=StressModel
    return cls,dict(resume_mode=mode,resume_block=int(os.environ.get('L2_WINDOW_BLOCK','40')),resume_burst=args.burst_top or 0)


run.model_factory=factory
run.main()
