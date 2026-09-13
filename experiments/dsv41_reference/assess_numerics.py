"""Quality report for normal floating-point differences; never label it bitwise parity."""
import argparse,hashlib,json
from pathlib import Path
import torch

def assess(reference,candidate):
    r=json.loads((reference/'manifest.json').read_text());c=json.loads((candidate/'manifest.json').read_text())
    for key in ['status','input_ids','config','source_sha256','kernel_sha256','runner_sha256','checkpoint_index_sha256']:
        if r.get(key)!=c.get(key):raise ValueError('incompatible '+key)
    if r['status']!='complete':raise ValueError('incomplete')
    def read(root,m,name):
        p=root/name
        if hashlib.sha256(p.read_bytes()).hexdigest()!=m['trace_files'][name]:raise ValueError('trace hash '+str(p))
        return torch.load(p,weights_only=True)
    report={'reference':str(reference),'candidate':str(candidate),'scope':'CPU reference' if not r.get('metal_moe') else 'hybrid reference; not independent CPU validation',
        'generated_ids_equal':r['generated_ids']==c['generated_ids'],'reference_text':r['generated_text'],'candidate_text':c['generated_text'],'steps':[]}
    for step in range(min(len(r['generated_ids']),len(c['generated_ids']))):
        x=read(reference,r,f'{step:02d}_logits.pt').float().reshape(-1)
        y=read(candidate,c,f'{step:02d}_logits.pt').float().reshape(-1)
        if x.shape!=y.shape or not torch.isfinite(y).all():raise ValueError('invalid logits')
        d=y-x;tx=x.topk(10);ty=y.topk(10)
        same_context=r['generated_ids'][:step]==c['generated_ids'][:step]
        logx=x.log_softmax(0);logy=y.log_softmax(0)
        row={'step':step,'same_input_context':same_context,'max_abs':float(d.abs().max()),'rmse':float(d.square().mean().sqrt()),
             'cosine':float(torch.nn.functional.cosine_similarity(x,y,dim=0)),'kl_reference_to_candidate':float((logx.exp()*(logx-logy)).sum()),
             'top1_equal':int(tx.indices[0])==int(ty.indices[0]),'top10_overlap':len(set(tx.indices.tolist())&set(ty.indices.tolist())),
             'top10_order_equal':torch.equal(tx.indices,ty.indices),'reference_top10':tx.indices.tolist(),'candidate_top10':ty.indices.tolist()}
        report['steps'].append(row)
    report['note']='Report, not a universal quality guarantee. After generated tokens diverge, logits use different contexts.'
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('reference',type=Path);p.add_argument('candidate',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=assess(a.reference,a.candidate);a.output.write_text(json.dumps(report,indent=2));print(json.dumps(report))
