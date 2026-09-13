import json
import struct
import tempfile
import unittest
from pathlib import Path
import torch
import cpu_kernel as k
from run_reference import Store

class ReferenceTests(unittest.TestCase):
    def setUp(self): torch.set_default_dtype(torch.bfloat16)
    def test_fp4_all_codes_and_ties(self):
        raw=torch.arange(16,dtype=torch.uint8).repeat_interleave(2)
        x=k.FP4[raw.long()].reshape(1,32)
        packed,scale=k.fp4_act_quant(x,32)
        expected=raw[::2] | raw[1::2]<<4
        self.assertTrue(torch.equal(packed.view(torch.uint8).flatten(),expected))
        self.assertEqual(scale.float().item(),1)
        vals=torch.tensor([.25,.75,1.25,1.75,2.5,3.5,5,6]*4,dtype=torch.float32).reshape(1,32)
        out=k.fp4_act_quant(vals.clone(),32,True)
        self.assertEqual(out[0,:8].tolist(),[0,1,1,2,2,4,4,6])
    def test_fp8_quant_scale_and_zero(self):
        x=torch.zeros(2,64,dtype=torch.bfloat16); x[1,0]=450
        q,s=k.act_quant(x,32,'ue8m0',torch.float8_e8m0fnu)
        self.assertTrue(torch.isfinite(s.float()).all())
        self.assertEqual(s.float()[1,0].item(),2)
        self.assertEqual(q.float()[1,0].item(),224)
    def test_gemm_exact_integer_fixture(self):
        # Exactly representable products; independent dense dequantization oracle.
        torch.manual_seed(4)
        a=torch.randint(-4,5,(3,64)).float().to(torch.float8_e4m3fn)
        packed=torch.randint(0,256,(8,32),dtype=torch.uint8)
        ws=torch.ones(8,2).to(torch.float8_e8m0fnu)
        s=torch.ones(3,2).to(torch.float8_e8m0fnu)
        w=torch.stack((k.FP4[(packed&15).long()],k.FP4[(packed>>4).long()]),-1).flatten(-2)
        got=k.fp4_gemm(a,s,packed.view(torch.float4_e2m1fn_x2),ws,act_block_size=32)
        self.assertTrue(torch.equal(got,(a.float()@w.T).bfloat16()))
    def test_attention_mask_sink_and_empty(self):
        q=torch.zeros(1,1,2,32); kv=torch.ones(1,3,32)
        ids=torch.tensor([[[0,1,-1]]],dtype=torch.int32)
        y=k.sparse_attn(q,kv,torch.zeros(2,dtype=torch.float32),ids,1)
        self.assertTrue(torch.equal(y,torch.full_like(y,2/3)))
        z=k.sparse_attn(q,kv,torch.zeros(2,dtype=torch.float32),torch.full_like(ids,-1),1)
        self.assertTrue(torch.equal(z,torch.zeros_like(z)))
    def test_fp8_nonuniform_row_block_scales(self):
        torch.manual_seed(7)
        a=torch.randint(-3,4,(2,64)).float().to(torch.float8_e4m3fn)
        b=torch.randint(-3,4,(64,64)).float().to(torch.float8_e4m3fn)
        sa=torch.tensor([[1.,2.],[4.,.5]],dtype=torch.float32)
        sb=torch.tensor([[.5,4.],[2.,1.]],dtype=torch.float32)
        got=k.fp8_gemm(a,sa,b,sb,block_size=32)
        aa=a.float()*sa.repeat_interleave(32,-1)
        bb=b.float()*sb.repeat_interleave(32,0).repeat_interleave(32,1)
        self.assertTrue(torch.equal(got,(aa@bb.T).bfloat16()))
    def test_attention_two_blocks_with_sink(self):
        q=torch.zeros(1,1,2,32); kv=torch.ones(1,65,32)
        ids=torch.arange(65,dtype=torch.int32).reshape(1,1,65)
        got=k.sparse_attn(q,kv,torch.zeros(2,dtype=torch.float32),ids,1)
        self.assertTrue(torch.equal(got,torch.full_like(got,65/66)))
    def test_ssd_rows_repeat_and_bounds(self):
        with tempfile.TemporaryDirectory() as d:
            t=torch.arange(24,dtype=torch.float32).reshape(6,4)
            raw=t.numpy().tobytes()
            h=json.dumps({'x':{'dtype':'F32','shape':[6,4],'data_offsets':[0,len(raw)]}}).encode()
            Path(d,'x.safetensors').write_bytes(struct.pack('<Q',len(h))+h+raw)
            s=Store(Path(d))
            try:
                self.assertTrue(torch.equal(s.read('x'),t))
                ids=torch.tensor([[5,0,5]])
                self.assertTrue(torch.equal(s.read('x',ids),t[ids]))
                with self.assertRaises(IndexError): s.read('x',torch.tensor([6]))
            finally: s.close()

if __name__=='__main__': unittest.main()
