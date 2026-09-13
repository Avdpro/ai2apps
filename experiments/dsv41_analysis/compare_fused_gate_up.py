import json
from pathlib import Path
from compare_tail_policies import comparison
root=Path(__file__).resolve().parents[2];reports={}
for name in ['control','fused','repeat','code','compact']:
 p=root/f'artifacts/dsv41-fused-{name}-20260913'
 if not (p/'manifest.json').exists():continue
 m=json.loads((p/'manifest.json').read_text())
 if m['status']!='complete':continue
 r=comparison(Path(m['replay_reference']),p)
 r.update(prefill_tps=len(m['input_ids'])/m['step_seconds'][0],peak_gb=m['sampled_physical_footprint_peak_bytes']/1e9,max_abs_all=max(s['max_abs'] for s in r['steps']))
 reports[name]=r
 print(name,r['prefill_tps'],r['peak_gb'],r['max_abs_all'])
(root/'artifacts/dsv41-fused-comparisons-20260913.json').write_text(json.dumps(reports,indent=2))
