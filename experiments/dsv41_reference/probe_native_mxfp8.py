#!/usr/bin/env python3
"""Diagnostic only: original bytes through native MLX MXFP8, no requantization."""
import argparse,hashlib,json,time
from pathlib import Path
import mlx.core as mx
import numpy as np
import torch
import metal_dense_cpu_order

def main():
    parser=argparse.ArgumentParser();parser.add_argument('case',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    d=torch.load(args.case,weights_only=True);k=d['a'].shape[-1];n=d['b'].shape[0]
    raw=d['b'].view(torch.uint8).contiguous().numpy().view(np.uint32).reshape(n,k//4)
    scale=d['sb'].view(torch.uint8).repeat_interleave(32,dim=0)[:n].contiguous().numpy()
    w=mx.array(raw);sw=mx.array(scale)
    reference_weight=d['b'].float()*d['sb'].float().repeat_interleave(32,dim=0)[:n].repeat_interleave(32,dim=1)
    dequant=mx.dequantize(w,sw,group_size=32,bits=8,mode='mxfp8')
    mx.eval(dequant)
    exact_weights=np.array_equal(np.array(dequant.astype(mx.float32)),reference_weight.numpy())
    if not exact_weights:raise RuntimeError('native dequantization changes weights')
    x=d['a'].float().reshape(-1,k)*d['sa'].float().reshape(-1,k//32).repeat_interleave(32,dim=1)
    x=mx.array(x.numpy());mx.eval(x,w,sw)
    durations=[]
    for _ in range(3):
        start=time.perf_counter();out=mx.quantized_matmul(x,w,sw,group_size=32,bits=8,mode='mxfp8');mx.eval(out);durations.append(time.perf_counter()-start)
    qa=mx.array(d['a'].float().reshape(-1,k).numpy());sa=mx.array(d['sa'].float().reshape(-1,k//32).numpy())
    raw_w=mx.array(d['b'].view(torch.uint8).numpy());raw_sw=mx.array(d['sb'].view(torch.uint8).numpy())
    mx.eval(qa,sa,raw_w,raw_sw);ordered_times=[];m=qa.shape[0]
    for _ in range(3):
        start=time.perf_counter()
        ordered=metal_dense_cpu_order.kernel()(inputs=[qa,sa,raw_w,raw_sw],template=[('M',m),('K',k),('N',n),('T',mx.bfloat16)],grid=(n*32,m,1),threadgroup=(128,1,1),output_shapes=[(m,n)],output_dtypes=[mx.bfloat16])[0]
        mx.eval(ordered);ordered_times.append(time.perf_counter()-start)
    actual=torch.from_numpy(np.array(out.astype(mx.float32))).bfloat16().reshape(d['expected'].shape)
    mismatch=actual!=d['expected']
    report={'diagnostic_only':True,'weights_exact':exact_weights,'output_exact':torch.equal(actual.view(torch.uint8),d['expected'].view(torch.uint8)),
            'different_elements':int(mismatch.sum()),'elements':actual.numel(),'max_abs_diff':float((actual.float()-d['expected'].float()).abs().max()),
            'gemm_seconds':durations,'ordered_gemm_seconds':ordered_times,'input_shape':list(x.shape),'weight_shape':list(d['b'].shape),'native_output_dtype':str(out.dtype),
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'case_sha256':hashlib.sha256(args.case.read_bytes()).hexdigest(),
            'note':'device-resident operator timings, first call may include compilation; different reduction semantics, not an accepted precision-preserving replacement'}
    args.output.write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
