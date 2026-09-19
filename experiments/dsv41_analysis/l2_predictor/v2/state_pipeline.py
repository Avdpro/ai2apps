"""Finite collect/train milestones for the active continuous optimization task."""
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path('artifacts/dsv41-l2-state-v3-20260916');HERE=Path(__file__).parent

def main():
 # Only proceed after explicit pilot parity receipt, never merely elapsed time.
 while not (ROOT/'pilot-verified.json').exists():
  if (ROOT/'status.json').exists() and json.loads((ROOT/'status.json').read_text()).get('phase')=='failed':raise RuntimeError('state pilot failed')
  time.sleep(15)
 with (ROOT/'collection.log').open('w') as log:
  collector=subprocess.Popen([sys.executable,str(HERE/'collect.py')],env=dict(os.environ,L2_DATA_ROOT=str(ROOT)),stdout=log,stderr=subprocess.STDOUT)
  (ROOT/'pipeline-pids.json').write_text(json.dumps(dict(supervisor=os.getpid(),collector=collector.pid)))
  stages=[(8,8,128,'pilot-r128'),(24,20,256,'intermediate-r256'),(64,26,256,'full-r256'),(64,26,512,'full-r512')]
  while stages:
   counts={'train':0,'validation':0};plan=json.loads((ROOT/'plan.json').read_text())
   for row in plan['samples']:
    if (ROOT/'data'/row['id']/'verified.json').exists():counts[row['split']]+=1
   tr,va,rank,name=stages[0]
   if counts['train']>=tr and counts['validation']>=va:
    out=ROOT/name
    if not (out/'result.json').exists():
     with (ROOT/(name+'.log')).open('w') as training_log:
      subprocess.run([sys.executable,str(HERE/'train_state.py'),'--rank',str(rank),'--output',str(out)],stdout=training_log,stderr=subprocess.STDOUT,check=True)
    result=json.loads((out/'result.json').read_text());print(json.dumps(dict(stage=name,result=result)),flush=True);stages.pop(0)
   elif collector.poll() is not None:
    if collector.returncode:raise RuntimeError('collection failed; inspect collection.log')
    raise RuntimeError('collection completed below expected sequence thresholds')
   else:time.sleep(30)
  code=collector.wait()
  if code:raise RuntimeError('collection failed')
 (ROOT/'pipeline-complete.json').write_text(json.dumps(dict(status='milestones_complete',goal_70_percent_not_automatically_accepted=True)))
if __name__=='__main__':main()
