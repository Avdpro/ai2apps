"""Run host/partial command-buffer diagnostics after timed GPU comparisons finish."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

matrix=Path('artifacts/dsv41-l2-window-matrix-v1-20260917')
root=Path('artifacts/dsv41-l2-window-profile-v1-20260917');root.mkdir(exist_ok=False)
while not (matrix/'report.json').exists():
    if (matrix/'status.json').exists() and json.loads((matrix/'status.json').read_text())['phase']=='failed':raise RuntimeError('Matrix failed; profiling not started')
    time.sleep(10)
gold=json.loads(Path('artifacts/dsv41-l2-prefetch-policy-20260916/6-baseline-zero/manifest.json').read_text())
try:
    for predictor in ('state','lookahead','block6'):
        (root/'status.json').write_text(json.dumps(dict(phase='running',case=predictor,pid=os.getpid())))
        env=dict(os.environ,DYLD_LIBRARY_PATH=str(Path('artifacts/dsv41-miss-resume-mlx-build').resolve()),L2_WINDOW_PREDICTOR=predictor,L2_WINDOW_EXECUTOR='window',DSV41_NATIVE_WINDOW='1',L2_WINDOW_BLOCK='4',L2_WINDOW_NOTICE='packet',L2_TRACE_SCHEDULER='1')
        for key in ('L2_DISABLE_PREFETCH','L2_VERIFY_LAYERS','L2_VERIFY_STATE_ROOTS'):env.pop(key,None)
        cmd=[sys.executable,str(Path(__file__).with_name('entry.py')),'--output',str(root/predictor),'--prompt',gold['prompt'],'--decode','32','--prefill-slots','64','--logits-mode','hash','--inference-mode','legacy','--expert-no-cache','--force-input-tokens',str(matrix/'tokens.json')]
        with (root/f'{predictor}.log').open('w') as log:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        m=json.loads((root/predictor/'manifest.json').read_text());assert m['logits_sha256']==gold['logits_sha256'][:33]
    (root/'status.json').write_text(json.dumps(dict(phase='complete')))
except BaseException as error:
    (root/'status.json').write_text(json.dumps(dict(phase='failed',error=str(error))));raise
