#!/usr/bin/env python3
"""Add FP8 dense/shared-expert Metal GEMMs to the routed-expert checkpoint."""
import hashlib,json,sys,types
from pathlib import Path
import cpu_kernel
import metal_dense
import run_metal_moe

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1])
    cpu_fp8=cpu_kernel.fp8_gemm
    cpu_kernel.fp8_gemm=metal_dense.fp8_gemm
    # Preserve exact recorded sublayer boundaries while migrating inner GEMMs.
    # This rule applies to every layer, not to selected failing samples/layers.
    sys.modules['kernel']=cpu_kernel
    sys.path.insert(0,str(Path('artifacts/dsv41-download/DeepSeek-V4.1-Flash/inference').resolve()))
    import model
    original_init=model.Block.__init__
    def init(self,*args,**kwargs):
        original_init(self,*args,**kwargs)
        for projection in (self.attn.wo_b,self.ffn.shared_experts.w2):
            def forward(module,x):
                qa,sa=cpu_kernel.act_quant(x,32,'ue8m0',torch.float8_e8m0fnu)
                return cpu_fp8(qa,sa,module.weight,module.scale,torch.float8_e8m0fnu,32)
            projection.forward=types.MethodType(forward,projection)
    import torch
    model.Block.__init__=init
    try:run_metal_moe.main()
    finally:
        manifest=output/'manifest.json'
        if manifest.exists():
            r=json.loads(manifest.read_text());r['metal_dense']={'scope':'inner FP8 GEMMs on Metal; all attention wo_b and shared-expert w2 retained on CPU for strict boundaries',
                'statistics':metal_dense.stats,'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(metal_dense.__file__)]}}
            manifest.write_text(json.dumps(r,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
