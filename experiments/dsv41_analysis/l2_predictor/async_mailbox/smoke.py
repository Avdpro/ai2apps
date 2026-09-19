"""Isolated callback correctness/overlap; no model or SSD performance claim."""
import json,sys,threading,time
from pathlib import Path
sys.path.insert(0,str(Path('artifacts/dsv41-l2-async-mailbox-build').resolve()))
import mlx.core as mx
import _l2_mailbox as native
box=native.Mailbox();records=[];stop=threading.Event()
def worker():
 while not stop.is_set():
  for row in box.drain():records.append((time.perf_counter(),row))
  time.sleep(.0001)
t=threading.Thread(target=worker);t.start()
try:
 roots=[]
 for i in range(64):roots.append(native.notify(box,mx.arange(12,dtype=mx.int32)+i*12,i))
 mx.eval(*roots)
 limit=time.perf_counter()+5
 while len(records)<64 and time.perf_counter()<limit:time.sleep(.001)
 assert sorted(r[1] for r in records)==[[i,*range(i*12,(i+1)*12)] for i in range(64)]
 for i,r in enumerate(roots):assert r.tolist()==list(range(i*12,(i+1)*12))
 records.clear();x=mx.eye(1024);w=mx.eye(1024);mx.eval(x,w)
 packet=native.notify(box,mx.arange(6,dtype=mx.int32),100)
 start=time.perf_counter();mx.async_eval(packet) # Submit notification separately, without blocking the host.
 # A GPU dependency ensures notification precedes the measured synthetic tail.
 y=x+mx.sum(packet).astype(mx.float32)*1e-8
 for _ in range(64):y=y@w
 mx.async_eval(y);submitted=time.perf_counter();mx.eval(y);end=time.perf_counter()
 limit=time.perf_counter()+5
 while not records and time.perf_counter()<limit:time.sleep(.001)
 assert records and records[0][1]==[100,0,1,2,3,4,5]
 result=dict(packets_verified=65,graph_build_and_enqueue_seconds=submitted-start,tail_completed_seconds=end-start,notification_seconds=records[0][0]-start,notification_before_tail=records[0][0]<end,main_thread_notification_waits=0,scope='Synthetic GPU tail only; no full-model overhead or SSD-readiness validation')
 out=Path('artifacts/dsv41-l2-async-mailbox-build/smoke.json');out.write_text(json.dumps(result,indent=2));print(json.dumps(result))
finally:stop.set();t.join()
