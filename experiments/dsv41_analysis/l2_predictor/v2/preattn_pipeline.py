"""Temporarily serialize the full-model collectors; resume the original in finally."""
import json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path('artifacts/dsv41-l2-preattn-v4-20260916');HERE=Path(__file__).parent;PARENT=19953

def status(phase):
 (ROOT/'serial-bulk-state.json').write_text(json.dumps(dict(phase=phase,paused_collector=PARENT,supervisor=os.getpid(),updated=time.time()),indent=2))
def interrupted(*args):raise SystemExit('interrupted')
def main():
 cmd=subprocess.check_output(['ps','-p',str(PARENT),'-o','command='],text=True);assert 'l2_predictor/v2/collect.py' in cmd
 signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted);child=None;os.kill(PARENT,signal.SIGSTOP)
 try:
  status('waiting_for_current_sequence')
  while True:
   rows=subprocess.check_output(['ps','-axo','pid,ppid,state'],text=True).splitlines()[1:]
   if not any(len(r.split())>=3 and r.split()[1]==str(PARENT) and 'Z' not in r.split()[2] for r in rows):break
   time.sleep(3)
  status('collecting_preattn')
  with (ROOT/'collection-bulk.log').open('w') as log:
   child=subprocess.Popen([sys.executable,str(HERE/'collect.py')],env=dict(os.environ,L2_DATA_ROOT=str(ROOT)),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   stages=[(8,'medium-correction'),(20,'full-correction')]
   while stages:
    counts={'train':0,'validation':0};plan=json.loads((ROOT/'plan.json').read_text())
    for row in plan['samples']:
     if (ROOT/'data'/row['id']/'verified.json').exists():counts[row['split']]+=1
    threshold,name=stages[0]
    if min(counts.values())>=threshold:
     status('training_'+name)
     with (ROOT/(name+'.log')).open('w') as training_log:
      subprocess.run([sys.executable,str(HERE/'train_preattn.py'),'--output',str(ROOT/name)],stdout=training_log,stderr=subprocess.STDOUT,check=True)
     stages.pop(0);status('collecting_preattn')
    elif child.poll() is not None:raise RuntimeError('collection exited before required verified cohorts; inspect log')
    else:time.sleep(20)
   if child.wait()!=0:raise RuntimeError('collector failed')
  (ROOT/'bulk-complete.json').write_text(json.dumps(dict(status='complete',goal_unverified=True)))
 finally:
  if child is not None and child.poll() is None:
   os.killpg(child.pid,signal.SIGTERM);child.wait()
  os.kill(PARENT,signal.SIGCONT);status('original_collector_resumed')
if __name__=='__main__':main()
