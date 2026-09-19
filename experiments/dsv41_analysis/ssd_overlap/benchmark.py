import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
root=Path('artifacts/dsv41-ssd-overlap-20260915');root.mkdir(exist_ok=True);src=root/'source'
if not src.exists():
 for sub in ['dsv41_mlx','dsv41_reference']:shutil.copytree(Path('experiments')/sub,src/'experiments'/sub,ignore=shutil.ignore_patterns('__pycache__'))
 (src/'artifacts').symlink_to(Path('artifacts').resolve(),target_is_directory=True)
 shutil.copy2('experiments/dsv41_analysis/ssd_overlap/entry.py',src/'experiments/dsv41_mlx/overlap_entry.py')
(root/'source-hashes.json').write_text(json.dumps({str(p.relative_to(src)):hashlib.sha256(p.read_bytes()).hexdigest() for p in src.rglob('*.py')},indent=2))
rows=[];reference=None;plans={}
for name,mode,count in [('baseline1','baseline',0),('serial16','serial',16),('overlap16','overlap',16),('overlap48','overlap',48),('serial48','serial',48),('baseline2','baseline',0)]:
 out=root/name
 if not (out/'manifest.json').exists():
  cmd=[sys.executable,str(src/'experiments/dsv41_mlx/overlap_entry.py'),'--prompt-json','artifacts/dsv41-l1-shape-20260915/dataset/coding-en-train-18.json','--decode','64','--prefill-slots','64','--logits-mode','hash','--output',str(out)]
  env=dict(os.environ,OVERLAP_MODE=mode,OVERLAP_COUNT=str(count),OVERLAP_OUTPUT=str(out))
  with out.with_suffix('.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
 m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete';assert m['sampled_physical_footprint_peak_bytes']<65e9
 sig=[m[k] for k in ['input_ids','generated_ids','logits_sha256','cache_stats']]
 if reference is None:reference=sig
 else:assert sig==reference,name
 o=json.loads((out/'overlap.json').read_text());events=o['events'];assert len(events)==64
 if count:
  requests=[e['io']['requests'] for e in events]
  if count in plans:assert plans[count]==requests
  else:plans[count]=requests
 # Report both full decode and later64-8 steps, without concealing startup.
 def summary(es):
  compute=sum(e['compute_end']-e['begin'] for e in es);wall=sum(e['end']-e['begin'] for e in es);io=sum(e['io']['end']-e['io']['begin'] for e in es);overlap=sum(max(0,min(e['compute_end'],e['io']['end'])-max(e['begin'],e['io']['begin'])) for e in es)
  return dict(compute_s=compute,total_s=wall,io_s=io,io_window_overlap_s=overlap,wait_after_compute_s=wall-compute,aux_gb=sum(e['io']['bytes'] for e in es)/1e9)
 row=dict(name=name,tps=64/sum(m['step_seconds'][1:]),peak_gb=m['sampled_physical_footprint_peak_bytes']/1e9,all=summary(events),tail56=summary(events[8:]));rows.append(row);(root/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
(root/'complete.json').write_text(json.dumps({'runs':6,'exact_logits_and_routes':True,'same_random_reads':True,'all_under_65gb':True}))
