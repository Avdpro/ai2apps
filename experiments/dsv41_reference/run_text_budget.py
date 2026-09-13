"""Text-only 65 decimal GB budget and sampled macOS physical footprint."""
import ctypes,hashlib,json,os,sys,threading
from pathlib import Path
import torch
import mlx.core as mx
import run_context_bounded

class Usage(ctypes.Structure):
    _fields_=[('uuid',ctypes.c_uint8*16)]+[(k,ctypes.c_uint64) for k in ['user','system','idle','interrupt','pageins','wired','resident','footprint','start','exit','child_user','child_system','child_idle','child_interrupt','child_pageins','child_elapsed','diskread','diskwrite']]

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1]);budget=65_000_000_000
    lib=ctypes.CDLL('/usr/lib/libproc.dylib',use_errno=True);lib.proc_pid_rusage.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_void_p];lib.proc_pid_rusage.restype=ctypes.c_int
    peak=0;error=None;samples=0;stop=threading.Event()
    def sample():
        nonlocal peak,error,samples
        u=Usage()
        if lib.proc_pid_rusage(os.getpid(),2,ctypes.byref(u))!=0:error='proc_pid_rusage failed';return
        peak=max(peak,u.footprint);samples+=1
    sample()
    if error:raise RuntimeError(error)
    def monitor():
        while not stop.wait(.02):sample()
    worker=threading.Thread(target=monitor,daemon=True);worker.start()
    old_call=torch.nn.Module._call_impl;previous=mx.set_memory_limit(60_000_000_000)
    def call(self,*a,**kw):
        if type(self).__name__ in ('Block','Transformer'):
            if error:raise RuntimeError(error)
            if peak>budget:raise MemoryError('65 GB sampled process footprint exceeded')
        return old_call(self,*a,**kw)
    torch.nn.Module._call_impl=call
    try:run_context_bounded.main()
    finally:
        torch.nn.Module._call_impl=old_call;stop.set();worker.join();sample();mx.set_memory_limit(previous)
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['text_memory_budget']={'budget_bytes':budget,'mlx_limit_bytes':60_000_000_000,'sampled_physical_footprint_peak_bytes':peak,'samples':samples,'sample_interval_seconds':.02,'within_sampled_budget':peak<=budget,'scope':'macOS rusage_info_v2 physical footprint sampled every 20ms; abort checked at layer boundaries; not an instantaneous OS hard cap','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
            if peak>budget:r['status']='failed';r['error']='sampled physical footprint exceeded 65 GB'
            path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
