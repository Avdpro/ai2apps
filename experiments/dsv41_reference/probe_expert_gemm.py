import json,time
import numpy as np
import mlx.core as mx
from metal_bank import MetalBank
from metal_expert import act_quant
from native_mx_bf16 import linear
bank=MetalBank('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/experts/layer-0.bin',[0,1,2,3],l0_slots=0)
try:
    rng=np.random.default_rng(37);records=[]
    for per in [32,128,512]:
        x=mx.array(rng.standard_normal((4*per,5120)).astype(np.float32)).astype(mx.bfloat16);slots=mx.repeat(mx.arange(4,dtype=mx.int32),per);mx.eval(x,slots)
        def grouped():
            q,s=act_quant(x);z=(q.reshape(-1,160,32)*s[:,:,None]).reshape(-1,5120).astype(mx.bfloat16)
            return mx.concatenate([mx.quantized_matmul(z[e*per:(e+1)*per],bank.arrays[0][e].view(mx.uint32),bank.arrays[1][e],group_size=32,bits=4,mode='mxfp4') for e in range(4)])
        def gathered():return linear(x,bank.arrays[0],bank.arrays[1],slots)
        results={};values={}
        for name,fn in [('gather',gathered),('gemm',grouped)]:
            y=fn();mx.eval(y);times=[]
            for _ in range(5):
                start=time.perf_counter();y=fn();mx.eval(y);times.append(time.perf_counter()-start)
            values[name]=np.array(y.astype(mx.float32));results[name]=times
        d=values['gather']-values['gemm'];records.append({'tokens_per_expert':per,'seconds':results,'max_abs':float(np.max(np.abs(d))),'rmse':float(np.sqrt(np.mean(d*d))),'different':int(np.count_nonzero(d))})
    print(json.dumps(records,indent=2))
finally:bank.close()
