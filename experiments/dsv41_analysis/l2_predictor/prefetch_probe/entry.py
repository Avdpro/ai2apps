"""Opt-in short-block prefetch with physical staging slots and exact main output."""
import importlib.util,json,os,sys,time,threading
from pathlib import Path
import mlx.core as mx
path=Path(__file__).resolve().parent.parent/'resident_probe'/'entry.py';spec=importlib.util.spec_from_file_location('resident_proposal',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
sys.path.insert(0,str(Path(__file__).parent.resolve()))
sys.path.insert(0,str(Path('artifacts/dsv41-l2-async-mailbox-build').resolve()))
import _l2_mailbox as native
from scheduler import Scheduler
from staged_bank import StagedBank
import model
model.LRUMetalBank=StagedBank
class HostMailbox:
 def __init__(self):self.lock=threading.Lock();self.rows=[]
 def push(self,rows):
  with self.lock:self.rows.extend(rows)
 def drain(self):
  with self.lock:rows=self.rows;self.rows=[];return rows
class PrefetchProbe(module.Probe):
 def __init__(self,*a,**kw):
  self.startup=os.environ.get('L2_CREDIT_STARTUP','0')=='1';self.startup_replaced=0;self.startup_miss=0;self.notice_mode=os.environ.get('L2_NOTICE_MODE','async');assert self.notice_mode in ('async','packed','credit');self.sent_layers=set();self.packed_readbacks=0;self.notice_group=int(os.environ.get('L2_NOTICE_GROUP','1'));assert 1<=self.notice_group<=6;self.pending_notices=[];self.credit_rows=[];self.credit_metadata={};self.credits=0;self.saved_readbacks=0;self.sent_notices=0;self.scheduler=None;self.box=HostMailbox() if self.notice_mode=='packed' else native.Mailbox();self.notices=[];self.timed_steps=[];self.enabled=os.environ['L2_PREFETCH']=='1';super().__init__(*a,**kw)
 def __call__(self,ids,start=0):
  self.step_begin=time.perf_counter();self.notices=[];self.pending_notices=[];self.sent_layers=set();self.credit_metadata={};self.startup_replaced=0;self.startup_miss=0;self.credits=int(self.startup and self.notice_mode=="credit");self.saved_readbacks=0;self.sent_notices=0
  if start and self.scheduler:self.scheduler.begin(self.decode_step+1)
  return super().__call__(ids,start)
 def moe(self,l,x,start):
  result=super().moe(l,x,start)
  if start and self.scheduler:
   if self.predicting and self.notice_mode in ('async','credit'):
    layers=[l]
    if self.notice_mode=='credit':
     self.pending_notices.append(l);size=int(self.mode[5:]);end=(l+1)%size==0 or l==39
     if len(self.pending_notices)<self.notice_group and not end:return result
     layers=self.pending_notices;self.pending_notices=[]
     if self.credits==0:
      self.scheduler.event('notice_skipped_credit',layers=list(layers))
      with self.scheduler.cv:self.scheduler.processed+=len(layers);self.scheduler.cv.notify_all()
      return result
     self.credits-=1;self.sent_notices+=1
    ids=mx.concatenate([mx.argsort(self.predictions[j])[-6:][::-1].astype(mx.int32) for j in layers]);packet=native.notify(self.box,ids,self.decode_step*40+layers[0]);self.notices.append(packet);mx.async_eval(packet)
    self.scheduler.event('notice_submitted',layers=list(layers))
   elif not self.predicting:self.scheduler.close_layer(l)
  return result
 def miss_metadata(self,l,ids):
  if self.notice_mode=='credit' and l in self.credit_metadata:return self.credit_metadata.pop(l)
  return super().miss_metadata(l,ids)
 def routes_all_hit(self,l,ids,mapped,required=None):
  if self.scheduler and self.notice_mode=='credit' and not self.predicting:
   assert required is None and self.l1_policy=='eviction_dual'
   if self.startup and l==0:
    began=time.perf_counter()
    with self.scheduler.cv:
     while self.scheduler.startup_ids is None:
      if self.scheduler.error:raise self.scheduler.error
      if time.perf_counter()-began>30:raise TimeoutError('startup route notification')
      self.scheduler.cv.wait(.001)
     hit=all(e in self.scheduler.resident[0] for e in self.scheduler.startup_ids)
    self.startup_replaced=1;self.startup_miss=int(not hit)
    return hit
   assert self.ticks[l]+self.c.n_activated_experts<2**24
   hit=mx.all(mapped>=0)
   rank=.75*self.fast[l]*(32*(1-2**(-1/8)))+.25*self.slow[l]*(32*(1-2**(-1/64)))
   metadata=mx.concatenate([ids.astype(mx.float32),self.ages[l].astype(mx.float32),rank])
   # Preserve device-only actual indices on all-hit: host sees zeros there.
   packet=mx.concatenate([hit.reshape(1).astype(mx.float32),mx.where(hit,mx.zeros_like(metadata),metadata)]).tolist()
   self.packed_readbacks+=1
   if not packet[0]:
    n=ids.size;k=self.banks[l].capacity;payload=packet[1:]
    self.credit_metadata[l]=([int(v) for v in payload[:n]],[int(v) for v in payload[n:n+k]],payload[n+k:])
    self.credits+=1;self.saved_readbacks+=1
   return bool(packet[0])
  if not self.scheduler or self.notice_mode!='packed' or self.predicting:return super().routes_all_hit(l,ids,mapped,required)
  # Replace the original scalar CPU read with one packed read. Only route
  # proposals already constructed in the current short block are included.
  layers=sorted(set(self.predictions)-self.sent_layers)
  hit=mx.all(mapped>=0) if required is None else ~mx.any(required&(mapped<0))
  parts=[hit.reshape(1).astype(mx.int32)]+[mx.argsort(self.predictions[j])[-6:][::-1].astype(mx.int32) for j in layers]
  packet=mx.concatenate(parts).tolist();self.packed_readbacks+=1
  self.box.push([[self.decode_step*40+j,*packet[1+6*i:1+6*(i+1)]] for i,j in enumerate(layers)])
  self.sent_layers.update(layers)
  return bool(packet[0])
 def collection_roots(self):return [*super().collection_roots(),*self.notices]
 def collection_complete(self):
  if not self.active and self.enabled and self.scheduler is None:
   self.scheduler=Scheduler(self,self.box)
   for layer,bank in self.banks.items():
    original=bank._read_ready
    def read(ids,slots,layer=layer,original=original):return self.scheduler.read(layer,ids,slots,original)
    bank._read_ready=read
  elif self.active and self.scheduler:
   self.scheduler.finish_token()
   if self.notice_mode=='credit':
    assert self.sent_notices<=self.saved_readbacks+self.startup_replaced and self.credits==self.saved_readbacks+self.startup_replaced-self.sent_notices
    assert not self.credit_metadata
    self.credit_rows.append(dict(step=self.decode_step,saved_metadata_readbacks=self.saved_readbacks,startup_replaced=self.startup_replaced,startup_miss=self.startup_miss,async_notifications=self.sent_notices,baseline_route_boundaries=40+self.saved_readbacks+self.startup_miss,candidate_route_boundaries=40-self.startup_replaced+self.startup_miss+self.sent_notices))
  super().collection_complete()
  self.timed_steps.append(time.perf_counter()-self.step_begin)
 def close(self):
  Path(os.environ['L2_PROBE_OUTPUT'],'timing.json').write_text(json.dumps(dict(step_seconds=self.timed_steps,includes='Model entry through token collection completion, including prefetch tail wait and routing diagnostics')))
  if self.scheduler:
   if self.scheduler.trace_enabled:Path(os.environ['L2_PROBE_OUTPUT'],'scheduler-events.json').write_text(json.dumps(dict(clock='perf_counter seconds; host events, not GPU timestamps',events=self.scheduler.events)))
   self.scheduler.close();Path(os.environ['L2_PROBE_OUTPUT'],'prefetch.json').write_text(json.dumps(dict(records=self.scheduler.records,reads=self.scheduler.reads,tokens=self.scheduler.stats,staging_slots_per_layer=8,per_token_read_cap=64,zero_copy=True,notice_mode=self.notice_mode,startup=self.startup,notice_group=self.notice_group,extra_async_notifications_per_token=40 if self.notice_mode=='async' else (sum(r['async_notifications'] for r in self.credit_rows)/len(self.credit_rows) if self.credit_rows else 0),credit_rows=self.credit_rows,packed_readbacks=self.packed_readbacks),indent=2))
  super().close()
module.run.Model=PrefetchProbe
module.run.main()
