"""Timely L2 coverage is distinct from late-but-useful predictions."""
import argparse,json
from pathlib import Path
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);a=ap.parse_args();assert (a.root/'complete.json').exists()
dirs=[p for p in a.root.iterdir() if p.is_dir() and (p/'manifest.json').exists()];man={p.name:json.loads((p/'manifest.json').read_text()) for p in dirs};first=next(iter(man.values()));reference=None;result={}
for p in dirs:
 d=man[p.name];assert d['status']=='complete'
 for k in ['input_ids','generated_ids','logits_sha256','cache_stats']:assert d[k]==first[k],(p.name,k)
 with np.load(p/'routing.npz') as z:resident=z['resident'];actual=z['actual'].astype(int)
 if reference is None:reference=(resident.copy(),actual.copy())
 else:assert np.array_equal(resident,reference[0]) and np.array_equal(actual,reference[1]),p.name
 misses=int((~np.take_along_axis(resident,actual,axis=-1)).sum());t=d['step_seconds'][5:];row=dict(steady_after4_tps=len(t)/sum(t),peak_bytes=d['sampled_physical_footprint_peak_bytes'],base_misses=misses,expert_no_cache=d['expert_no_cache'])
 if (p/'timing.json').exists():
  all_times=json.loads((p/'timing.json').read_text())['step_seconds'][5:];row['end_to_end_after4_tps']=len(all_times)/sum(all_times)
 if (p/'prefetch.json').exists():
  f=json.loads((p/'prefetch.json').read_text());s={k:sum(r[k] for r in f['records']) for k in ['requested','timely','late','foreground']};assert s['requested']==misses and s['timely']+s['late']+s['foreground']==misses
  assert all(r['reserved_reads']<=64 and r['completed_reads']<=64 for r in f['tokens']);reads=len(f['reads']);unused=sum(r['unused'] for r in f['tokens']);assert reads==s['timely']+s['late']+unused
  if f.get('notice_mode')=='credit':
   assert len(f['credit_rows'])==len(actual)
   if f.get('startup'):
    with np.load(p/'routing.npz') as z:predicted_first=np.argsort(z['predictions'][:,0],axis=-1)[:,-6:]
    assert np.array_equal(np.sort(predicted_first,axis=-1),np.sort(actual[:,0],axis=-1)), 'Startup route must exactly match real main routing'
   for token in f['credit_rows']:
    miss_layers=sum(r['requested']>0 for r in f['records'] if r['step']==token['step'])
    assert token['saved_metadata_readbacks']+token.get('startup_miss',0)==miss_layers
    assert token['candidate_route_boundaries']<=token['baseline_route_boundaries']
   row['route_boundaries_baseline']=sum(r['baseline_route_boundaries'] for r in f['credit_rows'])
   row['route_boundaries_candidate']=sum(r['candidate_route_boundaries'] for r in f['credit_rows'])
  tail=[r['tail_wait_seconds'] for r in f['tokens']][4:];assert len(tail)==len(t);row['runner_plus_tail_after4_tps']=len(t)/(sum(t)+sum(tail))
  row.update(timely_coverage=s['timely']/misses,late_coverage=s['late']/misses,prefetch_reads=reads,unused_reads=unused,wasted_MB_per_token=unused*18.800640/len(actual),total_decode_read_change_fraction=(reads+s['foreground'])/misses-1,extra_async_notifications_per_token=f.get('extra_async_notifications_per_token',40),notice_mode=f.get('notice_mode','async'),staging_slots_total=320,staging_payload_GB=320*18.800640/1000,**s)
 result[p.name]=row
report=dict(results=result,exact_primary_parity=True,test_opened=False,scope='Development prompt comparison; decode length recorded in each manifest. Same L0/L1 logical membership and exact logits. Timely measured at foreground bank read entry after original fence. Notification/readback mode is recorded per candidate; packed mode replaces the original scalar cache-hit readback. No independent-conversation acceptance.')
(a.root/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
