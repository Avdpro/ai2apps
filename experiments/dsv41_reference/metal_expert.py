"""Decode-oriented group32 FP8-activation x original FP4 Metal reference kernels."""
from functools import lru_cache
import mlx.core as mx

@lru_cache(None)
def quant_kernel():
    return mx.fast.metal_kernel(name='dsv41_fp8_act',input_names=['x'],output_names=['q','scales'],source=r'''
      uint i=thread_position_in_grid.x;
      float v=float(x[i]);
      float a=simd_max(abs(v));
      float s=exp2(ceil(log2(max(a,1e-4f)/448.0f)));
      float z=clamp(v/s,-448.0f,448.0f);
      float az=abs(z);
      float step=az < 0.015625f ? 0.001953125f : exp2(floor(log2(az))-3.0f);
      q[i]=copysign(min(rint(az/step)*step,448.0f),z);
      if ((i&31)==0) scales[i/32]=s;
    ''')

def act_quant(x):
    if x.shape[-1]%32: raise ValueError('group32 required')
    return quant_kernel()(inputs=[x],grid=(x.size,1,1),threadgroup=(128,1,1),
        output_shapes=[x.shape,(*x.shape[:-1],x.shape[-1]//32)],output_dtypes=[mx.float32,mx.float32])

@lru_cache(None)
def gemm_kernel():
    return mx.fast.metal_kernel(name='dsv41_fp8_fp4_group32',input_names=['a','sa','w','sw','slots'],output_names=['out'],source=r'''
      const uint lane=thread_index_in_simdgroup;
      const uint n=thread_position_in_grid.x/32;
      const uint m=thread_position_in_grid.y;
      if (n>=N) return;
      const uint slot=uint(slots[m]);
      const float lut[8]={0.0f,0.5f,1.0f,1.5f,2.0f,3.0f,4.0f,6.0f};
      float acc=0.0f;
      for (uint group=0;group<K/32;group++) {
        uint k=group*32+lane;
        uint byte=uint(w[(slot*N+n)*(K/2)+k/2]);
        uint code=(byte>>((k&1)*4))&15;
        float val=lut[code&7]; if(code&8)val=-val;
        float dot=simd_sum(a[m*K+k]*val);
        float ws=exp2(float(sw[(slot*N+n)*(K/32)+group])-127.0f);
        acc=acc+(dot*sa[m*(K/32)+group])*ws;
      }
      if(lane==0) out[m*N+n]=T(acc);
    ''')

def linear(x,weight,scale,slots):
    m,k=x.shape; n=weight.shape[1]
    a,sa=act_quant(x)
    return gemm_kernel()(inputs=[a,sa,weight,scale,slots],template=[('K',k),('N',n),('T',mx.bfloat16)],
        grid=(n*32,m,1),threadgroup=(128,1,1),output_shapes=[(m,n)],output_dtypes=[mx.bfloat16])[0]

@lru_cache(None)
def silu_table():
    # GEMM emits BF16: the entire gate domain has only 65536 bit patterns.
    # Reproduce this reference's CPU SiLU rounding once, then lookup on GPU.
    import torch
    import torch.nn.functional as F
    bits=torch.arange(65536,dtype=torch.int32).to(torch.uint16)
    values=bits.view(torch.bfloat16).float().clamp(max=10)
    return mx.array(F.silu(values).numpy())

@lru_cache(None)
def swiglu_kernel():
    return mx.fast.metal_kernel(name='dsv41_bf16_swiglu_table',input_names=['gate','up','weights','table'],output_names=['hidden'],source=r'''
      uint i=thread_position_in_grid.x;
      uint bits=as_type<uint>(float(gate[i]))>>16;
      float val=table[bits]*clamp(float(up[i]),-10.0f,10.0f);
      val=weights[i/D]*val;
      hidden[i]=T(val);
    ''')

def expert(x,bank,slots,route_weights):
    gate=linear(x,bank[0],bank[1],slots)
    up=linear(x,bank[4],bank[5],slots)
    hidden=swiglu_kernel()(inputs=[gate,up,route_weights,silu_table()],template=[('D',gate.shape[-1]),('T',mx.bfloat16)],
        grid=(gate.size,1,1),threadgroup=(128,1,1),output_shapes=[gate.shape],output_dtypes=[mx.bfloat16])[0]
    return linear(hidden,bank[2],bank[3],slots)
