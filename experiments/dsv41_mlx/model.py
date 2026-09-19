"""Pure MLX text DS4.1 Flash, original checkpoint and SSD expert storage.
Port of the downloaded official model; arithmetic and state ownership are explicit.
"""
import hashlib,json,math,sys
from pathlib import Path
from types import SimpleNamespace
from collections import Counter
import numpy as np
import mlx.core as mx
from storage import Storage
from kernels import quant,norm,rope_freq,rope,rope_selected,sinkhorn,sparse,index_scores,index_topk
from engram import HashState
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dsv41_reference'))
from lru_metal_bank import LRUMetalBank

class Model:
    def __init__(self,config,store,tokenizer,expert_store,max_seq=4096,main_slots=40,hot_slots=8,trace=None,matrix_prefill=True,prefill_slots=0,prefill_top=None,shared_dispatch=False,fused_gate_up=False,prefill_hot_direct=True,decode_dispatch="legacy",attention_chunk=64,main_shape=None,expert_no_cache=False):
        c=dict(gate_temp=1.,norm_topk_prob=True,temperature=0.);c.update(config);self.c=SimpleNamespace(**c)
        self.shared_dispatch=shared_dispatch or fused_gate_up
        self.fused_gate_up=fused_gate_up
        if decode_dispatch not in ("legacy","shared","unsorted"):raise ValueError("invalid Decode dispatch")
        self.decode_dispatch=decode_dispatch
        if attention_chunk not in (64,128,256):raise ValueError("invalid attention chunk")
        self.attention_chunk=attention_chunk
        self.prefill_executor=None
        if prefill_slots:
            from prefill import Prefill
            self.prefill_executor=Prefill(prefill_slots,prefill_top,prefill_hot_direct)
        self.s=store;self.expert_store=Path(expert_store);self.main_slots=main_slots;self.hot_slots=hot_slots;self.trace=trace;self.matrix_prefill=matrix_prefill
        self.expert_no_cache=expert_no_cache
        self.main_capacities=tuple(main_shape) if main_shape is not None else (main_slots,)*self.c.n_layers
        if len(self.main_capacities)!=self.c.n_layers or any(type(v) is not int or v<=0 for v in self.main_capacities):raise ValueError('invalid per-layer capacity')
        if main_shape is not None:
            balanced=all(type(v) is int and v in (32,36,40,44,48) for v in self.main_capacities) and sum(self.main_capacities)==1600
            growth=all(type(v) is int and v in (40,48) for v in self.main_capacities) and self.main_capacities.count(48)==8
            if not (balanced or growth) or hot_slots!=8:raise ValueError('invalid L1 shape budget')
        manifest=json.loads((self.expert_store/'manifest.json').read_text())
        expected=self.s.source_index_sha256
        if manifest.get('status')!='complete' or manifest.get('checkpoint_index_sha256')!=expected or manifest.get('layers')!=list(range(self.c.n_layers)):raise ValueError('expert store/checkpoint mismatch')
        self.hash=HashState(self.c,tokenizer,max_seq);self.states={};self.banks={};self.shared={};self.freqs={};self.max_seq=max_seq
        self.main_slot_masks={};self.lookups={};self.ages={};self.ticks={};self.cache_counters=mx.zeros((self.c.n_layers,3),dtype=mx.uint32)
        self.stats=dict(route_requests=0,l1_hits=0,l0_hits=0,misses=0,all_hit_steps=0,decode_host_ids=0,prefill_groups=0)
        for l in range(self.c.n_layers):
            ratio=self.c.compress_ratios[l]
            self.states[l]={'window':mx.zeros((1,self.c.window_size,self.c.head_dim),dtype=mx.bfloat16)}
            if l in self.c.kv_source_layers:
                self.states[l]['compressed']=mx.zeros((1,max_seq//ratio,self.c.head_dim),dtype=mx.bfloat16)
                self.states[l]['index']=mx.zeros((1,max_seq//ratio,self.c.index_head_dim),dtype=mx.bfloat16)
                if ratio>1:
                    self.states[l]['kv_state']=mx.zeros((1,ratio,self.c.head_dim),dtype=mx.float32)
                    self.states[l]['score_state']=mx.full((1,ratio,self.c.head_dim),-mx.inf,dtype=mx.float32)
        for compressed in [False,True]:
            self.freqs[compressed]=rope_freq(self.c.rope_head_dim,max_seq,self.c.original_seq_len if compressed else 0,self.c.compress_rope_theta if compressed else self.c.rope_theta,self.c.rope_factor,self.c.beta_fast,self.c.beta_slow)
    def emit(self,name,x):
        if self.trace:self.trace(name,x)
    def w(self,name,dtype=None):return self.s.weight(name,dtype)
    def linear(self,name,x,force_f32=False):
        kind=self.s.entries[name+'.weight'][2]['dtype']
        if kind=='F8_E4M3':
            w,s=self.s.fp8(name);a=quant(x).astype(mx.bfloat16)
            return mx.quantized_matmul(a,w,s,group_size=32,bits=8,mode='mxfp8').astype(mx.bfloat16)
        w=self.w(name+'.weight',mx.float32 if force_f32 else None)
        return x.astype(w.dtype)@w.T
    def norm(self,name,x):return norm(x,self.w(name+'.weight'),self.c.norm_eps)
    def hc_pre(self,x,pre):return mx.sum(pre[...,None]*x.astype(mx.float32),axis=2).astype(x.dtype)
    def hc_mixes(self,p,x,kind):
        f=x.reshape(*x.shape[:2],-1).astype(mx.float32)
        mix=(f@self.w(p+'.hc_'+kind+'_fn').T)*mx.rsqrt(mx.mean(f*f,axis=-1,keepdims=True)+self.c.norm_eps)
        return sinkhorn(mix,self.w(p+'.hc_'+kind+'_scale'),self.w(p+'.hc_'+kind+'_base'),self.c.hc_mult,self.c.hc_sinkhorn_iters,self.c.hc_eps)
    def hc_post(self,x,residual,post,comb):
        return (post[...,None]*x[:,:,None,:]+mx.sum(comb[...,None]*residual[:,:,:,None,:],axis=2)).astype(x.dtype)
    def engram(self,l,x,ids):
        c=self.c;p=f'layers.{l}.engram';v=self.s.embedding(p+'.embed',ids,True).reshape(*ids.shape[:2],-1)
        kv=self.linear(p+'.wkv',v);key=kv[...,:c.hc_mult*c.dim].astype(mx.float32).reshape(*x.shape);value=kv[...,c.hc_mult*c.dim:].astype(mx.float32)
        h=x.astype(mx.float32);weight=self.w(p+'.q_weight').astype(mx.float32)*self.w(p+'.k_weight').astype(mx.float32)
        rstd=mx.rsqrt(mx.mean(h*h,axis=-1)+c.norm_eps)*mx.rsqrt(mx.mean(key*key,axis=-1)+c.norm_eps)
        dot=mx.sum(h*weight*key,axis=-1)*rstd*c.dim**-.5
        signed=mx.where((dot.view(mx.uint32)&mx.array(0x80000000,dtype=mx.uint32))!=0,-1.,1.)*mx.sqrt(mx.maximum(mx.abs(dot),1e-6));gate=mx.sigmoid(signed)
        if getattr(self,'image_mask',None) is not None:gate=mx.where(self.image_mask[...,None],0,gate)
        return (h+gate[...,None]*value[:,:,None,:]).astype(x.dtype)
    def compress(self,l,x,start):
        c=self.c;p=f'layers.{l}.attn.compressor';ratio=c.compress_ratios[l];st=self.states[l];n=x.shape[1]
        if ratio==1:return self.norm(p+'.norm',self.linear(p+'.wkv',x))
        kv=self.linear(p+'.wkv',x,True);score=self.linear(p+'.wgate',x,True)
        if start==0:
            rem=n%ratio;cut=n-rem
            if rem:st['kv_state'][:,:rem]=kv[:,cut:];st['score_state'][:,:rem]=score[:,cut:]
            if n<ratio:return None
            kv=kv[:,:cut].reshape(1,-1,ratio,c.head_dim);score=score[:,:cut].reshape(kv.shape)
            y=mx.sum(kv*mx.softmax(score,axis=2),axis=2)
        else:
            slot=start%ratio;st['kv_state'][:,slot]=kv[:,0];st['score_state'][:,slot]=score[:,0]
            if (start+1)%ratio:return None
            y=mx.sum(st['kv_state']*mx.softmax(st['score_state'],axis=1),axis=1,keepdims=True)
        return self.norm(p+'.norm',y.astype(x.dtype))
    def candidates(self,score,lens):
        c=self.c;width=score.shape[-1];pad=(-width)%c.candidate_block_size
        padded=mx.pad(score,[(0,0)]*(score.ndim-1)+[(0,pad)],constant_values=-mx.inf)
        groups=mx.max(padded.reshape(*score.shape[:-1],-1,c.candidate_block_size),axis=-1)
        last=(lens-1)//c.candidate_block_size
        groups=mx.where(mx.arange(groups.shape[-1])==last,mx.inf,groups)
        count=min(c.candidate_topk_blocks,groups.shape[-1]);idx=mx.argsort(groups,axis=-1)[...,-count:]
        selected=mx.take_along_axis(groups,idx,axis=-1)>-mx.inf
        mask=mx.zeros(groups.shape,dtype=mx.bool_)
        # Batch=1; scatter on last axis through flattened query rows.
        flat=mask.reshape(-1,groups.shape[-1]);flat[mx.arange(flat.shape[0])[:,None],idx.reshape(flat.shape[0],-1)]=selected.reshape(flat.shape[0],-1)
        return mx.repeat(flat.reshape(groups.shape),c.candidate_block_size,axis=-1)[...,:width]
    def index(self,l,x,qr,latent,start,offset):
        c=self.c;p=f'layers.{l}.attn.indexer';ratio=c.compress_ratios[l];end=start+x.shape[1];freq=self.freqs[True];rd=c.rope_head_dim
        if l in c.kv_source_layers and latent is not None:
            positions=mx.arange(0,x.shape[1]-x.shape[1]%ratio,ratio) if start==0 else mx.array([start+1-ratio])
            k=self.norm(p+'.k_norm',self.linear(p+'.wk',latent));k=rope_selected(k,freq,positions,rd);k=quant(k,32,True)
            self.states[l]['index'][:,start//ratio:start//ratio+k.shape[1]]=k;self.shared['index']=self.states[l]['index']
        q=self.linear(p+'.wq_b',qr).reshape(1,x.shape[1],c.index_n_heads,c.index_head_dim)
        q=quant(rope(q,freq,start,rd),32,True);k=self.shared['index'][:,:end//ratio]
        weights=self.linear(p+'.weights_proj',x)*(c.index_head_dim**-.5*c.index_n_heads**-.5)
        # Official einsum emits BF16 before relu/weight/reduce.
        score=index_scores(q,k,weights)
        lens=(mx.arange(1,x.shape[1]+1)//ratio)[:,None] if start==0 else end//ratio
        if start==0:score=mx.where(mx.arange(end//ratio)>=lens,-mx.inf,score)
        if l==c.candidate_source_layer:self.shared['candidates']=self.candidates(score,lens)
        elif 0<=c.candidate_source_layer<l:score=mx.where(self.shared['candidates'],score,-mx.inf)
        top=min(c.index_topk,end//ratio);idx=index_topk(score,top)
        return mx.where(idx<lens,idx+offset,-1).astype(mx.int32)
    def attention(self,l,x,start):
        c=self.c;p=f'layers.{l}.attn';st=self.states[l];n=x.shape[1];ratio=c.compress_ratios[l];freq=self.freqs[bool(ratio)];rd=c.rope_head_dim
        qr=self.norm(p+'.q_norm',self.linear(p+'.wq_a',x))
        q=rope(self.linear(p+'.wq_b',qr).reshape(1,n,c.n_heads,c.head_dim),freq,start,rd)
        kv=quant(rope(self.norm(p+'.kv_norm',self.linear(p+'.wkv',x)),freq,start,rd))
        if start==0:
            # Preserve the exact ring positions for the next Decode.
            for begin in range(0,n,c.window_size):
                part=kv[:,begin:begin+c.window_size];st['window'][:,:part.shape[1]]=part
            end=mx.arange(n)[:,None];idx=mx.maximum(end-c.window_size+1,0)+mx.arange(min(n,c.window_size))[None,:]
            idx=mx.where(idx>end,-1,idx)[None].astype(mx.int32);window=kv
        else:
            st['window'][:,start%c.window_size]=kv[:,0];window=st['window'];oldest=start%c.window_size+1
            idx=mx.concatenate([mx.arange(oldest,c.window_size),mx.arange(oldest)])[None,None,:]
            idx=mx.where(idx>start,-1,idx).astype(mx.int32)
        if ratio:
            clen=(start+n)//ratio;latent=None
            if l in c.kv_source_layers:latent=self.compress(l,x,start);self.shared['compressed']=st['compressed']
            if l in c.index_source_layers:
                ci=mx.zeros((1,n,0),dtype=mx.int32) if clen==0 else self.index(l,x,qr,latent,start,window.shape[1])
                self.shared['indices']=ci
            else:ci=self.shared['indices']
            if latent is not None:
                positions=mx.arange(0,n-n%ratio,ratio) if start==0 else mx.array([start+1-ratio])
                latent=quant(rope_selected(latent,freq,positions,rd),16,True,True)
                st['compressed'][:,start//ratio:start//ratio+latent.shape[1]]=latent
                # MLX updates are functional: publish the updated array explicitly.
                self.shared['compressed']=st['compressed']
            window=mx.concatenate([window,self.shared['compressed'][:,:clen]],axis=1);idx=mx.concatenate([idx,ci],axis=-1)
        out=sparse(q,window,self.w(p+'.attn_sink'),idx,c.head_dim**-.5,self.attention_chunk)
        out=rope(out,freq,start,rd,True).reshape(1,n,c.o_groups,-1)
        w=self.s.grouped(p+'.wo_a').reshape(c.o_groups,c.o_lora_rank,-1)
        out=mx.transpose(mx.transpose(out,(0,2,1,3))@mx.swapaxes(w,-1,-2),(0,2,1,3)).reshape(1,n,-1)
        return self.linear(p+'.wo_b',out)
    def expert_linear(self,x,w,s,slots,segments=None):
        if segments is not None and self.matrix_prefill and any(n>=128 for _,n in segments):
            z=quant(x).astype(mx.bfloat16);chunks=[];positions=[];small=[];offset=0
            for slot,n in segments:
                rows=list(range(offset,offset+n))
                if n>=128:
                    chunks.append(mx.quantized_matmul(z[offset:offset+n],w[slot].view(mx.uint32),s[slot],group_size=32,bits=4,mode='mxfp4'))
                    positions.extend(rows)
                else:small.extend(rows)
                offset+=n
            if small:
                ir=mx.array(small,dtype=mx.int32)
                chunks.append(self.expert_linear(x[ir],w,s,slots[ir]));positions.extend(small)
            return mx.concatenate(chunks)[mx.argsort(mx.array(positions,dtype=mx.int32))].astype(mx.bfloat16)
        z=quant(x).reshape(x.shape[0],1,x.shape[-1]).astype(mx.bfloat16)
        order=mx.argsort(slots);inverse=mx.argsort(order)
        out=mx.gather_qmm(z[order],w.view(mx.uint32),s,lhs_indices=mx.arange(x.shape[0],dtype=mx.uint32),rhs_indices=slots[order].astype(mx.uint32),group_size=32,bits=4,mode='mxfp4',sorted_indices=True)
        return out[inverse,0,:].astype(mx.bfloat16)
    def expert(self,x,bank,slots,rw,segments=None):
        if segments is None and x.shape[0]<=self.c.n_activated_experts and self.decode_dispatch!="legacy":
            from expert_dispatch import decode_expert
            return decode_expert(x,bank.arrays,slots,rw,self.decode_dispatch)
        if self.shared_dispatch and segments is not None:
            from expert_dispatch import expert
            return expert(self,x,bank,slots,rw,segments)
        a=bank.arrays;gate=self.expert_linear(x,a[0],a[1],slots,segments).astype(mx.float32);up=self.expert_linear(x,a[4],a[5],slots,segments).astype(mx.float32)
        gate=mx.minimum(gate,10);up=mx.clip(up,-10,10)
        h=(rw[:,None]*((gate*mx.sigmoid(gate))*up)).astype(mx.bfloat16)
        return self.expert_linear(h,a[2],a[3],slots,segments)
    def shared_expert(self,l,x):
        p=f'layers.{l}.ffn.shared_experts';gate=mx.minimum(self.linear(p+'.w1',x).astype(mx.float32),10);up=mx.clip(self.linear(p+'.w3',x).astype(mx.float32),-10,10)
        return self.linear(p+'.w2',(gate*mx.sigmoid(gate)*up).astype(x.dtype))
    def refresh_slot_roles(self,l,bank):
        if bank.dynamic_roles:
            main=set(bank.main.values())
            self.main_slot_masks[l]=mx.array([s in main for s in range(bank.capacity)],dtype=mx.bool_)
    def route_cache_counts(self,l,mapped):
        if l in self.main_slot_masks:
            resident=mapped>=0
            main=resident & self.main_slot_masks[l][mx.maximum(mapped,0)]
            return mx.stack([mx.sum(main),mx.sum(resident & ~main),mx.sum(~resident)]).astype(mx.uint32)
        return mx.stack([mx.sum((mapped>=0)&(mapped<self.main_capacities[l])),mx.sum(mapped>=self.main_capacities[l]),mx.sum(mapped<0)]).astype(mx.uint32)
    def routes_all_hit(self,l,ids,mapped,required=None):
        if required is not None:return not bool(mx.any(required&(mapped<0)).item())
        return bool(mx.all(mapped>=0).item())
    def burst_miss_metadata(self,l,ids,required,mapped):
        if self.l1_policy=='eviction_dual':
            if self.ticks[l]+self.c.n_activated_experts>=2**24:raise RuntimeError('packed cache ages exceed exact float32 integer range')
            rank=.75*self.fast[l]*(32*(1-2**(-1/8)))+.25*self.slow[l]*(32*(1-2**(-1/64)))
            packed=mx.concatenate([ids.astype(mx.float32),required.astype(mx.float32),mapped.astype(mx.float32),self.ages[l].astype(mx.float32),rank]).tolist()
            n=self.c.n_activated_experts;k=self.banks[l].capacity
            return ([int(v) for v in packed[:n]],[bool(v) for v in packed[n:2*n]],
                    [int(v) for v in packed[2*n:3*n]],[int(v) for v in packed[3*n:3*n+k]],packed[3*n+k:])
        return ids.tolist(),required.tolist(),mapped.tolist(),self.ages[l].tolist(),None
    def miss_metadata(self,l,ids):
        return ids.tolist(),self.ages[l].tolist(),None
    def prepare_miss(self,l,bank,host,scores):
        return bank.prepare(host)
    def moe(self,l,x,start):
        c=self.c;p=f'layers.{l}.ffn.gate';flat=x.reshape(-1,c.dim)
        scores=(flat.astype(mx.float32)@self.w(p+'.weight',mx.float32).T)/c.gate_temp
        scores=mx.sqrt(mx.logaddexp(scores,mx.array(0.,dtype=mx.float32)))
        bias=self.w(p+'.bias')
        if getattr(self,'image_mask',None) is not None:bias=mx.where(self.image_mask.reshape(-1,1),self.w(p+'.bias_vl'),bias)
        ids=mx.argsort(scores+bias,axis=-1)[...,-c.n_activated_experts:][...,::-1]
        weights=mx.take_along_axis(scores,ids,axis=-1);weights=weights/(mx.sum(weights,axis=-1,keepdims=True)+1e-20)*c.route_scale
        order=mx.argsort(ids,axis=-1);ids=mx.take_along_axis(ids,order,axis=-1);weights=mx.take_along_axis(weights,order,axis=-1)
        self.emit(f'layers.{l}.gate',ids)
        if l not in self.banks:
            # Host metadata only: choose current-context Main before SSD reads.
            mx.eval(ids);host=ids.tolist();counts=Counter(e for row in host for e in row)
            selected=[e for e,_ in sorted(counts.items(),key=lambda p:(-p[1],p[0]))[:self.main_capacities[l]]]
            selected+=[e for e in range(c.n_routed_experts) if e not in selected][:self.main_capacities[l]-len(selected)]
            self.banks[l]=LRUMetalBank(self.expert_store/f'layer-{l}.bin',selected,l0_slots=self.hot_slots,no_cache=self.expert_no_cache)
        bank=self.banks[l]
        if flat.shape[0]>1 and self.prefill_executor is not None:
            out=self.prefill_executor.dispatch(self,l,flat,ids,weights,bank,scores)
        elif flat.shape[0]>1:
            mx.eval(ids);host=ids.tolist();pairs={}
            for row,es in enumerate(host):
                for rank,e in enumerate(es):pairs.setdefault(e,[]).append((row,rank))
            main=[e for e in sorted(pairs) if e in bank.main];cold=[e for e in sorted(pairs) if e not in bank.main]
            groups=([main] if main else [])+[cold[i:i+self.hot_slots] for i in range(0,len(cold),self.hot_slots)]
            values=[];positions=[]
            for es in groups:
                ss=bank.prepare(es);rows=[];ranks=[];locals=[]
                for j,e in enumerate(es):
                    for row,rank in pairs[e]:rows.append(row);ranks.append(rank);locals.append(j)
                ir=mx.array(rows,dtype=mx.int32);ik=mx.array(ranks,dtype=mx.int32)
                y=self.expert(flat[ir],bank,ss[mx.array(locals,dtype=mx.int32)],weights[ir,ik],[(bank.main[e] if e in bank.main else bank.hot[e],len(pairs[e])) for e in es]);bank.track(y);mx.eval(y)
                values.append(y);positions.extend(row*c.n_activated_experts+rank for row,rank in zip(rows,ranks))
            out=mx.concatenate(values)[mx.argsort(mx.array(positions,dtype=mx.int32))].reshape(flat.shape[0],c.n_activated_experts,c.dim)
            self.stats['prefill_groups']+=len(groups)
        else:
            if l not in self.lookups:
                mapping=[-1]*c.n_routed_experts
                for e,s in {**bank.main,**bank.hot}.items():mapping[e]=s
                self.lookups[l]=mx.array(mapping,dtype=mx.int32)
                ages=[0]*bank.capacity
                for age,slot in enumerate(bank.hot.values()):ages[slot]=age+1
                self.ages[l]=mx.array(ages,dtype=mx.int32);self.ticks[l]=bank.capacity
            mapped=self.lookups[l][ids[0]]
            self.cache_counters[l]=self.cache_counters[l]+self.route_cache_counts(l,mapped)
            if self.routes_all_hit(l,ids[0],mapped):
                slots=mapped;self.stats['all_hit_steps']+=1
            else:
                host,ages,promotion_scores=self.miss_metadata(l,ids[0])
                bank.hot=dict(sorted(bank.hot.items(),key=lambda pair:ages[pair[1]]))
                slots=self.prepare_miss(l,bank,host,promotion_scores);self.stats['decode_host_ids']+=len(host)
                mapping=[-1]*c.n_routed_experts
                for e,s in {**bank.main,**bank.hot}.items():mapping[e]=s
                self.lookups[l]=mx.array(mapping,dtype=mx.int32)
            self.ticks[l]+=c.n_activated_experts
            self.ages[l][slots]=self.ticks[l]+mx.arange(c.n_activated_experts,dtype=mx.int32)
            # Cache-policy metadata on a miss; all-hit indices remain on GPU.
            self.stats['route_requests']+=c.n_activated_experts
            out=self.expert(mx.broadcast_to(flat,(c.n_activated_experts,c.dim)),bank,slots,weights[0])[None]
            bank.track(out)
        y=mx.zeros((flat.shape[0],c.dim),dtype=mx.float32)
        for rank in range(c.n_activated_experts):y=y+out[:,rank,:].astype(mx.float32)
        return (y.reshape(x.shape)+self.shared_expert(l,x)).astype(x.dtype)
    def __call__(self,ids,start=0):
        c=self.c
        if ids.shape[0]!=1 or start+ids.shape[1]>self.max_seq:raise ValueError('batch/context limit')
        if start>0 and ids.shape[1]!=1:raise ValueError('incremental forward supports one decode token; chunked prefill is not implemented')
        self.image_mask=(self.vision_types>=0) if start==0 and hasattr(self,'vision_types') else None
        hashes=self.hash(ids,start,None if self.image_mask is None else ~self.image_mask);self.emit('engram_hashes',hashes)
        h=self.s.embedding('embed',ids)
        if start==0 and hasattr(self,'vision_images'):
            for img in self.vision_images:
                features=self.vision(img.patches,img.n_vit_h,img.n_vit_w);mx.eval(features)
                ts=mx.array(img.types,dtype=mx.int32);span=mx.zeros((len(img.types),c.dim),dtype=h.dtype)
                for kind,name in [(0,'image_start'),(2,'image_newline'),(3,'image_end')]:span=mx.where((ts==kind)[:,None],self.w(name),span)
                positions=mx.array([i for i,t in enumerate(img.types) if t==1],dtype=mx.int32);span[positions]=features
                h[0,img.start:img.start+len(img.types)]=span
                if hasattr(self,'vision_stage'):self.vision_stage('encoded:'+img.path)
        h=mx.repeat(h[:,:,None,:],c.hc_mult,axis=2)
        # Official initial mix selects the first residual stream.
        pre=mx.zeros(h.shape[:-1],dtype=mx.float32);pre[:,:,0]=1.0
        for l in range(c.n_layers):
            p=f'layers.{l}'
            if l in c.engram_layer_ids:h=self.engram(l,h,hashes[:,:,c.engram_layer_ids.index(l),:])
            residual=h;attn_pre,attn_post,attn_comb=self.hc_mixes(p,h,'attn')
            x=self.norm(p+'.attn_norm',self.hc_pre(h,pre));x=self.attention(l,x,start);self.emit(p+'.attn',x)
            h=self.hc_post(x,residual,attn_post,attn_comb)
            residual=h;ffn_pre,ffn_post,ffn_comb=self.hc_mixes(p,h,'ffn')
            x=self.norm(p+'.ffn_norm',self.hc_pre(h,attn_pre));x=self.moe(l,x,start)
            h=self.hc_post(x,residual,ffn_post,ffn_comb);pre=ffn_pre;self.emit(p,h)
        h=self.norm('norm',self.hc_pre(h,pre))
        logits=h[:,-1].astype(mx.float32)@self.w('head.weight',mx.float32).T
        return logits
    def close(self):
        if self.prefill_executor is not None:self.prefill_executor.release()
        for b in self.banks.values():b.close()
        self.s.close()
