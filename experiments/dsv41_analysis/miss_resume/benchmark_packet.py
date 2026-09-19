"""Sequential paired native-packet / eager benchmarks, with explicit all-miss stress."""
import json,os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];here=Path(__file__).parent
work=root/'artifacts/dsv41-miss-resume-20260916';work.mkdir(exist_ok=True)
prompt=root/'artifacts/dsv41-miss-resume-20260915/bench-wheel/prompt.json'
plan=[('natural-old-a',True,False,0,64),('natural-new-b',False,False,0,64),('natural-old-b',True,False,0,64),
      ('allmiss-old-a',True,True,0,16),('allmiss-new-a',False,True,0,16),('allmiss-new-b',False,True,0,16),('allmiss-old-b',True,True,0,16),
      ('burst2-new',False,False,2,64),('burst4-new',False,False,4,64)]
rows=[]
for name,eager,stress,top,n in plan:
    env={k:v for k,v in os.environ.items() if not k.startswith('DSV41_')}
    env.update(DYLD_LIBRARY_PATH=str(root/'artifacts/dsv41-miss-resume-mlx-build'),DSV41_RESUME_MODE='auto',DSV41_RESUME_BLOCK='4',DSV41_RESUME_EAGER=str(int(eager)),DSV41_RESUME_BURST=str(top),DSV41_RESUME_STRESS_ALL_MISS=str(int(stress)))
    cmd=[sys.executable,str(here/'entry.py'),'--prompt-json',str(prompt),'--decode',str(n),'--prefill-slots','64','--logits-mode','hash','--output',str(work/name)]
    print('RUN',name,flush=True)
    with (work/(name+'.log')).open('w') as f:subprocess.run(cmd,env=env,cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True)
    m=json.loads((work/name/'manifest.json').read_text());a=json.loads((work/name/'adaptive-l1.json').read_text())
    reference=(work/'allmiss-old-a') if stress else root/f'artifacts/dsv41-miss-resume-20260915/bench-wheel/installed-top{top}-block0'
    ref=json.loads((reference/'manifest.json').read_text());ad=json.loads((reference/'adaptive-l1.json').read_text())
    checks={k:m[k]==ref[k] for k in ['logits_sha256','expert_read_bytes','expert_total_read_bytes']}
    checks.update({k:a[k]==ad[k] for k in ['per_layer_counts','promotions','slot_swap_promotions','bank_fence_calls','promotion_extra_fences']})
    if stress:
        counts=a['per_layer_counts'];checks['every_layer_real_miss']=all(row==[0,0,6*n] for row in counts)
    row=dict(name=name,eager=eager,stress_all_miss=stress,top=top,decode=n,tps=n/sum(m['step_seconds'][1:]),tail_tps=min(32,n-1)/sum(m['step_seconds'][-min(32,n-1):]),peak_bytes=m['sampled_physical_footprint_peak_bytes'],checks=checks,stats=m['miss_resume']['stats'],bank_fences=a['bank_fence_calls'],expert_read_bytes=m['expert_read_bytes'])
    rows.append(row);(work/'packet-results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
    if not all(checks.values()):raise RuntimeError('parity failed '+name)
print('ALL PAIRS EXACT',flush=True)
