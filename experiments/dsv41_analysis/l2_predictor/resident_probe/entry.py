"""Resident-only approximate route proposal followed by unchanged exact forward."""
import hashlib,json,os,sys,time
from pathlib import Path
import numpy as np
import mlx.core as mx
source=Path('artifacts/dsv41-l2-preattn-v4-20260916/source/experiments/dsv41_mlx')
sys.path.insert(0,str(source.resolve()))
import run
from model import Model as StaticModel
from burst import snapshot_tree,BurstModel
Base=run.Model
class Probe(Base):
 def __init__(self,*a,**kw):
  source_bytes=Path(__file__).read_bytes();Path(os.environ['L2_PROBE_OUTPUT'],'proposal-source.py').write_bytes(source_bytes);self.proposal_source_sha256=hashlib.sha256(source_bytes).hexdigest()
  super().__init__(*a,**kw);self.mode=os.environ['L2_PROBE_MODE'];self.tail_policy=os.environ.get('L2_PROBE_TAIL',self.mode if self.mode in ('replace','renorm') else 'zero');self.canonical_order=os.environ.get('L2_PROBE_CANONICAL','0')=='1';self.predicting=False;self.active=False;self.predictions={};self.actual={};self.consumer_roots=[];self.rows=[];self.timings=[]
 def emit(self,name,x):
  if self.predicting:return
  super().emit(name,x)
  if self.active and name.endswith('.gate'):self.actual[int(name.split('.')[1])]=x.reshape(-1)
 def moe(self,l,x,start):
  if not self.predicting:return super().moe(l,x,start)
  c=self.c;flat=x.reshape(-1,c.dim);p=f'layers.{l}.ffn.gate';bank=self.banks[l]
  score=mx.sqrt(mx.logaddexp((flat.astype(mx.float32)@self.w(p+'.weight',mx.float32).T)/c.gate_temp,0));rank=score+self.w(p+'.bias');self.predictions[l]=rank[0]
  ids=mx.argsort(rank,axis=-1)[0,-c.n_activated_experts:]
  if self.canonical_order:ids=ids[::-1]
  weights=score[0,ids];weights=weights/(mx.sum(weights)+1e-20)*c.route_scale
  if self.canonical_order:
   order=mx.argsort(ids);ids=ids[order];weights=weights[order]
  slots=self.probe_lookup[l][ids];valid=slots>=0
  if self.tail_policy=='replace':
   from tail_policy import replace_tail
   ids,weights,slots,_=replace_tail(score[0],self.w(p+'.bias'),ids,weights,mx.zeros(ids.shape,mx.bool_),self.probe_lookup[l],'renorm',c.route_scale);valid=slots>=0
  if self.tail_policy=='renorm':weights=weights*valid;weights=weights/(mx.sum(weights)+1e-20)*c.route_scale
  values=self.expert(mx.broadcast_to(flat,(c.n_activated_experts,c.dim)),bank,mx.maximum(slots,0),weights);values=mx.where(valid[:,None],values,mx.zeros_like(values));bank.track(values);self.consumer_roots.append(values)
  y=mx.zeros((1,c.dim),mx.float32)
  for k in range(c.n_activated_experts):y=y+values[k:k+1].astype(mx.float32)
  return (y.reshape(x.shape)+self.shared_expert(l,x)).astype(x.dtype)
 def __call__(self,ids,start=0):
  self.active=bool(start);self.actual={};self.predictions={};self.consumer_roots=[]
  if start:
   self.resident=np.zeros((40,384),bool);self.probe_lookup={}
   for l,bank in self.banks.items():
    mapping=np.full(384,-1,np.int32)
    for e,slot in {**bank.main,**bank.hot}.items():mapping[e]=slot
    self.resident[l]=mapping>=0;self.probe_lookup[l]=mx.array(mapping)
   if self.mode.startswith('block'):return self.block_forward(ids,start,int(self.mode[5:]))
   if self.mode!='baseline':
    saved=snapshot_tree((self.states,self.shared,self.hash.cache));self.predicting=True;begin=time.perf_counter()
    try:
     StaticModel.__call__(self,ids,start)
     # Submit without waiting. Track all bank consumers before real slot reuse.
     mx.async_eval(*self.predictions.values(),*self.consumer_roots)
    finally:self.states,self.shared,self.hash.cache=saved;self.predicting=False
    self.timings.append(dict(build_submit_seconds=time.perf_counter()-begin))
  return super().__call__(ids,start)
 def block_forward(self,ids,start,size):
  assert ids.shape==(1,1);self.decode_step+=1;self.image_mask=None;c=self.c
  hashes=self.hash(ids,start);h=mx.repeat(self.s.embedding('embed',ids)[:,:,None,:],c.hc_mult,axis=2);pre=mx.zeros(h.shape[:-1],mx.float32);pre[:,:,0]=1.
  begin=time.perf_counter()
  for layer in range(0,40,size):
   end=min(layer+size,40);saved=snapshot_tree((self.states,self.shared));ah,ap=h,pre;self.predicting=True
   try:
    for j in range(layer,end):ah,ap=BurstModel.layer(self,j,ah,ap,hashes,start)
    mx.async_eval(ah,ap,*[self.predictions[j] for j in range(layer,end)])
   finally:self.states,self.shared=saved;self.predicting=False
   for j in range(layer,end):h,pre=BurstModel.layer(self,j,h,pre,hashes,start);self.emit(f'layers.{j}',h)
  self.timings.append(dict(interleaved_forward_build_seconds=time.perf_counter()-begin))
  normed=self.norm('norm',self.hc_pre(h,pre));logits=normed[:,-1].astype(mx.float32)@self.w('head.weight',mx.float32).T
  mx.eval(*self.frequency.values(),*self.fast.values(),*self.slow.values(),*self.recent.values())
  return logits
 def collection_roots(self):return [*self.predictions.values(),*self.actual.values(),*self.consumer_roots]
 def collection_complete(self):
  if self.active:
   assert len(self.actual)==40
   self.rows.append(dict(resident=self.resident,actual=np.stack([np.array(self.actual[l]) for l in range(40)]),**({'predictions':np.stack([np.array(self.predictions[l]) for l in range(40)])} if self.mode!='baseline' else {})))
  self.predictions={};self.actual={};self.consumer_roots=[]
 def close(self):
  out=Path(os.environ['L2_PROBE_OUTPUT'])
  if self.rows:np.savez_compressed(out/'routing.npz',**{k:np.stack([r[k] for r in self.rows]) for k in self.rows[0]})
  (out/'probe.json').write_text(json.dumps(dict(proposal_source_sha256=self.proposal_source_sha256,mode=self.mode,tail_policy=self.tail_policy,canonical_order=self.canonical_order,timings=self.timings,scope='Approximate resident-only proposals, no speculative SSD reads. Exact main pass follows restored state. No L2 prefetch deployed.'),indent=2));super().close()
if __name__=='__main__':
 run.Model=Probe
 run.main()
