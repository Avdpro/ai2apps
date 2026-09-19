"""Bounded paired runtime comparison; exact logits required across cache policies."""
import json,subprocess,sys,time
from pathlib import Path
ROOT=Path('artifacts/dsv41-l1-runtime-20260915')
ROOT.mkdir(exist_ok=True)
data=json.loads(Path('artifacts/dsv41-l1-shape-20260915/dataset/dataset-manifest.json').read_text())
rows={r['id']:r for r in data['samples']}
results=[]
for name in ['coding-en-train-18','long-math_logic-zh-test']:
    row=rows[name];reference=None
    for repeat in range(2):
        policies=['baseline','dual_fast75','probation32_8']
        if repeat:policies.reverse()
        for policy in policies:
            out=ROOT/f'{name}-{policy}-{repeat}'
            cmd=[sys.executable,'experiments/dsv41_mlx/run.py','--prompt-json',row['fixture'],'--output',str(out),'--decode',str(row['decode_steps']),'--prefill-slots','64','--logits-mode','hash','--l1-policy',policy]
            if not (out/'manifest.json').exists():
                with out.with_suffix('.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
            m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete'
            signature=[m[k] for k in ['input_ids','generated_ids','logits_sha256']]
            if reference is None:reference=signature
            assert signature==reference,(name,policy,'parity')
            assert m['sampled_physical_footprint_peak_bytes']<65e9
            r=dict(case=name,repeat=repeat,policy=policy,tps=(len(m['step_seconds'])-1)/sum(m['step_seconds'][1:]),read_bytes=m['expert_total_read_bytes'],peak=m['sampled_physical_footprint_peak_bytes'],adaptive=m['adaptive_l1'])
            results.append(r);(ROOT/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps({k:v for k,v in r.items() if k!='adaptive'}),flush=True)
(ROOT/'complete.json').write_text(json.dumps(dict(runs=len(results),exact_logits=True)))
