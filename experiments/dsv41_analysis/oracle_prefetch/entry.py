"""Oracle-only direct destination prefetch. Never enable with guessed destinations."""
import json,os,threading,time
from pathlib import Path
import run
Base=run.Model
class Scheduler:
 def __init__(self,model,plan,batch):
  self.model=model;self.plan=plan;self.batch=batch;self.cv=threading.Condition();self.jobs={};self.layer=0;self.busy=False;self.foreground=0;self.stop=False;self.error=None;self.events=[];self.step=0
  self.worker=threading.Thread(target=self.loop,daemon=True);self.worker.start()
 def begin(self,step):
  with self.cv:
   assert not self.busy and all(j['pos']==len(j['ids']) for j in self.jobs.values())
   self.step=step;self.layer=0;self.jobs={int(j['layer']):dict(j,pos=0) for j in self.plan[str(step)]};self.cv.notify_all()
 def at_layer(self,l):
  with self.cv:self.layer=l;self.cv.notify_all()
 def perform(self,j,end,bg):
  start=j['pos'];t=time.perf_counter()
  self.model.original[j['layer']](j['ids'][start:end],j['slots'][start:end])
  self.events.append(dict(step=self.step,layer=j['layer'],experts=end-start,background=bg,seconds=time.perf_counter()-t))
  with self.cv:j['pos']=end
 def loop(self):
  while True:
   with self.cv:
    while True:
     if self.stop:return
     available=[j for l,j in sorted(self.jobs.items()) if 5<=l<=self.layer+8 and j['pos']<len(j['ids'])]
     if not self.busy and not self.foreground and available:
      j=available[0];self.busy=True;break
     self.cv.wait()
   try:self.perform(j,min(len(j['ids']),j['pos']+self.batch),True)
   except BaseException as e:
    with self.cv:self.error=e;self.stop=True
   finally:
    with self.cv:self.busy=False;self.cv.notify_all()
 def read(self,l,ids,slots):
  began=time.perf_counter()
  with self.cv:
   if self.error:raise self.error
   j=self.jobs[l];assert j['ids']==list(ids) and j['slots']==list(slots),'oracle destination mismatch'
   ready=j['pos']==len(j['ids']);self.foreground+=1
   while self.busy and j['pos']<len(j['ids']):self.cv.wait()
   if self.error:self.foreground-=1;raise self.error
   if j['pos']==len(j['ids']):
    self.foreground-=1;self.cv.notify_all();self.model.fulfilled.append(dict(step=self.step,layer=l,ready=ready,wait_s=time.perf_counter()-began));return
   self.busy=True
  try:self.perform(j,len(j['ids']),False)
  finally:
   with self.cv:self.busy=False;self.foreground-=1;self.cv.notify_all()
  self.model.fulfilled.append(dict(step=self.step,layer=l,ready=False,wait_s=time.perf_counter()-began))
 def close(self):
  with self.cv:self.stop=True;self.cv.notify_all()
  self.worker.join()
  if self.error:raise self.error
class Oracle(Base):
 def __init__(self,*a,**kw):
  self.mode=os.environ['ORACLE_MODE'];self.step=0;self.original={};self.record={};self.fulfilled=[];self.scheduler=None
  self.plan=json.loads(Path(os.environ['ORACLE_PLAN']).read_text()) if self.mode!='baseline' else None
  super().__init__(*a,**kw)
 def moe(self,l,x,start):
  if start and self.scheduler:self.scheduler.at_layer(l)
  return super().moe(l,x,start)
 def __call__(self,ids,start=0):
  if start:
   self.step+=1;self.record[str(self.step)]=[]
   if self.scheduler:self.scheduler.begin(self.step)
  y=super().__call__(ids,start)
  if not start:
   for l,b in self.banks.items():
    self.original[l]=b._read_ready
    def read(experts,slots,l=l):
     self.record[str(self.step)].append(dict(layer=l,ids=list(experts),slots=list(slots)))
     if self.scheduler:return self.scheduler.read(l,experts,slots)
     return self.original[l](experts,slots)
    b._read_ready=read
   if self.mode!='baseline':self.scheduler=Scheduler(self,self.plan,int(os.environ['ORACLE_BATCH']))
  return y
 def close(self):
  if self.scheduler:self.scheduler.close()
  p=Path(os.environ['ORACLE_OUTPUT']);(p/'oracle-plan.json').write_text(json.dumps(self.record))
  (p/'oracle-stats.json').write_text(json.dumps(dict(mode=self.mode,events=self.scheduler.events if self.scheduler else [],fulfilled=self.fulfilled,total_native_bytes=sum(b.bytes for b in self.banks.values()),native_calls=sum(b.loads for b in self.banks.values()),bank_fences=sum(b.fence_calls for b in self.banks.values())),indent=2))
  super().close()
run.Model=Oracle
run.main()
