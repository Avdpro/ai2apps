"""Opt-in Decode Burst with first-miss rollback; Prefill is exact unless independently enabled.
Top-N is ranked by the native biased router score. Resident tail contributions
are retained, cold tails are zero, and original Top-6 weights are not renormalized.
"""
import mlx.core as mx
from adaptive import AdaptiveModel
from model import Model


def snapshot_tree(value, memo=None):
    """Retain independent MLX array handles; preserve aliases within the snapshot."""
    if memo is None:memo={}
    key=id(value)
    if key in memo:return memo[key]
    if isinstance(value,mx.array):out=mx.array(value)
    elif isinstance(value,dict):
        out={};memo[key]=out
        out.update((k,snapshot_tree(v,memo)) for k,v in value.items());return out
    elif isinstance(value,list):out=[snapshot_tree(v,memo) for v in value]
    elif isinstance(value,tuple):out=tuple(snapshot_tree(v,memo) for v in value)
    else:return value
    memo[key]=out;return out


class BurstModel(AdaptiveModel):
    def __init__(self,*args,burst_top=2,block_layers=1,tail_policy="zero",**kwargs):
        if burst_top not in (2,4) or block_layers not in (1,2,4):raise ValueError('Burst Top2/4, Block1/2/4 only')
        if tail_policy not in ("zero","zero-renorm","fixed-top","renorm") or (tail_policy!="zero" and block_layers!=1):raise ValueError("Tail substitution currently requires Block1")
        self.tail_policy=tail_policy
        super().__init__(*args,**kwargs)
        self.burst_top=burst_top;self.block_layers=block_layers;self.records={}
        self.burst_stats=dict(blocks=0,accepted_blocks=0,rollbacks=0,replayed_layers=0,discarded_layers=0,committed_prefix_layers=0,committed_layers=0,checks=0,mandatory_loads=0,rollback_offsets={},histogram={})
        self.burst_counts=mx.zeros((self.c.n_layers,4),dtype=mx.uint32)
        self.tail_replacements=mx.zeros((self.c.n_layers,),dtype=mx.uint32)
        self.speculative=False

    def prepare_decode(self):
        # Maintenance is outside transactions, based only on previously committed routes.
        for layer,bank in self.banks.items():
            if self.decode_step>1 and (self.decode_step-1)%16==0:
                scores=self.frequency[layer].tolist();main=dict(bank.main)
                candidates=sorted((e for e in range(self.c.n_routed_experts) if e not in main),key=lambda e:(-scores[e],e))
                victims=sorted(main,key=lambda e:(scores[e],e));pairs=[]
                for new,old in zip(candidates[:4],victims[:4]):
                    if scores[new]>=3 and scores[new]>scores[old]+2:pairs.append((new,old,main[old]))
                if pairs:
                    bank._load([p[0] for p in pairs],[p[2] for p in pairs])
                    for new,old,slot in pairs:
                        del bank.main[old];bank.main[new]=slot;bank.hot.pop(new,None)
                    self.promotions.append(dict(step=self.decode_step,layer=layer,pairs=pairs))
                self.frequency[layer]=self.frequency[layer]*.5
            mapping=[-1]*self.c.n_routed_experts
            for e,s in {**bank.main,**bank.hot}.items():mapping[e]=s
            self.lookups[layer]=mx.array(mapping,dtype=mx.int32)
            if layer not in self.ages:
                ages=[0]*bank.capacity
                for age,slot in enumerate(bank.hot.values()):ages[slot]=age+1
                self.ages[layer]=mx.array(ages,dtype=mx.int32);self.ticks[layer]=bank.capacity

    def moe(self,l,x,start):
        if not start:return super().moe(l,x,start)
        c=self.c;flat=x.reshape(-1,c.dim);p=f'layers.{l}.ffn.gate';bank=self.banks[l]
        score=(flat.astype(mx.float32)@self.w(p+'.weight',mx.float32).T)/c.gate_temp
        score=mx.sqrt(mx.logaddexp(score,mx.array(0.,dtype=mx.float32)))
        ranked=mx.argsort(score+self.w(p+'.bias'),axis=-1)[...,-c.n_activated_experts:][...,::-1]
        weights=mx.take_along_axis(score,ranked,axis=-1)
        weights=weights/(mx.sum(weights,axis=-1,keepdims=True)+1e-20)*c.route_scale
        order=mx.argsort(ranked,axis=-1)
        ids=mx.take_along_axis(ranked,order,axis=-1)[0]
        weights=mx.take_along_axis(weights,order,axis=-1)[0]
        required=(order[0]<self.burst_top)
        mapped=self.lookups[l][ids];missing=required&(mapped<0)
        record=dict(ids=ids,required=required,before=mapped,missing=mx.any(missing))
        if not self.speculative and bool(record['missing'].item()):
            host=ids.tolist();needed=required.tolist();slots=mapped.tolist();ages=self.ages[l].tolist()
            bank.hot=dict(sorted(bank.hot.items(),key=lambda pair:ages[pair[1]]))
            requested=[e for e,must,slot in zip(host,needed,slots) if must or slot>=0]
            self.burst_stats['mandatory_loads']+=sum(must and slot<0 for must,slot in zip(needed,slots))
            bank.prepare(requested)
            mapping=[-1]*c.n_routed_experts
            for e,s in {**bank.main,**bank.hot}.items():mapping[e]=s
            self.lookups[l]=mx.array(mapping,dtype=mx.int32);mapped=self.lookups[l][ids]
        if self.tail_policy in ("fixed-top","renorm"):
            from tail_policy import replace_tail
            execution_ids,weights,mapped,replacements=replace_tail(score[0],self.w(p+'.bias'),ids,weights,required,self.lookups[l],self.tail_policy,c.route_scale)
            self.tail_replacements[l]=self.tail_replacements[l]+replacements
        valid=mapped>=0;safe=mx.maximum(mapped,0)
        if self.tail_policy=="zero-renorm":
            from tail_policy import renormalize_retained
            weights=renormalize_retained(weights,valid,c.route_scale)
        # Safe placeholder is never committed for a required miss; cold tails are zero.
        out=self.expert(mx.broadcast_to(flat,(c.n_activated_experts,c.dim)),bank,safe,weights)
        out=mx.where(valid[:,None],out,mx.zeros_like(out));bank.track(out)
        record.update(mapped=mapped,valid=valid);self.records[l]=record
        y=mx.zeros((1,c.dim),dtype=mx.float32)
        for rank in range(c.n_activated_experts):y=y+out[rank:rank+1].astype(mx.float32)
        return (y.reshape(x.shape)+self.shared_expert(l,x)).astype(x.dtype)

    def layer(self,l,h,pre,hashes,start):
        c=self.c;p=f'layers.{l}'
        if l in c.engram_layer_ids:h=self.engram(l,h,hashes[:,:,c.engram_layer_ids.index(l),:])
        residual=h;attn_pre,attn_post,attn_comb=self.hc_mixes(p,h,'attn')
        x=self.norm(p+'.attn_norm',self.hc_pre(h,pre));x=self.attention(l,x,start)
        h=self.hc_post(x,residual,attn_post,attn_comb)
        residual=h;ffn_pre,ffn_post,ffn_comb=self.hc_mixes(p,h,'ffn')
        x=self.norm(p+'.ffn_norm',self.hc_pre(h,attn_pre));x=self.moe(l,x,start)
        return self.hc_post(x,residual,ffn_post,ffn_comb),ffn_pre

    def commit(self,l):
        r=self.records[l];ids=r['ids'];mapped=r['mapped'];valid=r['valid'];before=r['before']
        self.frequency[l][ids]=self.frequency[l][ids]+1
        self.cache_counters[l]=self.cache_counters[l]+mx.stack([mx.sum((before>=0)&(before<self.main_slots)),mx.sum(before>=self.main_slots),mx.sum(before<0)]).astype(mx.uint32)
        self.burst_counts[l]=self.burst_counts[l]+mx.stack([mx.sum(r['required']&(before<0)),mx.sum((~r['required'])&(~valid)),mx.sum(valid),mx.sum(r['required'])]).astype(mx.uint32)
        self.ticks[l]+=self.c.n_activated_experts
        updates=self.ticks[l]+mx.arange(self.c.n_activated_experts,dtype=mx.int32)
        mask=(mx.arange(self.banks[l].capacity)[:,None]==mapped[None,:])&valid[None,:]
        self.ages[l]=mx.max(mx.where(mask,updates[None,:],self.ages[l][:,None]),axis=1)
        self.stats['route_requests']+=self.c.n_activated_experts
        self.burst_stats['committed_layers']+=1
        # Trace only accepted routes, without double counting Adaptive.emit frequency.
        Model.emit(self,f'layers.{l}.gate',ids[None])

    def __call__(self,ids,start=0):
        if not start:return super().__call__(ids,start)
        if ids.shape!=(1,1) or start+1>self.max_seq:raise ValueError('Burst supports batch-one Decode only')
        self.decode_step+=1;self.prepare_decode();self.records={}
        hashes=self.hash(ids,start) # updated once per token, never replayed by a block
        h=mx.repeat(self.s.embedding('embed',ids)[:,:,None,:],self.c.hc_mult,axis=2)
        pre=mx.zeros(h.shape[:-1],dtype=mx.float32);pre[:,:,0]=1.;l=0
        while l<self.c.n_layers:
            if self.block_layers==1:
                self.speculative=False;h,pre=self.layer(l,h,pre,hashes,start);self.commit(l)
                self.burst_stats['checks']+=1;l+=1;continue
            end=min(l+self.block_layers,self.c.n_layers);boundaries=[];self.speculative=True
            for j in range(l,end):
                boundaries.append((h,pre,snapshot_tree((self.states,self.shared))))
                h,pre=self.layer(j,h,pre,hashes,start)
            flags=mx.stack([self.records[j]['missing'] for j in range(l,end)])
            mx.eval(h,pre,flags) # materialize *all* speculative bank consumers before any reload
            misses=flags.tolist();self.burst_stats['checks']+=1;self.burst_stats['blocks']+=1
            if not any(misses):
                for j in range(l,end):self.commit(j)
                self.burst_stats['accepted_blocks']+=1;l=end
            else:
                offset=misses.index(True);failed=l+offset
                for j in range(l,failed):self.commit(j)
                h,pre,state=boundaries[offset];self.states,self.shared=state
                # No candidate state or metadata after the first true miss is accepted.
                self.burst_stats['rollbacks']+=1;self.burst_stats['committed_prefix_layers']+=offset
                self.burst_stats['discarded_layers']+=end-failed;self.burst_stats['replayed_layers']+=1
                k=str(offset);self.burst_stats['rollback_offsets'][k]=self.burst_stats['rollback_offsets'].get(k,0)+1
                for j in range(failed,end):self.records.pop(j,None)
                self.speculative=False;h,pre=self.layer(failed,h,pre,hashes,start);self.commit(failed)
                self.burst_stats['checks']+=1;l=failed+1
            boundaries.clear()
        self.speculative=False
        h=self.norm('norm',self.hc_pre(h,pre))
        logits=h[:,-1].astype(mx.float32)@self.w('head.weight',mx.float32).T
        mx.eval(*self.frequency.values(),self.burst_counts)
        return logits

    def close(self):
        mx.eval(self.burst_counts,self.tail_replacements)
        self.burst_report=dict(tail_policy=self.tail_policy,tail_replacements=self.tail_replacements.tolist(),top_n=self.burst_top,block_layers=self.block_layers,ranking='native biased router Top-6 order',tail='resident retained, cold zero, no renormalization' if self.tail_policy=='zero' else ('cold zero, retained weights renormalized' if self.tail_policy=='zero-renorm' else 'resident high-score substitution; '+self.tail_policy),prefill=('exact' if self.prefill_executor is None or self.prefill_executor.top is None else 'burst-top'+str(self.prefill_executor.top)),statistics=self.burst_stats,per_layer_counts=self.burst_counts.tolist(),count_columns=['required_misses','omitted_tail_routes','executed_routes','required_routes'])
        super().close()
