import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];rows=[]
def launch(label,args,reference=None):
 out=ROOT/('artifacts/dsv41-tail-'+label+'-20260913')
 entry='run_tail_probe.py' if reference else None
 cmd=[sys.executable,str(ROOT/('experiments/dsv41_analysis/'+entry if entry else 'experiments/dsv41_mlx/run.py')),*args,'--output',str(out)]
 if reference:cmd+=['--reference',str(reference)]
 with Path('/tmp/dsv41-tail-'+label+'.log').open('w') as log:subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
 m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete';n=len(m['step_seconds'])-1
 row=dict(label=label,tps=n/sum(m['step_seconds'][1:]),peak_gb=m['sampled_physical_footprint_peak_bytes']/1e9,replacements=sum(m.get('burst',{}).get('tail_replacements',[])),output=str(out));rows.append(row);print(json.dumps(row),flush=True);return out
for policy in ['zero','fixed-top','renorm']:
 launch('128-'+policy,['--burst-top','2','--burst-tail',policy,'--prompt-json',str(ROOT/'artifacts/dsv41-benchmark2048-prompt.json'),'--decode','128'])
for label,prompt in [('code','```python\ndef binary_search(items, target):\n    '),('zh','人工智能模型中的过拟合是指')]:
 args=['--prompt',prompt,'--decode','32'];ref=launch(label+'-exact',args)
 for policy in ['zero','fixed-top','renorm']:launch(label+'-'+policy,[*args,'--burst-top','2','--burst-tail',policy],ref)
(ROOT/'artifacts/dsv41-tail-matrix-20260913.json').write_text(json.dumps(rows,indent=2))
