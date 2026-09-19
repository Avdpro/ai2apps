import json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[2];base=root/'artifacts/dsv41-multiturn-20260913';runs=[]
expected={('text',3):['青松','团子','周六','九点'],('text-long',2):['林舟','成都','周日','三点'],('vision',1):['胡萝卜'],('vision',2):['胡萝卜'],('vision',3):['胡萝卜','玉米'],('vision',4):['B']}
for case,count in [('text',3),('text-long',2),('vision',4)]:
 for i in range(1,count+1):
  p=base/f'{case}-{i}';m=json.load(open(p/'manifest.json'));assert m['status']=='complete' and not m['torch_imported'];assert m['generated_text'].endswith('<｜end▁of▁sentence｜>')
  for filename,h in m['trace_files'].items():assert hashlib.sha256((p/filename).read_bytes()).hexdigest()==h
  answer=m['generated_text'].split('<｜end▁of▁sentence｜>')[0]
  for word in expected.get((case,i),[]):assert word in answer,(case,i,answer)
  if case=='vision' and i==3:assert answer.index('胡萝卜')<answer.index('玉米')
  for im in m.get('image_inputs',[]):assert hashlib.sha256(Path(im['path']).read_bytes()).hexdigest()==im['sha256']
  runs.append(dict(case=case,turn=i,prompt_tokens=len(m['input_ids']),image_count=len(m.get('image_inputs',[])),answer=answer,peak_gb=m['sampled_physical_footprint_peak_bytes']/1e9,manifest_sha256=hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest()))
audits={};checks=[]
for p in base.glob('kv-*/audit.json'):
 m=json.load(open(p));audits[p.parent.name]=m
 for t in m['turns']:checks+=t['checks']
repeats={}
for name in ['text-3','vision-4']:
 r=json.load(open(base/f'{name}-repeat/comparison.json'));assert max(x['max_abs'] for x in r['steps'])==0;repeats[name]='all logits exact'
result=dict(mode='Full-history replay conversations; separate teacher-forced KV audit, no incremental new images',runs=runs,repeats=repeats,kv=dict(checked=len(checks),top1_equal=sum(x['top1_equal'] for x in checks),max_kl=max(x['kl'] for x in checks),max_abs=max(x['max_abs'] for x in checks),audits=audits))
(base/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(len(runs),'turns;',result['kv']['checked'],'KV checks;',result['kv']['top1_equal'],'Top1 matches')
