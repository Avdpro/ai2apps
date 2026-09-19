"""Serialize a small model timing probe after v5; always restore v3 collector."""
import json,os,signal,subprocess,sys,time
from pathlib import Path
root=Path('artifacts/dsv41-l2-prefetch-probe-20260916');root.mkdir(exist_ok=True)
parent=19953
cmd=subprocess.check_output(['ps','-p',str(parent),'-o','command='],text=True);assert 'l2_predictor/v2/collect.py' in cmd
child=None
signal.signal(signal.SIGTERM,lambda *a:(_ for _ in ()).throw(SystemExit('interrupted')))
os.kill(parent,signal.SIGSTOP)
try:
 while True:
  rows=subprocess.check_output(['ps','-axo','pid,ppid,state'],text=True).splitlines()[1:]
  if not any(len(r.split())>=3 and r.split()[1]==str(parent) and 'Z' not in r.split()[2] for r in rows):break
  time.sleep(3)
 for mode in ['block2-off','block2-on','block4-on','block4-off']:
  out=root/mode;assert not out.exists()
  env=dict(os.environ,DYLD_LIBRARY_PATH=str(Path('artifacts/dsv41-miss-resume-mlx-build').resolve()),L2_PROBE_MODE=mode.split('-')[0],L2_PREFETCH='1' if mode.endswith('-on') else '0',L2_PROBE_OUTPUT=str(out))
  with (root/f'{mode}.log').open('w') as log:
   child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('entry.py')),'--output',str(out),'--prompt','Explain why a database index speeds up queries.','--decode','16','--prefill-slots','64','--logits-mode','hash','--inference-mode','legacy'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   if child.wait():raise RuntimeError(f'{mode} failed')
 (root/'complete.json').write_text(json.dumps(dict(complete=True)))
finally:
 if child is not None and child.poll() is None:os.killpg(child.pid,signal.SIGTERM);child.wait()
 os.kill(parent,signal.SIGCONT)
 (root/'resumed.json').write_text(json.dumps(dict(resumed=parent)))
