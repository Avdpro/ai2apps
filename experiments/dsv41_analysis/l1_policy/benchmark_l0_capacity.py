"""L0 8/12/16 on identical frozen forward + eviction_dual, with 65GB guard."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
root=Path('artifacts/dsv41-l0-capacity-20260915');root.mkdir(exist_ok=True)
base=Path('artifacts/dsv41-old-l1-transplant-20260915/l1-transplant')
for cap in [8,12,16]:
 dst=root/f'source-{cap}'
 if not dst.exists():
  shutil.copytree(base,dst,symlinks=True,ignore=shutil.ignore_patterns('__pycache__'))
  p=dst/'experiments/dsv41_mlx/run.py';s=p.read_text();assert "'hot_slots':8" in s;s=s.replace("'hot_slots':8",f"'hot_slots':{cap}");p.write_text(s)
  (dst/'experiments/dsv41_mlx/run_l1.py').write_text(f'import run\noriginal=run.Model.__init__\ndef init(self,*a,**kw):\n kw["hot_slots"]={cap}\n original(self,*a,**kw)\n self.l1_policy="eviction_dual"\nrun.Model.__init__=init\nrun.main()\n')
 for p in (base/'experiments/dsv41_mlx').glob('*.py'):
  if p.name not in ['run.py','run_l1.py']:assert p.read_bytes()==(dst/'experiments/dsv41_mlx'/p.name).read_bytes()
(root/'source-hashes.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for cap in [8,12,16] for sub in ['dsv41_mlx','dsv41_reference'] for p in (root/f'source-{cap}'/'experiments'/sub).glob('*.py')},indent=2))
results=[]
for case,steps,caps in [('coding-en-train-18',128,[8,12,16]),('long-math_logic-zh-test',512,[16,12,8])]:
 ref=None
 for cap in caps:
  out=root/f'{case}-l0-{cap}'
  cmd=[sys.executable,str(root/f'source-{cap}'/'experiments/dsv41_mlx/run_l1.py'),'--prompt-json',f'artifacts/dsv41-l1-shape-20260915/dataset/{case}.json','--decode',str(steps),'--prefill-slots','64','--main-slots','40','--decode-dispatch','legacy','--logits-mode','hash','--output',str(out)]
  if not (out/'manifest.json').exists():
   with out.with_suffix('.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
  m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete';assert m['hot_slots']==cap and m['main_capacities']==[40]*40
  assert m['sampled_physical_footprint_peak_bytes']<65e9
  sig=[m[k] for k in ['input_ids','generated_ids','logits_sha256']]
  if ref is None:ref=sig
  else:assert sig==ref,(case,cap,'logits mismatch')
  c=m['cache_stats'];a=m['adaptive_l1'];t=m['step_seconds'];assert a['policy']=='eviction_dual' and a['promotion_reuse']['copied_bytes']==0
  result=dict(case=case,l0=cap,tps=steps/sum(t[1:]),tail_tps=(steps-16)/sum(t[17:]),hit_pct=100*(c['l1_hits']+c['l0_hits'])/c['route_requests'],l1_hits=c['l1_hits'],l0_hits=c['l0_hits'],misses=c['misses'],all_hit_pct=100*c['all_hit_steps']/(40*steps),io_s=sum(a['decode_io_seconds'].values()),requested_gb=m['expert_total_read_bytes']/1e9,peak_gb=m['sampled_physical_footprint_peak_bytes']/1e9,promotions=sum(len(p['pairs']) for p in a['promotions']),readbacks=40*steps+(40*steps-c['all_hit_steps']),fences=a['bank_fence_calls'])
  results.append(result);(root/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps(result),flush=True)
(root/'complete.json').write_text(json.dumps({'runs':len(results),'all_logits_exact':True,'under_65gb':True}))
