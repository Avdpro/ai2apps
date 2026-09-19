"""Compare live MLX policy decisions against independent frozen-route replay."""
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
sys.path.insert(0,str(Path('experiments/dsv41_mlx').resolve()))
sys.path.insert(0,str(Path('experiments/dsv41_reference').resolve()))
from adaptive import AdaptiveModel
import mlx.core as mx
from simulate import simulate,POLICIES,initial

class RuntimePolicyTest(unittest.TestCase):
    def test_packed_age_range_fails_before_readback(self):
        m=AdaptiveModel.__new__(AdaptiveModel);m.l1_policy='eviction_dual'
        m.ticks={0:2**24};m.c=SimpleNamespace(n_activated_experts=6)
        with self.assertRaisesRegex(RuntimeError,'exact float32'):
            m.miss_metadata(0,None)
    def test_replay(self):
        path=Path('artifacts/dsv41-l1-shape-20260915/trace40/coding-en-train-18-r0/routes.npz')
        if not path.exists():path=next(Path('artifacts/dsv41-l1-shape-20260915/trace40').glob('*/routes.npz'))
        with np.load(path) as z:prefill=z['prefill'];decode=z['decode']
        for policy in [p for p in POLICIES if p['name'] in ['baseline','dual_fast75','probation32_8']]:
            for layer in [0,19,39]:
                # Trace axes are layer, token, top-k.
                pre=prefill[layer];dec=decode[layer]
                ref=simulate(pre,dec,policy,events=True)
                main,hot=initial(pre,40);bank=SimpleNamespace(main=main,hot=hot)
                m=AdaptiveModel.__new__(AdaptiveModel);m.c=SimpleNamespace(n_routed_experts=384,n_activated_experts=6)
                m.l1_policy=policy['name'];m.dynamic=True;m.protected={};m.role_swaps=0;m.lookups={};m.promotions=[]
                score=mx.array(np.bincount(pre.reshape(-1).astype(int),minlength=384).astype(np.float32)*np.float32(12/len(pre)))
                m.frequency={layer:score};m.fast={layer:score/(32*(1-2**(-1/8)))};m.slow={layer:score/(32*(1-2**(-1/64)))};m.recent={layer:mx.full((32,6),-1,dtype=mx.int32)}
                observed=[];m.promote_payload=lambda b,p:observed.append({'experts':[x[0] for x in p],'slots':[x[2] for x in p]})
                for step,(ids,event) in enumerate(zip(dec,ref['events']),1):
                    m.decode_step=step;observed.clear();m.maintain(layer,bank)
                    expected=[r for r in event['reads'] if all(s<40 for s in r['slots'])]
                    self.assertEqual(observed,expected,(policy['name'],layer,step))
                    m.observe(layer,mx.array(ids.astype(np.int32)))
                    for read in event['reads']:
                        for e,s in zip(read['experts'],read['slots']):
                            if s>=40:
                                bank.hot={v:t for v,t in bank.hot.items() if t!=s};bank.hot[e]=s
                    mx.eval(*m.frequency.values(),*m.fast.values(),*m.slow.values(),*m.recent.values())
if __name__=='__main__':unittest.main()
