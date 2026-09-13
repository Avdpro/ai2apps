import subprocess,sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[2]
for name,flags in [('repeat-base',['--prefill-slots','0']),('repeat64',['--prefill-slots','64']),('repeat-top2',['--prefill-slots','64','--prefill-top','2']),('both-top2',['--prefill-slots','64','--prefill-top','2','--burst-top','2'])]:
 cmd=[sys.executable,'experiments/dsv41_analysis/run_prefill_probe.py','--reference','artifacts/dsv41-default-dynamic128-20260913','--prompt-json','artifacts/dsv41-benchmark2048-prompt.json','--decode','32','--output',f'artifacts/dsv41-prefill-{name}-20260913']+flags
 with Path('/tmp/dsv41-prefill-'+name+'.log').open('w') as log:subprocess.run(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
 m=json.loads((root/f'artifacts/dsv41-prefill-{name}-20260913/manifest.json').read_text());assert m['status']=='complete'
 print(name,'prefill',2048/m['step_seconds'][0],'decode',32/sum(m['step_seconds'][1:]),'peak',m['sampled_physical_footprint_peak_bytes']/1e9,flush=True)
