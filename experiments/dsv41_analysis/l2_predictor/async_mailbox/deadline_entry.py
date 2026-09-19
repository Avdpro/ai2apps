"""Measure early-prediction delivery versus real route delivery. No SSD prefetch."""
import json,os,sys,threading,time
from pathlib import Path
import mlx.core as mx
ROOT=Path('artifacts/dsv41-l2-preattn-v4-20260916')
sys.path.insert(0,str((ROOT/'source/experiments/dsv41_mlx').resolve()))
sys.path.insert(0,str(Path('artifacts/dsv41-l2-async-mailbox-build').resolve()))
import _l2_mailbox as native
import run
Base=run.Model
class Deadline(Base):
 def __init__(self,*args,**kw):
  super().__init__(*args,**kw);self.step=0;self.active=False;self.events=[];self.box=native.Mailbox();self.stop=threading.Event();self.mode=os.environ['L2_DEADLINE_MODE'];self.pred_roots=[]
  self.mean=mx.load(str(ROOT/'full-correction/mean.safetensors'))['mean'];mx.eval(self.mean)
  self.thread=threading.Thread(target=self.consume,daemon=True);self.thread.start()
 def consume(self):
  while not self.stop.is_set():
   for row in self.box.drain():self.events.append(dict(time=time.perf_counter(),sequence=row[0],ids=row[1:]))
   time.sleep(.0001)
 def emit(self,name,x):
  super().emit(name,x)
  if not self.active or self.mode=='baseline':return
  if name.endswith('.l2_preattn'):
   layer=int(name.split('.')[1]);p=f'layers.{layer}.ffn.gate';score=mx.sqrt(mx.logaddexp((x.astype(mx.float32)+self.mean[layer])@self.w(p+'.weight',mx.float32).T,0))+self.w(p+'.bias');ids=mx.argsort(score)[-12:][::-1].astype(mx.int32);seq=(self.step*40+layer)*2
  elif name.endswith('.gate'):
   layer=int(name.split('.')[1]);ids=x.reshape(-1).astype(mx.int32);seq=(self.step*40+layer)*2+1
  else:return
  packet=native.notify(self.box,ids,seq);self.pred_roots.append(packet);mx.async_eval(packet)
 def __call__(self,ids,start=0):
  self.active=bool(start)
  if start:self.step+=1
  return super().__call__(ids,start)
 def collection_roots(self):return self.pred_roots
 def collection_complete(self):self.pred_roots=[]
 def close(self):
  if self.pred_roots:mx.eval(*self.pred_roots)
  time.sleep(.005);self.stop.set();self.thread.join()
  self.events.extend(dict(time=time.perf_counter(),sequence=r[0],ids=r[1:]) for r in self.box.drain())
  Path(os.environ['L2_DEADLINE_OUTPUT'],'delivery.json').write_text(json.dumps(dict(mode=self.mode,events=self.events,scope='CPU-observed delivery timestamps; two nonblocking submissions/layer; no SSD reads or L2 consumption'),indent=2))
  super().close()
run.Model=Deadline
run.main()
