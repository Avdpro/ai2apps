"""Transactional verification tests independent of the 510 GB checkpoint."""
from types import SimpleNamespace
import pytest
import mlx.core as mx
from omlx.patches.deepseek_v41.dspark import DSparkSession,TargetSnapshot

class Draft:
    width=3
    def __init__(self,proposal):self.proposal=proposal;self.offset=4;self.committed=[];self.windows={}
    def propose(self,seed):return self.proposal,[]
    def append(self,hidden,start):
        assert start==self.offset
        self.offset+=1;self.committed.append(int(hidden.item()))

class FakeModel:
    def __init__(self):
        self.max_seq=32;self.states={0:{'window':mx.array([0])}};self.shared={}
        self.hash=SimpleNamespace(cache=mx.zeros((32,),dtype=mx.int32))
        self.dspark_hidden=mx.array([0]);self.lookups={1:'old'};self.banks={1:'resident'}
    def __call__(self,ids,start):
        token=int(ids.item());self.hash.cache[start]=token
        self.states[0]['window'][0]=token;self.dspark_hidden=mx.array([token])
        return scores(token+1)
    def complete_forward(self,*args):mx.eval(*args)
    def verify_block(self,ids,start):
        values=[];hidden=[];prefix=[];shared=[]
        for i,token in enumerate(ids[0].tolist()):
            values.append(self(mx.array([[token]]),start+i))
            hidden.append(mx.array(self.dspark_hidden).reshape(1,1,1))
            prefix.append({0:{'window':mx.array(self.states[0]['window'])}})
            shared.append({})
        return mx.stack(values,axis=1),mx.concatenate(hidden,axis=1),prefix,shared

def scores(token):return mx.array([[float(i==token) for i in range(16)]])

def session(proposal):
    s=object.__new__(DSparkSession);s.model=FakeModel();s.draft=Draft(proposal);s.position=4
    s.stats=dict(cycles=0,proposed=0,accepted=0,rejections=0,verify_tokens=0,replay_tokens=0)
    return s

@pytest.mark.parametrize('proposal,expected',[
    ([2,3,4],[1,2,3,4]),([9,3,4],[1]),([2,9,4],[1,2]),([2,3,9],[1,2,3])])
@pytest.mark.parametrize('verifier',['serial','block'])
def test_accept_prefix_and_restore_rejected_state(proposal,expected,verifier):
    s=session(proposal);s.verifier=verifier;out,logits=s.cycle(scores(1),4)
    assert out==expected
    assert int(mx.argmax(logits).item())==expected[-1]+1
    assert s.model.hash.cache[4:4+len(out)].tolist()==out
    assert s.model.hash.cache[4+len(out):8].tolist()==[0]*(4-len(out))
    assert s.draft.committed==out and s.position==4+len(out)
    assert s.model.banks=={1:'resident'}
    if verifier=='block':assert s.stats['replay_tokens']==0

@pytest.mark.parametrize('limit',[1,2,3])
def test_budget(limit):
    s=session([2,3,4]);out,_=s.cycle(scores(1),limit)
    assert out==list(range(1,limit+1))

@pytest.mark.parametrize('verifier',['serial','block'])
def test_eos_inside_accepted_prefix(verifier):
    s=session([2,3,4]);s.verifier=verifier;out,_=s.cycle(scores(1),4,eos=2)
    assert out==[1,2] and s.draft.committed==out
    assert s.model.hash.cache[6:8].tolist()==[0,0]

def test_seed_eos_does_not_mutate_state():
    s=session([2,3,4]);out,_=s.cycle(scores(1),4,eos=1)
    assert out==[1] and s.position==4 and not s.draft.committed

def test_snapshot_owns_array_objects():
    m=FakeModel();snap=TargetSnapshot.take(m);m(mx.array([[7]]),4)
    snap.restore(m)
    assert m.hash.cache[4].item()==0 and m.states[0]['window'].item()==0
    assert m.lookups=={} and m.banks=={1:'resident'}

def test_verification_exception_restores_target(monkeypatch):
    s=session([2,3,4]);original=s.forward
    def fail(token,position):
        value=original(token,position)
        if position==6:raise RuntimeError('injected verification failure')
        return value
    monkeypatch.setattr(s,'forward',fail)
    with pytest.raises(RuntimeError,match='injected'):s.cycle(scores(1),4)
    assert s.position==4 and s.draft.offset==4
    assert s.model.hash.cache[4:8].tolist()==[0]*4

def test_context_boundary_uses_plain_decode():
    s=session([2,3,4]);s.model.max_seq=5
    out,_=s.cycle(scores(1),4)
    assert out==[1] and s.position==5
    out,_=s.cycle(scores(2),4)
    assert out==[]

def test_index_rebinds_source_between_compression_boundaries(monkeypatch):
    from omlx.patches.deepseek_v41 import model as module
    m=object.__new__(module.Model)
    m.c=SimpleNamespace(compress_ratios=[2],rope_head_dim=32,kv_source_layers=[0],
                        index_n_heads=1,index_head_dim=32,candidate_source_layer=-1,index_topk=2)
    source=mx.ones((1,8,32));m.states={0:{'index':source}}
    m.shared={'index':mx.zeros((1,8,32))};m.freqs={True:None}
    m.linear=lambda p,x:mx.ones((1,1,1 if p.endswith('weights_proj') else 32))
    monkeypatch.setattr(module,'rope',lambda q,*a:q)
    monkeypatch.setattr(module,'quant',lambda q,*a:q)
    seen=[]
    def scores(q,k,w):
        seen.append(k);return mx.zeros((1,1,k.shape[1]))
    monkeypatch.setattr(module,'index_scores',scores)
    monkeypatch.setattr(module,'index_topk',lambda score,n:mx.array([[[0,1]]]))
    m.index(0,mx.zeros((1,1,32)),mx.zeros((1,1,32)),None,4,128)
    assert mx.all(seen[0]==1).item()


@pytest.mark.parametrize('optimized',[False,True])
def test_verify_prefill_reuses_hot_without_disk_reads(optimized):
    from omlx.patches.deepseek_v41.prefill import Prefill
    bank=SimpleNamespace(main={10:0},hot={11:1},info={'shapes':[(1,)]*6})
    def unexpected(*args,**kwargs):raise AssertionError('resident Hot must not be loaded again')
    bank.prepare=unexpected
    tracked=[];bank.track=tracked.append
    model=SimpleNamespace(hot_slots=1,c=SimpleNamespace(dim=2))
    model.expert=lambda flat,target,slots,weights,segments:flat.astype(mx.bfloat16)
    executor=Prefill(2,reuse_hot=True,lazy_scratch=optimized,defer_completion=optimized)
    out=executor.dispatch(model,0,mx.array([[1.,2.],[3.,4.]]),mx.array([[10],[11]]),
                          mx.ones((2,1)),bank,mx.zeros((2,12)))
    assert out.tolist()==[[[1.,2.]],[[3.,4.]]]
    assert executor.report['read_bytes']==0
    if optimized:
        assert executor.buffers==[None,None] and len(tracked)==1
    executor.release()

@pytest.mark.parametrize('optimized',[False,True])
def test_verify_retention_preserves_reused_hot_over_cold_candidate(monkeypatch,optimized):
    from omlx.patches.deepseek_v41 import prefill
    bank=SimpleNamespace(main={},hot={11:0},info={'shapes':[(1,)]*6,'record_bytes':6},
                         fd=0,records={12:12},workers=1)
    def unexpected(*a,**kw):raise AssertionError('useful Hot must survive cold scratch load')
    bank.prepare=unexpected
    tracked=[];bank.track=tracked.append
    reads=[]
    def read(fd,offset,size,records,slots,*args):
        reads.extend(records);return len(records)*size
    monkeypatch.setattr(prefill.native,'preadv_fused_experts',read)
    model=SimpleNamespace(hot_slots=1,c=SimpleNamespace(dim=2))
    model.expert=lambda flat,target,slots,weights,segments:flat.astype(mx.bfloat16)
    executor=prefill.Prefill(2,reuse_hot=True,retain_routes=True,lazy_scratch=optimized,defer_completion=optimized)
    out=executor.dispatch(model,0,mx.array([[1.,2.],[3.,4.],[5.,6.]]),
                          mx.array([[11],[11],[12]]),mx.ones((3,1)),bank,mx.zeros((3,13)))
    assert out.tolist()==[[[1.,2.]],[[3.,4.]],[[5.,6.]]]
    assert bank.hot=={11:0} and reads==[12]
    assert executor.report['read_bytes']==6
    if optimized:
        assert executor.buffers[0] is not None and executor.buffers[1] is None
        assert len(tracked)==1
    executor.release()

@pytest.mark.parametrize('width',[1,3,4,6])
def test_batched_qmv_matches_individual_fp8_projection(width):
    import numpy as np
    from omlx.patches.deepseek_v41.model import Model
    rng=np.random.default_rng(123)
    bits=rng.integers(0,126,size=(64,128),dtype=np.uint8)
    bits |= rng.integers(0,2,size=bits.shape,dtype=np.uint8)*128
    packed=mx.array(bits.view(np.uint32))
    scales=mx.full((64,4),127,dtype=mx.uint8)
    m=object.__new__(Model);m.s=SimpleNamespace(entries={'p.weight':(0,0,{'dtype':'F8_E4M3'})},fp8=lambda name:(packed,scales))
    x=mx.array(rng.normal(size=(1,width,128)).astype(np.float32)).astype(mx.bfloat16)
    reference=mx.concatenate([m.linear('p',x[:,i:i+1]) for i in range(width)],axis=1)
    m.verify_active=True;actual=m.linear('p',x)
    assert mx.all(actual==reference).item()

def test_verify_active_flag_clears_after_exception(monkeypatch):
    from omlx.patches.deepseek_v41.model import Model
    m=object.__new__(Model)
    def fail(*a):
        assert m.verify_active
        raise RuntimeError('intentional')
    monkeypatch.setattr(m,'_verify_block',fail)
    with pytest.raises(RuntimeError):m.verify_block(None,0)
    assert not m.verify_active

def test_hc_verify_preserves_single_token_coefficients():
    import numpy as np
    from omlx.patches.deepseek_v41.model import Model
    rng=np.random.default_rng(42);m=object.__new__(Model)
    m.c=SimpleNamespace(norm_eps=1e-20,hc_mult=4,hc_sinkhorn_iters=20,hc_eps=1e-6)
    weights={'p.hc_attn_fn':mx.array(rng.normal(0,.01,(24,20480)).astype(np.float32)),
             'p.hc_attn_scale':mx.array([.1,.2,.3]),'p.hc_attn_base':mx.zeros((24,))}
    m.w=lambda name:weights[name]
    x=mx.array(rng.normal(size=(1,6,4,5120)).astype(np.float32)).astype(mx.bfloat16)
    parts=[m.hc_mixes('p',x[:,i:i+1],'attn') for i in range(6)]
    reference=[mx.concatenate([v[j] for v in parts],axis=1) for j in range(3)]
    m.verify_active=True;actual=m.hc_mixes('p',x,'attn')
    assert all(mx.all(a==b).item() for a,b in zip(actual,reference))


def test_adaptive_length_grows_slowly_and_cuts_rejected_suffix():
    from omlx.patches.deepseek_v41.dspark import AdaptiveDraftLength
    p=AdaptiveDraftLength(5)
    for expected in [3,4,5,5]:
        w=p.width;p.observe(w,w);assert p.width==w
        p.observe(w,w);assert p.width==expected
    p.observe(5,1);assert p.width==2
    p.observe(2,0);assert p.width==1
    p.observe(1,0);assert p.width==1


def test_adaptive_length_ignores_clipped_and_terminal_evidence():
    from omlx.patches.deepseek_v41.dspark import AdaptiveDraftLength
    p=AdaptiveDraftLength(5)
    p.observe(1,1);p.observe(2,0,terminal=True)
    assert p.width==2 and p.streak==0
    assert AdaptiveDraftLength(1).width==1


@pytest.mark.parametrize('proposal,expected', [([2,3,4],[1,2,3]),([2,9,4],[1,2]),([9,3,4],[1])])
def test_dynamic_block_preserves_exact_committed_context(proposal,expected):
    from omlx.patches.deepseek_v41.dspark import AdaptiveDraftLength
    s=session(proposal);s.verifier='block';s.length_policy=AdaptiveDraftLength(3)
    out,logits=s.cycle(scores(1),4)
    assert out==expected and s.draft.committed==expected
    assert s.model.hash.cache[4:8].tolist()==expected+[0]*(4-len(expected))
    assert s.stats['replay_tokens']==0
    assert s.stats['length_decisions'][0]['accepted']==len(expected)-1


def test_partial_acceptance_does_not_overreact_to_one_rejected_tail():
    from omlx.patches.deepseek_v41.dspark import AdaptiveDraftLength
    p=AdaptiveDraftLength(5)
    p.observe(2,1)
    assert p.width==2 and p.streak==0
    p.observe(2,0)
    assert p.width==1



@pytest.mark.parametrize('write_slot',[1,0])
@pytest.mark.parametrize('independent',[False,True])
def test_overlapped_hot_load_only_reads_immutable_slots(write_slot,independent):
    from omlx.patches.deepseek_v41.prefill import Prefill
    events=[]
    bank=SimpleNamespace(main={10:0},hot={11:1},info={'shapes':[(1,)]*6},track=lambda value:None)
    def prepare(ids,on_read_ready=None):
        events.append('fence');on_read_ready([write_slot]);events.append('read')
        bank.hot={12:1}
    bank.prepare=prepare
    def expert(flat,target,slots,weights,segments):
        events.append(('compute',slots.tolist()));return flat.astype(mx.bfloat16)
    model=SimpleNamespace(hot_slots=1,c=SimpleNamespace(dim=2),expert=expert)
    p=Prefill(2,reuse_hot=True,lazy_scratch=True,defer_completion=True,overlap_hot=True)
    args=(model,0,mx.array([[1.,2.],[3.,4.],[5.,6.]]),mx.array([[11],[10],[12]]),mx.ones((3,1)),bank,mx.zeros((3,13)))
    kwargs={'on_io_ready':lambda:events.append('shared')} if independent else {}
    if write_slot==0:
        with pytest.raises(RuntimeError,match='overwritten'):p.dispatch(*args,**kwargs)
        assert events==[('compute',[1]),'fence']
    else:
        out=p.dispatch(*args,**kwargs)
        assert out.tolist()==[[[1.,2.]],[[3.,4.]],[[5.,6.]]]
        assert events==[('compute',[1]),'fence']+(['shared'] if independent else [])+[('compute',[0]),'read',('compute',[1])]
    p.release()


def test_bank_overlap_callback_runs_after_fence_before_native_read():
    from omlx.patches.deepseek_v41.resident_bank import MetalBank,LRUMetalBank
    events=[];b=object.__new__(MetalBank)
    b._fence=lambda:events.append('fence')
    b._read_ready=lambda ids,slots:events.append(('read',ids,slots))
    b._load([2],[7],on_read_ready=lambda slots:events.append(('launch',slots)))
    assert events==['fence',('launch',[7]),('read',[2],[7])]
    with pytest.raises(ValueError,match='slot roles'):
        LRUMetalBank.prepare(b,[],promotion_scores=[],on_read_ready=lambda slots:None)


def test_overlap_prepare_keeps_requested_hot_and_main_slots_immutable():
    from omlx.patches.deepseek_v41.resident_bank import LRUMetalBank
    b=object.__new__(LRUMetalBank)
    b.main={10:0};b.hot={11:1,13:2};b.capacity=3;b.l0_slots=2
    b.records={i:i for i in [10,11,12,13]};b.hits=b.misses=b.evictions=0
    events=[]
    def load(ids,slots,on_read_ready=None):
        on_read_ready(slots);events.append((ids,slots))
    b._load=load
    slots=b.prepare([11,12],on_read_ready=lambda slots:events.append(('launch',slots)))
    assert events==[('launch',[2]),([12],[2])]
    assert b.main=={10:0} and b.hot=={11:1,12:2}
    assert slots.tolist()==[1,2]


def test_scratch_release_does_not_require_cyclic_gc(monkeypatch):
    import gc
    import weakref
    from omlx.patches.deepseek_v41 import prefill

    class Payload:
        pass

    refs=[]
    def allocate(*args,**kwargs):
        payload=Payload();refs.append(weakref.ref(payload));return payload
    monkeypatch.setattr(prefill.mx,'zeros',allocate)
    pending=object();evaluated=[]
    def evaluate(*arrays):
        if arrays==(pending,):
            assert all(ref() is not None for ref in refs)
            evaluated.append(pending)
    monkeypatch.setattr(prefill.mx,'eval',evaluate)
    executor=prefill.Prefill(2)
    was_enabled=gc.isenabled();gc.disable()
    try:
        for _ in range(3):
            executor.buffers=[None,None]
            bank=SimpleNamespace(info={'shapes':[(4,),(8,)]})
            executor.allocate_scratch(0,bank)
            executor.allocate_scratch(1,bank)
            executor.pending=[pending,None]
            executor.release()
            assert all(ref() is None for ref in refs)
            refs.clear()
        assert len(evaluated)==3
        executor.release()  # idempotent
    finally:
        if was_enabled:gc.enable()


def test_independent_callback_runs_before_native_read(monkeypatch):
    from omlx.patches.deepseek_v41 import prefill
    events=[]
    bank=SimpleNamespace(main={},hot={},info={'shapes':[(1,)]*6,'record_bytes':6},fd=0,records={12:12},workers=1)
    def read(fd,offset,size,records,slots,*args):
        assert events==['ready'];events.append('read');return len(records)*size
    monkeypatch.setattr(prefill.native,'preadv_fused_experts',read)
    model=SimpleNamespace(hot_slots=1,c=SimpleNamespace(dim=2))
    model.expert=lambda flat,target,slots,weights,segments:flat.astype(mx.bfloat16)
    executor=prefill.Prefill(2,reuse_hot=True,retain_routes=True,lazy_scratch=True,defer_completion=True)
    # Retain an existing hot expert; missing expert must be streamed.
    bank.hot={11:0};bank.track=lambda y:None
    out=executor.dispatch(model,0,mx.array([[1.,2.],[3.,4.],[5.,6.]]),mx.array([[11],[11],[12]]),mx.ones((3,1)),bank,mx.zeros((3,13)),on_io_ready=lambda:events.append('ready'))
    assert out.tolist()==[[[1.,2.]],[[3.,4.]],[[5.,6.]]]
    assert events==['ready','read']
    executor.release()
