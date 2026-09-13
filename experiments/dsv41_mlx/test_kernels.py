"""Cross-backend tests only; torch is never imported by the inference runner."""
import sys
from pathlib import Path
import numpy as np
import mlx.core as mx
import torch
from kernels import quant,fp8_decode,sinkhorn
sys.path.append(str(Path(__file__).resolve().parents[1]/'dsv41_reference'))
import cpu_kernel

torch.manual_seed(73)
x=torch.randn(3,7,512).bfloat16()*3
for group,four,e4 in [(32,False,False),(32,True,False),(16,True,True)]:
    a=x.clone()
    if four:cpu_kernel.fp4_act_quant(a,group,True,torch.float8_e4m3fn if e4 else torch.float8_e8m0fnu)
    else:cpu_kernel.act_quant(a,group,'ue8m0',torch.float8_e8m0fnu,True)
    y=quant(mx.array(x.float().numpy()).astype(mx.bfloat16),group,four,e4);mx.eval(y)
    b=np.array(y.astype(mx.float32));err=float(np.max(np.abs(a.float().numpy()-b)));print(group,four,e4,err);assert err==0
raw=np.arange(256,dtype=np.uint8);expected=torch.from_numpy(raw).view(torch.float8_e4m3fn).float().numpy();actual=np.array(fp8_decode(mx.array(raw)))
mask=np.isfinite(expected);assert np.array_equal(expected[mask],actual[mask])
print('quantization and FP8 decode passed')
