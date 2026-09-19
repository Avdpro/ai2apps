"""Verify exact primary execution before interpreting approximate route quality."""
import json
from pathlib import Path
import numpy as np
root=Path('artifacts/dsv41-l2-resident-probe-20260916');assert (root/'complete.json').exists()
names=['baseline','zero','renorm','baseline-repeat']+(['replace'] if (root/'complete-replace.json').exists() else [])+(['block2','block4'] if (root/'complete-blocks.json').exists() else []);man={n:json.loads((root/n/'manifest.json').read_text()) for n in names};ref=man['baseline'];keys=['input_ids','generated_ids','logits_sha256','cache_stats','expert_read_bytes']
for n,d in man.items():
 assert d['status']=='complete',(n,d['status'])
 for key in keys:assert d[key]==ref[key],(n,key)
results={}
for n in names:
 d=man[n];t=d['step_seconds'][5:];result=dict(steady_after4_tps=len(t)/sum(t),peak_bytes=d['sampled_physical_footprint_peak_bytes'])
 if n in ['zero','renorm','replace','block2','block4']:
  with np.load(root/n/'routing.npz') as z:resident=z['resident'];actual=z['actual'].astype(int);scores=z['predictions']
  truth=np.zeros(resident.shape,bool);np.put_along_axis(truth,actual,True,axis=-1);missing=truth&~resident;denom=int(missing.sum());ids=np.argsort(scores,axis=-1)[...,-12:][...,::-1];rank=np.take_along_axis(scores,ids,axis=-1);correct=np.take_along_axis(truth,ids,axis=-1);eligible=~np.take_along_axis(resident,ids,axis=-1);policies={}
  for budget in [48,64]:
   for k in [6,12]:
    proposed=eligible[...,:k].reshape(len(scores),-1);take=proposed&(np.cumsum(proposed,axis=-1)<=budget);hits=int((take&correct[...,:k].reshape(len(scores),-1)).sum());reads=int(take.sum());policies[f'layer-major-top{k}-cap{budget}']=dict(coverage=hits/denom,reads_per_token=reads/len(scores),useful_per_token=hits/len(scores),waste_MB_per_token=(reads-hits)*18.800640/len(scores))
   if n.startswith('block'):continue # Future blocks are not yet predictable.
   # All proposals are available from the resident pass before the exact pass.
   priority=np.where(eligible,rank-rank[...,5:6],-np.inf).reshape(len(scores),-1);order=np.argsort(priority,axis=-1)[:,-budget:];valid=np.take_along_axis(eligible.reshape(len(scores),-1),order,axis=-1);hit=np.take_along_axis(correct.reshape(len(scores),-1),order,axis=-1)&valid;hits=int(hit.sum());reads=int(valid.sum());policies[f'global-gap-cap{budget}']=dict(coverage=hits/denom,reads_per_token=reads/len(scores),useful_per_token=hits/len(scores),waste_MB_per_token=(reads-hits)*18.800640/len(scores))
  result.update(policies=policies,base_misses=denom)
 results[n]=result
report=dict(parity_keys=keys,results=results,test_opened=False,scope='One short diagnostic prompt/16 decode. Two-pass GPU proposal cost included, no SSD prefetch. Global proposal selection assumes notification after proposal pass; no timely READY measurement.')
(root/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
