"""Burst copy/swap parity including rollback statistics."""
import json,subprocess,sys
from pathlib import Path
root=Path('artifacts/dsv41-slot-swap-20260915');rows=json.loads(Path('artifacts/dsv41-l1-shape-20260915/dataset/dataset-manifest.json').read_text())['samples'];row=next(r for r in rows if r['id']=='general-zh-train-20');checks=[]
for top,block in [(2,1),(4,4)]:
 reference=None
 for variant in ['copy','swap']:
  out=root/f'burst-top{top}-block{block}-{variant}'
  cmd=[sys.executable,'experiments/dsv41_mlx/run.py','--prompt-json',row['fixture'],'--output',str(out),'--decode','32','--prefill-slots','64','--logits-mode','hash','--l1-policy','eviction_dual','--burst-top',str(top),'--block-layers',str(block)]
  if variant=='copy':cmd+=['--promotion-copy']
  if not (out/'manifest.json').exists():
   with out.with_suffix('.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
  m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete'
  signature=[m[k] for k in ['generated_ids','logits_sha256','cache_stats','expert_total_read_bytes','burst']]+[m['adaptive_l1']['per_layer_counts'],m['adaptive_l1']['bank_fence_calls']]
  if reference is None:reference=signature
  assert signature==reference,(top,block,'parity')
  if variant=='swap':assert m['adaptive_l1']['promotion_reuse']['copied_bytes']==0 and m['adaptive_l1']['slot_swap_promotions']['experts']>0
  checks.append(dict(top=top,block=block,variant=variant,exact=True,peak=m['sampled_physical_footprint_peak_bytes']))
(root/'burst-check.json').write_text(json.dumps(checks,indent=2));print(json.dumps(checks))
