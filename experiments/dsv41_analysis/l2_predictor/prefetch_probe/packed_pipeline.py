"""Serialized development policy comparisons after existing full training completes."""
import json,os,signal,subprocess,sys,time,hashlib
from pathlib import Path
here=Path(__file__).parent
root=Path('artifacts/dsv41-l2-prefetch-packed-20260916');root.mkdir(exist_ok=True)
receipt=Path('artifacts/dsv41-l2-prefetch-development-20260916/report.json')
child=None
signal.signal(signal.SIGTERM,lambda *a:(_ for _ in ()).throw(SystemExit('interrupted')))
def status(**kw):
 (root/'status.json').write_text(json.dumps(dict(pid=os.getpid(),updated_at=time.time(),**kw),indent=2))
try:
 status(phase='waiting_for_training',receipt=str(receipt))
 while not receipt.exists():time.sleep(20)
 # Freeze the exact experiment entry points before any model run.
 source=root/'source';source.mkdir(exist_ok=True)
 hashes={}
 for directory in [here,here.parent/'resident_probe']:
  for p in directory.glob('*.py'):
   name=directory.name+'-'+p.name;data=p.read_bytes();(source/name).write_bytes(data);hashes[name]=hashlib.sha256(data).hexdigest()
 (root/'source-hashes.json').write_text(json.dumps(hashes,indent=2))
 modes=[('baseline','async'),('block4','async'),('block4','packed'),('block6','packed'),('baseline','async')]
 for index,(mode,notice) in enumerate(modes):
  tail="zero"
  name=f'{index}-{mode}-{notice}';out=root/name
  if (out/'manifest.json').exists() and json.loads((out/'manifest.json').read_text()).get('status')=='complete':continue
  assert not out.exists(),f'Incomplete output requires inspection: {out}'
  status(phase='running',variant=name)
  env=dict(os.environ,DYLD_LIBRARY_PATH=str(Path('artifacts/dsv41-miss-resume-mlx-build').resolve()),L2_PROBE_MODE=mode,L2_PROBE_TAIL=tail,L2_NOTICE_MODE=notice,L2_PROBE_CANONICAL='1',L2_PREFETCH='0' if mode=='baseline' else '1',L2_PROBE_OUTPUT=str(out))
  with (root/f'{name}.log').open('w') as log:
   child=subprocess.Popen([sys.executable,str(here/'entry.py'),'--output',str(out),'--prompt','Explain why a database index speeds up queries.','--decode','32','--prefill-slots','64','--logits-mode','hash','--inference-mode','legacy','--expert-no-cache'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   if child.wait():raise RuntimeError(f'{name} failed')
 (root/'complete.json').write_text(json.dumps(dict(complete=True,independent_acceptance=False)))
 subprocess.run([sys.executable,str(here/'report.py'),'--root',str(root)],check=True,stdout=(root/'report.log').open('w'))
 status(phase='complete',goal_complete=False)
except BaseException as error:
 status(phase='failed',error=str(error));raise
finally:
 if child is not None and child.poll() is None:os.killpg(child.pid,signal.SIGTERM);child.wait()
