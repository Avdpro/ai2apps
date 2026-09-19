"""Check in-place slot publication and queued-read cancellation before model use."""
import sys,threading
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path('experiments/dsv41_reference').resolve()))
from scheduler import Scheduler
s=Scheduler.__new__(Scheduler);s.cv=threading.Condition();s.io=threading.Lock();s.error=None;s.foreground=0;s.closed=set();s.step=1;s.records=[];s.cancelled=0;s.spent=2;s.recycle_cancelled=True
b=SimpleNamespace(reserved=set(range(48,56)),dynamic_roles=False);s.model=SimpleNamespace(banks={3:b})
s.jobs={(3,17):dict(state='ready',slot=50,used=False),(3,19):dict(state='queued',slot=51,used=False)};calls=[]
def original(ids,slots):calls.append((ids[:],slots[:]))
slots=[41,42];s.read(3,[17,19],slots,original)
assert slots==[50,42] and calls==[([19],[42])]
assert b.reserved==set([41,48,49,51,52,53,54,55]) and b.dynamic_roles
assert s.jobs[3,17]['state']=='consumed' and s.jobs[3,19]['state']=='cancelled'
assert s.records[0]['timely']==1 and s.records[0]['foreground']==1 and s.records[0]['late']==0
assert s.foreground==0
print('Ready slot ownership swap, in-place destinations, queued cancellation: passed')

assert s.cancelled==1 and s.spent==1
s.close_layer(3)
assert s.cancelled==1 and s.spent==1, 'Repeated closure must not double-release budget'
print('Cancelled unread request releases budget exactly once: passed')
# No I/O runs in this deterministic admission test. Check the actual read
# reservation stays bounded even when cumulative admissions exceed the cap.
q=Scheduler.__new__(Scheduler);q.cv=threading.Condition();q.jobs={};q.closed=set();q.processed=0;q.step=1;q.spent=0;q.admitted=0;q.cancelled=0;q.recycle_cancelled=True
q.resident={l:set() for l in range(40)};q.free={l:list(range(48,56)) for l in range(40)}
class Box:
 def __init__(self,rows):self.rows=rows
 def drain(self):rows=self.rows;self.rows=[];return rows
q.box=Box([[40+l,*range(6)] for l in range(11)])
q.drain();assert q.spent==64 and q.admitted==64
q.close_layer(0);assert q.spent==58 and q.cancelled==6
q.box.rows=[[51,*range(6)]];q.drain()
assert q.spent==64 and q.admitted==70
assert sum(j['state']=='queued' for j in q.jobs.values())==64
q.close_layer(0);assert q.spent==64
print('Cumulative admissions may exceed 64, outstanding read reservations never do: passed')
