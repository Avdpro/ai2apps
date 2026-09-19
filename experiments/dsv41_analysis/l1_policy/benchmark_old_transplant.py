"""Frozen pre-L1 source versus L1-only transplant; no live runtime edits."""
import ast,hashlib,json,shutil,subprocess,sys
from pathlib import Path
root=Path('artifacts/dsv41-old-l1-transplant-20260915');root.mkdir(exist_ok=True)
old=Path('artifacts/dsv41-historical-tps-check-20260915/pre-l1-source')
new=root/'l1-transplant'
if not new.exists():
 shutil.copytree(old,new,symlinks=True,ignore=shutil.ignore_patterns('__pycache__'))
 for f in ['experiments/dsv41_mlx/adaptive.py','experiments/dsv41_reference/metal_bank.py','experiments/dsv41_reference/lru_metal_bank.py']:
  shutil.copy2(f,new/f)
 p=new/'experiments/dsv41_mlx/model.py';s=p.read_text();current=Path('experiments/dsv41_mlx/model.py').read_text()
 cls=next(n for n in ast.parse(current).body if isinstance(n,ast.ClassDef) and n.name=='Model')
 methods=[]
 for n in cls.body:
  if isinstance(n,ast.FunctionDef) and n.name in ['refresh_slot_roles','route_cache_counts','miss_metadata','prepare_miss']:
   methods.append('\n'.join(current.splitlines()[n.lineno-1:n.end_lineno]))
 s=s.replace('        self.lookups={};','        self.main_slot_masks={};self.lookups={};',1)
 s=s.replace('    def moe(self,l,x,start):','\n'.join(methods)+'\n    def moe(self,l,x,start):',1)
 # Replace only the original counter assignment, not the transplanted helper.
 s=s.replace('self.cache_counters[l]=self.cache_counters[l]+mx.stack([mx.sum((mapped>=0)&(mapped<self.main_capacities[l])),mx.sum(mapped>=self.main_capacities[l]),mx.sum(mapped<0)]).astype(mx.uint32)','self.cache_counters[l]=self.cache_counters[l]+self.route_cache_counts(l,mapped)')
 s=s.replace('host=ids[0].tolist();ages=self.ages[l].tolist()','host,ages,promotion_scores=self.miss_metadata(l,ids[0])')
 s=s.replace('slots=bank.prepare(host);self.stats','slots=self.prepare_miss(l,bank,host,promotion_scores);self.stats')
 p.write_text(s)
 (new/'experiments/dsv41_mlx/run_l1.py').write_text('import run\noriginal=run.Model.__init__\ndef init(self,*a,**kw):\n original(self,*a,**kw)\n self.l1_policy="eviction_dual"\nrun.Model.__init__=init\nrun.main()\n')
# Verify every non-cache runtime module still exactly matches frozen source.
changed={'model.py','adaptive.py'}
for p in (old/'experiments/dsv41_mlx').glob('*.py'):
 if p.name not in changed:assert p.read_bytes()==(new/'experiments/dsv41_mlx'/p.name).read_bytes(),p.name
(root/'source-hashes.json').write_text(json.dumps({str(p.relative_to(new)):hashlib.sha256(p.read_bytes()).hexdigest() for sub in ['dsv41_mlx','dsv41_reference'] for p in (new/'experiments'/sub).glob('*.py')},indent=2))
data=json.loads(Path('artifacts/dsv41-l1-shape-20260915/dataset/dataset-manifest.json').read_text());coding=next(r for r in data['samples'] if r['id']=='coding-en-train-18')
results=[]
for case,fixture,order in [('science','experiments/dsv41_analysis/fixtures/prefill2048.json',['old','transplant']),('coding',coding['fixture'],['transplant','old'])]:
 ref=None
 for variant in order:
  out=root/f'{case}-{variant}';runner=old/'experiments/dsv41_mlx/run.py' if variant=='old' else new/'experiments/dsv41_mlx/run_l1.py'
  cmd=[sys.executable,str(runner),'--prompt-json',fixture,'--decode','128','--prefill-slots','64','--main-slots','40','--decode-dispatch','legacy','--logits-mode','hash','--output',str(out)]
  if not (out/'manifest.json').exists():
   with out.with_suffix('.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
  m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete'
  sig=[m[k] for k in ['input_ids','generated_ids','logits_sha256']]
  if ref is None:ref=sig
  else:assert sig==ref
  c=m['cache_stats'];a=m['adaptive_l1'];t=m['step_seconds']
  r=dict(case=case,variant=variant,tps=128/sum(t[1:]),tail112_tps=112/sum(t[17:]),hit_pct=100*(c['l1_hits']+c['l0_hits'])/c['route_requests'],misses=c['misses'],io_s=sum(a['decode_io_seconds'].values()),peak_gb=m['sampled_physical_footprint_peak_bytes']/1e9)
  results.append(r);(root/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps(r),flush=True)
(root/'complete.json').write_text(json.dumps({'runs':4,'exact_logits':True,'old_forward_runner_preserved':True}))
