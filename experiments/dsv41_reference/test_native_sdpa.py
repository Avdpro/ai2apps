import torch
from cpu_kernel import sparse_attn as reference
from mlx_sdpa_attention import sparse_attn

torch.manual_seed(49)
for length in [1,7]:
    q=torch.randn(1,length,64,512).bfloat16()
    kv=torch.randn(1,80,512).bfloat16()
    idx=torch.randint(0,80,(1,length,128),dtype=torch.int32);idx[:,:,-17:]=-1
    sink=torch.randn(64)
    a=reference(q,kv,sink,idx,512**-.5).float()
    b=sparse_attn(q,kv,sink,idx,512**-.5).float()
    rmse=(a-b).square().mean().sqrt().item()
    print(dict(length=length,max_abs=(a-b).abs().max().item(),rmse=rmse))
    assert torch.isfinite(b).all() and rmse<.004
