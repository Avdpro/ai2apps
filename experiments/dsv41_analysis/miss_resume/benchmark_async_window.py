"""Paired synchronous/asynchronous native window4, same public CLI."""
import json,os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
work=Path(os.environ.get('DSV41_WINDOW_BENCH_DIR',str(root/'artifacts/dsv41-allhit-isolation-20260916/real-window4'))).resolve()
work.mkdir(parents=True,exist_ok=True)
prompt=root/'artifacts/dsv41-tps-anchor-20260916/prompt.json'
rows=[]
for name,mode,top in [('sync-a','window',2),('async-a','window',2),('async-b','window',2),('sync-b','window',2)]:
 env={k:v for k,v in os.environ.items() if not k.startswith('DSV41_') and k!='DYLD_LIBRARY_PATH'}
 env['DSV41_ASYNC_WINDOW']='1' if name.startswith('async') else '0'
 env['DSV41_WINDOW_FORCE']='1'
 cmd=[sys.executable,str(root/'experiments/dsv41_mlx/run.py'),'--inference-mode',mode,'--burst-top',str(top),'--resume-block','4','--prompt-json',str(prompt),'--decode','128','--prefill-slots','64','--logits-mode','hash','--output',str(work/name)]
 print('RUN',name,flush=True)
 with (work/(name+'.log')).open('w') as f:subprocess.run(cmd,env=env,cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True)
 d=json.loads((work/name/'manifest.json').read_text());t=d['step_seconds'][1:]
 ref=work/'sync-a'/'manifest.json';a=json.loads(ref.read_text())
 checks={k:a[k]==d[k] for k in ('logits_sha256','expert_read_bytes','expert_total_read_bytes')}
 checks.update({k:a['adaptive_l1'][k]==d['adaptive_l1'][k] for k in ('per_layer_counts','promotions','bank_fence_calls')})
 row=dict(name=name,mode=mode,top=top,tps=128/sum(t),tail_tps=112/sum(t[16:]),first=t[0],peak=d['sampled_physical_footprint_peak_bytes'],checks=checks,controller=d.get('miss_resume',{}).get('stats'))
 rows.append(row);(work/'final-results.json').write_text(json.dumps(rows,indent=2));print(json.dumps({k:v for k,v in row.items() if k!='controller'}),flush=True)
 if not all(checks.values()):raise RuntimeError('Parity failed '+name)
