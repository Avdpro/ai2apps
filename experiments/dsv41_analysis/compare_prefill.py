"""Compare fixed-token Prefill experiments; preserve per-step evidence."""
import json
from pathlib import Path
from compare_tail_policies import comparison
ROOT=Path(__file__).resolve().parents[2]
reports={}
paths=sorted((ROOT/'artifacts').glob('dsv41-prefill-*-20260913'))
paths+=[ROOT/'artifacts/dsv41-prefill64-exact-20260913']
for p in paths:
 if not (p/'manifest.json').exists():continue
 m=json.loads((p/'manifest.json').read_text())
 if m['status']!='complete':continue
 ref=Path(m.get('replay_reference',ROOT/'artifacts/dsv41-default-dynamic128-20260913'))
 r=comparison(ref,p)
 r['predictions_match_reference_prefix']=m['generated_ids']==json.loads((ref/'manifest.json').read_text())['generated_ids'][:len(m['generated_ids'])]
 r['prefill_tps']=len(m['input_ids'])/m['step_seconds'][0];r['peak_gb']=m['sampled_physical_footprint_peak_bytes']/1e9
 pr=m.get('prefill_report',{});layers=pr.get('layers',[])
 r['prefill_scratch_read_bytes']=pr.get('read_bytes',0)
 r['expert_total_read_bytes']=m['expert_read_bytes']+r['prefill_scratch_read_bytes']
 if layers:
  r['retained_route_fraction']=sum(x['retained_routes'] for x in layers)/sum(x['total_routes'] for x in layers)
  r['required_unique_sum']=sum(x['required_unique'] for x in layers);r['groups']=sum(x['groups'] for x in layers)
 reports[p.name]=r
 print(p.name, json.dumps({k:v for k,v in r.items() if k not in ['steps','reference','candidate']}))
(ROOT/'artifacts/dsv41-prefill-comparisons-20260913.json').write_text(json.dumps(reports,indent=2))
