import json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
for name,shared,label in [('control',False,'128'),('repeat',True,'128'),('code',True,'code')]:
 ref=root/('artifacts/dsv41-default-dynamic128-20260913' if label=='128' else 'artifacts/dsv41-tail-code-exact-20260913')
 cmd=[sys.executable,'experiments/dsv41_analysis/run_prefill_probe.py','--reference',str(ref),'--decode','32','--prefill-slots','64','--output',f'artifacts/dsv41-dispatch-{name}-20260913']
 if label=='128':cmd+=['--prompt-json','artifacts/dsv41-benchmark2048-prompt.json']
 else:cmd+=['--prompt',json.loads((ref/'manifest.json').read_text())['prompt']]
 if shared:cmd+=['--shared-dispatch']
 with open('/tmp/dsv41-dispatch-'+name+'.log','w') as log:subprocess.run(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
 print(name,'complete',flush=True)
