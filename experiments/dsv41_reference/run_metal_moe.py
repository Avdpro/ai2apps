#!/usr/bin/env python3
"""Full reference flow with Metal routed experts and native L0/L1 storage.
This trace-fixture prototype keeps dense/attention/router/shared experts on CPU.
"""
import argparse,hashlib,json,sys,time
from collections import Counter
from pathlib import Path
import numpy as np
import torch
import mlx.core as mx
import cpu_kernel
import run_reference
from metal_bank import MetalBank
from metal_expert import expert

decode_reducer = None  # Optional device-side ordered route reduction.
prefill_executor = None  # Optional experimental scheduler; default path unchanged.

def main():
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--expert-store',type=Path,default=Path('artifacts/dsv41-metal-fixtures'))
    options,remaining=parser.parse_known_args()
    sys.argv=[sys.argv[0],*remaining]
    fixtures=options.expert_store
    full=False
    if (fixtures/'manifest.json').exists():
        manifest=json.loads((fixtures/'manifest.json').read_text())
        full=manifest.get('status')=='complete' and manifest.get('layers')==list(range(40))
        if full:
            index=Path('artifacts/dsv41-download/DeepSeek-V4.1-Flash/model.safetensors.index.json')
            digest=hashlib.sha256(index.read_bytes()).hexdigest()
            if manifest.get('checkpoint_index_sha256')!=digest:raise ValueError('expert store checkpoint mismatch')
            for layer in range(40):
                path=fixtures/f'layer-{layer}.bin';info=json.loads(Path(str(path)+'.json').read_text())
                if info.get('complete_experts')!=384 or info.get('checkpoint_index_sha256')!=digest or path.stat().st_size!=384*info['record_bytes']:
                    raise ValueError(f'incomplete expert store layer {layer}')
    if '--checkpoint' in sys.argv or ('--prompt' in sys.argv and not full):
        raise ValueError('A new prompt requires a complete expert store; alternate checkpoints are not supported')
    output=Path(sys.argv[sys.argv.index('--output')+1])
    root=Path('artifacts/dsv41-reference-baseline-20260913')
    sys.modules['kernel']=cpu_kernel
    sys.path.insert(0,str(Path('artifacts/dsv41-download/DeepSeek-V4.1-Flash/inference').resolve()))
    import model
    banks={};compute_seconds=0.;route_calls=0
    def forward(self,x,image_mask=None):
        nonlocal compute_seconds,route_calls
        shape=x.shape;x=x.reshape(-1,self.dim)
        weights,indices=self.gate(x,None if image_mask is None else image_mask.flatten())
        layer=self.layer_id
        if layer not in banks:
            _,prefill=torch.load(root/f'00_layers.{layer}.ffn.gate.pt',weights_only=True)
            l1=[e for e,_ in sorted(Counter(prefill.flatten().tolist()).items(),key=lambda pair:(-pair[1],pair[0]))[:8]]
            banks[layer]=MetalBank(fixtures/f'layer-{layer}.bin',l1)
        bank=banks[layer]
        if prefill_executor is not None and x.shape[0]>1:
            y,elapsed,calls=prefill_executor(x,weights,indices,bank)
            compute_seconds+=elapsed;route_calls+=calls
            y+=self.shared_experts(x)
            return y.to(x.dtype).reshape(shape)
        y=torch.zeros_like(x,dtype=torch.float32)
        for row in range(x.shape[0]):
            order=torch.argsort(indices[row]);ids=indices[row,order].tolist()
            slots=bank.prepare(ids)
            inp=mx.array(x[row:row+1].float().numpy()).astype(mx.bfloat16)
            inp=mx.broadcast_to(inp,(len(ids),self.dim))
            rw=mx.array(weights[row,order].float().numpy())
            start=time.perf_counter();out=expert(inp,bank.arrays,slots,rw);bank.track(out);mx.eval(out)
            if decode_reducer is not None:
                reduced=decode_reducer(out);mx.eval(reduced)
                compute_seconds+=time.perf_counter()-start;route_calls+=1
                y[row]+=torch.from_numpy(np.array(reduced))
            else:
                compute_seconds+=time.perf_counter()-start;route_calls+=1
                values=torch.from_numpy(np.array(out.astype(mx.float32)))
                for i in range(len(ids)):y[row]+=values[i]
        y+=self.shared_experts(x)
        return y.to(x.dtype).reshape(shape)
    model.MoE.forward=forward
    try:run_reference.main()
    finally:
        manifest=output/'manifest.json'
        if manifest.exists():
            r=json.loads(manifest.read_text())
            r['metal_moe']={'scope':'hybrid CPU backbone / Metal routed experts',
                'expert_store':str(fixtures.resolve()),'full_expert_store':full,'l1_selection':'fixed bootstrap from baseline prefill, unchanged for new prompts',
                'l1_experts_per_layer':8,'l0_slots_per_layer':6,'router_on_cpu':True,'loader':'original GLM/Qwen native preadv_fused_experts',
                'native_io_seconds':sum(b.io_seconds for b in banks.values()),'native_read_bytes':sum(b.bytes for b in banks.values()),
                'native_calls':sum(b.loads for b in banks.values()),'route_calls':route_calls,'expert_gpu_seconds':compute_seconds,
                'mlx_peak_bytes':mx.get_peak_memory(),'device':mx.device_info(),
                'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('metal_expert.py'),Path(__file__).with_name('metal_bank.py'),Path('omlx/custom_kernels/glm_moe_dsa/csrc/expert_loader.cpp')]}}
            manifest.write_text(json.dumps(r,indent=2,ensure_ascii=False));print(json.dumps(r['metal_moe']),flush=True)
        for bank in banks.values():bank.close()
if __name__=='__main__':main()
