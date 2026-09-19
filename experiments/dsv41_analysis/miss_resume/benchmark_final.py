"""Final controller validation against the unchanged installed-kernel references."""
import os,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[3];base=root/'artifacts/dsv41-miss-resume-20260915/bench-wheel';work=root/'artifacts/dsv41-miss-resume-20260915/bench-final';work.mkdir(exist_ok=True)
rows=[]
for top,block in [(0,1),(0,2),(0,4),(2,1),(2,2),(2,4),(4,1),(4,4)]:
    name=f'top{top}-block{block}';out=work/name
    ref=json.loads((base/f'installed-top{top}-block0/manifest.json').read_text())
    env=os.environ.copy()
    for key in list(env):
        if key.startswith('DSV41_'):env.pop(key)
    env.update(DYLD_LIBRARY_PATH=str(root/'artifacts/dsv41-miss-resume-mlx-build'),DSV41_RESUME_MODE='guarded',DSV41_RESUME_BLOCK=str(block),DSV41_RESUME_BURST=str(top))
    cmd=[str(root/'.venv/bin/python'),str(Path(__file__).with_name('entry.py')),'--output',str(out),'--prompt-json',str(base/'prompt.json'),'--decode','64','--prefill-slots','64','--logits-mode','hash']
    print('RUN',name,flush=True)
    with (work/(name+'.log')).open('w') as f:subprocess.run(cmd,cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    m=json.loads((out/'manifest.json').read_text());dt=m['step_seconds'][1:]
    exact=m['logits_sha256']==ref['logits_sha256'];r=dict(name=name,top=top,block=block,exact_logits=exact,decode_tps=64/sum(dt),tail32_tps=32/sum(dt[-32:]),peak_bytes=m['sampled_physical_footprint_peak_bytes'],cache=m['cache_stats'],stats=m['miss_resume']['stats'],reference=str(base/f'installed-top{top}-block0'))
    rows.append(r);(work/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(r),flush=True)
    if not exact:raise RuntimeError('Accuracy failure '+name)
print('ALL FINAL PAIRS EXACT',flush=True)
