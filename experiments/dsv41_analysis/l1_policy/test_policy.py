import unittest
import numpy as np
from simulate import POLICIES,simulate
from replay import layer_replay

class Tests(unittest.TestCase):
    def test_baseline_exact_events(self):
        rng=np.random.default_rng(741)
        pre=np.array([sorted(rng.choice(384,6,replace=False)) for _ in range(29)])
        dec=np.array([sorted(rng.choice(90,6,replace=False)) for _ in range(80)])
        a=simulate(pre,dec,POLICIES[0],events=True);b=layer_replay(pre,dec,40)
        self.assertEqual(a['events'],b['events']);self.assertEqual(a['loads'],b['loads'])
    def test_all_policies_are_causal(self):
        rng=np.random.default_rng(92);pre=np.arange(60).reshape(10,6)
        left=np.array([sorted(rng.choice(120,6,replace=False)) for _ in range(80)])
        right=left.copy();right[35:]=np.arange(200,206)
        for policy in POLICIES:
            a=simulate(pre,left,policy,events=True);b=simulate(pre,right,policy,events=True)
            self.assertEqual(a['events'][:35],b['events'][:35],policy['name'])
            self.assertEqual(a['loads'],a['misses']+a['promotion_loads'])
    def test_promotion_copy_is_not_free(self):
        pre=np.arange(60).reshape(10,6);dec=np.tile(np.arange(54,60),(64,1))
        a=simulate(pre,dec,POLICIES[0])
        self.assertGreater(a['hot_rereads'],0);self.assertEqual(a['loads'],a['misses']+a['promotion_loads'])

if __name__=='__main__':unittest.main()
