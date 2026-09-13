"""Group32 FP8 GEMM migration; preserve CPU reference block scaling and BF16 output."""
from functools import lru_cache
import mlx.core as mx
import numpy as np
import torch

@lru_cache(None)
def kernel():
    return mx.fast.metal_kernel(name='dsv41_fp8_dense_compensated_group32',input_names=['a','sa','w','sw'],output_names=['out'],source=r'''
      #pragma clang fp reassociate(off)
      #pragma clang fp contract(off)
      uint lane=thread_index_in_simdgroup;
      uint n=thread_position_in_grid.x/32;
      uint m=thread_position_in_grid.y;
      if(n>=N)return;
      float acc=0.0f;
      for(uint g=0;g<K/32;g++) {
        uint k=g*32+lane;
        uint code=uint(w[n*K+k]);
        uint exp=(code>>3)&15;uint frac=code&7;
        float val=exp==0 ? float(frac)*0.001953125f : (1.0f+float(frac)*0.125f)*exp2(float(exp)-7.0f);
        if(code&128)val=-val;
        // Float8 products have at most eight significant bits. Preserve the
        // low part of the SIMD tree before rounding its group dot to float32.
        float high=a[m*K+k]*val;
        float low=0.0f;
        for (ushort offset=16;offset>0;offset>>=1) {
          float other=simd_shuffle_xor(high,offset);
          float other_low=simd_shuffle_xor(low,offset);
          float sum=high+other;
          float v=sum-high;
          float error=(high-(sum-v))+(other-v);
          low=(low+other_low)+error;
          high=sum;
        }
        float dot=high+low;
        float ws=exp2(float(sw[(n/32)*(K/32)+g])-127.0f);
        acc=acc+(dot*sa[m*(K/32)+g])*ws;
      }
      if(lane==0)out[m*N+n]=T(acc);
    ''')

stats={'calls':0,'weight_upload_bytes':0}
def fp8_gemm(a,a_s,b,b_s,scale_dtype=torch.float32,block_size=128):
    if block_size!=32 or b_s.dtype!=torch.float8_e8m0fnu:raise ValueError('released group32 UE8M0 required')
    k=a.shape[-1];n=b.shape[0];m=a.numel()//k
    qa=mx.array(a.float().reshape(m,k).numpy());sa=mx.array(a_s.float().reshape(m,-1).numpy())
    w=mx.array(b.view(torch.uint8).numpy());sw=mx.array(b_s.view(torch.uint8).numpy())
    out=kernel()(inputs=[qa,sa,w,sw],template=[('K',k),('N',n),('T',mx.bfloat16)],grid=(n*32,m,1),threadgroup=(128,1,1),output_shapes=[(m,n)],output_dtypes=[mx.bfloat16])[0]
    mx.eval(out);stats['calls']+=1;stats['weight_upload_bytes']+=b.numel()+b_s.numel()
    return torch.from_numpy(np.array(out.astype(mx.float32))).bfloat16().reshape(*a.shape[:-1],n)
