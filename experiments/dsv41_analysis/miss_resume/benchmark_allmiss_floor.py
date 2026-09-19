"""Actual SSD all-miss ABBA: original Burst versus adaptive window entry."""
import os,sys,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[3];here=Path(__file__).parent
work=root/'artifacts/dsv41-allmiss-floor-20260916';work.mkdir(exist_ok=True)
rows=json.loads((work/'results.json').read_text()) if len(sys.argv)>1 and (work/'results.json').exists() else []
for name,eager,top in [('old-a',True,2),('new-a',False,2),('new-b',False,2),('old-b',True,2),('old-top4',True,4),('new-top4',False,4),('old-natural',True,0),('new-natural',False,0)]:
 if len(sys.argv)>1 and name not in sys.argv[1:]:continue
 env={k:v for k,v in os.environ.items() if not k.startswith('DSV41_')}
 env.update(DYLD_LIBRARY_PATH=str(root/'artifacts/dsv41-miss-resume-mlx-build'),DSV41_RESUME_MODE='window' if top else 'auto',DSV41_RESUME_EAGER=str(int(eager)),DSV41_RESUME_BURST=str(top),DSV41_RESUME_BLOCK='4',DSV41_RESUME_STRESS_ALL_MISS='1',DSV41_ASYNC_WINDOW='1')
 cmd=[sys.executable,str(here/'entry.py'),'--prompt-json',str(root/'artifacts/dsv41-miss-resume-20260915/bench-wheel/prompt.json'),'--decode','32','--prefill-slots','64','--logits-mode','hash','--output',str(work/name)]
 print('RUN',name,flush=True)
 with (work/(name+'.log')).open('w') as f:subprocess.run(cmd,env=env,cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True)
 d=json.loads((work/name/'manifest.json').read_text());ref=json.loads((work/('old-natural' if top==0 else 'old-a' if top==2 else 'old-top4')/'manifest.json').read_text())
 checks={k:d[k]==ref[k] for k in ['logits_sha256','expert_read_bytes','expert_total_read_bytes']}
 checks.update({k:d['adaptive_l1'][k]==ref['adaptive_l1'][k] for k in ['per_layer_counts','promotions','bank_fence_calls']})
 checks['all_layers_cold']=all(x==[0,0,192] for x in d['adaptive_l1']['per_layer_counts'])
 if not eager:
  st=d['miss_resume']['stats'];checks['every_layer_missed']=st['packet_misses']==1280;checks['no_speculative_work']=st['constructed_layers']==0 and st['window_tokens']==0
 t=d['step_seconds'][1:];row=dict(name=name,tps=32/sum(t),tail_tps=24/sum(t[8:]),checks=checks,stats=d['miss_resume']['stats'],peak=d['sampled_physical_footprint_peak_bytes'],expert_bytes=d['expert_read_bytes'])
 rows.append(row);(work/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps({k:v for k,v in row.items() if k!='stats'}),flush=True)
 assert all(checks.values()),name
