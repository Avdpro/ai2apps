import tempfile,unittest
from unittest.mock import patch
import numpy as np
import mlx.core as mx
from test_promotion_copy import Tests
from metal_bank import native

class EvictionTests(unittest.TestCase):
    def test_one_fence_copy_before_overwrite_and_protect_current_main(self):
        with tempfile.TemporaryDirectory() as d:
            _,b=Tests().make_bank(d)
            try:
                b.prepare([2,3,4]);scores=[0,0,10,4,4,1]
                old=b.arrays[0][b.hot[2]].astype(mx.float32).sum();b.track(old)
                before=b.fence_calls;read=native.preadv_fused_experts
                with patch.object(native,'preadv_fused_experts',wraps=read) as spy:
                    b.prepare([0,5],promotion_scores=scores)
                    self.assertEqual(spy.call_count,1);self.assertEqual(spy.call_args.args[3],[5])
                self.assertEqual(b.fence_calls-before,1);self.assertEqual(old.item(),32)
                self.assertEqual(b.main,{0:0,2:1});self.assertEqual(b.last_eviction_promotions,[(2,1,1)])
                for a in b.arrays:
                    self.assertTrue(np.all(np.array(a[1])==2));self.assertTrue(np.all(np.array(a[b.hot[5]])==5))
            finally:b.close()
    def test_free_hot_slot_and_low_score_do_not_promote(self):
        with tempfile.TemporaryDirectory() as d:
            _,b=Tests().make_bank(d)
            try:
                scores=[20,20,10,10,10,10]
                b.prepare([2],promotion_scores=scores);self.assertEqual(b.copy_experts,0)
                b.prepare([3,4],promotion_scores=scores)
                before=b.fence_calls;b.prepare([5],promotion_scores=scores)
                self.assertEqual(b.fence_calls-before,1);self.assertEqual(b.copy_experts,0)
                before=b.fence_calls;b.prepare([5],promotion_scores=scores);self.assertEqual(b.fence_calls,before)
            finally:b.close()
if __name__=='__main__':unittest.main()
