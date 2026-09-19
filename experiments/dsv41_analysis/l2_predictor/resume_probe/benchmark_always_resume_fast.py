"""Strict continuation acceptance: never admits or falls back to packet."""
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
import numpy as np
import struct
def load_file(path):
 raw=Path(path).read_bytes();n=struct.unpack('<Q',raw[:8])[0];header=json.loads(raw[8:8+n]);data=raw[8+n:]
 return {k:(v['dtype'],v['shape'],data[v['data_offsets'][0]:v['data_offsets'][1]]) for k,v in header.items() if k!='__metadata__'}
root=Path('artifacts/dsv41-l2-always-resume-fast-v1-20260917')
root.mkdir(exist_ok=True)
here=Path(__file__).parent
if not (root/'source').exists():shutil.copytree(here,root/'source/resume_probe',ignore=shutil.ignore_patterns('__pycache__'))
gold=json.loads(Path('artifacts/dsv41-l2-prefetch-policy-20260916/6-baseline-zero/manifest.json').read_text())
(root/'tokens.json').write_text(json.dumps(gold['generated_ids']))
cases=[]
for mode,block in [('packet',2),('resume',2),('resume',4)]:cases.append(dict(name=f'audit-{mode}-{block}',mode=mode,block=block,n=4,stress=False,top=0,predictor='none',audit=True))
for stress,n in [(False,32),(True,16)]:
 for i,mode in enumerate(['packet','resume','resume','packet']):cases.append(dict(name=f'{"stress" if stress else "normal"}-{i}-{mode}',mode=mode,block=2,n=n,stress=stress,top=0,predictor='none',audit=False))
for top in (2,4):
 for mode in ('packet','resume'):cases.append(dict(name=f'burst{top}-{mode}',mode=mode,block=2,n=32,stress=False,top=top,predictor='none',audit=False))
for pred in ('state','lookahead','block6'):cases.append(dict(name=f'l2-{pred}',mode='resume',block=2,n=8,stress=False,top=0,predictor=pred,audit=False))
sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'source/resume_probe').glob('*') if p.is_file()}
sources.update({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('artifacts/dsv41-l2-fast-resume-native-build').glob('*.so')})
sources['artifacts/dsv41-resume-fast-mlx-build/libmlx.dylib']=hashlib.sha256(Path('artifacts/dsv41-resume-fast-mlx-build/libmlx.dylib').read_bytes()).hexdigest()
(root/'plan.json').write_text(json.dumps(dict(cases=cases,sources=sources),indent=2))
results={}
try:
 for i,c in enumerate(cases):
  for p,h in sources.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
  (root/'status.json').write_text(json.dumps(dict(phase='running',case=c['name'],index=i,total=len(cases),pid=os.getpid())))
  env={k:v for k,v in os.environ.items() if not k.startswith(('L2_','DSV41_'))}
  env.update(DYLD_LIBRARY_PATH=str(Path('artifacts/dsv41-resume-fast-mlx-build').resolve()),L2_NATIVE_BUILD='artifacts/dsv41-l2-fast-resume-native-build',L2_WINDOW_EXECUTOR=c['mode'],L2_WINDOW_BLOCK=str(c['block']),L2_WINDOW_PREDICTOR=c['predictor'],L2_MIN_LEAD_LAYERS='1',L2_AUDIT_GPU=str(int(c['audit'] and c['mode']=='resume')),L2_AUDIT_STATE=str(int(c['audit'])),DSV41_RESUME_STRESS_ALL_MISS=str(int(c['stress'])))
  out=root/c['name'];cmd=[sys.executable,str(root/'source/resume_probe/entry.py'),'--output',str(out),'--prompt',gold['prompt'],'--decode',str(c['n']),'--prefill-slots','64','--logits-mode','hash','--inference-mode','legacy','--expert-no-cache','--force-input-tokens',str(root/'tokens.json')]
  if c['top']:cmd+=['--burst-top',str(c['top'])]
  if not (out/'manifest.json').exists():
   with (root/(c['name']+'.log')).open('w') as log:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
  m=json.loads((out/'manifest.json').read_text());d=json.loads((out/'l2-window.json').read_text());s=d['stats']
  assert m['status']=='complete' and m['sampled_physical_footprint_peak_bytes']<65e9
  if not c['top']:assert m['logits_sha256']==gold['logits_sha256'][:c['n']+1],c['name']
  elif c['mode']=='resume':assert m['logits_sha256']==json.loads((root/f"burst{c['top']}-packet/manifest.json").read_text())['logits_sha256']
  assert s['completed_layers']==40*c['n']
  if c['mode']=='resume':
   assert s['packet_checks']==s['packet_tokens']==s['native_tail_tokens']==0
   assert s['gpu_router_visits']==40*c['n']
  if c['stress']:assert s['misses']==40*c['n']
  if c['audit'] and c['mode']=='resume':
   assert s['gpu_layer_starts']==s['gpu_moe_completions']==40*c['n']
   ref=root/'audit-packet-2'
   for p in out.glob('state-*.safetensors'):
    a=load_file(str(p));b=load_file(str(ref/p.name));assert set(a)==set(b)
    assert all(v==b[k] for k,v in a.items()),p
   for p in out.glob('state-*.json'):assert json.loads(p.read_text())==json.loads((ref/p.name).read_text()),p
  assert all(t['reads']<=64 for t in d['tokens'])
  assert all(t['submissions']+t['notices']<=41 for t in d['history'])
  times=m['step_seconds'][1:]
  results[c['name']]=dict(**c,tps=len(times)/sum(times),after4_tps=len(times[4:])/sum(times[4:]) if len(times)>4 else None,stats=s,peak_GB=m['sampled_physical_footprint_peak_bytes']/1e9,expert_read_bytes=m['expert_read_bytes'],l2_used=sum(t['used'] for t in d['tokens']))
  (root/'report.json').write_text(json.dumps(results,indent=2))
 (root/'status.json').write_text(json.dumps(dict(phase='complete')))
except BaseException as e:
 (root/'status.json').write_text(json.dumps(dict(phase='failed',error=str(e))));raise
