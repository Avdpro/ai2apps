import sys
from pathlib import Path
sys.path.insert(0,str(Path('artifacts/dsv41-miss-resume-native-build').resolve()))
import mlx.core as mx
import _miss_resume as native
s=native.Session()
x=mx.arange(13,dtype=mx.float32);ids=mx.arange(6,dtype=mx.int32);lookup=mx.arange(384,dtype=mx.int32)
ages=mx.zeros((48,),dtype=mx.int32);rank=mx.zeros((384,),dtype=mx.float32)
mx.eval(x,ids,lookup,ages,rank)
c=native.retain(x);assert c is not x
x[0]=99;mx.eval(x,c);assert c[0].item()==0
x=c
for miss in (False,True):
    lut=mx.array(lookup)
    if miss:lut[3]=-1
    mx.eval(lut)
    s.begin()
    a=x*2
    held,slots=native.gate(s,a,ids,lut,2,ages,rank,mx.array([1]*6,dtype=mx.int32),[])
    y=mx.sum(held*3)
    mx.eval(y,slots,held)
    status=s.finish()
    assert status[2]==(2 if miss else -1),status
    assert held.tolist()==[2.0*i for i in range(13)]
    if not miss:assert y.item()==468
    else:assert status[3]==1 and status[10]==3
    print('miss' if miss else 'hit',status,flush=True)
