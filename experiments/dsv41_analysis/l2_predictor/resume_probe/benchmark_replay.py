"""Fixed-input replay/packet comparisons. No packet fallback in the candidate."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--decode',type=int,default=2);p.add_argument('--packet',action='store_true');p.add_argument('--stress',action='store_true');p.add_argument('--audit',action='store_true');p.add_argument('--sync-build',action='store_true');a=p.parse_args()
root=Path('artifacts/dsv41-resume-replay-20260917');root.mkdir(exist_ok=True)
g=json.loads(Path('artifacts/dsv41-l2-prefetch-policy-20260916/6-baseline-zero/manifest.json').read_text());(root/'tokens.json').write_text(json.dumps(g['generated_ids']))
env={k:v for k,v in os.environ.items() if not k.startswith(('L2_','DSV41_'))}
env.update(DYLD_LIBRARY_PATH=str(Path('artifacts/dsv41-resume-replay-mlx-build').resolve()),L2_NATIVE_BUILD='artifacts/dsv41-l2-replay-resume-native-build',L2_WINDOW_EXECUTOR='packet' if a.packet else 'resume',L2_CAPTURE_REPLAY='0' if a.packet else '1',L2_WINDOW_BLOCK='40',L2_WINDOW_PREDICTOR='none',L2_AUDIT_GPU=str(int(a.audit and not a.packet)),L2_AUDIT_STATE=str(int(a.audit)),DSV41_RESUME_STRESS_ALL_MISS=str(int(a.stress)))
if a.sync_build:env['DSV41_ASYNC_WINDOW']='0'
out=root/a.name
cmd=[sys.executable,str(Path(__file__).with_name('entry.py')),'--output',str(out),'--prompt',g['prompt'],'--decode',str(a.decode),'--prefill-slots','64','--logits-mode','hash','--inference-mode','legacy','--expert-no-cache','--force-input-tokens',str(root/'tokens.json')]
(root/(a.name+'-command.json')).write_text(json.dumps(dict(command=cmd,env={k:v for k,v in env.items() if k.startswith(('L2_','DSV41_','DYLD_'))}),indent=2))
with (root/(a.name+'.log')).open('w') as log:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
m=json.loads((out/'manifest.json').read_text());s=json.loads((out/'l2-window.json').read_text())['stats']
r=dict(tps=a.decode/sum(m['step_seconds'][1:]),exact=m['logits_sha256']==g['logits_sha256'][:a.decode+1],stats=s,peak_GB=m['sampled_physical_footprint_peak_bytes']/1e9)
(root/(a.name+'-result.json')).write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2),flush=True)
assert r['exact']
assert r['peak_GB']<65
if not a.packet:
 assert s['packet_checks']==s['packet_tokens']==s['native_tail_tokens']==0
 assert s['constructed_layers']==s['gpu_router_visits']==a.decode*40
 assert s['submissions']==s['misses']+a.decode
if a.stress:assert s['misses']==a.decode*40
