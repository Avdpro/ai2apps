"""Sequential GPU benchmarks; abort a candidate pair on any logit divergence."""
import json,os,subprocess,sys,hashlib,time
from pathlib import Path
root=Path(__file__).resolve().parents[3];work=root/'artifacts/dsv41-miss-resume-20260915/bench-wheel';work.mkdir(exist_ok=True)
source=json.loads((root/'artifacts/dsv41-oracle-prefetch-20260915/coding-en-train-18-baseline1/manifest.json').read_text())
fixture=work/'prompt.json';fixture.write_text(json.dumps({k:source[k] for k in ('prompt','input_ids')},ensure_ascii=False,indent=2))
plans=[('installed',0,0),('eager',0,0),('resume',0,1),('resume',0,4),('installed',2,0),('resume',2,1),('resume',2,4),('installed',4,0),('resume',4,1),('resume',4,4)]
results=[];refs={}
for mode,top,block in plans:
    name=f'{mode}-top{top}-block{block}';out=work/name
    if out.exists():raise RuntimeError('Refusing to overwrite '+str(out))
    env=os.environ.copy()
    for k in list(env):
        if k.startswith('DSV41_RESUME_') or k=='DYLD_LIBRARY_PATH':env.pop(k)
    script=root/'experiments/dsv41_mlx/run.py' if mode=='installed' else Path(__file__).with_name('entry.py')
    cmd=[str(root/'.venv/bin/python'),str(script),'--output',str(out),'--prompt-json',str(fixture),'--decode','64','--prefill-slots','64','--logits-mode','hash']
    if mode!='installed':
        env['DYLD_LIBRARY_PATH']=str(root/'artifacts/dsv41-miss-resume-mlx-build')
        env['DSV41_RESUME_MODE']='guarded';env['DSV41_RESUME_EAGER']='1' if mode=='eager' else '0';env['DSV41_RESUME_BLOCK']=str(block or 1);env['DSV41_RESUME_BURST']=str(top)
    else:
        cmd+=['--inference-mode','legacy']
        if top:cmd+=['--burst-top',str(top)]
    print('RUN',name,flush=True)
    with (work/(name+'.log')).open('w') as log:subprocess.run(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    m=json.loads((out/'manifest.json').read_text());times=m['step_seconds'][1:]
    if mode=='installed':refs[top]=m['logits_sha256']
    exact=m['logits_sha256']==refs[top]
    result={'name':name,'mode':mode,'top':top,'block':block,'exact_logits':exact,'decode_tps':len(times)/sum(times),'tail32_tps':32/sum(times[-32:]),'peak_bytes':m['sampled_physical_footprint_peak_bytes'],'cache':m['cache_stats'],'controller':m.get('miss_resume')}
    results.append(result);(work/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps({k:result[k] for k in ('name','exact_logits','decode_tps','tail32_tps','peak_bytes')}),flush=True)
    if not exact:raise RuntimeError('Logit mismatch '+name)
print('ALL PAIRS EXACT',flush=True)
