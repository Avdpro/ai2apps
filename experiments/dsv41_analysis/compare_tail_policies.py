import json,hashlib
from pathlib import Path
import numpy as np
from safetensors.numpy import load_file
ROOT=Path(__file__).resolve().parents[2]

def comparison(ref,candidate):
 a=json.loads((ref/'manifest.json').read_text());b=json.loads((candidate/'manifest.json').read_text());forced='decode_input_ids' in b
 assert a['status']==b['status']=='complete' and a['input_ids']==b['input_ids']
 n=min(len(a['generated_ids']),len(b['generated_ids']));steps=[]
 if forced:assert b['decode_input_ids']==a['generated_ids'][:n-1]
 for i in range(n):
  name=f'{i:02d}_logits.safetensors'
  for p,m in [(ref,a),(candidate,b)]:assert hashlib.sha256((p/name).read_bytes()).hexdigest()==m['trace_files'][name]
  x,y=[load_file(str(p/name))['logits'].astype(np.float64).reshape(-1) for p in [ref,candidate]]
  assert np.isfinite(y).all()
  lx=x-x.max();lx-=np.log(np.exp(lx).sum());ly=y-y.max();ly-=np.log(np.exp(ly).sum())
  steps.append(dict(step=i,same_context=forced or a['generated_ids'][:i]==b['generated_ids'][:i],kl=float(np.sum(np.exp(lx)*(lx-ly))),rmse=float(np.sqrt(np.mean((x-y)**2))),top1_equal=int(x.argmax())==int(y.argmax()),max_abs=float(np.max(np.abs(x-y)))))
 valid=[s for s in steps[1:] if s['same_context']]
 return dict(reference=str(ref),candidate=str(candidate),teacher_forced=forced,generated_ids_equal=a['generated_ids']==b['generated_ids'],same_context_decode_steps=len(valid),mean_kl=float(np.mean([s['kl'] for s in valid])),max_kl=max(s['kl'] for s in valid),top1_match=sum(s['top1_equal'] for s in valid)/len(valid),mean_rmse=float(np.mean([s['rmse'] for s in valid])),prefill_max_abs=steps[0]['max_abs'],steps=steps)

if __name__=='__main__':
 reports={}
 for label in ['128','code','zh']:
  ref=ROOT/('artifacts/dsv41-default-dynamic128-20260913' if label=='128' else f'artifacts/dsv41-tail-{label}-exact-20260913')
  for policy in ['zero','fixed-top','renorm']:
   r=comparison(ref,ROOT/f'artifacts/dsv41-tail-{label}-{policy}-20260913');reports[label+'-'+policy]=r
   print(label,policy,'same_context',r['same_context_decode_steps'],'meanKL',r['mean_kl'],'maxKL',r['max_kl'],'Top1',r['top1_match'],'prefill max',r['prefill_max_abs'])
 (ROOT/'artifacts/dsv41-tail-comparisons-20260913.json').write_text(json.dumps(reports,indent=2))
