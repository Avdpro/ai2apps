import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dsv41_mlx'))
import mlx.core as mx
import numpy as np
from tail_policy import replace_tail
score=mx.arange(1,17,dtype=mx.float32);bias=mx.zeros((16,));bias[2]=100
ids=mx.array([1,3,5,7,9,11]);weights=mx.array([.5,.4,.25,.15,.12,.08]);must=mx.array([True,True,False,False,False,False])
mapping=mx.arange(16);mapping[7]=-1;mapping[11]=-1
for policy in ['fixed-top','renorm']:
 chosen,w,slots,n=replace_tail(score,bias,ids,weights,must,mapping,policy)
 mx.eval(chosen,w,slots,n);chosen=chosen.tolist();w=np.array(w)
 assert chosen==[1,2,3,5,9,15] and n.item()==2 and min(slots.tolist())>=0
 assert abs(w.sum()-1.5)<1e-6
 if policy=='fixed-top':assert w[chosen.index(1)]==.5 and w[chosen.index(3)]==np.float32(.4)
 else:assert np.allclose(w,np.array([2,3,4,6,10,16])/41*1.5)
 chosen,w,slots,n=replace_tail(score,bias,ids,weights,must,mx.arange(16),policy)
 mx.eval(chosen,w,n);assert chosen.tolist()==ids.tolist() and np.array_equal(np.array(w),np.array(weights)) and n.item()==0
print('Tail selection, residency, Top2 weight preservation, normalization and all-hit identity passed')
