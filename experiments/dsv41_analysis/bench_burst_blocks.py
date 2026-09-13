"""Sequential GPU benchmark matrix; fixed 2048-token input and 128 Decode steps."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
rows=[]
for top,block in [(2,1),(2,4),(2,2),(4,2),(4,4),(4,1)]:
    out=ROOT/f'artifacts/dsv41-burst128-t{top}-b{block}-20260913'
    cmd=[sys.executable,str(ROOT/'experiments/dsv41_mlx/run.py'),'--burst-top',str(top),'--block-layers',str(block),'--prompt-json',str(ROOT/'artifacts/dsv41-benchmark2048-prompt.json'),'--decode','128','--output',str(out)]
    with Path(f'/tmp/dsv41-burst128-t{top}-b{block}.log').open('w') as log:subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete'
    stat=m['burst']['statistics'];row=dict(top=top,block=block,tps=128/sum(m['step_seconds'][1:]),peak_gb=m['sampled_physical_footprint_peak_bytes']/1e9,rollbacks=stat['rollbacks'],blocks=stat['blocks'],checks=stat['checks'],discarded=stat['discarded_layers'],output=str(out))
    rows.append(row);print(json.dumps(row),flush=True)
Path(ROOT/'artifacts/dsv41-burst128-matrix-20260913.json').write_text(json.dumps(rows,indent=2))
