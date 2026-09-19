"""GPU primitives retaining official group32 activation quantization."""
import math
from functools import lru_cache
import mlx.core as mx

@lru_cache(None)
def quant_kernel(group,fp4,e4):
    source=r'''
    uint i=thread_position_in_grid.x;
    float v=float(x[i]),a=abs(v);
    for(uint d=G/2;d>0;d/=2)a=max(a,simd_shuffle_xor(a,d));
    float s,z,r;
    if(FOUR){
      if(E4){
        s=max(a,6.0f*exp2(-9.0f))/6.0f;
        float step=s<0.015625f?0.001953125f:exp2(floor(log2(s))-3.0f);
        s=rint(s/step)*step;
      }else s=exp2(ceil(log2(max(a,6.0f*exp2(-126.0f))/6.0f)));
      z=clamp(v/s,-6.0f,6.0f);
      const float lut[8]={0,1,2,4,.5,1.5,3,6};
      float best=1e30f; r=0;
      for(uint j=0;j<8;j++){float d=abs(abs(z)-lut[j]);if(d<best){best=d;r=lut[j];}}
      r=copysign(r,z);
    }else{
      s=exp2(ceil(log2(max(a,1e-4f)/448.0f)));
      z=clamp(v/s,-448.0f,448.0f);
      float az=abs(z),step=az<0.015625f?0.001953125f:exp2(floor(log2(az))-3.0f);
      r=copysign(min(rint(az/step)*step,448.0f),z);
    }
    out[i]=T(r*s);
    '''
    return mx.fast.metal_kernel(name=f'dsv41_quant_{group}_{fp4}_{e4}',input_names=['x'],output_names=['out'],source=source)
def quant(x,group=32,fp4=False,e4=False):
    if x.shape[-1]%group:raise ValueError('quant group shape')
    return quant_kernel(group,fp4,e4)(inputs=[x],template=[('G',group),('FOUR',fp4),('E4',e4),('T',x.dtype)],grid=(x.size,1,1),threadgroup=(128,1,1),output_shapes=[x.shape],output_dtypes=[x.dtype])[0]
def fp8_decode(x):
    mag=x&127;exp=(mag>>3).astype(mx.int32);mant=(mag&7).astype(mx.float32)
    v=mx.where(exp==0,mant*2**-9,(1+mant/8)*mx.power(2.,exp.astype(mx.float32)-7))
    return mx.where((x&128)!=0,-v,v)
def norm(x,w,eps):
    f=x.astype(mx.float32);return (f*mx.rsqrt(mx.mean(f*f,axis=-1,keepdims=True)+eps)*w.astype(mx.float32)).astype(x.dtype)
def rope_freq(dim,length,original,base,factor,beta_fast,beta_slow):
    f=1/(base**(mx.arange(0,dim,2,dtype=mx.float32)/dim))
    if original:
        corr=lambda n:dim*math.log(original/(n*2*math.pi))/(2*math.log(base))
        low=max(math.floor(corr(beta_fast)),0);high=min(math.ceil(corr(beta_slow)),dim-1)
        ramp=mx.clip((mx.arange(dim//2,dtype=mx.float32)-low)/max(high-low,1e-3),0,1)
        smooth=1-ramp
        f=f/factor*(1-smooth)+f*smooth
    phase=mx.arange(length,dtype=mx.float32)[:,None]*f[None,:]
    return mx.cos(phase),mx.sin(phase)
def rope(x,freq,start,rd,inverse=False):
    cos,sin=freq;cos=cos[start:start+x.shape[1]];sin=sin[start:start+x.shape[1]]
    if x.ndim==4:cos=cos[None,:,None,:];sin=sin[None,:,None,:]
    else:cos=cos[None];sin=sin[None]
    if inverse:sin=-sin
    tail=x[...,-rd:].astype(mx.float32).reshape(*x.shape[:-1],rd//2,2)
    a,b=tail[...,0],tail[...,1]
    y=mx.stack([a*cos-b*sin,a*sin+b*cos],axis=-1).reshape(*x.shape[:-1],rd).astype(x.dtype)
    return mx.concatenate([x[...,:-rd],y],axis=-1)
def rope_selected(x,freq,positions,rd):
    cos,sin=freq;cs=cos[positions];ss=sin[positions]
    tail=x[...,-rd:].astype(mx.float32).reshape(*x.shape[:-1],rd//2,2)
    a,b=tail[...,0],tail[...,1]
    y=mx.stack([a*cs-b*ss,a*ss+b*cs],axis=-1).reshape(*x.shape[:-1],rd).astype(x.dtype)
    return mx.concatenate([x[...,:-rd],y],axis=-1)
def sinkhorn(mixes,scale,base,h=4,iters=20,eps=1e-6):
    pre=mx.sigmoid(mixes[...,:h]*scale[0]+base[:h])+eps
    post=2*mx.sigmoid(mixes[...,h:2*h]*scale[1]+base[h:2*h])
    c=mx.softmax((mixes[...,2*h:]*scale[2]+base[2*h:]).reshape(*mixes.shape[:-1],h,h),axis=-1)+eps
    c=c/(mx.sum(c,axis=-2,keepdims=True)+eps)
    for _ in range(iters-1):
        c=c/(mx.sum(c,axis=-1,keepdims=True)+eps);c=c/(mx.sum(c,axis=-2,keepdims=True)+eps)
    return pre,post,c
def index_scores(q,k,weights):
    # Keep the BF16 dot-product boundary before the original reduction.
    score=mx.einsum('bshd,btd->bsht',q,k)
    return mx.sum(mx.maximum(score,0)*weights[...,None],axis=2)

def index_topk(score,top):
    return mx.sort(mx.argsort(score,axis=-1)[...,-top:],axis=-1).astype(mx.int32)

def sparse_gather(kv,idx):
    return kv[mx.maximum(idx,0)][:,None]

def sparse_sdpa(q,v,sink,idx,scale):
    return mx.fast.scaled_dot_product_attention(q[:,:,None,:],v,v,scale=scale,mask=(idx>=0)[:,None,None,:],sinks=sink.astype(q.dtype))[:,:,0,:]

def sparse(q,kv,sink,indices,scale,chunk_size=64):
    batches=[]
    for b in range(q.shape[0]):
        chunks=[]
        for start in range(0,q.shape[1],chunk_size):
            idx=indices[b,start:start+chunk_size];v=sparse_gather(kv[b],idx)
            chunks.append(sparse_sdpa(q[b,start:start+chunk_size],v,sink,idx,scale))
        batches.append(mx.concatenate(chunks))
    return mx.stack(batches)
