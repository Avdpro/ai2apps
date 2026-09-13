import json,tempfile,unittest
from pathlib import Path
import mlx.core as mx
from lru_metal_bank import LRUMetalBank

class LRUTests(unittest.TestCase):
    def test_free_slots_lru_protection_and_failed_publication(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'records.bin';path.write_bytes(b''.join(bytes([i])*96 for i in range(5)))
            Path(str(path)+'.json').write_text(json.dumps({'expert_to_record':{i:i for i in range(6)},'record_bytes':96,'shapes':[[2,8]]*6}))
            bank=LRUMetalBank(path,[0],l0_slots=3)
            try:
                bank.prepare([1]);bank.prepare([2]);bank.prepare([3])
                self.assertEqual(set(bank.hot),{1,2,3});self.assertEqual(bank.evictions,0)
                bank.prepare([1]);bank.prepare([4])
                self.assertEqual(set(bank.hot),{1,3,4})
                before=bank.bytes;slots=bank.prepare([3,1,4])
                self.assertEqual(bank.bytes,before)
                old=bank.arrays[0][slots[0]].astype(mx.float32).sum();bank.track(old)
                bank.prepare([2,1,4]);self.assertEqual(old.item(),48)
                self.assertEqual(set(bank.hot),{2,1,4})
                with self.assertRaises((IndexError,RuntimeError)):bank.prepare([5,1,4])
                self.assertNotIn(5,bank.hot);self.assertNotIn(2,bank.hot)
            finally:bank.close()

if __name__=='__main__':unittest.main()
