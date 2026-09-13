import json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
for name,fused,label in [('control',False,'128'),('fused',True,'128'),('repeat',True,'128'),('code',True,'code')]:
 ref=root/('artifacts/dsv41-default-dynamic128-20260913' if label=='128' else 'artifacts/dsv41-tail-code-exact-20260913')
 cmd=[sys.executable,'experiments/dsv41_analysis/run_prefill_probe.py','--reference',str(ref),'--decode','32','--prefill-slots','64','--shared-dispatch','--output',f'artifacts/dsv41-fused-{name}-20260913']
 if label=='128':cmd+=['--prompt-json','artifacts/dsv41-benchmark2048-prompt.json']
 else:cmd+=['--prompt',json.loads((ref/'manifest.json').read_text())['prompt']]
 if fused:cmd+=['--fused-gate-up']
 with open('/tmp/dsv41-fused-'+name+'.log','w') as log:subprocess.run(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
 m=json.loads((root/f'artifacts/dsv41-fused-{name}-20260913/manifest.json').read_text());assert m['status']=='complete'
 print(name,len(m['input_ids'])/m['step_seconds'][0],m['sampled_physical_footprint_peak_bytes']/1e9,flush=True)
