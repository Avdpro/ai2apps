import json,hashlib
import numpy as np
from safetensors.numpy import load_file
from pathlib import Path
from compare_tail_policies import comparison
root=Path(__file__).resolve().parents[2];reports={}
for name in ['first','control','repeat','final','code','both']:
 p=root/f'artifacts/dsv41-hot-direct-{name}-20260913'
 if not (p/'manifest.json').exists():continue
 m=json.loads((p/'manifest.json').read_text())
 if m['status']!='complete':continue
 ref=root/('artifacts/dsv41-tail-code-exact-20260913' if name=='code' else 'artifacts/dsv41-prefill-final-both-top2-20260913' if name=='both' else 'artifacts/dsv41-prefill-final64-20260913')
 r=comparison(ref,p);old=json.loads((ref/'manifest.json').read_text())
 r.update(prefill_tps=len(m['input_ids'])/m['step_seconds'][0],peak_gb=m['sampled_physical_footprint_peak_bytes']/1e9,max_abs_all=max(x['max_abs'] for x in r['steps']),cache_counts_equal=m['adaptive_l1']['per_layer_counts']==old['adaptive_l1']['per_layer_counts'],expert_bytes=m['expert_total_read_bytes'])
 timings={}
 for layer in m.get('prefill_report',{}).get('layers',[]):
  for k,v in layer.get('timing',{}).items():timings[k]=timings.get(k,0)+v
 r['async_dispatch_timings']=timings;reports[name]=r
 print(name,{k:r[k] for k in ['prefill_tps','peak_gb','max_abs_all','cache_counts_equal','expert_bytes']})
profile=root/'artifacts/dsv41-hot-direct-profile-20260913'
if (profile/'profile.json').exists():
 pr=json.loads((profile/'profile.json').read_text());pm=json.loads((profile/'manifest.json').read_text())
 base=root/'artifacts/dsv41-prefill-final64-20260913';bm=json.loads((base/'manifest.json').read_text());assert pm['input_ids']==bm['input_ids']
 arrays=[]
 for directory,manifest in [(profile,pm),(base,bm)]:
  path=directory/'00_logits.safetensors';assert hashlib.sha256(path.read_bytes()).hexdigest()==manifest['trace_files'][path.name]
  arrays.append(load_file(str(path))['logits'].astype(np.float64))
 delta=float(np.max(np.abs(arrays[0]-arrays[1])));assert delta==0
 exclusive=sum(v['exclusive_seconds'] for v in pr['operations'].values());total=pr['operations']['forward']['inclusive_seconds'];assert abs(exclusive-total)<1e-6
 reports['profile_validation']=dict(prefill_max_abs=delta,exclusive_sum=exclusive,forward_inclusive=total,profile_path=str(profile/'profile.json'))
(root/'artifacts/dsv41-hot-direct-comparisons-20260913.json').write_text(json.dumps(reports,indent=2))
