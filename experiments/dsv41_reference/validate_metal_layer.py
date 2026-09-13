"""Real layer replay against CPU golden; records numerical differences without hiding them."""
import argparse,hashlib,json,time
from collections import Counter
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
import mlx.core as mx
import cpu_kernel as cpu
from run_reference import Store
from metal_bank import MetalBank
from metal_expert import expert as metal_expert, act_quant


def tensor(x):return mx.array(x.float().numpy()).astype(mx.bfloat16)
def host(x):mx.eval(x);return torch.from_numpy(np.array(x.astype(mx.float32))).bfloat16()
def cpu_linear(store,prefix,x,fp4):
    w=store.read(prefix+'.weight');s=store.read(prefix+'.scale')
    a,sa=cpu.act_quant(x,32,'ue8m0',torch.float8_e8m0fnu)
    if fp4:return cpu.fp4_gemm(a,sa,w.view(torch.float4_e2m1fn_x2),s,act_block_size=32)
    return cpu.fp8_gemm(a,sa,w,s,block_size=32)
def cpu_expert(store,prefix,x,weights=None,fp4=True):
    gate=cpu_linear(store,prefix+'.w1',x,fp4).float().clamp(max=10)
    up=cpu_linear(store,prefix+'.w3',x,fp4).float().clamp(-10,10)
    hidden=F.silu(gate)*up
    if weights is not None:hidden=hidden*weights
    return cpu_linear(store,prefix+'.w2',hidden.bfloat16(),fp4)
def reconstruct(store,root,step,layer):
    h,_,_,_=torch.load(root/f'{step:02d}_layers.{layer}_input.pt',weights_only=True)
    attn=torch.load(root/f'{step:02d}_layers.{layer}.attn.pt',weights_only=True)
    prefix=f'layers.{layer}'
    flat=h.flatten(2).float()
    mixes=F.linear(flat,store.read(prefix+'.hc_attn_fn'))*torch.rsqrt(flat.square().mean(-1,keepdim=True)+1e-20)
    pre,post,comb=cpu.hc_split_sinkhorn(mixes,store.read(prefix+'.hc_attn_scale'),store.read(prefix+'.hc_attn_base'))
    h=(post.unsqueeze(-1)*attn.unsqueeze(-2)+torch.sum(comb.unsqueeze(-1)*h.unsqueeze(-2),dim=2)).bfloat16()
    x=torch.sum(pre.unsqueeze(-1)*h.float(),dim=2).bfloat16()
    f=x.float()*torch.rsqrt(x.float().square().mean(-1,keepdim=True)+1e-20)
    return (store.read(prefix+'.ffn_norm.weight')*f).bfloat16().flatten(0,1)
def metrics(a,b):
    diff=(a.float()-b.float()).abs()
    return {'bitwise_equal':torch.equal(a,b),'max_abs':diff.max().item(),'rms_error':diff.square().mean().sqrt().item(),'equal_fraction':(a==b).float().mean().item(),'finite':bool(torch.isfinite(a.float()).all())}

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--layer',type=int,default=0);p.add_argument('--store',type=Path,default=Path('artifacts/dsv41-layer0-experts.bin'));a=p.parse_args()
    torch.set_num_threads(4);torch.set_default_dtype(torch.bfloat16)
    root=Path('artifacts/dsv41-reference-baseline-20260913');store=Store(Path('artifacts/dsv41-download/DeepSeek-V4.1-Flash'))
    _,prefill_ids=torch.load(root/f'00_layers.{a.layer}.ffn.gate.pt',weights_only=True)
    l1=[i for i,_ in sorted(Counter(prefill_ids.flatten().tolist()).items(),key=lambda x:(-x[1],x[0]))[:8]]
    bank=MetalBank(a.store,l1);bank.verify_bytes(store,a.layer)
    results=[]
    for step in range(4):
        x=reconstruct(store,root,step,a.layer)
        weights,ids=torch.load(root/f'{step:02d}_layers.{a.layer}.ffn.gate.pt',weights_only=True)
        gold=torch.load(root/f'{step:02d}_layers.{a.layer}.ffn.pt',weights_only=True).flatten(0,1)
        cpu_y=torch.zeros_like(x,dtype=torch.float32)
        for e in sorted(set(ids.flatten().tolist())):
            row,col=torch.where(ids==e)
            cpu_y[row]+=cpu_expert(store,f'layers.{a.layer}.ffn.experts.{e}',x[row],weights[row,col,None])
        shared=cpu_expert(store,f'layers.{a.layer}.ffn.shared_experts',x,fp4=False)
        rebuilt=(cpu_y+shared).bfloat16()
        if not torch.equal(rebuilt,gold): raise AssertionError(('CPU reconstruction',step,metrics(rebuilt,gold)))
        # Independent activation quantizer check on actual hidden states.
        qa,qs=act_quant(tensor(x));mx.eval(qa,qs)
        ca,cs=cpu.act_quant(x,32,'ue8m0',torch.float8_e8m0fnu)
        quant_exact=np.array_equal(np.array(qa),ca.float().numpy()) and np.array_equal(np.array(qs),cs.float().numpy())
        actual=[];route_times=[]
        for row in range(x.shape[0]):
            order=torch.argsort(ids[row]);selected=ids[row,order].tolist()
            slots=bank.prepare(selected)
            inp=tensor(x[row:row+1].repeat(6,1));rw=mx.array(weights[row,order].float().numpy())
            start=time.perf_counter();out=metal_expert(inp,bank.arrays,slots,rw);bank.track(out);mx.eval(out)
            route_times.append(time.perf_counter()-start)
            total=mx.zeros((5120,),dtype=mx.float32)
            for i in range(6):total=total+out[i].astype(mx.float32)
            actual.append(host((total+tensor(shared[row]).astype(mx.float32)).astype(mx.bfloat16)))
        got=torch.stack(actual)
        result={'step':step,'cpu_reconstruction_exact':True,'fp8_activation_exact':quant_exact,'metal_moe':metrics(got,gold),'kernel_seconds':route_times}
        results.append(result);print(result,flush=True)
    bank.verify_bytes(store,a.layer)
    # Repeated decode input: all-hit slot reuse, warm compilation, no I/O in timed region.
    selected=ids[0,torch.argsort(ids[0])].tolist();slots=bank.prepare(selected)
    inp=tensor(x[:1].repeat(6,1));rw=mx.array(weights[0,torch.argsort(ids[0])].float().numpy());times=[]
    for _ in range(10):
        t=time.perf_counter();out=metal_expert(inp,bank.arrays,slots,rw);bank.track(out);mx.eval(out);times.append(time.perf_counter()-t)
    report={'device':mx.device_info(),'layer':a.layer,'l1_ids':l1,'l0_slots':6,'record_bytes':bank.info['record_bytes'],
       'loader':'original GLM/Qwen expert_loader.cpp, isolated Python 3.13 binding','native_read_bytes':bank.bytes,'native_calls':bank.loads,'native_io_seconds':bank.io_seconds,
       'loader_byte_exact':True,'results':results,'warm_decode_six_expert_seconds':times,
       'mlx_peak_bytes':mx.get_peak_memory(),'scope':'one real layer; shared expert remains CPU; not end-to-end GPU inference',
       'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('metal_expert.py'),Path(__file__).with_name('metal_bank.py'),Path('omlx/custom_kernels/glm_moe_dsa/csrc/expert_loader.cpp')]}}
    a.output.write_text(json.dumps(report,indent=2));bank.close();store.close()
if __name__=='__main__':main()
