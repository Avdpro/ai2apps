import argparse,json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=root/'artifacts/dsv41-multiturn-ssd');args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False)
image_root=root/'artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/inference/examples/images'
def image(name):return {'type':'image_url','image_url':{'url':str(image_root/name)}}
cases={
 'text':['我的代号是青松，我养了一只叫团子的猫。请只回复“记住了”。','我准备周六上午九点带它去体检。请只回复“记住了”。','我的代号、猫的名字、体检时间分别是什么？请用一句话回答。'],
 'vision':[[image('carrots.jpeg'),{'type':'text','text':'请记住这张图为图片A。请说出图中的食材。'}],'刚才图片A里的食材是什么？请只回答名称。',[image('corn.jpeg'),{'type':'text','text':'这是图片B。请按A、B顺序列出两张图片中的食材，不要交换顺序。'}],'刚才A和B哪个是玉米？请只回答图片字母。']}
for case,turns in cases.items():
 messages=[]
 for i,question in enumerate(turns):
  messages.append(dict(role='user',content=question));path=out/f'{case}-{i+1}-messages.json';path.write_text(json.dumps(messages,ensure_ascii=False,indent=2))
  target=out/f'{case}-{i+1}'
  cmd=[sys.executable,'experiments/dsv41_mlx/run.py','--messages-json',str(path),'--stop-at-eos','--decode','64','--prefill-slots','64','--vision-max-tokens','256','--output',str(target)]
  with (out/f'{case}-{i+1}.log').open('w') as log:subprocess.run(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
  m=json.load(open(target/'manifest.json'));assert m['status']=='complete'
  answer=m['generated_text'].split('<｜end▁of▁sentence｜>')[0];messages.append(dict(role='assistant',content=answer))
  print(case,i+1,'tokens',len(m['input_ids']),'peak',m['sampled_physical_footprint_peak_bytes']/1e9,'answer',answer,flush=True)
 (out/f'{case}-transcript.json').write_text(json.dumps(messages,ensure_ascii=False,indent=2))
