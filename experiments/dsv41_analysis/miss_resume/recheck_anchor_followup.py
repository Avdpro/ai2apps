"""Verify native-only auto and match the historical Top2 policy/Prefill settings."""
import json,os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];work=root/'artifacts/dsv41-tps-anchor-20260916';rows=[]
plan=[('top2-auto-native','auto','eviction_dual',64),('top2-legacy-repeat','legacy','eviction_dual',64),('historical-top2-legacy','legacy','baseline',0),('historical-top2-auto','auto','baseline',0)]
for name,mode,policy,prefill in plan:
 out=work/name;env={k:v for k,v in os.environ.items() if not k.startswith('DSV41_') and k!='DYLD_LIBRARY_PATH'}
 cmd=[sys.executable,str(root/'experiments/dsv41_mlx/run.py'),'--inference-mode',mode,'--prompt-json',str(work/'prompt.json'),'--decode','128','--prefill-slots',str(prefill),'--l1-policy',policy,'--burst-top','2','--logits-mode','hash','--output',str(out)]
 print('RUN',name,flush=True)
 with (work/(name+'.log')).open('w') as f:subprocess.run(cmd,env=env,cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True)
 d=json.loads((out/'manifest.json').read_text());t=d['step_seconds'][1:];c=d['cache_stats'];rows.append(dict(name=name,mode=mode,policy=policy,prefill_slots=prefill,tps=128/sum(t),first_decode_seconds=t[0],tail112_tps=112/sum(t[16:]),top6_hit_rate=1-c['misses']/c['route_requests'],controller=d.get('miss_resume',{}).get('stats'),peak_bytes=d['sampled_physical_footprint_peak_bytes']));(work/'followup-results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows[-1]),flush=True)
for left,right in [('top2-legacy','top2-auto-native'),('top2-legacy','top2-legacy-repeat'),('historical-top2-legacy','historical-top2-auto')]:
 a=json.loads((work/left/'manifest.json').read_text());b=json.loads((work/right/'manifest.json').read_text());checks={k:a[k]==b[k] for k in ['logits_sha256','expert_read_bytes','expert_total_read_bytes']};checks.update({k:a['adaptive_l1'][k]==b['adaptive_l1'][k] for k in ['per_layer_counts','promotions','bank_fence_calls']});assert all(checks.values()),(left,right,checks);(work/(right+'-verification.json')).write_text(json.dumps(checks,indent=2));print(left,right,checks,flush=True)
