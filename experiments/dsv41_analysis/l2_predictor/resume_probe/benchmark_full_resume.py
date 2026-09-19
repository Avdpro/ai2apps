"""Full 40-layer continuation semantics; diagnostic, no packet fallback."""
import os,json,subprocess,sys,struct
from pathlib import Path
r=Path('artifacts/dsv41-l2-always-resume-fast-v1-20260917')
g=json.loads(Path('artifacts/dsv41-l2-prefetch-policy-20260916/6-baseline-zero/manifest.json').read_text())
def tensors(p):
 raw=p.read_bytes();n=struct.unpack('<Q',raw[:8])[0];h=json.loads(raw[8:8+n]);b=raw[8+n:]
 return {k:(v['dtype'],v['shape'],b[v['data_offsets'][0]:v['data_offsets'][1]]) for k,v in h.items() if k!='__metadata__'}
results={}
for stress,n in [(False,4),(True,2)]:
 name='full40-stress' if stress else 'full40-normal'
 out=r/name
 env={k:v for k,v in os.environ.items() if not k.startswith(('L2_','DSV41_'))}
 env.update(DYLD_LIBRARY_PATH=str(Path('artifacts/dsv41-resume-fast-mlx-build').resolve()),L2_NATIVE_BUILD='artifacts/dsv41-l2-fast-resume-native-build',L2_WINDOW_EXECUTOR='resume',L2_WINDOW_BLOCK='40',L2_WINDOW_PREDICTOR='none',L2_AUDIT_GPU='1',L2_AUDIT_STATE='1',DSV41_RESUME_STRESS_ALL_MISS=str(int(stress)))
 cmd=[sys.executable,str(r/'source/resume_probe/entry.py'),'--output',str(out),'--prompt',g['prompt'],'--decode',str(n),'--prefill-slots','64','--logits-mode','hash','--inference-mode','legacy','--expert-no-cache','--force-input-tokens',str(r/'tokens.json')]
 with (r/(name+'.log')).open('w') as log:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
 m=json.loads((out/'manifest.json').read_text());d=json.loads((out/'l2-window.json').read_text());s=d['stats']
 assert m['status']=='complete' and m['logits_sha256']==g['logits_sha256'][:n+1]
 assert s['gpu_router_visits']==s['gpu_layer_starts']==s['gpu_moe_completions']==40*n
 assert s['packet_checks']==s['packet_tokens']==s['native_tail_tokens']==0
 assert s['submissions']==s['misses']+n
 assert m['sampled_physical_footprint_peak_bytes']<65e9
 if stress:assert s['misses']==40*n
 for p in out.glob('state-*.safetensors'):
  a=tensors(p);b=tensors(r/'audit-packet-2'/p.name)
  keys=[k for k in a if k.startswith(('states.','shared.','engram_hash.'))] if stress else list(a)
  assert all(a[k]==b[k] for k in keys),p
 results[name]=dict(decode=n,stats=s,peak_GB=m['sampled_physical_footprint_peak_bytes']/1e9,tps=n/sum(m['step_seconds'][1:]),diagnostic_markers=True,exact=True)
 (r/'full40-report.json').write_text(json.dumps(results,indent=2))
