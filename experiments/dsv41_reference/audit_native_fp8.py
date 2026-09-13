import json,sys
from pathlib import Path
import torch,cpu_kernel,native_mx,run_native_fp8_only

cpu=cpu_kernel.fp8_gemm;native=native_mx.fp8_gemm;rows=[]
output=Path(sys.argv[sys.argv.index('--output')+1])
def audited(*args,**kwargs):
    actual=native(*args,**kwargs);expected=cpu(*args,**kwargs);d=(actual.float()-expected.float())
    rows.append({'index':len(rows),'shape':list(actual.shape),'different':int((actual!=expected).sum()),'elements':actual.numel(),'max_abs':float(d.abs().max()),'rmse':float(d.square().mean().sqrt()),'rms':float(expected.float().square().mean().sqrt())})
    if len(rows)>=30:raise RuntimeError('diagnostic first 30 FP8 calls captured')
    return actual
native_mx.fp8_gemm=audited
try:run_native_fp8_only.main()
finally:
    if output.exists():(output/'fp8-audit.json').write_text(json.dumps(rows,indent=2))
