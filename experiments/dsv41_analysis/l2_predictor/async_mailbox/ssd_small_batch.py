"""Real GLM/Qwen preadv latency with bounded scratch and no model concurrency."""
import fcntl,json,os,random,sys,time
from pathlib import Path
import numpy as np
import mlx.core as mx
sys.path.insert(0,str(Path('experiments/dsv41_reference').resolve()))
from metal_bank import native
store=Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/experts');out=Path('artifacts/dsv41-l2-ssd-small-batch-20260916');out.mkdir(exist_ok=False)
infos=[json.loads((store/f'layer-{i}.bin.json').read_text()) for i in range(40)];info=infos[0]
assert all(i['shapes']==info['shapes'] and i['record_bytes']==info['record_bytes'] for i in infos)
scratch=tuple(mx.zeros((4,*shape),dtype=mx.uint8) for shape in info['shapes']);mx.eval(*scratch);mx.synchronize()
fds=[];events=[];rng=random.Random(918)
try:
 for layer in range(40):
  fd=os.open(store/f'layer-{layer}.bin',os.O_RDONLY);fcntl.fcntl(fd,48,1);fds.append(fd)
 # Interleave batch sizes and workers; count cold samples separately.
 for iteration in range(50):
  configs=[(1,1),(1,4),(2,2),(4,4)];rng.shuffle(configs)
  for count,workers in configs:
   layer=rng.randrange(40);experts=rng.sample(range(384),count);records=[infos[layer]['expert_to_record'][str(e)] for e in experts];begin=time.perf_counter();size=native.preadv_fused_experts(fds[layer],0,info['record_bytes'],records,list(range(count)),*scratch,workers);elapsed=time.perf_counter()-begin;assert size==count*info['record_bytes'];events.append(dict(iteration=iteration,count=count,workers=workers,layer=layer,experts=experts,seconds=elapsed,bytes=size))
finally:
 for fd in fds:os.close(fd)
summary={}
for count,workers in [(1,1),(1,4),(2,2),(4,4)]:
 values=np.array([r['seconds'] for r in events if r['count']==count and r['workers']==workers and r['iteration']>=5]);summary[f'{count}/{workers}']=dict(samples=len(values),ms_quantiles=dict(zip(['p10','median','p90'],(np.quantile(values,[.1,.5,.9])*1000).tolist())),fraction_under_062ms=float((values<=.00062).mean()))
(out/'result.json').write_text(json.dumps(dict(summary=summary,record_bytes=info['record_bytes'],scratch_bytes=sum(x.nbytes for x in scratch),events=events,scope='Native preadv, F_NOCACHE, original SSD checkpoint; no concurrent model. Not GPU timing or actual prediction READY proof.'),indent=2));print(json.dumps(summary,indent=2))
