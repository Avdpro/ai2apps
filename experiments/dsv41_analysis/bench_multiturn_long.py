import json,subprocess,sys
from pathlib import Path
root=Path('artifacts/dsv41-multiturn-20260913');messages=[]
questions=['我的名字是林舟，旅行目的地是成都，出发时间是周六上午九点。'+('这是一段用于测试上下文记忆的背景文字，与个人信息无关。'*14)+'请只回复“记住了”。','把出发时间改为周日下午三点。我的名字、目的地和最新出发时间分别是什么？请用一句话回答。']
for i,q in enumerate(questions,1):
 messages.append(dict(role='user',content=q));path=root/f'text-long-{i}-messages.json';path.write_text(json.dumps(messages,ensure_ascii=False,indent=2))
 cmd=[sys.executable,'experiments/dsv41_mlx/run.py','--messages-json',str(path),'--stop-at-eos','--decode','64','--prefill-slots','64','--output',str(root/f'text-long-{i}')]
 with (root/f'text-long-{i}.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
 m=json.load(open(root/f'text-long-{i}/manifest.json'));assert m['status']=='complete';answer=m['generated_text'].split('<｜end▁of▁sentence｜>')[0];messages.append(dict(role='assistant',content=answer));print(i,len(m['input_ids']),answer,flush=True)
(root/'text-long-transcript.json').write_text(json.dumps(messages,ensure_ascii=False,indent=2))
with (root/'kv-text-long-1-2.log').open('w') as log:subprocess.run([sys.executable,'experiments/dsv41_analysis/audit_multiturn_kv.py','--case','text-long','--first','1','--last','2'],stdout=log,stderr=subprocess.STDOUT,check=True)
