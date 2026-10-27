"""Opt-in DSpark correctness prototype for original 1017 SSD checkpoints.

No serving activation. Serial mode is a correctness oracle. Block mode groups
expert work across candidates and commits accepted prefix state without replay.
Only greedy sampling and natural (all routed experts) execution are supported.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
import mlx.core as mx
from .model import Model
from .kernels import quant, rope, sparse


class DSparkDraft:
    # Reuse exactly the target's original-precision arithmetic helpers.
    w = Model.w
    linear = Model.linear
    norm = Model.norm
    hc_pre = Model.hc_pre
    hc_post = Model.hc_post
    hc_mixes = Model.hc_mixes

    def __init__(self, target, config):
        from types import SimpleNamespace
        self.s = target.s
        self.c = SimpleNamespace(**config)
        self.width = int(self.c.dspark_block_size)
        self.layers = tuple(self.c.dspark_target_layer_ids)
        if self.width <= 0 or tuple(sorted(set(self.layers))) != self.layers:
            raise ValueError('invalid DSpark configuration')
        if any(i < 0 or i >= target.c.n_layers for i in self.layers):
            raise ValueError('invalid target capture layer')
        self.freq = target.freqs[False]
        self.max_seq = target.max_seq
        self.windows = {}
        self.offset = 0

    def reset(self):
        self.windows = {}
        self.offset = 0

    def append(self, hidden, start):
        """Only committed target hidden states enter the draft context."""
        if start != self.offset:
            raise ValueError('non-contiguous DSpark context')
        c = self.c
        main = self.norm('mtp.0.main_norm', self.linear('mtp.0.main_proj', hidden))
        for layer in range(c.n_mtp_layers):
            p = f'mtp.{layer}.attn'
            kv = quant(rope(self.norm(p+'.kv_norm', self.linear(p+'.wkv', main)),
                            self.freq, start, c.rope_head_dim))
            window = self.windows.get(layer)
            if window is None:
                window = mx.zeros((1,c.window_size,c.head_dim), dtype=mx.bfloat16)
            # Last window only, with absolute physical ring positions.
            length = hidden.shape[1]
            begin = max(0, length-c.window_size)
            positions = (mx.arange(begin,length)+start) % c.window_size
            window[:,positions] = kv[:,begin:]
            self.windows[layer] = window
        self.offset += hidden.shape[1]
        mx.eval(*self.windows.values())

    def attention(self, layer, x):
        c = self.c; p = f'mtp.{layer}.attn'; n = x.shape[1]; start = self.offset
        qr = self.norm(p+'.q_norm', self.linear(p+'.wq_a',x))
        q = rope(self.linear(p+'.wq_b',qr).reshape(1,n,c.n_heads,c.head_dim),
                 self.freq,start,c.rope_head_dim)
        kv = quant(rope(self.norm(p+'.kv_norm',self.linear(p+'.wkv',x)),
                        self.freq,start,c.rope_head_dim))
        kv = mx.concatenate([self.windows[layer],kv],axis=1)
        indices = mx.concatenate([mx.arange(min(start,c.window_size)),
                                  c.window_size+mx.arange(n)]).astype(mx.int32)
        indices = mx.broadcast_to(indices[None,None,:],(1,n,indices.size))
        out = sparse(q,kv,self.w(p+'.attn_sink'),indices,c.head_dim**-.5,64)
        out = quant(rope(out,self.freq,start,c.rope_head_dim,True).reshape(1,n,c.o_groups,-1))
        w = self.s.grouped(p+'.wo_a').reshape(c.o_groups,c.o_lora_rank,-1)
        out = mx.transpose(mx.transpose(out,(0,2,1,3))@mx.swapaxes(w,-1,-2),(0,2,1,3)).reshape(1,n,-1)
        return self.linear(p+'.wo_b',out)

    def expert_linear(self, p, x):
        # Lazy packed resident draft experts; no conversion or new weight files.
        w = self.w(p+'.weight').view(mx.uint32)
        scale = self.w(p+'.scale')
        return mx.quantized_matmul(quant(x).astype(mx.bfloat16),w,scale,
                                   group_size=32,bits=4,mode='mxfp4').astype(mx.bfloat16)

    def expert(self, p, x, weights=None, packed=True):
        linear = self.expert_linear if packed else self.linear
        gate = mx.minimum(linear(p+'.w1',x).astype(mx.float32),self.c.swiglu_limit)
        up = mx.clip(linear(p+'.w3',x).astype(mx.float32),-self.c.swiglu_limit,self.c.swiglu_limit)
        h = gate*mx.sigmoid(gate)*up
        if weights is not None:h = weights*h
        return linear(p+'.w2',h.astype(x.dtype))

    def moe(self, layer, x):
        c = self.c; p = f'mtp.{layer}.ffn'; flat = x.reshape(-1,c.dim)
        scores = (flat.astype(mx.float32)@self.w(p+'.gate.weight',mx.float32).T)/getattr(c,'gate_temp',1.)
        scores = mx.sqrt(mx.logaddexp(scores,mx.array(0.,dtype=mx.float32)))
        ids = mx.argsort(scores+self.w(p+'.gate.bias'),axis=-1)[:,-c.dspark_n_activated_experts:][:,::-1]
        weights = mx.take_along_axis(scores,ids,axis=-1)
        weights = weights/(mx.sum(weights,axis=-1,keepdims=True)+1e-20)*c.route_scale
        pairs = {}
        for row, selected in enumerate(ids.tolist()):
            for rank, expert in enumerate(selected):pairs.setdefault(expert,[]).append((row,rank))
        y = mx.zeros(flat.shape,dtype=mx.float32)
        # Reference accumulates contributions in increasing expert ID order.
        for expert, entries in sorted(pairs.items()):
            rows = mx.array([r for r,_ in entries],dtype=mx.int32)
            ranks = mx.array([k for _,k in entries],dtype=mx.int32)
            out = self.expert(p+f'.experts.{expert}',flat[rows],weights[rows,ranks,None])
            y[rows] = y[rows]+out.astype(mx.float32)
        return (y+self.expert(p+'.shared_experts',flat,packed=False)).astype(x.dtype).reshape(x.shape)

    def propose(self, seed):
        if self.offset <= 0:raise ValueError('DSpark context must be primed')
        if self.offset+self.width > self.max_seq:raise ValueError('DSpark context limit')
        c = self.c
        ids = mx.full((1,self.width),c.dspark_noise_token_id,dtype=mx.int32)
        ids[:,0] = seed
        h = mx.repeat(self.s.embedding('embed',ids)[:,:,None,:],c.hc_mult,axis=2)
        pre = mx.zeros(h.shape[:-1],dtype=mx.float32); pre[:,:,0] = 1
        for layer in range(c.n_mtp_layers):
            p = f'mtp.{layer}'
            residual = h; ap,ao,ac = self.hc_mixes(p,h,'attn')
            h = self.hc_post(self.attention(layer,self.norm(p+'.attn_norm',self.hc_pre(h,pre))),residual,ao,ac)
            residual = h; pre,fo,fc = self.hc_mixes(p,h,'ffn')
            h = self.hc_post(self.moe(layer,self.norm(p+'.ffn_norm',self.hc_pre(h,ap))),residual,fo,fc)
        p = f'mtp.{c.n_mtp_layers-1}'
        hidden = self.hc_pre(h,pre)
        logits = self.norm(p+'.norm',hidden).astype(mx.float32)@self.w('head.weight',mx.float32).T
        tokens = []; confidence = []; previous = seed
        for i in range(self.width):
            embed = self.s.embedding(p+'.markov_head.embed',mx.array([previous],dtype=mx.int32))
            bias = embed.astype(mx.float32)@self.w(p+'.markov_head.head.weight',mx.float32).T
            previous = int(mx.argmax(logits[:,i]+bias,axis=-1).item()); tokens.append(previous)
            features = mx.concatenate([hidden[:,i].astype(mx.float32),embed.astype(mx.float32)],axis=-1)
            confidence.append(float(self.linear(p+'.confidence_head.proj',features,True).item()))
        return tokens, confidence


@dataclass
class TargetSnapshot:
    states: dict
    shared: dict
    hash_cache: object
    hidden: object

    @classmethod
    def take(cls, model):
        # mx.array creates distinct array objects: later indexed assignment must
        # not mutate the snapshot's Python object (MLX updates are functional).
        clone = lambda d:{k:mx.array(v) for k,v in d.items()}
        return cls({k:clone(v) for k,v in model.states.items()},clone(model.shared),
                   mx.array(model.hash.cache),mx.array(model.dspark_hidden))

    def restore(self, model):
        model.states = {k:{n:mx.array(a) for n,a in v.items()} for k,v in self.states.items()}
        model.shared = {k:mx.array(a) for k,a in self.shared.items()}
        model.hash.cache = mx.array(self.hash_cache)
        model.dspark_hidden = mx.array(self.hidden)
        # Physical expert banks retain their CURRENT contents, never stale IDs.
        model.lookups = {}; model.ages = {}; model.ticks = {}; model.main_slot_masks = {}


class AdaptiveDraftLength:
    """Grow after sustained full acceptance; cut wasted suffixes immediately."""
    def __init__(self, maximum, initial=2):
        if maximum < 1:raise ValueError('invalid adaptive maximum')
        self.maximum=maximum;self.width=min(initial,maximum);self.streak=0

    def observe(self, proposed, accepted, terminal=False):
        # Budget/context clipping and EOS provide censored evidence, not failures.
        if terminal or proposed != self.width:return
        if accepted == proposed:
            self.streak+=1
            if self.streak>=2:
                self.width=min(self.maximum,self.width+1);self.streak=0
        else:
            self.width=max(1,min(self.width,accepted+1));self.streak=0


class DSparkSession:
    """Explicit reference session; never installed by the normal Engine."""
    def __init__(self, model, config, verifier='serial', draft_limit=None, adaptive_length=False):
        if verifier not in ('serial','block'):raise ValueError('invalid verifier')
        self.verifier=verifier
        if model.boost_top != model.c.n_activated_experts:
            raise ValueError('DSpark requires natural expert routing')
        self.model = model
        if verifier=='block' and getattr(model,'verify_prefill',None) is None:
            from .prefill import Prefill
            model.verify_prefill=Prefill(32,hot_direct=True,reuse_hot=True)
        self.draft = DSparkDraft(model,config)
        self.draft_limit=self.draft.width if draft_limit is None else int(draft_limit)
        if not 1<=self.draft_limit<=self.draft.width:raise ValueError('invalid draft limit')
        self.length_policy=AdaptiveDraftLength(self.draft_limit) if adaptive_length else None
        model.dspark_capture_layers = self.draft.layers
        self.position = 0
        self.stats = dict(cycles=0,proposed=0,accepted=0,rejections=0,verify_tokens=0,replay_tokens=0)

    def prime(self, prompt_ids):
        if self.length_policy is not None:self.length_policy=AdaptiveDraftLength(self.draft_limit)
        self.model.reset_sequence(); self.draft.reset()
        logits = self.model(mx.array([prompt_ids],dtype=mx.int32),0)
        self.model.complete_forward(logits,self.model.dspark_hidden)
        if self.model.prefill_executor is not None:self.model.prefill_executor.release()
        self.position = len(prompt_ids)
        self.draft.append(self.model.dspark_hidden,0)
        return logits

    def forward(self, token, position):
        logits = self.model(mx.array([[token]],dtype=mx.int32),position)
        self.model.complete_forward(logits,self.model.dspark_hidden)
        return logits,mx.array(self.model.dspark_hidden)

    def cycle(self, logits, limit, eos=None):
        if limit <= 0:return [],logits
        seed = int(mx.argmax(logits,axis=-1).item())
        # No speculative writes on EOS or context boundary.
        if seed == eos:return [seed],logits
        remaining = self.model.max_seq-self.position
        if remaining <= 0:return [],logits
        policy=getattr(self,'length_policy',None)
        selected=policy.width if policy is not None else getattr(self,'draft_limit',self.draft.width)
        width = min(limit-1,remaining-1,selected)
        if width <= 0 or self.position+self.draft.width>self.model.max_seq:
            next_logits,hidden = self.forward(seed,self.position)
            self.draft.append(hidden,self.position);self.position += 1
            return [seed],next_logits
        began = perf_counter()
        proposed,_ = self.draft.propose(seed)
        self.stats['draft_seconds'] = self.stats.get('draft_seconds',0.)+perf_counter()-began
        proposed = proposed[:width]
        snapshot = TargetSnapshot.take(self.model)
        draft_windows = {k:mx.array(v) for k,v in self.draft.windows.items()}
        draft_offset = self.draft.offset
        candidates = [seed,*proposed]
        results = []
        try:
            began = perf_counter()
            if getattr(self,'verifier','serial')=='block':
                values,hidden,prefix,shared=self.model.verify_block(
                    mx.array([candidates],dtype=mx.int32),self.position)
                self.model.complete_forward(values,hidden)
                results=[(values[:,i],hidden[:,i:i+1]) for i in range(len(candidates))]
                self.stats['verify_tokens'] += len(candidates)
            else:
                for i,token in enumerate(candidates):
                    results.append(self.forward(token,self.position+i))
                    self.stats['verify_tokens'] += 1
            self.stats['verify_seconds'] = self.stats.get('verify_seconds',0.)+perf_counter()-began
            accepted = 0
            for i,token in enumerate(proposed):
                if token != int(mx.argmax(results[i][0],axis=-1).item()):break
                accepted += 1
                if token == eos:break
            committed = candidates[:1+accepted]
            if len(committed)<len(candidates):
                began = perf_counter()
                if getattr(self,'verifier','serial')=='block':
                    count=len(committed)
                    cache=mx.array(snapshot.hash_cache)
                    cache[self.position:self.position+count]=self.model.hash.cache[self.position:self.position+count]
                    TargetSnapshot(prefix[count-1],shared[count-1],cache,
                                   results[count-1][1]).restore(self.model)
                else:
                    snapshot.restore(self.model)
                    results = []
                    for i,token in enumerate(committed):
                        results.append(self.forward(token,self.position+i))
                        self.stats['replay_tokens'] += 1
                self.stats['rejections'] += 1
                self.stats['replay_seconds'] = self.stats.get('replay_seconds',0.)+perf_counter()-began
            for i,(_,hidden) in enumerate(results[:len(committed)]):
                self.draft.append(hidden,self.position+i)
            self.position += len(committed)
        except BaseException:
            snapshot.restore(self.model)
            self.draft.windows = draft_windows
            self.draft.offset = draft_offset
            raise
        self.stats['cycles'] += 1;self.stats['proposed'] += len(proposed);self.stats['accepted'] += accepted
        if policy is not None:
            policy.observe(len(proposed),accepted,terminal=eos in committed)
            self.stats.setdefault('length_decisions',[]).append(dict(
                proposed=len(proposed),accepted=accepted,next_width=policy.width))
        return committed,results[len(committed)-1][0]
