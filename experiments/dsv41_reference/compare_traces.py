"""Compare saved tensor contents, not torch.save container bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import torch

def main():
    p=argparse.ArgumentParser(); p.add_argument('reference',type=Path); p.add_argument('candidate',type=Path); p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); errors=[]; counts={'files':0,'tensors':0,'elements':0}; maxdiff=0.
    r=json.loads((a.reference/'manifest.json').read_text()); c=json.loads((a.candidate/'manifest.json').read_text())
    for key in ['status','input_ids','generated_ids','config','source_sha256','kernel_sha256','runner_sha256','checkpoint_index_sha256']:
        if r.get(key)!=c.get(key): errors.append('manifest.'+key)
    if r.get('status')!='complete' or c.get('status')!='complete': errors.append('incomplete run')
    for directory, manifest in [(a.reference,r),(a.candidate,c)]:
        for name,digest in manifest.get('trace_files',{}).items():
            path=directory/name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                errors.append(str(path)+': manifest hash mismatch')
    ref={f.name for f in a.reference.glob('*.pt')}; cand={f.name for f in a.candidate.glob('*.pt')}
    if ref!=cand: errors.append('file set differs')
    def compare(x,y,label):
        nonlocal maxdiff
        if isinstance(x,torch.Tensor):
            counts['tensors']+=1; counts['elements']+=x.numel()
            if not isinstance(y,torch.Tensor) or x.shape!=y.shape or x.dtype!=y.dtype:
                errors.append(label+': metadata'); return
            # Raw bits also compare signed zero and infinities; avoids NaN equality ambiguity.
            if not torch.equal(x.contiguous().view(torch.uint8),y.contiguous().view(torch.uint8)):
                errors.append(label)
                if x.is_floating_point():
                    d=(x.float()-y.float()).abs(); finite=d[torch.isfinite(d)]
                    if finite.numel(): maxdiff=max(maxdiff,finite.max().item())
        elif isinstance(x,dict):
            if not isinstance(y,dict) or x.keys()!=y.keys(): errors.append(label+': keys'); return
            for k,v in x.items(): compare(v,y[k],label+'.'+k)
        elif isinstance(x,(tuple,list)):
            if not isinstance(y,(tuple,list)) or len(x)!=len(y): errors.append(label+': length'); return
            for i,(u,v) in enumerate(zip(x,y)): compare(u,v,label+'.'+str(i))
        elif x!=y: errors.append(label)
    for name in sorted(ref&cand):
        counts['files']+=1
        compare(torch.load(a.reference/name,weights_only=True),torch.load(a.candidate/name,weights_only=True),name)
    scope='CPU repeatability only; not independent CUDA parity'
    if r.get('metal_dense') or r.get('metal_moe'):
        scope='Hybrid baseline versus candidate; not CPU golden or independent CUDA parity'
    elif c.get('metal_dense'):
        scope='CPU golden versus hybrid Metal FP8/routed-expert path; not independent CUDA parity'
    elif c.get('metal_moe'):
        scope='CPU golden versus hybrid Metal routed experts; not independent CUDA parity'
    elif c.get('storage_optimization'):
        scope='CPU golden versus cached storage; not independent CUDA parity'
    result={'exact':not errors,**counts,'max_finite_abs_diff':maxdiff,'mismatches':errors,
            'reference':str(a.reference.resolve()),'candidate':str(a.candidate.resolve()),
            'scope':scope}
    a.output.write_text(json.dumps(result,indent=2)); print(json.dumps(result))
    if errors: raise SystemExit(1)

if __name__=='__main__': main()
