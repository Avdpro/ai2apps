"""Sequential correctness/performance gate for the reduced-overhead executor."""
import json,os,subprocess,sys
from pathlib import Path
from compare import compare
root=Path(__file__).resolve().parents[3];here=Path(__file__).parent
work=root/'artifacts/dsv41-burst-guard-opt-20260916';work.mkdir(exist_ok=True)
phase=sys.argv[1] if len(sys.argv)>1 else 'correctness'
if phase.startswith('correctness'):
 prompt=root/'artifacts/dsv41-miss-resume-20260915/bench-wheel/prompt.json'
 plan=[('check-old',True,2,4,8),('check-b2',False,2,2,8),('check-b4',False,2,4,8),('check-b40',False,2,40,8),('check-top4-old',True,4,4,8),('check-top4-b4',False,4,4,8)]
 if phase=='correctness-v2':plan=[('check-prefix-b2',False,2,2,8),('check-native-b2',False,2,2,8),('check-native-b4',False,2,4,8),('check-native-top4-b4',False,4,4,8)]
 if phase=='correctness-v3':plan=[('check-native-defer-b2',False,2,2,8),('check-native-defer-top4-b4',False,4,4,8)]
 if phase=='correctness-v4':plan=[('check-native-defer-stats-b2',False,2,2,8),('check-native-defer-stats-top4-b4',False,4,4,8)]
 if phase=='correctness-v5':plan=[('check-native-defer-stats-roots-b2',False,2,2,8),('check-native-defer-stats-roots-top4-b4',False,4,4,8)]
 if phase=='correctness-natural':plan=[('check-natural-old',True,0,2,8),('check-natural-prefix',False,0,2,8)]
 if phase=='correctness-v6':plan=[('check-native-defer-stats-roots-async-b2',False,2,2,8),('check-native-defer-stats-roots-async-top4-b4',False,4,4,8)]
else:
 prompt=root/'artifacts/dsv41-tps-anchor-20260916/prompt.json'
 plan=[('top2-old',True,2,4,128),('top2-b4',False,2,4,128),('top2-b2',False,2,2,128),('top4-old',True,4,4,128),('top4-b4',False,4,4,128)]
 if phase=='performance-v2':plan=[('top2-old',True,2,4,128),('top2-native-b4',False,2,4,128),('top2-native-b2',False,2,2,128),('top2-prefix-b4',False,2,4,128),('top4-old',True,4,4,128),('top4-native-b4',False,4,4,128)]
 if phase=='performance-v3':plan=[('top2-native-defer-b2',False,2,2,128),('top2-native-defer-adaptive-b4',False,2,4,128),('top4-native-defer-adaptive-b4',False,4,4,128),('top2-old-repeat',True,2,4,128)]
 if phase=='performance-v4':plan=[('top2-native-defer-stats-b2',False,2,2,128),('top2-native-defer-stats-adaptive-b4',False,2,4,128),('top4-native-defer-stats-adaptive-b4',False,4,4,128),('top2-old-repeat2',True,2,4,128)]
 if phase=='performance-v5':plan=[('top2-native-defer-stats-roots-b2',False,2,2,128),('top2-native-defer-stats-roots-adaptive-b4',False,2,4,128)]
 if phase=='performance-v6':plan=[('top2-native-defer-stats-roots-sync-a2',False,2,2,128),('top2-native-defer-stats-roots-async-a2',False,2,2,128),('top2-native-defer-stats-roots-async-b2',False,2,2,128),('top2-native-defer-stats-roots-sync-b2',False,2,2,128),('top2-native-defer-stats-roots-sync-b4',False,2,4,128),('top2-native-defer-stats-roots-async-b4',False,2,4,128)]
rows=[]
for name,eager,top,block,n in plan:
 out=work/name
 env={k:v for k,v in os.environ.items() if not k.startswith('DSV41_')}
 env.update(DYLD_LIBRARY_PATH=str(root/'artifacts/dsv41-miss-resume-mlx-build'),DSV41_RESUME_MODE='guarded',DSV41_RESUME_EAGER=str(int(eager)),DSV41_RESUME_BURST=str(top),DSV41_RESUME_BLOCK=str(block))
 env['DSV41_ASYNC_WINDOW']='1' if 'async' in name else '0'
 env['DSV41_LOCAL_ROOTS']='1' if 'roots' in name else '0'
 env['DSV41_DEFER_ROUTE_STATS']='1' if 'stats' in name else '0'
 env['DSV41_DEFER_COUNTERS']='1' if 'defer' in name else '0'
 env['DSV41_ADAPTIVE_WINDOWS']='1' if 'adaptive' in name else '0'
 env['DSV41_NATIVE_WINDOW']='1' if 'native' in name else '0'
 if phase.startswith('correctness'):env['DSV41_RESUME_STATE_DUMP']=str(out/'states')
 cmd=[sys.executable,str(here/'entry.py'),'--prompt-json',str(prompt),'--decode',str(n),'--prefill-slots','64','--logits-mode','hash','--output',str(out)]
 print('RUN',name,flush=True)
 with (work/(name+'.log')).open('w') as f:subprocess.run(cmd,env=env,cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True)
 d=json.loads((out/'manifest.json').read_text());t=d['step_seconds'][1:]
 refname=('check-natural-old' if top==0 else 'check-old' if top==2 else 'check-top4-old') if phase.startswith('correctness') else f'top{top}-old'
 a=json.loads((work/refname/'manifest.json').read_text())
 checks={k:d[k]==a[k] for k in ['logits_sha256','expert_read_bytes','expert_total_read_bytes']}
 checks.update({k:d['adaptive_l1'][k]==a['adaptive_l1'][k] for k in ['per_layer_counts','promotions','bank_fence_calls']})
 if phase.startswith('correctness'):checks['state_exact']=compare(work/refname/'states',out/'states')['exact']
 row=dict(name=name,tps=n/sum(t),first=t[0],tail_tps=(n-16)/sum(t[16:]) if n>16 else None,peak=d['sampled_physical_footprint_peak_bytes'],checks=checks,controller=d.get('miss_resume',{}).get('stats'))
 rows.append(row);(work/(phase+'-results.json')).write_text(json.dumps(rows,indent=2));print(json.dumps({k:v for k,v in row.items() if k!='controller'}),flush=True)
 if not all(checks.values()):raise RuntimeError('Parity failed: '+name)
