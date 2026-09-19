"""Reverse the two new-policy long runs after anomalous first-pass variability."""
import json,subprocess,sys
from pathlib import Path
r=Path('artifacts/dsv41-growth-transplant-20260915');assert (r/'complete.json').exists()
f='artifacts/dsv41-l1-shape-20260915/dataset/long-math_logic-zh-test.json'
for v in ['new40','new48']:
 out=r/f'long-math_logic-zh-test-{v}-repeat'
 cmd=[sys.executable,str(r/'new-source/experiments/dsv41_mlx/run_l1.py'),'--prompt-json',f,'--decode','512','--prefill-slots','64','--decode-dispatch','legacy','--logits-mode','hash','--output',str(out)]+(['--l1-shape','artifacts/dsv41-l1-growth-20260915/growth.json'] if v=='new48' else ['--main-slots','40'])
 with out.with_suffix('.log').open('w') as h:subprocess.run(cmd,stdout=h,stderr=subprocess.STDOUT,check=True)
 m=json.loads((out/'manifest.json').read_text());old=json.loads((r/f'long-math_logic-zh-test-{v}'/'manifest.json').read_text())
 for k in ['input_ids','generated_ids','logits_sha256','cache_stats']:assert m[k]==old[k]
 t=m['step_seconds'];print(json.dumps(dict(variant=v,tps=512/sum(t[1:]),tail_tps=496/sum(t[17:]))),flush=True)
