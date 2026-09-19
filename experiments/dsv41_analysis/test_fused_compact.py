import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dsv41_mlx'))
import mlx.core as mx
from model import Model,LRUMetalBank
bank=LRUMetalBank('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/experts/layer-0.bin',[0,1,2,3],l0_slots=0)
m=Model.__new__(Model);m.matrix_prefill=True;mx.random.seed(19)
reports=[]
for segments in [[(0,16),(1,32)],[(0,128),(1,32)],[(0,128),(1,128)]]:
 slots=mx.array([s for s,n in segments for _ in range(n)],dtype=mx.int32)
 x=mx.random.normal((slots.size,5120)).astype(mx.bfloat16);rw=mx.full((slots.size,),.25,dtype=mx.float32);mx.eval(x,rw,slots)
 outputs=[]
 for fused in [False,True]:
  m.shared_dispatch=True;m.fused_gate_up=fused;y=m.expert(x,bank,slots,rw,segments);mx.eval(y);outputs.append(y)
 diff=float(mx.max(mx.abs(outputs[0].astype(mx.float32)-outputs[1].astype(mx.float32))).item());assert diff==0,(segments,diff)
 reports.append(dict(segments=segments,max_abs=diff))
bank.close();print(json.dumps(reports))
Path('artifacts/dsv41-fused-compact-kernel-check-20260913.json').write_text(json.dumps(reports,indent=2))
