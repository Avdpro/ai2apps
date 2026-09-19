"""Continue lookahead training after all authorized state-data expansion finishes."""
import json,subprocess,sys,time
from pathlib import Path
root=Path('artifacts/dsv41-l2-state-v3-20260916');here=Path(__file__).parent
while not (root/'extension-complete.json').exists():time.sleep(20)
plan=json.loads((root/'plan.json').read_text());plan['samples']=[r for r in plan['samples'] if r['split'] in ['train','validation'] and (root/'data'/r['id']/'verified.json').exists()]
train={r['family_id'] for r in plan['samples'] if r['split']=='train'};val={r['family_id'] for r in plan['samples'] if r['split']=='validation'};assert train and val and not train&val
cohort=root/'lookahead-full-extended-cohort.json';assert not cohort.exists();cohort.write_text(json.dumps(plan,ensure_ascii=False,indent=2))
for rank in [0,64]:
 out=root/f'lookahead-full-extended-r{rank}'
 with (root/f'lookahead-full-extended-r{rank}.log').open('w') as log:
  subprocess.run([sys.executable,str(here/'train_router_lookahead.py'),'--cohort',str(cohort),'--per-layer-rank',str(rank),'--output',str(out)],check=True,stdout=log,stderr=subprocess.STDOUT)
 subprocess.run([sys.executable,str(here/'export_lookahead_priority.py'),'--model',str(out)],check=True)
 for split in ['validation','train']:
  with (out/f'priority-{split}.log').open('w') as log:subprocess.run([sys.executable,str(here/'evaluate_priority.py'),'--cohort',str(out/'priority'),'--evaluation-split',split],check=True,stdout=log)
(root/'lookahead-full-extended-complete.json').write_text(json.dumps(dict(complete=True,goal_complete=False,test_opened=False)))
