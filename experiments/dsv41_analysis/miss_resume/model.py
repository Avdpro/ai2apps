"""Experimental GPU-predicated Decode. Requires the isolated patched MLX build.

No default Runtime integration. Single request/stream; natural Top6 initially.
A miss resumes the current FFN from its retained router and HC tensors.
"""
import sys,os,time
from pathlib import Path
import mlx.core as mx
from adaptive import AdaptiveModel
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'artifacts/dsv41-miss-resume-native-build'))
import _miss_resume as native


def snapshot_tree(v,memo=None):
    # Independent array handles, with no lazy GPU copy hidden in the checkpoint.
    if memo is None:memo={}
    if id(v) in memo:return memo[id(v)]
    if isinstance(v,mx.array):out=native.retain(v)
    elif isinstance(v,dict):
        out={};memo[id(v)]=out
        out.update((k,snapshot_tree(x,memo)) for k,x in v.items());return out
    elif isinstance(v,list):out=[snapshot_tree(x,memo) for x in v]
    elif isinstance(v,tuple):out=tuple(snapshot_tree(x,memo) for x in v)
    else:return v
    memo[id(v)]=out;return out


def arrays(v):
    if isinstance(v,mx.array):return [v]
    if isinstance(v,dict):return [a for x in v.values() for a in arrays(x)]
    if isinstance(v,(tuple,list)):return [a for x in v for a in arrays(x)]
    return []


class MissResumeModel(AdaptiveModel):
    def __init__(self,*args,**kw):
        self.async_window=os.environ.get('DSV41_ASYNC_WINDOW','0')=='1'
        self.local_roots=os.environ.get('DSV41_LOCAL_ROOTS','0')=='1'
        self.defer_route_stats=os.environ.get('DSV41_DEFER_ROUTE_STATS','0')=='1'
        self.defer_counters=os.environ.get('DSV41_DEFER_COUNTERS','0')=='1'
        self.adaptive_windows=os.environ.get('DSV41_ADAPTIVE_WINDOWS','0')=='1'
        self.native_window=os.environ.get('DSV41_NATIVE_WINDOW','0')=='1'
        self.native_prefix=os.environ.get('DSV41_NATIVE_PREFIX','1')=='1'
        self.local_checkpoints=os.environ.get('DSV41_LOCAL_CHECKPOINTS','1')=='1'
        self.resume_block=int(kw.pop('resume_block',4))
        self.resume_burst=int(kw.pop('resume_burst',0))
        if self.native_window and not self.resume_burst:raise ValueError('native speculative windows require Burst safe slots')
        if self.resume_burst not in (0,2,4):raise ValueError('natural/Top2/Top4 only')
        if self.resume_block not in (1,2,4,40):raise ValueError('block must be 1/2/4/40')
        super().__init__(*args,**kw)
        if self.c.n_routed_experts!=384 or self.c.n_activated_experts!=6:raise ValueError('DS4.1F 384/Top6 layout required')
        self.session=native.Session()
        self.resume_stats=dict(submissions=0,misses=0,completed_layers=0,attention_replays=0,window_histogram={},miss_layer_histogram={},constructed_layers=0,build_seconds=0.,eval_seconds=0.)

    def _metadata_snapshot(self):
        return snapshot_tree((self.fast,self.slow,self.frequency,self.ages,self.ticks,self.cache_counters))

    def _local_metadata(self,l):
        return snapshot_tree(tuple(getattr(self,k)[l] for k in ('fast','slow','frequency','ages','ticks')))

    def _restore_local_metadata(self,l,values):
        for k,v in zip(('fast','slow','frequency','ages','ticks'),values):getattr(self,k)[l]=v

    def _compute_moe(self,l,r,slots):
        c=self.c;bank=self.banks[l];flat=r['x'].reshape(-1,c.dim)
        valid=slots>=0
        safe=mx.maximum(slots,0) if self.resume_burst else slots
        out=self.expert(mx.broadcast_to(flat,(6,c.dim)),bank,safe,r['weights'][0])[None]
        if self.resume_burst:out=mx.where(valid[None,:,None],out,mx.zeros_like(out))
        bank.track(out)
        y=mx.zeros((1,c.dim),dtype=mx.float32)
        for rank in range(6):y=y+out[:,rank,:].astype(mx.float32)
        y=(y.reshape(r['x'].shape)+self.shared_expert(l,r['x'])).astype(r['x'].dtype)
        self.ticks[l]+=6
        updates=self.ticks[l]+mx.arange(6,dtype=mx.int32)
        if self.resume_burst:
            mask=(mx.arange(bank.capacity)[:,None]==slots[None,:])&valid[None,:]
            self.ages[l]=mx.max(mx.where(mask,updates[None,:],self.ages[l][:,None]),axis=1)
        else:self.ages[l][slots]=updates
        self.cache_counters[l]=self.cache_counters[l]+r['counts']
        self.prefix_dependencies=(self.ages[l],self.fast[l],self.slow[l]) if self.defer_counters else (self.ages[l],self.fast[l],self.slow[l],self.cache_counters)
        h=self.hc_post(y,r['residual'],r['post'],r['comb'])
        return h,r['pre']

    def _layer(self,l,h,pre,hashes,start):
        c=self.c;p=f'layers.{l}'
        if self.local_checkpoints:
            self.before_layers[l]=(snapshot_tree(self.states[l]),self._local_metadata(l))
        if l in c.engram_layer_ids:h=self.engram(l,h,hashes[:,:,c.engram_layer_ids.index(l),:])
        residual=h;attn_pre,attn_post,attn_comb=self.hc_mixes(p,h,'attn')
        x=self.norm(p+'.attn_norm',self.hc_pre(h,pre));x=self.attention(l,x,start)
        h=self.hc_post(x,residual,attn_post,attn_comb)
        residual=h;ffn_pre,ffn_post,ffn_comb=self.hc_mixes(p,h,'ffn')
        x=self.norm(p+'.ffn_norm',self.hc_pre(h,attn_pre))
        flat=x.reshape(-1,c.dim);gate=p+'.ffn.gate'
        scores=mx.sqrt(mx.logaddexp((flat.astype(mx.float32)@self.w(gate+'.weight',mx.float32).T)/c.gate_temp,mx.array(0.,dtype=mx.float32)))
        ids=mx.argsort(scores+self.w(gate+'.bias'),axis=-1)[...,-6:][...,::-1]
        weights=mx.take_along_axis(scores,ids,axis=-1);weights=weights/(mx.sum(weights,axis=-1,keepdims=True)+1e-20)*c.route_scale
        order=mx.argsort(ids,axis=-1);ids=mx.take_along_axis(ids,order,axis=-1);weights=mx.take_along_axis(weights,order,axis=-1)
        prior_rank=.75*self.fast[l]*(32*(1-2**(-1/8)))+.25*self.slow[l]*(32*(1-2**(-1/64))) if self.resume_burst else None
        self.observe(l,ids[0])
        rank=.75*self.fast[l]*(32*(1-2**(-1/8)))+.25*self.slow[l]*(32*(1-2**(-1/64)))
        if self.resume_burst:rank=prior_rank
        required=(order[0]<self.resume_burst).astype(mx.int32) if self.resume_burst else mx.array([1]*6,dtype=mx.int32)
        r=dict(x=x,ids=ids,weights=weights,residual=residual,post=ffn_post,comb=ffn_comb,pre=ffn_pre,
               state=snapshot_tree((self.states[l] if self.local_checkpoints else self.states,self.shared)),
               metadata=(self._local_metadata(l),native.retain(self.cache_counters)) if self.local_checkpoints else self._metadata_snapshot())
        # All continuation tensors and current attention writes must precede the check.
        r['counts']=self.route_cache_counts(l,self.lookups[l][ids[0]])
        deps=arrays((weights,residual,ffn_post,ffn_comb,ffn_pre,r['state'],r['metadata'][0] if self.defer_counters and self.local_checkpoints else r['metadata'],() if self.defer_route_stats else r['counts'],self.token_dependencies,getattr(self,'prefix_dependencies',())))
        held,slots=native.gate(self.session,x,ids[0].astype(mx.int32),self.lookups[l],l,self.ages[l],rank,required,deps)
        r['x']=held
        self.records[l]=r
        return self._compute_moe(l,r,slots)

    def __call__(self,ids,start=0):
        if not start:return super().__call__(ids,start)
        if ids.shape!=(1,1) or start<0 or start+1>self.max_seq or self.l1_policy!='eviction_dual':
            raise ValueError('miss-resume requires single-token eviction_dual within max_seq')
        self.decode_step+=1;self.image_mask=None
        # Parameters first used at a compression boundary must be resident before
        # the guarded graph; Storage's lazy loaders contain mx.eval calls.
        if not getattr(self,'resume_warmed',False):
            for j in self.c.kv_source_layers:
                if self.c.compress_ratios[j]>1:self.w(f'layers.{j}.attn.compressor.norm.weight')
            for j in self.c.index_source_layers:
                names=['wq_b','weights_proj']
                if j in self.c.kv_source_layers:
                    names+=['wk'];self.w(f'layers.{j}.attn.indexer.k_norm.weight')
                for name in names:
                    p=f'layers.{j}.attn.indexer.{name}'
                    if self.s.entries[p+'.weight'][2]['dtype']=='F8_E4M3':self.s.fp8(p)
                    else:self.w(p+'.weight')
            self.resume_warmed=True
        for l,bank in self.banks.items():
            if l not in self.lookups:
                mapping=[-1]*self.c.n_routed_experts
                for e,slot in {**bank.main,**bank.hot}.items():mapping[e]=slot
                self.lookups[l]=mx.array(mapping,dtype=mx.int32)
                age=[0]*bank.capacity
                for t,slot in enumerate(bank.hot.values()):age[slot]=t+1
                self.ages[l]=mx.array(age,dtype=mx.int32);self.ticks[l]=bank.capacity
        hashes=self.hash(ids,start)
        embedding=self.s.embedding
        # Engram row addresses depend only on token history. Resolve before submission.
        eng={f'layers.{l}.engram.embed':embedding(f'layers.{l}.engram.embed',hashes[:,:,i,:],True)
             for i,l in enumerate(self.c.engram_layer_ids)}
        h=mx.repeat(embedding('embed',ids)[:,:,None,:],self.c.hc_mult,axis=2)
        pre=mx.zeros(h.shape[:-1],dtype=mx.float32);pre[:,:,0]=1.
        # Hoist these dependencies before the FIRST GPU gate, without a host wait.
        self.token_dependencies=tuple(eng.values())
        self.s.embedding=lambda name,idx,fp8=False:eng[name] if name in eng else embedding(name,idx,fp8)
        self.prefix_dependencies=()
        l=0;pending=None;missed=set();final_logits=None;native_layers=0
        try:
            while l<self.c.n_layers:
                extent=self.resume_block+(1 if pending is not None and self.resume_block==1 else 0)
                end=min(l+extent,self.c.n_layers)
                if self.adaptive_windows and self.decode_step>8:
                    # Use only misses already observed in this request. Stop a
                    # speculative segment before a frequently missing layer.
                    first_check=l+int(pending is not None)
                    for j in range(first_check,end):
                        if self.resume_stats['miss_layer_histogram'].get(str(j),0)/self.decode_step>.15:
                            end=max(first_check+1,j);break
                self.records={};self.before_layers={}
                build_start=time.perf_counter()
                if self.native_window:self.session.begin_packet()
                elif self.native_prefix:self.session.begin_prefix()
                else:self.session.begin()
                try:
                    if pending is not None:
                        r,slots=pending;h,pre=self._compute_moe(l,r,slots);pending=None
                        first=l+1
                    else:first=l
                    self.resume_stats['constructed_layers']+=end-first
                    for j in range(first,end):
                        h,pre=self._layer(j,h,pre,hashes,start)
                        if self.native_window and self.async_window:
                            # Enqueue without a host wait while Python builds the
                            # next layer. The existing window boundary owns commit.
                            mx.async_eval(h,pre)
                    logits=None
                    roots=[h,pre]
                    if end==self.c.n_layers:
                        normed=self.norm('norm',self.hc_pre(h,pre))
                        logits=normed[:,-1].astype(mx.float32)@self.w('head.weight',mx.float32).T
                        roots.append(logits)
                    eval_start=time.perf_counter();self.resume_stats['build_seconds']+=eval_start-build_start
                    state_roots=([self.states[j] for j in range(l,end)],self.shared,
                        [getattr(self,k)[j] for k in ('fast','slow','frequency','ages') for j in range(l,end)]) if self.local_roots else (self.states,self.shared,self.fast,self.slow,self.frequency,self.ages)
                    mx.eval(*roots,*arrays(state_roots),*(() if self.defer_counters else (self.cache_counters,)),*[v for bank in self.banks.values() for v in bank.pending])
                except BaseException:
                    mx.synchronize();self.session.finish();raise
                self.resume_stats['eval_seconds']+=time.perf_counter()-eval_start
                status=self.session.finish();self.resume_stats['submissions']+=1
                # Every tracked consumer was evaluated under the predicate above.
                # Retiring it now prevents graph growth on long all-hit runs.
                for bank in self.banks.values():bank.pending.clear()
                failed=status[2]
                committed=(end if failed<0 else failed)-l
                hist=self.resume_stats['window_histogram'];hist[str(committed)]=hist.get(str(committed),0)+1
                if failed>=0:
                    hist=self.resume_stats['miss_layer_histogram'];hist[str(failed)]=hist.get(str(failed),0)+1
                if failed<0:
                    self.resume_stats['completed_layers']+=end-l;l=end
                    if logits is not None:final_logits=logits
                    continue
                if not first<=failed<end:raise RuntimeError(('invalid continuation',status,l,end))
                if failed in missed:raise RuntimeError('repeated unresolved miss')
                missed.add(failed)
                self.resume_stats['completed_layers']+=failed-l;self.resume_stats['misses']+=1
                r=self.records[failed]
                if self.local_checkpoints:
                    # Attention only writes its own layer and the small shared map.
                    # Keep the completed prefix, retain this layer's post-attention
                    # state, and discard updates from skipped suffix layers.
                    for j in range(failed+1,end):
                        self.states[j],meta=self.before_layers[j]
                        self._restore_local_metadata(j,meta)
                    self.states[failed],self.shared=r['state']
                    meta,self.cache_counters=r['metadata']
                    self._restore_local_metadata(failed,meta)
                else:
                    self.states,self.shared=r['state']
                    self.fast,self.slow,self.frequency,self.ages,self.ticks,self.cache_counters=r['metadata']
                bank=self.banks[failed];metadata=self.session.metadata(bank.capacity)
                host=status[4:10];age=metadata[:bank.capacity];rank=metadata[bank.capacity:bank.capacity+384]
                needed=metadata[bank.capacity+384:bank.capacity+390];before=metadata[bank.capacity+390:bank.capacity+396]
                requested=[e for e,must,slot in zip(host,needed,before) if must or slot>=0]
                bank.hot=dict(sorted(bank.hot.items(),key=lambda pair:age[pair[1]]))
                before_io=bank.io_seconds
                slots=self.prepare_miss(failed,bank,requested,rank)
                self.decode_io[failed]=self.decode_io.get(failed,0)+bank.io_seconds-before_io
                self.stats['decode_host_ids']+=len(host)
                mapping=[-1]*self.c.n_routed_experts
                for e,slot in {**bank.main,**bank.hot}.items():mapping[e]=slot
                self.lookups[failed]=mx.array(mapping,dtype=mx.int32)
                slots=mx.array([mapping[e] for e in host],dtype=mx.int32)
                # Host-authored shared-memory arrays are already available; no GPU wait.
                if getattr(self,'resume_mode',None)=='auto' or (getattr(self,'resume_mode',None)=='window' and not getattr(self,'force_window',False)):
                    # Stop paying speculative dispatch overhead after the first
                    # miss. The current MoE is known safe and uses native dispatch.
                    h,pre=self._compute_moe(failed,r,slots)
                    self.resume_stats['completed_layers']+=1
                    self.resume_stats['native_tail_tokens']+=1
                    native_layers=self.c.n_layers-failed-1
                    final_logits=self.native_tail(failed+1,h,pre,hashes,start)
                    l=self.c.n_layers
                    break
                pending=(r,slots);l=failed
            self.stats['route_requests']+=(self.c.n_layers-native_layers)*6
            self.stats['all_hit_steps']+=self.c.n_layers-native_layers-len(missed)
        finally:self.s.embedding=embedding
        if final_logits is None:raise RuntimeError('missing completed logits')
        return final_logits
