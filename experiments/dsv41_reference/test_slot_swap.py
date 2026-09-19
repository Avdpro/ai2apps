import tempfile,unittest,random
from unittest.mock import patch
import numpy as np
from test_promotion_copy import Tests as Fixture

class SwapTests(unittest.TestCase):
    def test_random_logical_parity_and_zero_copy(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            _,copy=Fixture().make_bank(a);_,swap=Fixture().make_bank(b)
            rng=random.Random(913)
            try:
                with patch.object(swap,'_copy_ready',side_effect=AssertionError('swap must not copy')):
                    for step in range(160):
                        ids=rng.sample(range(6),rng.randint(1,3));scores=[rng.random()*20 for _ in range(6)]
                        for bank,zero in [(copy,False),(swap,True)]:
                            before=bank.fence_calls
                            missing=sum(e not in bank.main and e not in bank.hot for e in ids)
                            slots=bank.prepare(ids,promotion_scores=scores,slot_swap=zero)
                            self.assertEqual(bank.fence_calls-before,int(bool(missing)))
                            main=set(bank.main.values());hot=set(bank.hot.values())
                            self.assertFalse(main & hot);self.assertEqual(len(main),2);self.assertLessEqual(len(hot),3)
                            for e,s in zip(ids,slots.tolist()):
                                for array in bank.arrays:self.assertTrue(np.all(np.array(array[s])==e))
                        self.assertEqual(set(copy.main),set(swap.main));self.assertEqual(list(copy.hot),list(swap.hot))
                        self.assertEqual(copy.bytes,swap.bytes)
                self.assertGreater(swap.slot_swaps,0);self.assertEqual(swap.copy_bytes,0)
                self.assertGreater(copy.copy_bytes,0)
            finally:copy.close();swap.close()

if __name__=='__main__':unittest.main()
