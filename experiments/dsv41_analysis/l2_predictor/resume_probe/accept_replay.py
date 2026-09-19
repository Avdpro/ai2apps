"""Frozen-source ABBA floor measurements, with exact state and SSD checks."""
import hashlib,json,struct,subprocess,sys
from pathlib import Path
root=Path('artifacts/dsv41-resume-replay-20260917')
script=root/'acceptance-source/resume_probe/benchmark_replay.py'
hashes=json.loads((root/'acceptance-hashes.json').read_text())
def check_sources():
 for p,h in hashes.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
def tensors(p):
 raw=p.read_bytes();n=struct.unpack('<Q',raw[:8])[0];h=json.loads(raw[8:8+n]);b=raw[8+n:]
 return {k:(v['dtype'],v['shape'],b[v['data_offsets'][0]:v['data_offsets'][1]]) for k,v in h.items() if k!='__metadata__'}
for p in (root/'audit-replay-v12').glob('state-*.safetensors'):
 a=tensors(p);b=tensors(root/'audit-packet-v12'/p.name);assert set(a)==set(b)
 assert all(a[k]==b[k] for k in a),[k for k in a if a[k]!=b[k]]
for p in (root/'audit-replay-v12').glob('state-*.json'):
 assert json.loads(p.read_text())==json.loads((root/'audit-packet-v12'/p.name).read_text()),p
results={}
for stress in (True,False):
 for i,packet in enumerate((True,False,False,True)):
  check_sources();name=f"accept-{'stress' if stress else 'normal'}-{i}-{'packet' if packet else 'replay'}"
  cmd=[sys.executable,str(script),'--name',name,'--decode','32']
  if stress:cmd+=['--stress']
  if packet:cmd+=['--packet']
  print('RUN',name,flush=True)
  with (root/(name+'-driver.log')).open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
  result=json.loads((root/(name+'-result.json')).read_text());m=json.loads((root/name/'manifest.json').read_text());a=json.loads((root/name/'adaptive-l1.json').read_text())
  result.update(times=m['step_seconds'][1:],expert_read_bytes=m['expert_read_bytes'],bank_fence_calls=a['bank_fence_calls'],ssd_seconds=sum(a['decode_io_seconds'].values()))
  results[name]=result;(root/'acceptance-results.json').write_text(json.dumps(results,indent=2));print(name,result['tps'],flush=True)
check_sources()
summary={}
for stress in ('stress','normal'):
 group={mode:[r for k,r in results.items() if k.startswith(f'accept-{stress}-') and k.endswith(mode)] for mode in ('packet','replay')}
 for field in ('expert_read_bytes','bank_fence_calls'):
  assert len({r[field] for cases in group.values() for r in cases})==1,(stress,field)
 tps={mode:64/sum(sum(r['times']) for r in cases) for mode,cases in group.items()}
 steady={mode:56/sum(sum(r['times'][4:]) for r in cases) for mode,cases in group.items()}
 summary[stress]=dict(tps=tps,steady_tps=steady,ratio=tps['replay']/tps['packet'],steady_ratio=steady['replay']/steady['packet'])
(root/'acceptance-summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
