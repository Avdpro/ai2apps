"""Re-run the exact historical 7.x TPS fixture on current code."""
import json,subprocess,sys,hashlib
from pathlib import Path
import numpy as np
from safetensors.numpy import load_file
root=Path('artifacts/dsv41-historical-tps-check-20260915');root.mkdir(exist_ok=True)
oldpath=Path('artifacts/dsv41-decode-dispatch-ab-20260914/legacy1');old=json.loads((oldpath/'manifest.json').read_text())
oldhash=[]
for i in range(129):oldhash.append(hashlib.sha256(load_file(str(oldpath/f'{i:02d}_logits.safetensors'))['logits'].astype(np.float32).tobytes()).hexdigest())
results=[]
for variant,extra in [('historical-reread',['--l1-policy','baseline','--promotion-reread']),('current-baseline',['--l1-policy','baseline']),('current-new',['--l1-policy','eviction_dual'])]:
 out=root/variant
 cmd=[sys.executable,'experiments/dsv41_mlx/run.py','--prompt-json','experiments/dsv41_analysis/fixtures/prefill2048.json','--decode','128','--prefill-slots','64','--main-slots','40','--decode-dispatch','legacy','--logits-mode','hash','--output',str(out)]+extra
 if not (out/'manifest.json').exists():
  with out.with_suffix('.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete'
 assert m['input_ids']==old['input_ids'] and m['generated_ids']==old['generated_ids']
 assert m['logits_sha256']==oldhash,'historical logits'
 if variant!='current-new':
  assert m['cache_stats']==old['cache_stats']
  assert m['adaptive_l1']['promotions']==old['adaptive_l1']['promotions']
 c=m['cache_stats'];a=m['adaptive_l1'];r=dict(variant=variant,tps=128/sum(m['step_seconds'][1:]),prefill_tps=2048/m['step_seconds'][0],hit=100*(c['l1_hits']+c['l0_hits'])/c['route_requests'],misses=c['misses'],all_hit_steps=c['all_hit_steps'],io_seconds=sum(a['decode_io_seconds'].values()),read_bytes=m['expert_total_read_bytes'],peak=m['sampled_physical_footprint_peak_bytes'],historical_logits_equal=True)
 results.append(r);(root/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps(r),flush=True)
(root/'complete.json').write_text(json.dumps({'historical_fixture_exact':True,'historical_logits_equal':True,'runs':len(results)}))
