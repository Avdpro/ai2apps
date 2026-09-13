"""Verify transaction parity separately from Burst approximation differences."""
import json,hashlib
from pathlib import Path
import numpy as np
from safetensors.numpy import load_file
ROOT=Path(__file__).resolve().parents[2]

def compare(left,right):
    lm=json.loads((left/'manifest.json').read_text());rm=json.loads((right/'manifest.json').read_text())
    assert lm['status']==rm['status']=='complete' and lm['input_ids']==rm['input_ids']
    rows=[]
    for i in range(min(len(lm['generated_ids']),len(rm['generated_ids']))):
        name=f'{i:02d}_logits.safetensors'
        for p,m in [(left,lm),(right,rm)]:assert hashlib.sha256((p/name).read_bytes()).hexdigest()==m['trace_files'][name]
        x=load_file(str(left/name))['logits'].astype(np.float64).reshape(-1);y=load_file(str(right/name))['logits'].astype(np.float64).reshape(-1)
        assert np.isfinite(y).all()
        lx=x-x.max();lx-=np.log(np.exp(lx).sum());ly=y-y.max();ly-=np.log(np.exp(ly).sum())
        rows.append(dict(step=i,same_context=lm['generated_ids'][:i]==rm['generated_ids'][:i],max_abs=float(np.max(np.abs(x-y))),rmse=float(np.sqrt(np.mean((x-y)**2))),kl=float(np.sum(np.exp(lx)*(lx-ly)))))
    return dict(reference=str(left),candidate=str(right),generated_ids_equal=lm['generated_ids']==rm['generated_ids'],all_logits_exact=all(r['max_abs']==0 for r in rows),steps=rows)

if __name__=='__main__':
    report={}
    exact=ROOT/'artifacts/dsv41-default-dynamic128-20260913'
    for top in [2,4]:
        base=ROOT/f'artifacts/dsv41-burst128-t{top}-b1-20260913'
        report[f'top{top}_versus_exact']=compare(exact,base)
        for block in [2,4]:
            target=ROOT/f'artifacts/dsv41-burst128-t{top}-b{block}-20260913'
            result=compare(base,target);report[f'top{top}_block{block}']=result
            assert result['all_logits_exact'],f'Transaction mismatch: Top{top}/Block{block}'
    (ROOT/'artifacts/dsv41-burst128-comparisons-20260913.json').write_text(json.dumps(report,indent=2))
    for key,r in report.items():print(key,'IDs equal',r['generated_ids_equal'],'logits exact',r['all_logits_exact'],'max KL same context',max(s['kl'] for s in r['steps'] if s['same_context']))
