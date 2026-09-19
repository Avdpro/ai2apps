import sys
sys.path.insert(0,'artifacts/dsv41-l2-replay-resume-native-build')
import mlx.core as mx
import _l2_resume as n
s=n.Session();x=mx.array([1.,2.,3.,4.]);ids=mx.arange(6,dtype=mx.int32);lookup=mx.full((384,),-1,dtype=mx.int32);age=mx.zeros((56,),dtype=mx.int32);rank=mx.zeros((384,));required=mx.ones((6,),dtype=mx.int32)
mx.eval(x,ids,lookup,age,rank,required)
s.begin_replay()
for l in range(3):
 x,slots=n.gate(s,x,ids,lookup,l,age,rank,required,[])
 x=x+slots[0].astype(mx.float32)+1
 mx.async_eval(x)
mx.eval(x);s.seal_replay();status=s.finish();print('initial',status,flush=True)
for l in range(3):
 assert status[2]==l,status
 status=s.continue_replay(l,[l+1]*6);print('resume',l,status,flush=True)
print('output',x.tolist(),flush=True)
assert x.tolist()==[10.,11.,12.,13.]
s.release_replay()
