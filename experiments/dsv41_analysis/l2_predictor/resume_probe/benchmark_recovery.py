"""Paired regression gate; old packet vs restored admission, plus explicit transitions."""
import hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
root=Path('artifacts/dsv41-l2-window-recovery-v1-20260917')
here=Path(__file__).parent
shutil.copytree(here,root/'source/resume_probe',ignore=shutil.ignore_patterns('__pycache__'))
gold=json.loads(Path('artifacts/dsv41-l2-prefetch-policy-20260916/6-baseline-zero/manifest.json').read_text())
cases=[]
for stress,n in [(False,32),(True,16)]:
    for i,executor in enumerate(('packet','window2','window2','packet')):
        cases.append(dict(name=f'{"stress" if stress else "normal"}-{i}-{executor}',executor=executor,stress=stress,n=n,top=0,predictor='none',once=False))
for top in (2,4):
    for executor in ('packet','window2'):
        cases.append(dict(name=f'burst{top}-{executor}',executor=executor,stress=False,n=32,top=top,predictor='none',once=False))
for predictor in ('none','block6','state','lookahead'):
    cases.append(dict(name=f'transition-{predictor}',executor='window2',stress=False,n=8,top=0,predictor=predictor,once=True))
sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'source/resume_probe').glob('*') if p.is_file()}
sources.update({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('artifacts/dsv41-l2-resume-native-build').glob('*.so')})
(root/'plan.json').write_text(json.dumps(dict(cases=cases,sources=sources,scope='Same-source packet control; ABBA timing; diagnostic transition not speed acceptance'),indent=2))
results={}
try:
 for i,c in enumerate(cases):
    for path,sha in sources.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha
    (root/'status.json').write_text(json.dumps(dict(phase='running',index=i,total=len(cases),case=c['name'],pid=os.getpid())))
    env=dict(os.environ,DYLD_LIBRARY_PATH=str(Path('artifacts/dsv41-miss-resume-mlx-build').resolve()),L2_WINDOW_PREDICTOR=c['predictor'],L2_WINDOW_EXECUTOR=c['executor'],DSV41_NATIVE_WINDOW='1',L2_WINDOW_BLOCK='2',L2_WINDOW_NOTICE='packet',L2_TRACE_SCHEDULER='0',DSV41_LOCAL_ROOTS='1',DSV41_DEFER_COUNTERS='1',DSV41_DEFER_ROUTE_STATS='1',DSV41_ASYNC_WINDOW='1',L2_MIN_LEAD_LAYERS='1',DSV41_RESUME_STRESS_ALL_MISS=str(int(c['stress'])),L2_DIAGNOSTIC_WINDOW_ONCE=str(int(c['once'])),DSV41_WINDOW_FORCE='0')
    for key in ('L2_DISABLE_PREFETCH','L2_VERIFY_LAYERS','L2_VERIFY_STATE_ROOTS'):env.pop(key,None)
    out=root/c['name']
    cmd=[sys.executable,str(root/'source/resume_probe/entry.py'),'--output',str(out),'--prompt',gold['prompt'],'--decode',str(c['n']),'--prefill-slots','64','--logits-mode','hash','--inference-mode','legacy','--expert-no-cache','--force-input-tokens',str(root/'tokens.json')]
    if c['top']:cmd+=['--burst-top',str(c['top'])]
    with (root/(c['name']+'.log')).open('w') as log:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    m=json.loads((out/'manifest.json').read_text());d=json.loads((out/'l2-window.json').read_text());s=d['stats']
    assert m['status']=='complete' and m['sampled_physical_footprint_peak_bytes']<=65_000_000_000
    if not c['top']:assert m['logits_sha256']==gold['logits_sha256'][:c['n']+1],c['name']
    if c['top'] and c['executor']=='window2':
        ref=json.loads((root/f"burst{c['top']}-packet/manifest.json").read_text());assert m['logits_sha256']==ref['logits_sha256']
    assert s['completed_layers']==40*c['n']
    if c['stress']:assert s['misses']==40*c['n'] and s['constructed_layers']==0
    if c['once']:assert s['window_tokens']==1 and s['native_tail_tokens']==1
    assert all(t['reads']<=64 for t in d['tokens'])
    assert all(t['submissions']+t['notices']<=41 for t in d['history'])
    times=m['step_seconds'][1:]
    results[c['name']]=dict(**c,tps=len(times)/sum(times),after4_tps=len(times[4:])/sum(times[4:]),peak_GB=m['sampled_physical_footprint_peak_bytes']/1e9,stats=s,l2_reads=sum(t['reads'] for t in d['tokens']),l2_used=sum(t['used'] for t in d['tokens']),expert_read_bytes=m['expert_read_bytes'])
    (root/'report.json').write_text(json.dumps(results,indent=2))
 (root/'status.json').write_text(json.dumps(dict(phase='complete')))
except BaseException as e:
 (root/'status.json').write_text(json.dumps(dict(phase='failed',error=str(e))));raise
