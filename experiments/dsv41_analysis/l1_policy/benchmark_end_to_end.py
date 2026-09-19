"""Direct old L1 versus complete new L1: fresh ABBA, no cross-batch inference."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path('artifacts/dsv41-l1-end-to-end-20260915');ROOT.mkdir(exist_ok=True)
data=json.loads(Path('artifacts/dsv41-l1-shape-20260915/dataset/dataset-manifest.json').read_text());rows={r['id']:r for r in data['samples']};results=[]
for name in ['coding-en-train-18','long-math_logic-zh-test']:
 row=rows[name];reference=None
 for repeat in range(2):
  for policy in (['baseline','eviction_dual'] if repeat==0 else ['eviction_dual','baseline']):
   out=ROOT/f'{name}-{policy}-{repeat}'
   cmd=[sys.executable,'experiments/dsv41_mlx/run.py','--prompt-json',row['fixture'],'--output',str(out),'--decode',str(row['decode_steps']),'--prefill-slots','64','--logits-mode','hash','--l1-policy',policy]
   if not (out/'manifest.json').exists():
    with out.with_suffix('.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
   m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete'
   assert m['l1_policy']==policy and m['promotion_reuse']
   assert m['promotion_slot_swap']==(policy=='eviction_dual')
   if policy=='eviction_dual':assert m['adaptive_l1']['promotion_reuse']['copied_bytes']==0
   signature=[m[k] for k in ['input_ids','generated_ids','logits_sha256']]
   if reference is None:reference=signature
   assert signature==reference,(name,policy,'parity')
   assert m['sampled_physical_footprint_peak_bytes']<65e9
   a=m['adaptive_l1'];steps=row['decode_steps'];miss_steps=40*steps-m['cache_stats']['all_hit_steps']
   # Existing per-layer hit flag + miss metadata + periodic legacy score readbacks.
   readbacks=40*steps+(1 if policy=='eviction_dual' else 2)*miss_steps+(0 if policy=='eviction_dual' else ((steps-1)//16)*40)
   r=dict(case=name,repeat=repeat,policy=policy,tps=(len(m['step_seconds'])-1)/sum(m['step_seconds'][1:]),read_bytes=m['expert_total_read_bytes'],peak=m['sampled_physical_footprint_peak_bytes'],adaptive=a,readbacks=readbacks,miss_steps=miss_steps)
   results.append(r);(ROOT/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps({k:v for k,v in r.items() if k!='adaptive'}),flush=True)
 for repeat in range(2):
  b=next(r for r in results if r['case']==name and r['repeat']==repeat and r['policy']=='baseline');e=next(r for r in results if r['case']==name and r['repeat']==repeat and r['policy']=='eviction_dual')
  assert e['readbacks']<=b['readbacks']
  assert e['adaptive']['bank_fence_calls']<=b['adaptive']['bank_fence_calls']
(ROOT/'complete.json').write_text(json.dumps(dict(runs=len(results),exact_logits=True,no_added_readbacks_or_fences=True)))
