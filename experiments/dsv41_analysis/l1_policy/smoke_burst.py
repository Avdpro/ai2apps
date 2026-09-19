"""Small Burst integration smoke test, not throughput or cross-policy parity."""
import json,subprocess,sys
from pathlib import Path
root=Path('artifacts/dsv41-l1-runtime-20260915');data=json.loads(Path('artifacts/dsv41-l1-shape-20260915/dataset/dataset-manifest.json').read_text());row=next(r for r in data['samples'] if r['id']=='general-zh-train-20')
checks=[]
for policy,top,block in [('dual_fast75',2,1),('probation32_8',4,4)]:
 out=root/f'burst-{policy}-top{top}-block{block}'
 cmd=[sys.executable,'experiments/dsv41_mlx/run.py','--prompt-json',row['fixture'],'--output',str(out),'--decode','32','--prefill-slots','64','--logits-mode','hash','--l1-policy',policy,'--burst-top',str(top),'--block-layers',str(block)]
 if not (out/'manifest.json').exists():
  with out.with_suffix('.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete' and m['decode_forwards']==32
 assert m['adaptive_l1']['promotion_reuse']['copied_experts']>0
 assert sum(sum(c) for c in m['adaptive_l1']['per_layer_counts'])==32*40*6
 assert m['sampled_physical_footprint_peak_bytes']<65e9
 checks.append(dict(policy=policy,top=top,block=block,committed_routes=32*40*6,peak=m['sampled_physical_footprint_peak_bytes']))
(root/'burst-smoke.json').write_text(json.dumps(checks,indent=2));print(json.dumps(checks))
