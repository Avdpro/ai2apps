"""Re-anchor old/new performance on the historical 2048-token workload."""
import json,os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];work=root/'artifacts/dsv41-tps-anchor-20260916';work.mkdir(exist_ok=True)
hist=json.loads((root/'artifacts/dsv41-burst128-t2-b1-20260913/manifest.json').read_text())
(work/'prompt.json').write_text(json.dumps({'prompt':hist['prompt'],'input_ids':hist['input_ids']},ensure_ascii=False))
rows=[]
for name,mode,top,policy in [('natural-legacy','legacy',0,'eviction_dual'),('natural-auto','auto',0,'eviction_dual'),('top2-auto','auto',2,'eviction_dual'),('top2-legacy','legacy',2,'eviction_dual')]:
 out=work/name;env={k:v for k,v in os.environ.items() if not k.startswith('DSV41_') and k!='DYLD_LIBRARY_PATH'}
 cmd=[sys.executable,str(root/'experiments/dsv41_mlx/run.py'),'--inference-mode',mode,'--prompt-json',str(work/'prompt.json'),'--decode','128','--prefill-slots','64','--l1-policy',policy,'--logits-mode','hash','--output',str(out)]
 if top:cmd+=['--burst-top',str(top)]
 print('RUN',name,flush=True)
 with (work/(name+'.log')).open('w') as f:subprocess.run(cmd,env=env,cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True)
 d=json.loads((out/'manifest.json').read_text());t=d['step_seconds'][1:];c=d['cache_stats'];row={'name':name,'top':top,'policy':policy,'input_tokens':len(d['input_ids']),'decode':len(t),'tps':len(t)/sum(t),'first_decode_seconds':t[0],'tail112_tps':112/sum(t[16:]),'top6_hit_rate':1-c['misses']/c['route_requests'],'misses':c['misses'],'peak_bytes':d['sampled_physical_footprint_peak_bytes'],'controller':d.get('miss_resume',{}).get('stats')};rows.append(row);(work/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
for top,prefix in [(0,'natural'),(2,'top2')]:
 a=json.loads((work/(prefix+'-legacy')/'manifest.json').read_text());b=json.loads((work/(prefix+'-auto')/'manifest.json').read_text());checks={k:a[k]==b[k] for k in ['logits_sha256','expert_read_bytes','expert_total_read_bytes']};checks.update({k:a['adaptive_l1'][k]==b['adaptive_l1'][k] for k in ['per_layer_counts','promotions','bank_fence_calls']});print(prefix,checks,flush=True);assert all(checks.values());(work/(prefix+'-verification.json')).write_text(json.dumps(checks,indent=2))
