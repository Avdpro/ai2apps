"""ABBA copy versus logical-slot exchange: same policy and logical cache events."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path('artifacts/dsv41-slot-swap-20260915');ROOT.mkdir(exist_ok=True)
rows={r['id']:r for r in json.loads(Path('artifacts/dsv41-l1-shape-20260915/dataset/dataset-manifest.json').read_text())['samples']};results=[]
def logical_promotions(m):return [(p['step'],p['layer'],[pair[:2] for pair in p['pairs']]) for p in m['adaptive_l1']['promotions']]
for name in ['coding-en-train-18','long-math_logic-zh-test']:
 row=rows[name];reference=None
 for repeat in range(2):
  for variant in (['copy','swap'] if repeat==0 else ['swap','copy']):
   out=ROOT/f'{name}-{variant}-{repeat}'
   cmd=[sys.executable,'experiments/dsv41_mlx/run.py','--prompt-json',row['fixture'],'--output',str(out),'--decode',str(row['decode_steps']),'--prefill-slots','64','--logits-mode','hash','--l1-policy','eviction_dual']
   if variant=='copy':cmd+=['--promotion-copy']
   if not (out/'manifest.json').exists():
    with out.with_suffix('.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
   m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete'
   signature=[m[k] for k in ['input_ids','generated_ids','logits_sha256','cache_stats','expert_total_read_bytes']]+[logical_promotions(m),m['adaptive_l1']['per_layer_counts'],m['adaptive_l1']['bank_fence_calls']]
   if reference is None:reference=signature
   assert signature==reference,(name,variant,'exact/logical parity')
   assert m['sampled_physical_footprint_peak_bytes']<65e9
   a=m['adaptive_l1'];n=sum(len(p['pairs']) for p in a['promotions'])
   if variant=='swap':assert a['promotion_reuse']['copied_bytes']==0 and a['slot_swap_promotions']['experts']==n and n>0
   r=dict(case=name,repeat=repeat,variant=variant,tps=(len(m['step_seconds'])-1)/sum(m['step_seconds'][1:]),read_bytes=m['expert_total_read_bytes'],peak=m['sampled_physical_footprint_peak_bytes'],adaptive=a,cache_readbacks=40*row['decode_steps']+(40*row['decode_steps']-m['cache_stats']['all_hit_steps']))
   results.append(r);(ROOT/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps({k:v for k,v in r.items() if k!='adaptive'}),flush=True)
(ROOT/'complete.json').write_text(json.dumps(dict(runs=8,exact_logits=True,logical_cache_parity=True,identical_readbacks_and_fences=True,zero_promotion_copy=True)))
