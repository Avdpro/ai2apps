"""Per-forward profile of the owned-weight path, excluding snapshot capture."""
import cProfile,hashlib,json,sys,time
from pathlib import Path
import torch
import run_native_owned

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1]);old=torch.nn.Module._call_impl;steps=[]
    def call(self,*a,**kw):
        if type(self).__name__!='Transformer':return old(self,*a,**kw)
        pf=cProfile.Profile();start=time.perf_counter();pf.enable()
        try:return old(self,*a,**kw)
        finally:
            pf.disable();elapsed=time.perf_counter()-start
            pf.dump_stats(str(output/f'forward-{len(steps):02d}.prof'));steps.append(elapsed)
    torch.nn.Module._call_impl=call
    try:run_native_owned.main()
    finally:
        torch.nn.Module._call_impl=old
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['forward_profile']={'seconds':steps,'scope':'Transformer call incl weight hooks, excludes harness snapshots; cProfile overhead included','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
