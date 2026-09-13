import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
cases=[('baseline',0,None,'128'),('32-exact',32,None,'128'),('96-exact',96,None,'128'),('64-top4',64,4,'128'),('64-top2',64,2,'128')]
cases += [(f'64-{name}-{label}',64,top,label) for label in ['code','zh'] for name,top in [('exact',None),('top4',4),('top2',2)]]
rows=[]
for name,slots,top,label in cases:
 out=ROOT/f'artifacts/dsv41-prefill-{name}-20260913'
 cmd=[sys.executable,str(ROOT/'experiments/dsv41_analysis/run_prefill_probe.py'),'--prefill-slots',str(slots),'--output',str(out),'--decode','8' if label=='128' else '32']
 ref=ROOT/('artifacts/dsv41-default-dynamic128-20260913' if label=='128' else f'artifacts/dsv41-tail-{label}-exact-20260913');cmd+=['--reference',str(ref)]
 if label=='128':cmd+=['--prompt-json',str(ROOT/'artifacts/dsv41-benchmark2048-prompt.json')]
 else:cmd+=['--prompt',json.loads((ref/'manifest.json').read_text())['prompt']]
 if top:cmd+=['--prefill-top',str(top)]
 with Path(f'/tmp/dsv41-prefill-{name}.log').open('w') as log:subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
 m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete'
 row=dict(name=name,tps=len(m['input_ids'])/m['step_seconds'][0],peak_gb=m['sampled_physical_footprint_peak_bytes']/1e9,output=str(out));rows.append(row);print(json.dumps(row),flush=True)
(ROOT/'artifacts/dsv41-prefill-matrix-20260913.json').write_text(json.dumps(rows,indent=2))
