import sys
from pathlib import Path
sys.path.insert(0,str(Path('artifacts/dsv41-miss-resume-native-build').resolve()))
import mlx.core as mx
import numpy as np
import _miss_resume as native
s=native.Session();mx.random.seed(17)
x=mx.random.normal((1,5120)).astype(mx.bfloat16);w=mx.random.normal((384,5120)).astype(mx.bfloat16)
mx.eval(x,w)
ops={'cast':lambda:x.astype(mx.float32),'multiply':lambda:x*x,'sum':lambda:mx.sum(x.astype(mx.float32),axis=-1),'mean':lambda:mx.mean(x.astype(mx.float32),axis=-1),'rms_norm':lambda:mx.fast.rms_norm(x,None,1e-6),'sort':lambda:mx.argsort(x),'matmul_bf16':lambda:x@w.T,'matmul_f32':lambda:x.astype(mx.float32)@w.astype(mx.float32).T,'softmax':lambda:mx.softmax(x),'logaddexp':lambda:mx.logaddexp(x,0),'sigmoid':lambda:mx.sigmoid(x),'repeat':lambda:mx.repeat(x[:,:,None],4,axis=-1)}
for name,op in ops.items():
    a=op();mx.eval(a);av=np.array(a.astype(mx.float32))
    s.begin();b=op();mx.eval(b);s.finish();bv=np.array(b.astype(mx.float32))
    print(name,np.array_equal(av,bv),float(np.max(np.abs(av-bv))),flush=True)
a=mx.random.normal((6,5120)).astype(mx.bfloat16);b=mx.random.normal((8,512,5120)).astype(mx.bfloat16)
i=mx.arange(6,dtype=mx.uint32);q,sc=mx.quantize(b,group_size=32,bits=4,mode='mxfp4');mx.eval(a,q,sc,i)
for name,op in {'gather_qmm':lambda:mx.gather_qmm(a[:,None,:],q,sc,rhs_indices=i,group_size=32,bits=4,mode='mxfp4',sorted_indices=True),'qmm':lambda:mx.quantized_matmul(a,q[0],sc[0],group_size=32,bits=4,mode='mxfp4')}.items():
    ref=op();mx.eval(ref);s.begin();out=op();mx.eval(out);s.finish()
    aa=np.array(ref.astype(mx.float32));bb=np.array(out.astype(mx.float32));print(name,np.array_equal(aa,bb),float(np.max(np.abs(aa-bb))),flush=True)
q=mx.random.normal((1,64,1,512)).astype(mx.bfloat16);kv=mx.random.normal((1,1,128,512)).astype(mx.bfloat16);sink=mx.zeros((64,),dtype=mx.bfloat16);mask=(mx.arange(128)<7).reshape(1,1,1,128);mx.eval(q,kv,sink,mask)
for name,op in {'sdpa':lambda:mx.fast.scaled_dot_product_attention(q,kv,kv,scale=512**-.5),'sdpa_mask':lambda:mx.fast.scaled_dot_product_attention(q,kv,kv,scale=512**-.5,mask=mask),'sdpa_sink':lambda:mx.fast.scaled_dot_product_attention(q,kv,kv,scale=512**-.5,mask=mask,sinks=sink)}.items():
    ref=op();mx.eval(ref);s.begin();out=op();mx.eval(out);s.finish()
    aa=np.array(ref.astype(mx.float32));bb=np.array(out.astype(mx.float32));print(name,np.array_equal(aa,bb),float(np.max(np.abs(aa-bb))),float(np.max(np.abs(bb))),flush=True)
for t in (32,256,512,1024):
    k=mx.fast.metal_kernel(name='icb_thread_probe'+str(t),input_names=['x'],output_names=['out'],source='out[thread_position_in_grid.x] = float(simdgroup_index_in_threadgroup+1);')
    op=lambda:k(inputs=[x],grid=(t,1,1),threadgroup=(t,1,1),output_shapes=[(t,)],output_dtypes=[mx.float32])[0]
    ref=op();mx.eval(ref);s.begin();out=op();mx.eval(out);s.finish();aa=np.array(ref);bb=np.array(out);print('threads',t,np.array_equal(aa,bb),bb[-4:],flush=True)
ks=mx.fast.metal_kernel(name='icb_args_probe',input_names=['x'],output_names=['out'],source='out[thread_position_in_grid.x] = float(threadgroups_per_grid.x + threadgroups_per_grid.y*1000);')
for t in (256,1024):
 op=lambda:ks(inputs=[x],grid=(t*64,1,1),threadgroup=(t,1,1),output_shapes=[(t*64,)],output_dtypes=[mx.float32])[0]
 a=op();mx.eval(a);s.begin();b=op();mx.eval(b);s.finish();print('gridgroups',t,a[0].item(),b[0].item(),flush=True)
k=mx.fast.metal_kernel(name='icb_tgmem_probe',input_names=['x'],output_names=['out'],source='threadgroup float vals[1024]; uint t=thread_position_in_threadgroup.x; vals[t]=float(t); threadgroup_barrier(mem_flags::mem_threadgroup); out[thread_position_in_grid.x] = simd_sum(vals[(t+32)%1024]);')
op=lambda:k(inputs=[x],grid=(65536,1,1),threadgroup=(1024,1,1),output_shapes=[(65536,)],output_dtypes=[mx.float32])[0]
a=op();mx.eval(a);s.begin();b=op();mx.eval(b);s.finish();print('tgmem',np.array_equal(np.array(a),np.array(b)),a[:4].tolist(),b[:4].tolist(),flush=True)
a=mx.random.normal((64,512)).astype(mx.bfloat16);b=mx.random.normal((128,512)).astype(mx.bfloat16);mx.eval(a,b)
for dt in (mx.bfloat16,mx.float32):
 op=lambda:a.astype(dt)@b.astype(dt).T
 ref=op();mx.eval(ref);s.begin();out=op();mx.eval(out);s.finish();aa=np.array(ref.astype(mx.float32));bb=np.array(out.astype(mx.float32));print('gemm',dt,np.array_equal(aa,bb),float(np.max(np.abs(aa-bb))),float(np.max(np.abs(bb))),flush=True)
