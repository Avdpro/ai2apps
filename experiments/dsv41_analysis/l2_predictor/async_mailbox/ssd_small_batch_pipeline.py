"""Pause at collector sequence boundary, measure read latency, always resume."""
import json,os,signal,subprocess,sys,time
from pathlib import Path
wait=Path('artifacts/dsv41-l2-attn-reuse-v5-20260916');parent=19953
while True:
 p=wait/'serial-bulk-state.json'
 if p.exists() and json.loads(p.read_text())['phase']=='original_collector_resumed':
  assert (wait/'bulk-complete.json').exists(),'v5 collection failed';break
 time.sleep(10)
assert 'l2_predictor/v2/collect.py' in subprocess.check_output(['ps','-p',str(parent),'-o','command='],text=True)
child=None
def interrupt(*args):raise SystemExit('interrupted')
signal.signal(signal.SIGTERM,interrupt);signal.signal(signal.SIGINT,interrupt)
os.kill(parent,signal.SIGSTOP)
try:
 while True:
  rows=subprocess.check_output(['ps','-axo','pid,ppid,state'],text=True).splitlines()[1:]
  if not any(len(r.split())>=3 and r.split()[1]==str(parent) and 'Z' not in r.split()[2] for r in rows):break
  time.sleep(3)
 child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('ssd_small_batch.py'))],start_new_session=True)
 if child.wait():raise RuntimeError('SSD probe failed')
finally:
 if child is not None and child.poll() is None:os.killpg(child.pid,signal.SIGTERM);child.wait()
 os.kill(parent,signal.SIGCONT)
