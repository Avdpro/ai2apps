"""Run a full attention-state cohort after the real-model delivery probe."""
import json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path('artifacts/dsv41-l2-attn-reuse-v5-20260916');WAIT=Path('artifacts/dsv41-l2-deadline-v2-20260916');HERE=Path(__file__).parent;PARENT=19953

def main():
 while not (WAIT/'resumed.json').exists():time.sleep(10)
 if not (WAIT/'complete.json').exists():raise RuntimeError('delivery probe failed; inspect before continuing')
 cmd=subprocess.check_output(['ps','-p',str(PARENT),'-o','command='],text=True);assert 'l2_predictor/v2/collect.py' in cmd
 child=None
 def interrupted(*args):raise SystemExit('interrupted')
 signal.signal(signal.SIGINT,interrupted);signal.signal(signal.SIGTERM,interrupted);os.kill(PARENT,signal.SIGSTOP)
 try:
  (ROOT/'serial-bulk-state.json').write_text(json.dumps(dict(phase='waiting_for_current_sequence',paused_collector=PARENT,supervisor=os.getpid())))
  while True:
   rows=subprocess.check_output(['ps','-axo','pid,ppid,state'],text=True).splitlines()[1:]
   if not any(len(r.split())>=3 and r.split()[1]==str(PARENT) and 'Z' not in r.split()[2] for r in rows):break
   time.sleep(3)
  child=subprocess.Popen([sys.executable,str(HERE/'collect.py')],env=dict(os.environ,L2_DATA_ROOT=str(ROOT)),start_new_session=True)
  if child.wait()!=0:raise RuntimeError('attention reuse bulk failed')
  (ROOT/'bulk-complete.json').write_text(json.dumps(dict(complete=True)))
 finally:
  if child is not None and child.poll() is None:os.killpg(child.pid,signal.SIGTERM);child.wait()
  os.kill(PARENT,signal.SIGCONT);(ROOT/'serial-bulk-state.json').write_text(json.dumps(dict(phase='original_collector_resumed',paused_collector=PARENT,supervisor=os.getpid())))
if __name__=='__main__':main()
