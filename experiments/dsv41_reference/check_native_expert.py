import json
import numpy as np
import torch
import mlx.core as mx
from metal_bank import MetalBank
from run_reference import Store
import native_mx
import metal_expert

store=Store(__import__('pathlib').Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD'))
bank=MetalBank('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/experts/layer-0.bin',[0,1],l0_slots=6)
try:
    torch.manual_seed(37);x=mx.array(torch.randn(4,5120).bfloat16().float().numpy()).astype(mx.bfloat16)
    slots=bank.prepare([3,0,2,1]);rw=mx.array([.1,.2,.3,.4])
    for name,fn in [('gate',lambda f:f(x,bank.arrays[0],bank.arrays[1],slots)),('expert',lambda f:f(x,bank.arrays,slots,rw))]:
        a=fn(metal_expert.linear if name=='gate' else metal_expert.expert)
        b=fn(native_mx.linear if name=='gate' else native_mx.expert);mx.eval(a,b)
        aa=np.array(a.astype(mx.float32));bb=np.array(b.astype(mx.float32));print(name,{'max_abs':float(np.max(np.abs(aa-bb))),'rmse':float(np.sqrt(np.mean((aa-bb)**2))),'reference_rms':float(np.sqrt(np.mean(aa**2)))})
finally:bank.close();store.close()
