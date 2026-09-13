"""Remove unspecified bytes from unused Engram cache tails; never alter live state.
This postprocessor is recorded in each manifest. Model execution is unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import torch


def canonicalize(root):
    path=root/'manifest.json'; manifest=json.loads(path.read_text())
    if manifest['status']!='complete': raise ValueError('only completed runs may be canonicalized')
    if 'snapshot_canonicalization' in manifest: return
    changes=[]
    for step in range(manifest['decode_forwards']+1):
        file=root/f'{step:02d}_buffers.pt'
        before=hashlib.sha256(file.read_bytes()).hexdigest()
        if before!=manifest['trace_files'][file.name]: raise ValueError(f'trace integrity failure: {file}')
        buffers=torch.load(file,weights_only=True)
        cache=buffers['engram_hash.cache']
        valid=len(manifest['input_ids'])+step
        live=cache[:,:valid].clone()
        cache[:,valid:]=0
        assert torch.equal(live,cache[:,:valid])
        torch.save(buffers,file)
        after=hashlib.sha256(file.read_bytes()).hexdigest()
        manifest['trace_files'][file.name]=after
        changes.append({'file':file.name,'valid_tokens':valid,'zeroed_elements':cache[:,valid:].numel(),'before_sha256':before,'after_sha256':after})
    manifest['snapshot_canonicalization']={'kind':'zero-unwritten-engram-cache-tail',
        'reason':'official engram.py allocates torch.empty; only positions below consumed token count are defined',
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'changes':changes,
        'model_execution_modified':False}
    path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('directories',nargs='+',type=Path)
    for root in p.parse_args().directories: canonicalize(root); print(root)
