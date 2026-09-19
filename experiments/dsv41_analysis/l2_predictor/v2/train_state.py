"""Causal previous-layer-state predictor; validation-only, including partial-cohort pilots."""
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_flatten
ROOT=Path('artifacts/dsv41-l2-state-v3-20260916')

class StateHead(nn.Module):
 def __init__(self,rank):
  super().__init__();self.local=nn.Linear(5120,rank);self.token=nn.Linear(5120,rank,bias=False);self.final=nn.Linear(5120,rank,bias=False);self.cache=nn.Linear(384,rank,bias=False)
  self.layer=mx.zeros((40,rank));self.out=mx.random.normal((40,rank,384))*.02;self.bias=mx.zeros((40,384))
 def __call__(self,local,token,final,resident):
  def norm(x):return x*mx.rsqrt(mx.mean(x*x,axis=-1,keepdims=True)+1e-6)
  h=self.local(norm(local))+self.token(norm(token))[:,None]+self.final(norm(final))[:,None]+self.cache((resident>0).astype(mx.float32))+self.layer
  h=nn.gelu(h);return mx.matmul(h.transpose(1,0,2),self.out).transpose(1,0,2)+self.bias

class CrossStateHead(StateHead):
 def __init__(self,rank):
  super().__init__(rank);self.query=nn.Linear(rank,128,bias=False);self.kv=nn.Linear(5120,256);self.delta=nn.Linear(128,rank,bias=False);self.delta.weight=mx.zeros_like(self.delta.weight);self.query_position=mx.random.normal((40,rank))*.02
 def __call__(self,local,token,final,resident):
  def norm(x):return x*mx.rsqrt(mx.mean(x*x,axis=-1,keepdims=True)+1e-6)
  base=self.token(norm(token))[:,None]+self.final(norm(final))[:,None]+self.local.bias
  query=self.query(base+self.query_position);kv=self.kv(norm(local));key,value=mx.split(kv,2,axis=-1)
  attention=mx.softmax(mx.matmul(query,key.transpose(0,2,1))*(128**-.5),axis=-1)
  h=nn.gelu(base+self.delta(mx.matmul(attention,value)))
  return mx.matmul(h.transpose(1,0,2),self.out).transpose(1,0,2)+self.bias

def load(plan,split):
 chunks=[];ids=[]
 for row in plan['samples']:
  if row['split']!=split:continue
  d=ROOT/'data'/row['id']
  if not (d/'verified.json').exists():continue
  if not json.loads((d/'verified.json').read_text())['rows']:continue
  reference=Path('artifacts/dsv41-l2-v2-20260916/data')/row['id']/'manifest.json'
  if reference.exists():
   current=json.loads((d/'manifest.json').read_text());old=json.loads(reference.read_text())
   for key in ['input_ids','generated_ids','logits_sha256','expert_read_bytes','expert_total_read_bytes']:assert current[key]==old[key],(row['id'],key)
   for key in ['per_layer_counts','promotions','bank_fence_calls']:assert current['adaptive_l1'][key]==old['adaptive_l1'][key],(row['id'],key)
  with np.load(d/'supervision.npz') as z:
   y=np.zeros(z['resident'].shape,np.float32);np.put_along_axis(y,z['top6'].astype(int),1,axis=-1)
   chunks.append(tuple(z[k].copy() for k in ['previous_ffn','embedding','hidden','resident'])+(y,));ids.append(row['id'])
 assert chunks,split
 return tuple(np.concatenate([c[i] for c in chunks]) for i in range(5)),ids

def warm_start(model,rank):
 candidates=[Path('artifacts/dsv41-l2-v2-20260916/optimization-capacity-v3')/f'r{rank}-context0/model.safetensors',Path('artifacts/dsv41-l2-v2-20260916/optimization-v2')/f'r{rank}-context0/model.safetensors']
 # Only consume a completed ablation, never an in-progress checkpoint.
 path=next((p for p in candidates if p.exists() and (p.parent/'result.json').exists()),None)
 if path is None:return None
 w=mx.load(str(path));model.final.weight=w['down.weight'][:,:5120];model.token.weight=w['down.weight'][:,5120:]
 model.local.weight=mx.zeros_like(model.local.weight);model.local.bias=w['down.bias'];model.cache.weight=mx.zeros_like(model.cache.weight)
 model.out=w['up.weight'].reshape(40,384,rank).transpose(0,2,1);model.bias=w['up.bias'].reshape(40,384)
 return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),pretraining_rows=12032,method='Exact split of global input projection; zero-initialized local-state/cache residual branches')

def objective(m,a,b,c,r,t):
 z=m(a,b,c,r);w=(1+3*(r==0))*(1+15*t)
 return mx.mean((mx.logaddexp(z,0)-z*t)*w)

def evaluate(m,data):
 count=0;misses=0;hits={k:0 for k in [32,48,64,96]};loss=0
 for i in range(0,len(data[0]),32):
  a,b,c,r,t=[mx.array(x[i:i+32]) for x in data];z=m(a,b,c,r);v=objective(m,a,b,c,r,t);mx.eval(z,v);n=len(a);count+=n;loss+=v.item()*n
  eligible=data[3][i:i+32]==0;truth=data[4][i:i+32].astype(bool)&eligible;misses+=truth.sum();score=np.where(eligible,np.array(z),-np.inf).reshape(n,-1);ix=np.argsort(score,axis=-1)[:,-96:][:,::-1];good=np.take_along_axis(truth.reshape(n,-1),ix,axis=-1)
  for k in hits:hits[k]+=int(good[:,:k].sum())
 return dict(loss=loss/count,rows=count,misses_per_token=float(misses)/count,budgets={k:dict(coverage=v/int(misses),precision=v/(count*k),useful_per_token=v/count) for k,v in hits.items()})

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--rank',type=int,default=128);ap.add_argument('--epochs',type=int,default=30);ap.add_argument('--freeze-global',action='store_true');ap.add_argument('--attention',action='store_true');ap.add_argument('--cohort',type=Path);args=ap.parse_args();args.output.mkdir(exist_ok=False,parents=True)
 plan=json.loads((ROOT/'plan.json').read_text())
 if args.cohort:
  cohort=json.loads(args.cohort.read_text());allowed=set(cohort['train_sequences']+cohort['validation_sequences']);plan['samples']=[r for r in plan['samples'] if r['id'] in allowed]
 tr,trids=load(plan,'train');va,vaids=load(plan,'validation');mx.random.seed(17);rng=np.random.default_rng(17);m=(CrossStateHead if args.attention else StateHead)(args.rank);warm=warm_start(m,args.rank)
 if args.freeze_global:
  assert warm,'Frozen residual training requires pretrained head';m.freeze()
  if args.attention:
   m.query.unfreeze();m.kv.unfreeze();m.delta.unfreeze();m.unfreeze(keys='query_position',recurse=False)
  else:m.local.unfreeze(keys='weight')
 opt=optim.AdamW(learning_rate=1e-4 if warm else 3e-4,weight_decay=.01);vg=nn.value_and_grad(m,objective)
 (args.output/'manifest.json').write_text(json.dumps(dict(train_sequences=trids,validation_sequences=vaids,rank=args.rank,attention=args.attention,warm_start=warm,freeze_global=args.freeze_global,test_opened=False,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),feature='previous token FFN normalized input, current input embedding, previous final hidden, current resident tags'),indent=2))
 initial=evaluate(m,va);best=initial['budgets'][48]['coverage'];best_ev=initial;best_epoch=0;stale=0;hist=[dict(epoch=0,validation=initial)];start=time.time();m.save_weights(str(args.output/'model.safetensors'))
 for epoch in range(args.epochs):
  ids=rng.permutation(len(tr[0]));total=0
  for i in range(0,len(ids),32):
   ix=ids[i:i+32];arrays=[mx.array(x[ix]) for x in tr];v,g=vg(m,*arrays);opt.update(m,g);mx.eval(m.parameters(),opt.state,v);total+=v.item()*len(ix)
  ev=evaluate(m,va);score=ev['budgets'][48]['coverage'];row=dict(epoch=epoch+1,train_loss=total/len(ids),validation=ev,seconds=time.time()-start);hist.append(row)
  if score>best:best=score;best_ev=ev;best_epoch=epoch+1;stale=0;m.save_weights(str(args.output/'model.safetensors'))
  else:stale+=1
  (args.output/'history.json').write_text(json.dumps(hist,indent=2));print(json.dumps(dict(epoch=epoch+1,coverage48=score,coverage64=ev['budgets'][64]['coverage'])),flush=True)
  if stale>=5:break
 result=dict(best_epoch=best_epoch,validation=best_ev,train_rows=len(tr[0]),validation_rows=len(va[0]),parameters=sum(x.size for _,x in tree_flatten(m.parameters())),trainable_parameters=sum(x.size for _,x in tree_flatten(m.trainable_parameters())),seconds=time.time()-start)
 (args.output/'result.json').write_text(json.dumps(result,indent=2))
if __name__=='__main__':main()
