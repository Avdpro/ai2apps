import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dsv41_mlx'))
import mlx.core as mx
import numpy as np
from tail_policy import renormalize_retained
w=mx.array([.4,.35,.25,.2,.17,.13],dtype=mx.float32)
for mask in [[True,True,False,False,False,False],[True,True,False,True,False,True],[True]*6]:
 valid=mx.array(mask);out=renormalize_retained(w,valid);mx.eval(out)
 expected=np.array(w)*np.array(mask);expected=expected/expected.sum()*1.5
 assert np.allclose(np.array(out),expected) and abs(float(mx.sum(out).item())-1.5)<1e-6
 assert np.all(np.array(out)[~np.array(mask)]==0)
 if all(mask):assert np.array_equal(np.array(out),np.array(w))
print('Retained weights sum to 1.5, missing weights stay zero, all-hit identity passed')
