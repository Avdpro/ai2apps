"""Train-only confidence calibration and causal future-budget reservation."""
import argparse,json
from pathlib import Path
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--cohort',type=Path,required=True);ap.add_argument('--evaluation-split',choices=['train','validation'],default='validation');a=ap.parse_args()
def load(name):
 with np.load(a.cohort/name) as z:return {k:z[k] for k in z.files}
tr=load('train-proposals.npz');va=load(a.evaluation_split+'-proposals.npz')
edges=np.array([-.5,-.3,-.2,-.15,-.1,-.075,-.05,-.025,0,.025,.05,.075,.1,.15,.2,.3,.5])
def cells(data):
 gap=data['scores']-data['scores'][...,5:6]
 return np.searchsorted(edges,gap)
bt,bv=cells(tr),cells(va);nb=len(edges)+1
# Smoothed rank+margin reliability; no validation labels enter fitting.
base=np.zeros((12,nb));counts=np.zeros_like(base)
for k in range(12):
 for b in range(nb):
  mask=tr['eligible'][:,:,k]&(bt[:,:,k]==b);counts[k,b]=mask.sum();base[k,b]=tr['correct'][:,:,k][mask].sum()
prior=(base+1)/(counts+2)
prob=np.zeros((40,12,nb))
for l in range(40):
 for k in range(12):
  for b in range(nb):
   mask=tr['eligible'][:,l,k]&(bt[:,l,k]==b);prob[l,k,b]=(tr['correct'][:,l,k][mask].sum()+32*prior[k,b])/(mask.sum()+32)
def probabilities(b):return prob[np.arange(40)[None,:,None],np.arange(12)[None,None,:],b]
pt,pv=probabilities(bt),probabilities(bv)
# Histogram gives train-estimated future eligible opportunities at least as reliable.
bins=100
hist=np.zeros((40,bins+1))
for l in range(40):
 values=pt[:,l][tr['eligible'][:,l]];hist[l]=np.bincount(np.minimum((values*bins).astype(int),bins),minlength=bins+1)/len(pt)
future=np.cumsum(hist[::-1],axis=0)[::-1]-hist
better=np.cumsum(future[:,::-1],axis=1)[:,::-1]
results={};n=len(pv);miss=int(va['misses'].sum())
for budget in [48,64]:
 for factor in [0.,.5,.75,1.,1.25,1.5]:
  spent=np.zeros(n,int);useful=np.zeros(n,int)
  for l in range(40):
   order=np.argsort(pv[:,l],axis=-1)[:,::-1]
   for j in range(12):
    ids=order[:,j];ix=np.arange(n);p=pv[ix,l,ids];reserve=better[l,np.minimum((p*bins).astype(int),bins)]
    take=va['eligible'][ix,l,ids]&(spent<budget)&((budget-spent)>factor*reserve)
    spent+=take;useful+=take&va['correct'][ix,l,ids]
  results[f'{budget}/{factor}']=dict(coverage=int(useful.sum())/miss,reads_per_token=float(spent.mean()),useful_per_token=float(useful.mean()),precision=int(useful.sum())/max(1,int(spent.sum())),wasted_MB_per_token=float((spent-useful).mean())*18.800640)
report=dict(evaluation_split=a.evaluation_split,results=results,train_rows=len(pt),validation_rows=n,scope='Train-only confidence calibration/future expectation; current layer predictions only at selection time; cap never exceeded; offline/no deadline',test_opened=False)
(a.cohort/('priority-result.json' if a.evaluation_split=='validation' else 'priority-training-diagnostic.json')).write_text(json.dumps(report,indent=2));
if a.evaluation_split=='validation':np.savez_compressed(a.cohort/'priority-policy.npz',edges=edges,prob=prob,future_better=better)
print(json.dumps(results,indent=2))
