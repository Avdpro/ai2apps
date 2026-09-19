import json,subprocess,sys
from pathlib import Path
from tokenizers import Tokenizer
root=Path(__file__).resolve().parents[2];cp=root/'artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD';images=cp/'inference/examples/images'
cases=[('carrots1024',['--image',str(images/'carrots.jpeg'),'--vision-max-tokens','1024','--prompt','请简短说明图片里是什么食材。']),('two1024',['--image',str(images/'carrots.jpeg'),'--image',str(images/'corn.jpeg'),'--vision-max-tokens','1024','--prompt','请按第一张、第二张的顺序，说出图里的食材。'])]
for name,flags in cases:
 out=root/f'artifacts/dsv41-vision-{name}-20260913'
 cmd=[sys.executable,'experiments/dsv41_mlx/run.py','--decode','32','--prefill-slots','64','--output',str(out)]+flags
 with open('/tmp/dsv41-vision-'+name+'.log','w') as log:subprocess.run(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
 m=json.load(open(out/'manifest.json'));assert m['status']=='complete';print(name,len(m['input_ids']),m['sampled_physical_footprint_peak_bytes']/1e9,m['generated_text'],flush=True)
# Text of exactly the same token count as the larger single image input.
m=json.load(open(root/'artifacts/dsv41-vision-carrots1024-20260913/manifest.json'));n=len(m['input_ids'])
tok=Tokenizer.from_file(str(cp/'tokenizer.json'));base=json.load(open(root/'experiments/dsv41_analysis/fixtures/prefill2048.json'))
ids=base['input_ids'][:n];prompt=tok.decode(ids,skip_special_tokens=False);assert tok.encode(prompt).ids==ids
fixture=root/'artifacts/dsv41-vision-matched-text-prompt.json';fixture.write_text(json.dumps(dict(prompt=prompt,input_ids=ids)))
for name,fixture_path in [('matched-text',fixture),('text-regression',root/'experiments/dsv41_analysis/fixtures/prefill2048.json')]:
 out=root/f'artifacts/dsv41-vision-{name}-20260913';cmd=[sys.executable,'experiments/dsv41_mlx/run.py','--decode','32','--prefill-slots','64','--prompt-json',str(fixture_path),'--output',str(out)]
 with open('/tmp/dsv41-vision-'+name+'.log','w') as log:subprocess.run(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
 m=json.load(open(out/'manifest.json'));assert m['status']=='complete';print(name,len(m['input_ids']),m['sampled_physical_footprint_peak_bytes']/1e9,flush=True)
