"""Family-level validation uncertainty; never consumes the final holdout."""
import argparse,json
from pathlib import Path
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--cohort',type=Path,required=True);ap.add_argument('--source-root',type=Path,required=True);args=ap.parse_args()
with np.load(args.cohort/'validation-proposals.npz') as z:data={k:z[k] for k in z.files}
with np.load(args.cohort/'priority-policy.npz') as z:policy={k:z[k] for k in z.files}
meta=json.loads((args.cohort/'result.json').read_text());samples=[r for r in meta['samples'] if r['split']=='validation'];n=len(data['scores']);bins=np.searchsorted(policy['edges'],data['scores']-data['scores'][...,5:6]);p=policy['prob'][np.arange(40)[None,:,None],np.arange(12)[None,None,:],bins];spent=np.zeros(n,int);hits=np.zeros(n,int);rows=np.arange(n)
for layer in range(40):
 order=np.argsort(p[:,layer],axis=-1)[:,::-1]
 for j in range(12):
  k=order[:,j];confidence=p[rows,layer,k];reserve=policy['future_better'][layer,np.minimum((confidence*100).astype(int),100)];take=data['eligible'][rows,layer,k]&(spent<64)&(64-spent>1.25*reserve);spent+=take;hits+=take&data['correct'][rows,layer,k]
expected=json.loads((args.cohort/'priority-result.json').read_text())['results']['64/1.25']['coverage'];assert abs(hits.sum()/data['misses'].sum()-expected)<1e-12
cases=[];offset=0;families={}
for row in samples:
 with np.load(args.source_root/'data'/row['id']/'supervision.npz') as z:length=len(z['hidden'])
 end=offset+length;h=int(hits[offset:end].sum());m=int(data['misses'][offset:end].sum());r=int(spent[offset:end].sum());cases.append(dict(id=row['id'],family=row['family_id'],rows=length,hits=h,misses=m,reads=r,coverage=h/m));v=families.setdefault(row['family_id'],[0,0]);v[0]+=h;v[1]+=m;offset=end
assert offset==n
values=np.array(list(families.values()));rng=np.random.default_rng(916);draws=values[rng.integers(len(values),size=(10000,len(values)))].sum(1);ratios=draws[:,0]/draws[:,1]
result=dict(point_coverage=expected,family_count=len(families),family_bootstrap_95_interval=np.quantile(ratios,[.025,.975]).tolist(),cases=cases,test_opened=False,scope='Validation only; bootstrap resamples topic families, retaining paired languages. No SSD deadline and no final-test claim.')
(args.cohort/'coverage-uncertainty.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))
