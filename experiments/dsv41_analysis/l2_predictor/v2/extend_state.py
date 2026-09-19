"""Queue a broader training-only cohort after current state milestones finish."""
import json,os,subprocess,sys,time
from collections import defaultdict
from pathlib import Path
ROOT=Path('artifacts/dsv41-l2-state-v3-20260916');HERE=Path(__file__).parent

def main():
 plan=json.loads((ROOT/'plan.json').read_text());existing={r['id'] for r in plan['samples']};base=json.loads(Path('artifacts/dsv41-l1-shape-20260915/dataset/dataset-manifest.json').read_text());groups=defaultdict(list)
 for row in base['samples']:
  if row['split']=='train' and row['id'] not in existing:groups[(row['scope'],row['language'])].append(row)
 extra=[]
 for wave in range(2):
  for key in sorted(groups):
   if groups[key]:extra.append(groups[key].pop(0))
 assert len(extra)==40
 extended=dict(plan);extended['samples']=plan['samples']+extra;extended['maximum_rows']=sum(r['decode_steps'] for r in extended['samples']);extended['split_counts']={s:sum(r['split']==s for r in extended['samples']) for s in ['train','validation']};extended['extension_reason']='Broad training token/subject coverage; no validation/test families moved into training'
 (ROOT/'plan-extension.json').write_text(json.dumps(extended,ensure_ascii=False,indent=2))
 print(json.dumps(dict(queued_sequences=len(extra),queued_rows=sum(r['decode_steps'] for r in extra))),flush=True)
 while not (ROOT/'pipeline-complete.json').exists():time.sleep(30)
 (ROOT/'plan-original.json').write_text((ROOT/'plan.json').read_text());(ROOT/'plan.json').write_text(json.dumps(extended,ensure_ascii=False,indent=2))
 with (ROOT/'extension-collection.log').open('w') as log:
  subprocess.run([sys.executable,str(HERE/'collect.py')],env=dict(os.environ,L2_DATA_ROOT=str(ROOT)),stdout=log,stderr=subprocess.STDOUT,check=True)
 for rank in [256,512]:
  with (ROOT/f'extended-r{rank}.log').open('w') as log:
   subprocess.run([sys.executable,str(HERE/'train_state.py'),'--rank',str(rank),'--output',str(ROOT/f'extended-r{rank}')],stdout=log,stderr=subprocess.STDOUT,check=True)
 (ROOT/'extension-complete.json').write_text(json.dumps(dict(status='complete',goal_not_automatically_accepted=True)))
if __name__=='__main__':main()
