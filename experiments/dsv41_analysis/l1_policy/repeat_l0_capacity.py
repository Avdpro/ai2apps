import json,subprocess,sys
from pathlib import Path
r=Path('artifacts/dsv41-l0-capacity-20260915');assert (r/'complete.json').exists();rows=[]
for cap in [16,8]:
 out=r/f'coding-en-train-18-l0-{cap}-repeat'
 cmd=[sys.executable,str(r/f'source-{cap}/experiments/dsv41_mlx/run_l1.py'),'--prompt-json','artifacts/dsv41-l1-shape-20260915/dataset/coding-en-train-18.json','--decode','128','--prefill-slots','64','--main-slots','40','--decode-dispatch','legacy','--logits-mode','hash','--output',str(out)]
 with out.with_suffix('.log').open('w') as h:subprocess.run(cmd,stdout=h,stderr=subprocess.STDOUT,check=True)
 m=json.loads((out/'manifest.json').read_text());b=json.loads((r/f'coding-en-train-18-l0-{cap}/manifest.json').read_text())
 assert m['status']=='complete' and m['sampled_physical_footprint_peak_bytes']<65e9
 for k in ['input_ids','generated_ids','logits_sha256','cache_stats']:assert m[k]==b[k]
 t=m['step_seconds'];x=dict(l0=cap,tps=128/sum(t[1:]),tail_tps=112/sum(t[17:]),peak_gb=m['sampled_physical_footprint_peak_bytes']/1e9);rows.append(x);print(json.dumps(x),flush=True)
(r/'repeat-results.json').write_text(json.dumps(rows,indent=2));(r/'final-verification.json').write_text(json.dumps({'runs':8,'all_logits_exact':True,'under_65gb':True}))
