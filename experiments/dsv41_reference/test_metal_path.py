"""Requires Metal access; isolated native loader must already be built."""
import json,tempfile,unittest
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
import mlx.core as mx
import cpu_kernel
from metal_bank import MetalBank
from metal_expert import act_quant,silu_table,swiglu_kernel

class MetalTests(unittest.TestCase):
    def test_quantizer_realistic_range_and_boundaries(self):
        torch.manual_seed(8)
        x=(torch.randn(1024,32)*torch.logspace(-8,8,1024)[:,None]).bfloat16()
        x[0]=0;x[1]=448;x[2]=450
        q,s=act_quant(mx.array(x.float().numpy()).astype(mx.bfloat16));mx.eval(q,s)
        cq,cs=cpu_kernel.act_quant(x,32,'ue8m0',torch.float8_e8m0fnu)
        self.assertTrue(np.array_equal(np.array(q),cq.float().numpy()))
        self.assertTrue(np.array_equal(np.array(s),cs.float().numpy()))
    def test_swiglu_table_bf16_gate_domain_normal_range(self):
        bits=torch.arange(65536,dtype=torch.int32).to(torch.uint16)
        gate=bits.view(torch.bfloat16).float()
        mask=torch.isfinite(gate)&((gate.abs()>=1e-5)|(gate==0))
        gate=gate[mask];gate=gate[:(gate.numel()//128)*128].reshape(-1,128)
        up=torch.full_like(gate,.25);weights=torch.full((gate.shape[0],),.5)
        expected=(F.silu(gate.clamp(max=10))*up*weights[:,None]).bfloat16().float().numpy()
        result=swiglu_kernel()(inputs=[mx.array(gate.numpy()).astype(mx.bfloat16),mx.array(up.numpy()).astype(mx.bfloat16),mx.array(weights.numpy()),silu_table()],template=[('D',128),('T',mx.bfloat16)],grid=(gate.numel(),1,1),threadgroup=(128,1,1),output_shapes=[tuple(gate.shape)],output_dtypes=[mx.bfloat16])[0]
        mx.eval(result);self.assertTrue(np.array_equal(np.array(result.astype(mx.float32)),expected))
    def test_native_slot_overwrite_waits_for_lazy_consumer(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'records.bin';path.write_bytes(b''.join(bytes([i])*96 for i in range(3)))
            Path(str(path)+'.json').write_text(json.dumps({'expert_to_record':{i:i for i in range(4)},'record_bytes':96,'shapes':[[2,8]]*6}))
            bank=MetalBank(path,[0],l0_slots=1)
            try:
                slots=bank.prepare([1]);old=bank.arrays[0][slots[0]].astype(mx.float32).sum();bank.track(old)
                bank.prepare([2]);self.assertEqual(old.item(),16)
                self.assertEqual(mx.sum(bank.arrays[0][1].astype(mx.float32)).item(),32)
                self.assertEqual(mx.sum(bank.arrays[0][0].astype(mx.float32)).item(),0)
                with self.assertRaises((IndexError,RuntimeError)):bank.prepare([3])
                self.assertNotIn(3,bank.hot)
            finally:bank.close()

if __name__=='__main__':unittest.main()
