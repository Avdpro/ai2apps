import unittest
import torch
import cpu_kernel
import packed_projection

class PackedTests(unittest.TestCase):
    def test_shape_and_scale_cases(self):
        torch.set_default_dtype(torch.bfloat16);torch.manual_seed(29)
        for m,n,k in [(1,47,64),(5,128,160),(17,33,96)]:
            a=(torch.randn(m,k)*8).to(torch.float8_e4m3fn)
            b=(torch.randn(n,k)*8).to(torch.float8_e4m3fn)
            sa=torch.exp2(torch.randint(-4,5,(m,k//32)).float()).to(torch.float8_e8m0fnu)
            sb=torch.exp2(torch.randint(-4,5,((n+31)//32,k//32)).float()).to(torch.float8_e8m0fnu)
            self.assertTrue(torch.equal(cpu_kernel.fp8_gemm(a,sa,b,sb,block_size=32),packed_projection.fp8_gemm(a,sa,b,sb,block_size=32)),(m,n,k))
    def test_reject_other_group(self):
        with self.assertRaises(ValueError):packed_projection.fp8_gemm(None,None,None,None,block_size=128)

if __name__=='__main__':unittest.main()
