"""Controlled auxiliary expert I/O; scratch is never consumed by model GPU work."""
import concurrent.futures,fcntl,json,os,random,time
from pathlib import Path
import mlx.core as mx
import run
from metal_bank import native
Base=run.Model
class Overlap(Base):
 def __init__(self,*a,**kw):
  super().__init__(*a,**kw);self.mode=os.environ['OVERLAP_MODE'];self.count=int(os.environ['OVERLAP_COUNT']);self.events=[];self.step=0;self.future=None
  self.info=json.loads((self.expert_store/'layer-0.bin.json').read_text());self.scratch=tuple(mx.zeros((48,*s),dtype=mx.uint8) for s in self.info['shapes'])
  mx.eval(*self.scratch);mx.synchronize() # One-time allocation, before any timed decode.
  self.fds=[]
  for l in range(40):
   fd=os.open(self.expert_store/f'layer-{l}.bin',os.O_RDONLY);fcntl.fcntl(fd,48,1);self.fds.append(fd)
  self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
 def read(self,step):
  began=time.perf_counter();rng=random.Random(90210+step);total=0;requests=[]
  for offset in range(0,self.count,4):
   layer=rng.randrange(40);experts=rng.sample(range(384),min(4,self.count-offset));slots=list(range(offset,offset+len(experts)))
   total+=native.preadv_fused_experts(self.fds[layer],0,self.info['record_bytes'],experts,slots,*self.scratch,4);requests.append([layer,experts])
  assert total==self.count*self.info['record_bytes']
  return dict(begin=began,end=time.perf_counter(),bytes=total,requests=requests)
 def moe(self,l,x,start):
  y=super().moe(l,x,start)
  if start and l==0 and self.mode=='overlap':self.future=self.pool.submit(self.read,self.step)
  return y
 def __call__(self,ids,start=0):
  if not start:return super().__call__(ids,start)
  self.step+=1;began=time.perf_counter();y=super().__call__(ids,start)
  # The normal runner evaluates these same outputs at this boundary.
  mx.eval(y,self.cache_counters,*self.ages.values());computed=time.perf_counter()
  if self.mode=='serial':io=self.read(self.step)
  elif self.mode=='overlap':io=self.future.result();self.future=None
  else:io=dict(begin=computed,end=computed,bytes=0,requests=[])
  ended=time.perf_counter();self.events.append(dict(step=self.step,begin=began,compute_end=computed,end=ended,io=io));return y
 def close(self):
  self.pool.shutdown(wait=True)
  for fd in self.fds:os.close(fd)
  Path(os.environ['OVERLAP_OUTPUT'],'overlap.json').write_text(json.dumps(dict(mode=self.mode,count=self.count,record_bytes=self.info['record_bytes'],scratch_bytes=sum(a.nbytes for a in self.scratch),events=self.events),indent=2))
  super().close()
run.Model=Overlap
run.main()
