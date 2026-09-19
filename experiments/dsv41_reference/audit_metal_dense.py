#!/usr/bin/env python3
"""Stop at the first FP8 Metal/CPU mismatch and save a standalone reproducer."""
import json,sys
from pathlib import Path
import torch
import cpu_kernel
import metal_dense
import run_metal_dense

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1]);cpu=cpu_kernel.fp8_gemm;gpu=metal_dense.fp8_gemm
    active=[]
    def audited(*args,**kwargs):
        actual=gpu(*args,**kwargs);expected=cpu(*args,**kwargs)
        if not torch.equal(actual.contiguous().view(torch.uint8),expected.contiguous().view(torch.uint8)):
            name=getattr(active[-1],'audit_name','unknown') if active else 'outside Linear'
            torch.save({'a':args[0],'sa':args[1],'b':args[2],'sb':args[3],'actual':actual,'expected':expected},output/'fp8_failure.pt')
            (output/'fp8_failure.json').write_text(json.dumps({'module':name,'shape':list(actual.shape),'different_elements':int((actual!=expected).sum()),'max_abs':float((actual.float()-expected.float()).abs().max())},indent=2))
            raise RuntimeError('first FP8 mismatch: '+name)
        return actual
    metal_dense.fp8_gemm=audited
    sys.modules['kernel']=cpu_kernel
    sys.path.insert(0,str(Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/inference').resolve()))
    # run_metal_dense patches the kernel before importing model; preload with
    # the audited Metal function while keeping its captured CPU function intact.
    cpu_kernel.fp8_gemm=audited
    import model
    cpu_kernel.fp8_gemm=cpu
    old_init=model.Linear.__init__;old_transformer_init=model.Transformer.__init__
    def init(self,*args,**kwargs):
        old_init(self,*args,**kwargs)
        def after(module,args,result):
            active.pop()
        self.register_forward_pre_hook(lambda module,args:active.append(module))
        self.register_forward_hook(after,always_call=True)
    def transformer_init(self,*args,**kwargs):
        old_transformer_init(self,*args,**kwargs)
        for name,module in self.named_modules():module.audit_name=name
    model.Linear.__init__=init;model.Transformer.__init__=transformer_init
    run_metal_dense.main()
if __name__=='__main__':main()
