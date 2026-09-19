"""Bounded validation replay. Optimistic READY; foreground routing remains exact."""
import argparse,json
from collections import OrderedDict
from pathlib import Path
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--exclusive',action='store_true');ap.add_argument('--reserve-factor',type=float,default=1.25);ap.add_argument('--capacities',type=int,nargs='+',default=[64,128,256]);ap.add_argument('--output-name');args=ap.parse_args()
root=Path('artifacts/dsv41-l2-state-v3-20260916');source=root/'replay-expanded-r64';model=root/'lookahead-expanded-r64'
with np.load(source/'validation-proposals.npz') as z:data={k:z[k] for k in z.files}
with np.load(model/'priority/priority-policy.npz') as z:policy={k:z[k] for k in z.files}
with np.load(model/'priority/validation-proposals.npz') as z:
 for k in ['scores','eligible','correct','misses']:assert np.array_equal(data[k],z[k]),k
meta=json.loads((model/'manifest.json').read_text());gap=data['scores']-data['scores'][...,5:6];bins=np.searchsorted(policy['edges'],gap);prob=policy['prob'][np.arange(40)[None,:,None],np.arange(12)[None,None,:],bins];order=np.argsort(prob,axis=-1)[:,:,::-1]
sequences=[];offset=0
for name in meta['validation_sequences']:
 with np.load(root/'data'/name/'supervision.npz') as z:resident=z['resident'][:-1].copy();truth=z['top6'][:-1].copy()
 n=len(truth);sequences.append((name,offset,resident,truth));offset+=n
assert offset==len(prob)
results=[]
for capacity in args.capacities:
 assert 0<capacity<=448,'bounded diagnostic maximum448 slots'
 for budget in [0,48,64]:
  counters=dict(base_misses=0,foreground_reads=0,prefetch_reads=0,immediate_hits=0,carried_prediction_hits=0,demand_retention_hits=0,unused_prefetch_records=0,max_token_prefetch=0,max_resident=0)
  for name,offset,resident,truth in sequences:
   cache=OrderedDict()
   def insert(key,origin,token):
    if key in cache:cache.move_to_end(key);return
    if len(cache)>=capacity:
     _,entry=cache.popitem(last=False)
     if entry['origin']=='prediction' and not entry['used']:counters['unused_prefetch_records']+=1
    cache[key]=dict(origin=origin,token=token,used=False);counters['max_resident']=max(counters['max_resident'],len(cache))
   for token in range(len(truth)):
    row=offset+token;spent=0
    for layer in range(40):
     target=layer+1
     if budget and target<40:
      for k in order[row,target]:
       if spent>=budget:break
       e=int(data['ids'][row,target,k]);key=(target,e)
       if resident[token,target,e] or key in cache:continue
       p=prob[row,target,k];reserve=policy['future_better'][target,min(int(p*100),100)]
       if budget-spent<=args.reserve_factor*reserve:continue
       insert(key,'prediction',token);spent+=1;counters['prefetch_reads']+=1
     for e0 in truth[token,layer]:
      e=int(e0);key=(layer,e)
      if resident[token,layer,e]==0:
       counters['base_misses']+=1
       if key in cache:
        entry=cache[key];kind='demand_retention_hits' if entry['origin']=='demand' else ('immediate_hits' if entry['token']==token else 'carried_prediction_hits');counters[kind]+=1;entry['used']=True;cache.move_to_end(key)
        if args.exclusive:del cache[key]
       else:
        counters['foreground_reads']+=1
        if not args.exclusive:insert(key,'demand',token)
      elif key in cache:
       # A base-cache hit does not consume this duplicate L2 payload.
       if args.exclusive:
        entry=cache.pop(key)
        if entry['origin']=='prediction' and not entry['used']:counters['unused_prefetch_records']+=1
       else:cache.move_to_end(key)
    counters['max_token_prefetch']=max(counters['max_token_prefetch'],spent)
    assert spent<=budget and len(cache)<=capacity
   counters['unused_prefetch_records']+=sum(e['origin']=='prediction' and not e['used'] for e in cache.values())
  assert counters['base_misses']==int(data['misses'].sum())
  covered=counters['base_misses']-counters['foreground_reads'];assert covered==sum(counters[k] for k in ['immediate_hits','carried_prediction_hits','demand_retention_hits'])
  results.append(dict(capacity=capacity,prefetch_cap=budget,payload_GB=capacity*18.800640/1000,foreground_miss_coverage=covered/counters['base_misses'],prefetch_per_token=counters['prefetch_reads']/len(prob),unused_prefetch_MB_per_token=counters['unused_prefetch_records']*18.800640/len(prob),total_SSD_read_change_fraction=(counters['foreground_reads']+counters['prefetch_reads'])/counters['base_misses']-1,**counters))
report=dict(reserve_factor=args.reserve_factor,retention='unused-predictions-only' if args.exclusive else 'duplicate-demand-and-prediction',results=results,validation_rows=len(prob),sequence_count=len(sequences),test_opened=False,scope='Optimistic immediate READY at source layer before target; Bounded LRU L2; retention policy recorded separately. Memory is payload-only estimate, not measured footprint. Zero-prefetch control uses identical capacity. Base L0/L1 transitions fixed to exact trace; no cache mapping changes or deadline/TPS proof.')
(source/(args.output_name or ('persistent-replay-exclusive.json' if args.exclusive else 'persistent-replay.json'))).write_text(json.dumps(report,indent=2));print(json.dumps(results,indent=2))
