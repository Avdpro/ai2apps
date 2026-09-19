import sys
from pathlib import Path
sys.path.insert(0,str(Path('artifacts/dsv41-miss-resume-native-build').resolve()))
import mlx.core as mx
import numpy as np
import _miss_resume as native
mx.random.seed(7);s=native.Session()
x=mx.random.normal((1,64,512)).astype(mx.bfloat16)
w=[mx.random.normal((512,512)).astype(mx.bfloat16)*.01 for _ in range(4)]
ids=mx.arange(6,dtype=mx.int32);lut=mx.full((384,),-1,dtype=mx.int32);ages=mx.zeros((48,),dtype=mx.int32);rank=mx.zeros((384,),dtype=mx.float32)
mx.eval(x,*w,ids,lut,ages,rank)
def stage(x,w):
    y=x@w
    y=y.astype(mx.float32);y=y*mx.rsqrt(mx.mean(y*y,axis=-1,keepdims=True)+1e-6)
    return y.astype(mx.bfloat16)
a=x;refs=[]
for v in w:a=stage(a,v);mx.eval(a);refs.append(np.array(a.astype(mx.float32)))
b=x
for i,v in enumerate(w):
    s.begin();before=stage(b,v);held,slots=native.gate(s,before,ids,lut,i,ages,rank,mx.array([1]*6,dtype=mx.int32),[]);junk=stage(held,v);mx.eval(junk,slots,held);status=s.finish()
    out=np.array(held.astype(mx.float32));assert np.array_equal(out,refs[i]),(i,np.max(np.abs(out-refs[i])))
    assert status[2]==i;b=held
print('4 real GEMM stages with miss at every stage: exact')
