import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];rows=[]
cases=[('128-zero-control','zero',None,None),('128-zero-renorm','zero-renorm',None,None),('code-zero-renorm','zero-renorm','```python\ndef binary_search(items, target):\n    ','code'),('zh-zero-renorm','zero-renorm','人工智能模型中的过拟合是指','zh')]
for label,policy,prompt,ref in cases:
 out=ROOT/f'artifacts/dsv41-tail-{label}-20260913'
 entry='experiments/dsv41_analysis/run_tail_probe.py' if ref else 'experiments/dsv41_mlx/run.py'
 cmd=[sys.executable,str(ROOT/entry),'--burst-top','2','--burst-tail',policy,'--output',str(out)]
 if ref:cmd+=['--prompt',prompt,'--decode','32','--reference',str(ROOT/f'artifacts/dsv41-tail-{ref}-exact-20260913')]
 else:cmd+=['--prompt-json',str(ROOT/'artifacts/dsv41-benchmark2048-prompt.json'),'--decode','128']
 with Path('/tmp/dsv41-tail-'+label+'.log').open('w') as log:subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
 m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete'
 row=dict(label=label,tps=m['decode_forwards']/sum(m['step_seconds'][1:]),peak_gb=m['sampled_physical_footprint_peak_bytes']/1e9,replacements=sum(m['burst']['tail_replacements']),output=str(out));rows.append(row);print(json.dumps(row),flush=True)
(ROOT/'artifacts/dsv41-retained-renorm-matrix-20260913.json').write_text(json.dumps(rows,indent=2))
