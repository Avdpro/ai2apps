import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import mlx.core as mx
from lru_metal_bank import LRUMetalBank
from metal_bank import native

class Tests(unittest.TestCase):
    def test_old_native_fails_before_any_read(self):
        with tempfile.TemporaryDirectory() as d:
            _,b=self.make_bank(d);original=native.copy_expert_slots
            try:
                del native.copy_expert_slots
                with patch.object(native,'preadv_fused_experts',side_effect=AssertionError('must not read')):
                    with self.assertRaisesRegex(RuntimeError,'rebuild'):
                        b.load_promotions([2],[0])
            finally:native.copy_expert_slots=original;b.close()
    def make_bank(self,d):
        p=Path(d)/'experts.bin';p.write_bytes(b''.join(bytes([i])*96 for i in range(6)))
        Path(str(p)+'.json').write_text(json.dumps({'expert_to_record':{i:i for i in range(6)},'record_bytes':96,'shapes':[[2,8]]*6}))
        return p,LRUMetalBank(p,[0,1],l0_slots=3)
    def test_copy_requires_no_ssd_and_fences_lazy_consumers(self):
        with tempfile.TemporaryDirectory() as d:
            p,b=self.make_bank(d)
            try:
                b.prepare([2,3]);old=b.arrays[0][0].astype(mx.float32).sum();b.track(old)
                before=b.bytes;p.write_bytes(b'')
                with patch.object(native,'preadv_fused_experts',side_effect=AssertionError('unexpected SSD read')):
                    self.assertEqual(b.load_promotions([2,3],[0,1]),{'copied':2,'ssd':0})
                self.assertEqual(old.item(),0);self.assertEqual(b.bytes,before);self.assertEqual(b.copy_bytes,192)
                for a in b.arrays:
                    self.assertTrue(np.all(np.array(a[0])==2));self.assertTrue(np.all(np.array(a[1])==3))
                self.assertEqual(b.main,{0:0,1:1}) # caller publishes only after success
            finally:b.close()
    def test_mixed_only_reads_nonresident(self):
        with tempfile.TemporaryDirectory() as d:
            _,b=self.make_bank(d)
            try:
                b.prepare([2]);before=b.bytes;original=native.preadv_fused_experts
                with patch.object(native,'preadv_fused_experts',wraps=original) as read:
                    b.load_promotions([2,4],[0,1])
                    self.assertEqual(read.call_count,1);self.assertEqual(read.call_args.args[3],[4]);self.assertEqual(read.call_args.args[4],[1])
                self.assertEqual(b.bytes-before,96);self.assertEqual(b.copy_bytes,96)
                for a in b.arrays:
                    self.assertTrue(np.all(np.array(a[0])==2));self.assertTrue(np.all(np.array(a[1])==4))
            finally:b.close()
    def test_invalid_copy_does_not_mutate(self):
        with tempfile.TemporaryDirectory() as d:
            _,b=self.make_bank(d)
            try:
                before=[np.array(a) for a in b.arrays]
                for src,dst in [([0],[0]),([2,3],[0,0]),([5],[0]),([2],[-1]),([2,3],[0])]:
                    with self.assertRaises((ValueError,IndexError,RuntimeError)):
                        native.copy_expert_slots(src,dst,list(b.arrays))
                for a,v in zip(b.arrays,before):self.assertTrue(np.array_equal(np.array(a),v))
            finally:b.close()

if __name__=='__main__':unittest.main()
