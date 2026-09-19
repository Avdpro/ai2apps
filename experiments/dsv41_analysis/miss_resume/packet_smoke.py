"""Probe hit/required miss/optional miss packets and repeated buffer reuse."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path('artifacts/dsv41-miss-resume-native-build').resolve()))
import mlx.core as mx
import _miss_resume as native
s=native.Session();ids=mx.arange(6,dtype=mx.int32);ages=mx.arange(48,dtype=mx.int32);rank=mx.arange(384,dtype=mx.float32)
for missing,required in [(False,[1]*6),(True,[1]*6),(True,[1,1,0,0,0,0]),(False,[1]*6)]:
    lookup=mx.arange(384,dtype=mx.int32)
    if missing:lookup[3]=-1
    s.begin_packet();slots=native.probe(s,ids,lookup,19,ages,rank,mx.array(required,dtype=mx.int32));mx.eval(slots);status=s.finish()
    must=missing and required[3]
    assert status[2]==(19 if must else -1),status
    assert slots.tolist()==[0,1,2,-1 if missing else 3,4,5]
    if must:
        m=s.metadata(48);assert m[:48]==list(range(48));assert m[48:432]==list(range(384));assert status[3]==1 and status[10]==3
print('packet all-hit, required miss, optional miss, buffer reuse: exact')
