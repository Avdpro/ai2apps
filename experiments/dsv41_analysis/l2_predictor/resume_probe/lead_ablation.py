"""Paired development test: avoid spending SSD time on imminent deadlines."""
import json
import os
from pathlib import Path
import subprocess
import sys

root=Path('artifacts/dsv41-l2-lead-v1-20260917');root.mkdir(exist_ok=False)
matrix=Path('artifacts/dsv41-l2-window-matrix-v1-20260917');assert (matrix/'report.json').exists()
gold=json.loads(Path('artifacts/dsv41-l2-prefetch-policy-20260916/6-baseline-zero/manifest.json').read_text())
results={}
try:
    for index,lead in enumerate((0,1,2,2,1,0)):
        name=f'{index}-lead{lead}';out=root/name
        (root/'status.json').write_text(json.dumps(dict(phase='running',case=name,pid=os.getpid())))
        env=dict(os.environ,DYLD_LIBRARY_PATH=str(Path('artifacts/dsv41-miss-resume-mlx-build').resolve()),L2_WINDOW_PREDICTOR='block6',L2_WINDOW_EXECUTOR='window',DSV41_NATIVE_WINDOW='1',L2_WINDOW_BLOCK='4',L2_WINDOW_NOTICE='packet',L2_TRACE_SCHEDULER='0',L2_MIN_LEAD_LAYERS=str(lead))
        for key in ('L2_DISABLE_PREFETCH','L2_VERIFY_LAYERS','L2_VERIFY_STATE_ROOTS'):env.pop(key,None)
        cmd=[sys.executable,str(Path(__file__).with_name('entry.py')),'--output',str(out),'--prompt',gold['prompt'],'--decode','32','--prefill-slots','64','--logits-mode','hash','--inference-mode','legacy','--expert-no-cache','--force-input-tokens',str(matrix/'tokens.json')]
        with (root/f'{name}.log').open('w') as log:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        m=json.loads((out/'manifest.json').read_text());d=json.loads((out/'l2-window.json').read_text())
        assert m['logits_sha256']==gold['logits_sha256'][:33]
        assert m['sampled_physical_footprint_peak_bytes']<=65_000_000_000
        assert all(t['reads']<=64 for t in d['tokens'])
        assert all(t['submissions']+t['notices']<=41 for t in d['history'])
        t=m['step_seconds'][5:]
        results[name]=dict(lead=lead,after4_tps=len(t)/sum(t),reads=sum(x['reads'] for x in d['tokens']),used=sum(x['used'] for x in d['tokens']),unused=sum(x['unused'] for x in d['tokens']))
    (root/'report.json').write_text(json.dumps(results,indent=2));(root/'status.json').write_text(json.dumps(dict(phase='complete')))
except BaseException as error:
    (root/'status.json').write_text(json.dumps(dict(phase='failed',error=str(error))));raise
