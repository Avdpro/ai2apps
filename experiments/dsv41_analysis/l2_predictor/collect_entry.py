"""Diagnostic collection only: retain device tensors, export at completed step."""
import os,json
from pathlib import Path
import numpy as np
import mlx.core as mx
import run
Base=run.Model
class Collected(Base):
 def __init__(self,*a,**kw):
  self.pending_ranks={};self.pending_ids={};self.previous=None;self.previous_routes=None;self.samples=[]
  super().__init__(*a,**kw)
 def emit(self,name,x):
  if name.endswith('.l2_rank'):self.pending_ranks[int(name.split('.')[1])]=x[-1]
  elif name.endswith('.gate'):self.pending_ids[int(name.split('.')[1])]=x[-1]
  elif name=='l2_embedding':self.current_embedding=x[0,-1]
  elif name=='l2_final':self.current_hidden=x[0]
  return super().emit(name,x)
 def __call__(self,ids,start=0):
  y=super().__call__(ids,start)
  routes=mx.stack([self.pending_ids[l] for l in range(5,40)])
  if start:
   features=mx.concatenate([self.previous,self.current_embedding]).astype(mx.float16)
   rank=mx.stack([self.pending_ranks[l] for l in range(5,40)]).astype(mx.float16)
   mx.eval(y,features,rank,routes,self.previous_routes)
   self.samples.append((np.array(features),np.array(rank),np.array(routes).astype(np.uint16),np.array(self.previous_routes).astype(np.uint16),int(ids.item())))
  self.previous=mx.array(self.current_hidden);self.previous_routes=mx.array(routes)
  self.pending_ranks={};self.pending_ids={}
  return y
 def close(self):
  if self.samples:
   f,r,t,p,i=zip(*self.samples)
   np.savez(Path(os.environ['L2_COLLECT_OUTPUT'])/'supervision.npz',features=np.stack(f),router_rank=np.stack(r),top6=np.stack(t),previous_top6=np.stack(p),token_ids=np.array(i,dtype=np.int32))
  super().close()
run.Model=Collected
run.main()
