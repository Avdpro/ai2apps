"""Offline quality comparison: reference torch traces vs standalone MLX traces."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import torch
from safetensors.numpy import load_file

def main():
    ap=argparse.ArgumentParser();ap.add_argument('reference',type=Path);ap.add_argument('candidate',type=Path);a=ap.parse_args()
    r=json.loads((a.reference/'manifest.json').read_text());c=json.loads((a.candidate/'manifest.json').read_text())
    assert r['status']==c['status']=='complete' and r['input_ids']==c['input_ids']
    assert r.get('source_checkpoint_index_sha256',r['checkpoint_index_sha256'])==c.get('source_checkpoint_index_sha256',c['checkpoint_index_sha256'])
    assert {Path(k).name:v for k,v in r['source_sha256'].items()}==c['official_source_sha256']
    report={'scope':'full MLX vs previous reference; normal floating differences, not bitwise gate','reference':str(a.reference),'candidate':str(a.candidate),'reference_text':r['generated_text'],'candidate_text':c['generated_text'],'generated_ids_equal':r['generated_ids']==c['generated_ids'],'steps':[]}
    for i in range(min(len(r['generated_ids']),len(c['generated_ids']))):
        old=f'{i:02d}_logits.pt';new=f'{i:02d}_logits.safetensors'
        for root,m,name in [(a.reference,r,old),(a.candidate,c,new)]:assert hashlib.sha256((root/name).read_bytes()).hexdigest()==m['trace_files'][name]
        x=torch.load(a.reference/old,weights_only=True).float().reshape(-1);y=torch.from_numpy(load_file(str(a.candidate/new))['logits'].copy()).float().reshape(-1)
        assert x.shape==y.shape and torch.isfinite(y).all()
        lx=x.log_softmax(0);ly=y.log_softmax(0);d=x-y
        report['steps'].append({'step':i,'same_context':r['generated_ids'][:i]==c['generated_ids'][:i],'max_abs':d.abs().max().item(),'rmse':d.square().mean().sqrt().item(),'cosine':torch.nn.functional.cosine_similarity(x,y,dim=0).item(),'kl':(lx.exp()*(lx-ly)).sum().item(),'top1_equal':x.argmax().item()==y.argmax().item(),'top10_overlap':len(set(x.topk(10).indices.tolist())&set(y.topk(10).indices.tolist()))})
    (a.candidate/'numerics.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
