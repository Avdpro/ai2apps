"""Development-only fixed-input three-predictor / Top6,2,4 executor comparison."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

root=Path('artifacts/dsv41-l2-window-matrix-v1-20260917')
root.mkdir(exist_ok=False)
here=Path(__file__).parent
shutil.copytree(here,root/'source/resume_probe',ignore=shutil.ignore_patterns('__pycache__'))
gold_path=Path('artifacts/dsv41-l2-prefetch-policy-20260916/6-baseline-zero/manifest.json')
gold=json.loads(gold_path.read_text());tokens=root/'tokens.json';tokens.write_text(json.dumps(gold['generated_ids']))
cases=[]
for top in (0,2,4):
    cases.append(dict(name=f'packet-none-top{top}',executor='packet',predictor='none',top=top))
    for executor in ('guarded','window'):
        for predictor in ('none','state','lookahead','block6'):
            cases.append(dict(name=f'{executor}-{predictor}-top{top}',executor=executor,predictor=predictor,top=top))
sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'source/resume_probe').glob('*') if p.is_file()}
sources.update({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('experiments/dsv41_mlx').glob('*.py')})
sources.update({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('artifacts/dsv41-l2-resume-native-build').glob('*.so')})
(root/'plan.json').write_text(json.dumps(dict(cases=cases,decode=32,force_input_tokens=str(tokens),gold_sha256=hashlib.sha256(gold_path.read_bytes()).hexdigest(),sources=sources,scope='Development prompt, not independent acceptance; Burst uses fixed Top6 reference inputs to compare identical prefixes'),indent=2))
results={}
try:
    for index,case in enumerate(cases):
        for path,sha in sources.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha,path
        out=root/case['name']
        (root/'status.json').write_text(json.dumps(dict(pid=os.getpid(),phase='running',index=index,total=len(cases),case=case['name'],time=time.time())))
        env=dict(os.environ,DYLD_LIBRARY_PATH=str(Path('artifacts/dsv41-miss-resume-mlx-build').resolve()),L2_WINDOW_PREDICTOR=case['predictor'],L2_WINDOW_EXECUTOR=case['executor'],DSV41_NATIVE_WINDOW=str(int(case['executor']=='window')),L2_WINDOW_BLOCK='4',L2_WINDOW_NOTICE='packet',L2_TRACE_SCHEDULER='0')
        for key in ('L2_DISABLE_PREFETCH','L2_VERIFY_LAYERS','L2_VERIFY_STATE_ROOTS'):env.pop(key,None)
        cmd=[sys.executable,str(root/'source/resume_probe/entry.py'),'--output',str(out),'--prompt',gold['prompt'],'--decode','32','--prefill-slots','64','--logits-mode','hash','--inference-mode','legacy','--expert-no-cache','--force-input-tokens',str(tokens)]
        if case['top']:cmd+=['--burst-top',str(case['top'])]
        with (root/f'{case["name"]}.log').open('w') as log:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        m=json.loads((out/'manifest.json').read_text());d=json.loads((out/'l2-window.json').read_text())
        assert m['status']=='complete' and m['sampled_physical_footprint_peak_bytes']<=65_000_000_000
        if not case['top']:assert m['logits_sha256']==gold['logits_sha256'][:33],case['name']
        assert all(t['reads']<=64 for t in d['tokens'])
        assert all(t['submissions']+t['notices']<=41 for t in d['history'])
        times=m['step_seconds'][1:];tail=times[4:]
        result=dict(**case,tps=len(times)/sum(times),after4_tps=len(tail)/sum(tail),peak_GB=m['sampled_physical_footprint_peak_bytes']/1e9,
                    submissions=d['stats']['submissions'],notifications=sum(t['notices'] for t in d['history']),misses=d['stats']['misses'],
                    continuous_layers=d['stats']['window_histogram'],prefetch_reads=sum(t['reads'] for t in d['tokens']),
                    l2_used=sum(t['used'] for t in d['tokens']),unused=sum(t['unused'] for t in d['tokens']),
                    exact_top6_parity=not bool(case['top']),input_tokens=len(m['input_ids']),decode_tokens=len(times))
        results[case['name']]=result
        (root/'partial-results.json').write_text(json.dumps(results,indent=2))
    (root/'report.json').write_text(json.dumps(dict(results=results,scope='Fixed-input development comparison; no final holdout used'),indent=2))
    (root/'status.json').write_text(json.dumps(dict(phase='complete',time=time.time())))
except BaseException as error:
    (root/'status.json').write_text(json.dumps(dict(phase='failed',error=str(error),time=time.time())));raise
