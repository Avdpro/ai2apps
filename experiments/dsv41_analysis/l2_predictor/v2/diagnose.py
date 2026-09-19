"""Validation diagnostics only: token support and per-layer miss coverage."""
import json
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
import mlx.core as mx
from optimize import Head
from train import ROOT
plan=json.loads((ROOT/'plan.json').read_text());counts=Counter()
for row in plan['samples']:
 if row['split']=='train':counts.update(json.loads((ROOT/'data'/row['id']/'alignment.json').read_text())['token_ids'])
model=Head(512,False);path=ROOT/'optimization-capacity-v3/r512-context0/model.safetensors';model.load_weights(str(path));stats=defaultdict(lambda:[0,0,0]);layers=np.zeros((40,2),dtype=np.int64)
for row in plan['samples']:
 if row['split']!='validation':continue
 d=ROOT/'data'/row['id'];tokens=json.loads((d/'alignment.json').read_text())['token_ids']
 with np.load(d/'supervision.npz') as z:
  for start in range(0,len(tokens),64):
   stop=start+64;x=mx.array(np.concatenate([z['hidden'][start:stop],z['embedding'][start:stop]],axis=-1));r=z['resident'][start:stop];ids=z['top6'][start:stop].astype(int);truth=np.zeros_like(r,dtype=bool);np.put_along_axis(truth,ids,True,axis=-1);truth&=r==0
   score=np.array(model(x,mx.array(r),mx.zeros(r.shape)));score=np.where(r==0,score,-np.inf).reshape(len(x),-1);ix=np.argsort(score,axis=-1)[:,-48:];good=np.take_along_axis(truth.reshape(len(x),-1),ix,axis=-1)
   for j,token in enumerate(tokens[start:stop]):
    freq=counts[token];bucket='unseen' if freq==0 else '1-4' if freq<5 else '5-19' if freq<20 else '20+'
    for key in ['support:'+bucket,'language:'+row['language'],'scope:'+row['scope'],'kind:'+row['kind']]:stats[key][0]+=int(good[j].sum());stats[key][1]+=int(truth[j].sum());stats[key][2]+=1
    layers[:,0]+=np.bincount(ix[j][good[j]]//384,minlength=40);layers[:,1]+=truth[j].sum(axis=-1)
result=dict(groups={k:dict(coverage=v[0]/max(v[1],1),rows=v[2],misses=v[1]) for k,v in stats.items()},layers=[dict(layer=i,coverage=float(a)/max(int(b),1),misses=int(b)) for i,(a,b) in enumerate(layers)])
(ROOT/'optimization-capacity-v3/diagnostics-r512.json').write_text(json.dumps(result,indent=2));print(json.dumps(result['groups'],indent=2));print('worst_layers',sorted(result['layers'],key=lambda r:r['coverage'])[:8])
