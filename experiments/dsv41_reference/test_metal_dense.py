import unittest
import torch
import cpu_kernel
import metal_dense

class DenseTests(unittest.TestCase):
    def setUp(self):torch.set_default_dtype(torch.bfloat16)
    def test_all_finite_fp8_weight_codes(self):
        codes=torch.tensor([i for i in range(256) if i not in (127,255)],dtype=torch.uint8)
        b=codes[:,None].repeat(1,32).view(torch.float8_e4m3fn)
        a=torch.ones(1,32).to(torch.float8_e4m3fn)
        sa=torch.ones(1,1).to(torch.float8_e8m0fnu);sb=torch.ones(8,1).to(torch.float8_e8m0fnu)
        expected=cpu_kernel.fp8_gemm(a,sa,b,sb,block_size=32)
        actual=metal_dense.fp8_gemm(a,sa,b,sb,block_size=32)
        self.assertTrue(torch.equal(actual,expected))
    def test_nonuniform_scales_partial_row_block(self):
        torch.manual_seed(3)
        a=torch.randint(-4,5,(3,64)).float().to(torch.float8_e4m3fn)
        b=torch.randint(-4,5,(47,64)).float().to(torch.float8_e4m3fn)
        sa=torch.tensor([[.5,2],[1,4],[2,.25]],dtype=torch.float32).to(torch.float8_e8m0fnu)
        sb=torch.tensor([[.25,1],[2,4]],dtype=torch.float32).to(torch.float8_e8m0fnu)
        self.assertTrue(torch.equal(metal_dense.fp8_gemm(a,sa,b,sb,block_size=32),cpu_kernel.fp8_gemm(a,sa,b,sb,block_size=32)))
    def test_reject_nonreference_group(self):
        with self.assertRaises(ValueError):metal_dense.fp8_gemm(None,None,None,None,block_size=128)

if __name__=='__main__':unittest.main()
