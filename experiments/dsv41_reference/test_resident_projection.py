import unittest
import torch
import cpu_kernel
from resident_projection import ProjectionCache

class ResidentTests(unittest.TestCase):
    def test_reuse_and_budget_fallback(self):
        old=torch.get_default_dtype()
        try:
            torch.set_default_dtype(torch.bfloat16);torch.manual_seed(72)
            b=torch.randn(47,96).to(torch.float8_e4m3fn)
            sb=torch.exp2(torch.randint(-3,4,(2,3)).float()).to(torch.float8_e8m0fnu)
            for limit in (0,1024*1024):
                cache=ProjectionCache(limit)
                for m in (5,1,3):
                    a=torch.randn(m,96).to(torch.float8_e4m3fn)
                    sa=torch.exp2(torch.randint(-3,4,(m,3)).float()).to(torch.float8_e8m0fnu)
                    expected=cpu_kernel.fp8_gemm(a,sa,b,sb,block_size=32)
                    actual=cache.gemm((0,'wo_b'),a,sa,b,sb)
                    self.assertTrue(torch.equal(actual.view(torch.uint8),expected.view(torch.uint8)))
                self.assertLessEqual(cache.stats['payload_bytes'],limit)
                self.assertEqual(cache.stats['hits'],2 if limit else 0)
                self.assertEqual(cache.stats['misses'],1 if limit else 3)
        finally:torch.set_default_dtype(old)

if __name__=='__main__':unittest.main()
