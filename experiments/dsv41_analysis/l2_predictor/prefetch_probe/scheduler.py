"""Bounded native SSD jobs and zero-copy staging-slot handoff."""
import threading,time,os
from metal_bank import native
class Scheduler:
 def __init__(self,model,mailbox):
  self.trace_enabled=os.environ.get('L2_TRACE_SCHEDULER','0')=='1';self.events=[]
  self.recycle_cancelled=os.environ.get('L2_RECYCLE_CANCELLED','1')=='1';self.model=model;self.box=mailbox;self.cv=threading.Condition();self.io=threading.Lock();self.stop=False;self.error=None;self.step=0;self.jobs={};self.closed=set();self.processed=0;self.spent=0;self.foreground=0;self.records=[];self.reads=[];self.stats=[]
  self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
 def event(self,kind,**fields):
  if getattr(self,'trace_enabled',False):self.events.append(dict(kind=kind,time=time.perf_counter(),step=self.step,**fields))
 def begin(self,step):
  with self.cv:
   assert not any(j['state']=='loading' for j in self.jobs.values())
   self.step=step;self.startup_ids=None;self.jobs={};self.closed=set();self.processed=0;self.spent=0;self.admitted=0;self.cancelled=0
   self.resident={l:set(b.main)|set(b.hot) for l,b in self.model.banks.items()}
   self.free={l:sorted(b.reserved) for l,b in self.model.banks.items()}
   self.event('token_begin')
 def drain(self):
  raw=self.box.drain();notices=[]
  for row in raw:
   if len(row)==2 and row[1]==-1:raise RuntimeError('GPU notification failed')
   assert (len(row)-1)%6==0
   for offset in range((len(row)-1)//6):
    assert row[0]%40+offset<40
    notices.append([row[0]+offset,*row[1+6*offset:1+6*(offset+1)]])
  with self.cv:
   for row in notices:
    step,layer=divmod(row[0],40);assert step==self.step,(step,self.step);self.processed+=1
    self.event('notice_received',layer=layer,experts=list(row[1:]))
    if layer==0:self.startup_ids=list(row[1:])
    if layer in self.closed:
     self.event('notice_expired',layer=layer);continue
    for expert in row[1:]:
     if expert in self.resident[layer] or (layer,expert) in self.jobs:continue
     if self.spent>=64:
      self.event('budget_rejected',layer=layer,expert=expert);continue
     slot=self.free[layer].pop(0);self.jobs[layer,expert]=dict(layer=layer,expert=expert,slot=slot,state='queued',used=False,step=step);self.spent+=1;self.admitted+=1
     self.event('queued',layer=layer,expert=expert,slot=slot)
   self.cv.notify_all()
 def loop(self):
  try:
   while not self.stop:
    self.drain()
    with self.cv:
     job=next((j for j in self.jobs.values() if j['state']=='queued'),None) if not self.foreground else None
    if job is None:time.sleep(.0001);continue
    with self.io:
     with self.cv:
      if self.foreground or job['state']!='queued':continue
      job['state']='loading'
     bank=self.model.banks[job['layer']];begin=time.perf_counter()
     self.event('read_begin',layer=job['layer'],expert=job['expert'])
     count=native.preadv_fused_experts(bank.fd,0,bank.info['record_bytes'],[bank.records[job['expert']]],[job['slot']],*bank.arrays,bank.workers)
     assert count==bank.info['record_bytes']
     with self.cv:
      job['state']='ready';job['ready_time']=time.perf_counter();self.reads.append(dict(step=self.step,layer=job['layer'],expert=job['expert'],begin=begin,end=job['ready_time'],bytes=count));self.cv.notify_all()
      self.event('read_ready',layer=job['layer'],expert=job['expert'])
  except BaseException as e:
   with self.cv:self.error=e;self.cv.notify_all()
 def close_layer(self,l):
  with self.cv:
   self.closed.add(l)
   self.event('layer_closed',layer=l)
   for (layer,expert),job in self.jobs.items():
    if layer==l and job['state']=='queued':
     job['state']='cancelled';self.cancelled+=1
     self.event('cancelled_deadline',layer=layer,expert=expert)
     if self.recycle_cancelled:self.spent-=1
 def read(self,l,ids,slots,original):
  entered=time.perf_counter();bank=self.model.banks[l]
  self.event('foreground_enter',layer=l,experts=list(ids))
  with self.cv:
   if self.error:raise self.error
   timely={e for e in ids if (l,e) in self.jobs and self.jobs[l,e]['state']=='ready'}
   self.foreground+=1;self.close_layer(l)
  used=[];fallback=[]
  def transfer(i,e):
   job=self.jobs.get((l,e))
   if job is None or job['state']!='ready':return False
   source=job['slot'];destination=slots[i]
   assert source in bank.reserved and destination not in bank.reserved
   bank.reserved.remove(source);bank.reserved.add(destination);bank.dynamic_roles=True;slots[i]=source;job['state']='consumed';job['used']=True;used.append(e);return True
  try:
   with self.cv:
    for i,e in enumerate(ids):
     if e in timely:assert transfer(i,e)
   pending=[(i,e) for i,e in enumerate(ids) if e not in used]
   if pending:
    wait_begin=time.perf_counter()
    with self.io:
     self.event('foreground_io_acquired',layer=l,wait_seconds=time.perf_counter()-wait_begin)
     with self.cv:
      if self.error:raise self.error
      for i,e in pending:
       if not transfer(i,e):fallback.append((i,e))
     if fallback:
      self.event('foreground_read_begin',layer=l,experts=[e for i,e in fallback])
      dest=[slots[i] for i,e in fallback];original([e for i,e in fallback],dest)
      self.event('foreground_read_end',layer=l,experts=[e for i,e in fallback])
      for (i,e),slot in zip(fallback,dest):slots[i]=slot
  finally:
   with self.cv:self.foreground-=1;self.cv.notify_all()
  self.records.append(dict(step=self.step,layer=l,requested=len(ids),timely=len(timely),late=len(used)-len(timely),foreground=len(fallback),seconds=time.perf_counter()-entered))
  self.event('foreground_exit',layer=l,timely=len(timely),late=len(used)-len(timely),foreground=len(fallback))
 def finish_token(self):
  began=time.perf_counter()
  with self.cv:
   while self.processed<40 or any(j['state'] in ('queued','loading') for j in self.jobs.values()):
    if self.error:raise self.error
    if time.perf_counter()-began>30:raise TimeoutError('prefetch drain')
    self.cv.wait(.01)
   self.stats.append(dict(step=self.step,reserved_reads=self.spent,admitted_requests=self.admitted,cancelled_requests=self.cancelled,recycle_cancelled=self.recycle_cancelled,completed_reads=sum(j['state'] in ('ready','consumed') for j in self.jobs.values()),unused=sum(j['state']=='ready' for j in self.jobs.values()),tail_wait_seconds=time.perf_counter()-began))
   self.event('token_finish',tail_wait_seconds=time.perf_counter()-began)
 def close(self):
  self.stop=True;self.thread.join()
  if self.error:raise self.error
