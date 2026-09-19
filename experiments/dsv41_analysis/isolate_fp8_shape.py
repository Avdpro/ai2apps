"""Same quantized input/weight, batch vs row MXFP8 QMM with FP32 reference."""
import sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dsv41_mlx'))
import mlx.core as mx
from storage import Storage
from kernels import quant
out=Path('artifacts/dsv41-kv-precision-20260913');data=np.load(out/'replay.npz');s=Storage('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD')
def stats(x,y):
 a=np.array(x.astype(mx.float32)).astype(np.float64);b=np.array(y.astype(mx.float32)).astype(np.float64);d=a-b
 return dict(max_abs=float(abs(d).max()),rmse=float(np.sqrt(np.mean(d*d))),unequal=int(np.count_nonzero(d)))
rows=[]
for name in ['layers.0.attn.wq_a','layers.0.attn.wkv']:
 x=mx.array(data[name+'.input']).astype(mx.bfloat16);batch=mx.repeat(x,67,axis=1);a=quant(batch).astype(mx.bfloat16);b=quant(x).astype(mx.bfloat16);w,sc=s.fp8(name)
 kw=dict(group_size=32,bits=8,mode='mxfp8');yb=mx.quantized_matmul(a,w,sc,**kw)[:,-1:];ys=mx.quantized_matmul(b,w,sc,**kw)
 wd=mx.dequantize(w,sc,**kw).astype(mx.float32);ref=b.astype(mx.float32)@wd.T
 rows.append(dict(name=name,quantized_input=stats(a[:,-1:],b),batch_vs_row=stats(yb,ys),batch_vs_saved=stats(yb,mx.array(data[name+'.output'])),batch_vs_fp32=stats(yb,ref),row_vs_fp32=stats(ys,ref)))
s.close();(out/'isolated_fp8.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows))
