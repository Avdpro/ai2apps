"""Fit one causal attention reuse coefficient per layer using training states only."""
import json
from pathlib import Path
import numpy as np
root=Path('artifacts/dsv41-l2-attn-reuse-v5-20260916');plan=json.loads((root/'plan.json').read_text());sum_d=np.zeros((40,5120),np.float64);sum_y=np.zeros_like(sum_d);dd=np.zeros(40,np.float64);dy=dd.copy();count=0;names=[]
for row in plan['samples']:
 if row['split']!='train':continue
 assert (root/'data'/row['id']/'verified.json').exists()
 with np.load(root/'data'/row['id']/'supervision.npz') as z:
  p=z['preattn'].astype(np.float32);d=z['attention_reuse'].astype(np.float32)-p;y=z['actual_ffn'].astype(np.float32)-p
 sum_d+=d.sum(0,dtype=np.float64);sum_y+=y.sum(0,dtype=np.float64);dd+=(d*d).sum((0,2),dtype=np.float64);dy+=(d*y).sum((0,2),dtype=np.float64);count+=len(d);names.append(row['id'])
variance=dd-(sum_d*sum_d).sum(-1)/count;covariance=dy-(sum_d*sum_y).sum(-1)/count;coeff=np.clip(covariance/np.maximum(variance,1e-12),0,1)
report=dict(coefficients=coeff.tolist(),train_rows=count,train_sequences=names,test_opened=False,scope='One scalar/layer fit to centered FFN residual MSE; mean correction applied separately; no current attention target supplied at inference')
(root/'trained-blend.json').write_text(json.dumps(report,indent=2));print('blend min/median/max',np.quantile(coeff,[0,.5,1]).tolist())
