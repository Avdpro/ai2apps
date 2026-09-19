import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
root=Path('artifacts/dsv41-oracle-prefetch-20260915');root.mkdir(exist_ok=True);src=root/'source'
if not src.exists():
 for sub in ['dsv41_mlx','dsv41_reference']:shutil.copytree(Path('experiments')/sub,src/'experiments'/sub,ignore=shutil.ignore_patterns('__pycache__'))
 (src/'artifacts').symlink_to(Path('artifacts').resolve(),target_is_directory=True)
 shutil.copy2('experiments/dsv41_analysis/oracle_prefetch/entry.py',src/'experiments/dsv41_mlx/oracle_entry.py')
(root/'source-hashes.json').write_text(json.dumps({str(p.relative_to(src)):hashlib.sha256(p.read_bytes()).hexdigest() for p in src.rglob('*.py')},indent=2))
results=[]
for case,steps in [('coding-en-train-18',128),('long-math_logic-zh-test',512)]:
 reference=None
 order=['baseline1','oracle2','oracle4','baseline2'] if steps==128 else ['baseline1','oracle4','oracle2','baseline2']
 for name in order:
  out=root/f'{case}-{name}';mode='baseline' if name.startswith('baseline') else 'oracle';plan=root/f'{case}-baseline1/oracle-plan.json'
  cmd=[sys.executable,str(src/'experiments/dsv41_mlx/oracle_entry.py'),'--prompt-json',f'artifacts/dsv41-l1-shape-20260915/dataset/{case}.json','--decode',str(steps),'--prefill-slots','64','--logits-mode','hash','--output',str(out)]
  if not (out/'manifest.json').exists():
   env=dict(os.environ,ORACLE_MODE=mode,ORACLE_BATCH=name[-1],ORACLE_PLAN=str(plan),ORACLE_OUTPUT=str(out))
   with out.with_suffix('.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
  m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete';assert m['sampled_physical_footprint_peak_bytes']<65e9
  stat=json.loads((out/'oracle-stats.json').read_text());signature=[m[k] for k in ['input_ids','generated_ids','logits_sha256','cache_stats']]+[json.loads((out/'oracle-plan.json').read_text()),stat['total_native_bytes'],stat['bank_fences']]
  if reference is None:reference=signature
  else:assert signature==reference,(case,name,'parity')
  ev=stat['events'];fulfilled=stat['fulfilled'];t=m['step_seconds']
  r=dict(case=case,mode=name,tps=steps/sum(t[1:]),tail_tps=(steps-16)/sum(t[17:]),peak_gb=m['sampled_physical_footprint_peak_bytes']/1e9,background_experts=sum(e['experts'] for e in ev if e['background']),foreground_experts=sum(e['experts'] for e in ev if not e['background']),ready_layers=sum(e['ready'] for e in fulfilled),miss_layers=len(fulfilled),foreground_service_s=sum(e['wait_s'] for e in fulfilled),background_io_s=sum(e['seconds'] for e in ev if e['background']),native_calls=stat['native_calls'],native_gb=stat['total_native_bytes']/1e9)
  results.append(r);(root/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps(r),flush=True)
(root/'complete.json').write_text(json.dumps({'runs':8,'exact_logits_routes_destinations':True,'same_read_bytes_and_fences':True}))
