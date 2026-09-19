"""Byte-exact saved-state comparison without loading MLX or allocating GPU memory."""
import argparse,json,hashlib
from pathlib import Path

def tensors(path):
    raw=path.read_bytes();n=int.from_bytes(raw[:8],'little');header=json.loads(raw[8:8+n]);data=memoryview(raw)[8+n:]
    return {k:(v['dtype'],v['shape'],hashlib.sha256(data[slice(*v['data_offsets'])]).hexdigest()) for k,v in header.items() if k!='__metadata__'}

def compare(a,b):
    af={p.name:p for p in a.glob('*.safetensors')};bf={p.name:p for p in b.glob('*.safetensors')}
    errors=[];count=0
    if af.keys()!=bf.keys():errors.append({'files':sorted(af.keys()^bf.keys())})
    for name in sorted(af.keys()&bf.keys()):
        x=tensors(af[name]);y=tensors(bf[name]);count+=len(x)
        bad=[k for k in x.keys()|y.keys() if x.get(k)!=y.get(k)]
        if bad:errors.append({'file':name,'tensors':bad})
    return {'exact':not errors and count>0,'files':len(af),'tensors':count,'errors':errors}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('reference',type=Path);p.add_argument('candidate',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();r=compare(a.reference,a.candidate)
    if a.output:a.output.write_text(json.dumps(r,indent=2))
    print(json.dumps(r,indent=2));raise SystemExit(0 if r['exact'] else 1)
