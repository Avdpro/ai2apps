import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--full',action='store_true');a=p.parse_args()
root=Path('artifacts/dsv41-l2-predictor-20260915');plan=json.loads((root/'pilot-plan.json').read_text());rows=plan['all_samples'] if a.full else plan['samples'];records=[]
for row in rows:
 out=root/'data'/row['id'];out.parent.mkdir(exist_ok=True)
 ref=Path('artifacts/dsv41-l1-shape-20260915/trace40')/(row['id']+'-r0')/'manifest.json';b=json.loads(ref.read_text());began=time.time()
 if not (out/'verified.json').exists():
  assert not out.exists(),f'Inspect incomplete output before resume: {out}'
  assert hashlib.sha256(Path(row['fixture']).read_bytes()).hexdigest()==row['fixture_sha256']
  cmd=[sys.executable,str(root/'source/experiments/dsv41_mlx/collect_entry.py'),'--prompt-json',row['fixture'],'--decode',str(row['decode_steps']),'--prefill-slots','64','--logits-mode','hash','--output',str(out)]
  env=dict(os.environ,L2_COLLECT_OUTPUT=str(out))
  with out.with_suffix('.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
  m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete'
  for k in ['input_ids','generated_ids','logits_sha256']:assert m[k]==b[k],(row['id'],k)
  with np.load(out/'supervision.npz') as z:
   n=row['decode_steps'];assert z['features'].shape==(n,10240) and z['router_rank'].shape==(n,35,384) and z['top6'].shape==(n,35,6)
   assert z['token_ids'].tolist()==m['generated_ids'][:-1]
   with np.load(ref.parent/'routes.npz') as old:assert np.array_equal(z['top6'],old['decode'][:,5:,0,:])
   assert np.isfinite(z['features']).all() and np.isfinite(z['router_rank']).all()
  receipt=dict(id=row['id'],split=row['split'],family_id=row['family_id'],steps=n,wall_seconds=time.time()-began,bytes=(out/'supervision.npz').stat().st_size,peak_bytes=m['sampled_physical_footprint_peak_bytes'],exact_logits=True)
  (out/'verified.json').write_text(json.dumps(receipt,indent=2))
 records.append(json.loads((out/'verified.json').read_text()));(root/('collection-full.json' if a.full else 'collection-pilot.json')).write_text(json.dumps(records,indent=2));print(json.dumps(records[-1]),flush=True)
