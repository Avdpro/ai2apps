import subprocess,sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[2]
cases=[('control',['--prefill-hot-reread'],False),('repeat',[],False),('profile',[],True)]
for name,flags,profile in cases:
 entry='experiments/dsv41_analysis/profile_prefill.py' if profile else 'experiments/dsv41_analysis/run_prefill_probe.py'
 cmd=[sys.executable,entry,'--prompt-json','experiments/dsv41_analysis/fixtures/prefill2048.json','--decode','0' if profile else '32','--prefill-slots','64','--output',f'artifacts/dsv41-hot-direct-{name}-20260913']+flags
 if not profile:cmd+=['--reference','artifacts/dsv41-default-dynamic128-20260913']
 with open('/tmp/dsv41-hot-direct-'+name+'.log','w') as log:subprocess.run(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
 m=json.loads((root/f'artifacts/dsv41-hot-direct-{name}-20260913/manifest.json').read_text());assert m['status']=='complete'
 print(name,'prefill',2048/m['step_seconds'][0],'peak',m['sampled_physical_footprint_peak_bytes']/1e9,flush=True)
