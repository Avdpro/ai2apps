"""Four-way old-source capacity/policy factorial, fixed historical growth shape."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
root=Path('artifacts/dsv41-growth-transplant-20260915');root.mkdir(exist_ok=True)
sources={'old':Path('artifacts/dsv41-historical-tps-check-20260915/pre-l1-source'),'new':Path('artifacts/dsv41-old-l1-transplant-20260915/l1-transplant')}
current=Path('experiments/dsv41_mlx/model.py').read_text()
begin=current.index('        if main_shape is not None:\n');end=current.index('        manifest=json.loads',begin)
for name,src in sources.items():
 dst=root/(name+'-source')
 if not dst.exists():
  shutil.copytree(src,dst,symlinks=True,ignore=shutil.ignore_patterns('__pycache__'))
  shutil.copy2('experiments/dsv41_mlx/l1_shape.py',dst/'experiments/dsv41_mlx/l1_shape.py')
  p=dst/'experiments/dsv41_mlx/model.py';s=p.read_text();a=s.index('        if main_shape is not None and (');b=s.index('        manifest=json.loads',a);s=s[:a]+current[begin:end]+s[b:];p.write_text(s)
 # Only capacity validation and shape-file validation differ from respective base.
 for p in (src/'experiments/dsv41_mlx').glob('*.py'):
  if p.name not in ['model.py','l1_shape.py']:assert p.read_bytes()==(dst/'experiments/dsv41_mlx'/p.name).read_bytes()
(root/'source-hashes.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for name in sources for sub in ['dsv41_mlx','dsv41_reference'] for p in (root/(name+'-source')/'experiments'/sub).glob('*.py')},indent=2))
shape='artifacts/dsv41-l1-growth-20260915/growth.json'
caps=json.loads(Path(shape).read_text())['capacities'];assert [i for i,c in enumerate(caps) if c==48]==[0,3,4,13,15,19,23,39]
data=json.loads(Path('artifacts/dsv41-l1-shape-20260915/dataset/dataset-manifest.json').read_text());data={r['id']:r for r in data['samples']}
results=[]
variants=['old40','new40','old48','new48']
for case,order in [('coding-en-train-18',variants),('long-math_logic-zh-test',list(reversed(variants)))]:
 row=data[case];signature=None
 for variant in order:
  new=variant.startswith('new');growth=variant.endswith('48');dst=root/('new-source' if new else 'old-source');out=root/f'{case}-{variant}'
  runner=dst/'experiments/dsv41_mlx'/('run_l1.py' if new else 'run.py')
  cmd=[sys.executable,str(runner),'--prompt-json',row['fixture'],'--decode',str(row['decode_steps']),'--prefill-slots','64','--decode-dispatch','legacy','--logits-mode','hash','--output',str(out)]+(['--l1-shape',shape] if growth else ['--main-slots','40'])
  if not (out/'manifest.json').exists():
   with out.with_suffix('.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
  m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete';assert m['sampled_physical_footprint_peak_bytes']<65e9
  assert m['main_capacities']==(caps if growth else [40]*40)
  sig=[m[k] for k in ['input_ids','generated_ids','logits_sha256']]
  if signature is None:signature=sig
  else:assert sig==signature,(case,variant)
  c=m['cache_stats'];a=m['adaptive_l1'];t=m['step_seconds'];steps=len(t)-1
  if new:assert a['policy']=='eviction_dual' and a['promotion_reuse']['copied_bytes']==0
  # Cache readback API count derived from observed misses and actual call sites.
  miss_steps=40*steps-c['all_hit_steps'];readbacks=40*steps+(1 if new else 2)*miss_steps+(0 if new else ((steps-1)//16)*40)
  result=dict(case=case,variant=variant,tps=steps/sum(t[1:]),tail_tps=(steps-16)/sum(t[17:]),prefill_tps=len(m['input_ids'])/t[0],hit_pct=100*(c['l1_hits']+c['l0_hits'])/c['route_requests'],misses=c['misses'],io_s=sum(a['decode_io_seconds'].values()),requested_gb=m['expert_total_read_bytes']/1e9,peak_gb=m['sampled_physical_footprint_peak_bytes']/1e9,readback_calls=readbacks)
  results.append(result);(root/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps(result),flush=True)
(root/'complete.json').write_text(json.dumps({'runs':len(results),'all_logits_exact':True,'fixed_growth_layers':[0,3,4,13,15,19,23,39]}))
