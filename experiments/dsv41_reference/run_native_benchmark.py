"""Throughput companion: omit layer traces and buffer serialization, retain logits.

Official computation and reference harness remain unchanged. Harness buffer
cloning still occurs before the discarded save call; timings include that cost.
"""
import hashlib,json,sys
from pathlib import Path
import torch
import run_native_sdpa

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1]);removed={'forward':0,'pre':0,'discarded_saves':0}
    old_save=torch.save;old_forward=torch.nn.Module.register_forward_hook;old_pre=torch.nn.Module.register_forward_pre_hook
    def register(kind,original):
        def wrap(self,hook,*a,**kw):
            if 'save' in getattr(getattr(hook,'__code__',None),'co_freevars',()):
                removed[kind]+=1
                # Reference harness does not retain the returned handle.
                return None
            return original(self,hook,*a,**kw)
        return wrap
    def save(obj,f,*a,**kw):
        name=Path(f).name
        if name.endswith('_logits.pt') or name.endswith('_top10.pt'):return old_save(obj,f,*a,**kw)
        removed['discarded_saves']+=1
    torch.nn.Module.register_forward_hook=register('forward',old_forward)
    torch.nn.Module.register_forward_pre_hook=register('pre',old_pre)
    torch.save=save
    try:run_native_sdpa.main()
    finally:
        torch.save=old_save;torch.nn.Module.register_forward_hook=old_forward;torch.nn.Module.register_forward_pre_hook=old_pre
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['throughput_capture']={'scope':'logits/top10 only; layer trace hooks omitted; buffer save discarded after harness cloning; times include remaining capture overhead','statistics':removed,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
            path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
