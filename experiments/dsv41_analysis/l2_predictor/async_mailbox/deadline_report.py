"""Audit parity and observed notification lead; never equate this to SSD READY."""
import argparse,json
from pathlib import Path
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('artifacts/dsv41-l2-deadline-v2-20260916'));a=ap.parse_args()
assert (a.root/'complete.json').exists(),'probe still running or failed'
names=['baseline','notify','baseline-repeat'];man={n:json.loads((a.root/n/'manifest.json').read_text()) for n in names}
ref=man['baseline'];checks=['input_ids','generated_ids','logits_sha256','cache_stats','expert_read_bytes']
for n in names:
 assert man[n]['status']=='completed' or man[n]['status']=='complete',man[n]['status']
 for key in checks:assert man[n][key]==ref[key],(n,key)
events=json.loads((a.root/'notify/delivery.json').read_text())['events'];lookup={e['sequence']:e for e in events};assert len(lookup)==len(events)
expected=ref['decode_forwards']*40
# Runner decode_forwards excludes prefill; require all route pairs.
assert len(events)==expected*2,(len(events),expected)
lead=np.array([lookup[k+1]['time']-e['time'] for k,e in sorted(lookup.items()) if k%2==0]);assert (lead>=0).all()
throughput={n:dict(decode_tps=(len(d['step_seconds'])-1)/sum(d['step_seconds'][1:]),steady_after4_tps=(len(d['step_seconds'])-5)/sum(d['step_seconds'][5:]),peak_bytes=d['sampled_physical_footprint_peak_bytes']) for n,d in man.items()}
result=dict(parity_keys=checks,route_pairs=len(lead),lead_ms_quantiles=dict(zip(['min','p10','median','p90','max'],(np.quantile(lead,[0,.1,.5,.9,1])*1000).tolist())),fraction_lead_at_least_ms={str(ms):float((lead>=ms/1000).mean()) for ms in [.25,.5,1,1.5,2,3]},throughput=throughput,scope='CPU-poll observed delivery gap, not hardware GPU timings. No SSD prefetch or READY coverage measured. Synthetic historical SSD latencies are not acceptance evidence.')
(a.root/'report.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
