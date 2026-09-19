"""Paired end-to-end compatibility tests; not a throughput benchmark."""
import json,os,subprocess,sys
from pathlib import Path
import numpy as np
from compare import compare
root=Path(__file__).resolve().parents[3];work=root/'artifacts/dsv41-miss-resume-20260916/expanded-compat';work.mkdir(parents=True,exist_ok=True)
original=root/'artifacts/dsv41-multiturn-20260913'
vision=json.loads((original/'vision-2-messages.json').read_text())
for msg in vision:
    if isinstance(msg['content'],list):
        for part in msg['content']:
            if part.get('type')=='image_url':part['image_url']['url']=str(root/'artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/inference/examples/images/carrots.jpeg')
(work/'vision-messages.json').write_text(json.dumps(vision,ensure_ascii=False))
prompt=['--prompt-json',str(root/'artifacts/dsv41-miss-resume-20260915/bench-wheel/prompt.json')]
cases=[
 ('text-chat',4,['--messages-json',str(original/'text-3-messages.json')]),
 ('vision-chat',4,['--messages-json',str(work/'vision-messages.json'),'--vision-max-tokens','256']),
 ('diagnostics-main32',4,prompt+['--main-slots','32','--attention-chunk','128','--trace','--layer-progress','--collect-routes']),
 ('growth-fused',4,prompt+['--l1-shape',str(root/'artifacts/dsv41-l1-growth-20260915/growth.json'),'--fused-gate-up']),
 ('static-unsorted',4,prompt+['--static-l1','--decode-dispatch','unsorted','--attention-chunk','256']),
 ('baseline-zero-renorm',20,prompt+['--l1-policy','baseline','--burst-top','2','--burst-tail','zero-renorm']),
 ('dual-fixed-top',20,prompt+['--l1-policy','dual_fast75','--burst-top','4','--burst-tail','fixed-top']),
 ('probation-renorm',20,prompt+['--l1-policy','probation32_8','--burst-top','2','--burst-tail','renorm']),
 ('burst-prefill-shared',4,prompt+['--prefill-top','2','--main-slots','24','--shared-dispatch']),
 ('burst-block4',8,prompt+['--burst-top','2','--block-layers','4']),
]
rows=[]
for name,n,opts in cases:
    paths={}
    for mode in ['legacy','auto']:
        path=work/(name+'-'+mode);paths[mode]=path
        if not (path/'manifest.json').exists():
            env={k:v for k,v in os.environ.items() if not k.startswith('DSV41_') and k!='DYLD_LIBRARY_PATH'}
            cmd=[sys.executable,str(root/'experiments/dsv41_mlx/run.py'),'--inference-mode',mode,'--output',str(path),'--decode',str(n),'--prefill-slots','64','--logits-mode','hash',*opts]
            print('RUN',name,mode,flush=True)
            with (work/(name+'-'+mode+'.log')).open('w') as f:subprocess.run(cmd,env=env,cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True)
    old=json.loads((paths['legacy']/'manifest.json').read_text());new=json.loads((paths['auto']/'manifest.json').read_text())
    checks={k:old[k]==new[k] for k in ['logits_sha256','expert_read_bytes','expert_total_read_bytes']}
    checks['complete']=old['status']==new['status']=='complete'
    checks['new_executor']=new['miss_resume']['enabled'] and new['inference_selection']['selected']!='legacy'
    if name!='burst-block4':
        checks['cache_stats']=old['cache_stats']==new['cache_stats']
    for k in ['adaptive_l1']:
        if k in old:
            for key in ['per_layer_counts','promotions','bank_fence_calls','promotion_extra_fences']:
                if key in old[k]:checks[key]=old[k][key]==new[k][key]
    if '--trace' in opts:
        checks['trace_tensors']=compare(paths['legacy'],paths['auto'])['exact']
    if '--collect-routes' in opts:
        a=np.load(paths['legacy']/'routes.npz');b=np.load(paths['auto']/'routes.npz')
        checks['routes']=set(a.files)==set(b.files) and all(np.array_equal(a[k],b[k]) for k in a.files)
    row=dict(case=name,decode=n,selected=new['inference_selection'],stats=new['miss_resume']['stats'],peak_bytes=new['sampled_physical_footprint_peak_bytes'],checks=checks)
    rows.append(row);(work/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
    if not all(checks.values()):raise RuntimeError('Compatibility failure: '+name)
print('ALL COMPATIBILITY PAIRS EXACT',flush=True)
