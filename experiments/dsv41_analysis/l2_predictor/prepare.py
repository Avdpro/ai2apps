"""Freeze an instrumented diagnostic runner; production forward is untouched."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path('artifacts/dsv41-l2-predictor-20260915');ROOT.mkdir(exist_ok=True)
src=ROOT/'source'
if not src.exists():
 for sub in ['dsv41_mlx','dsv41_reference']:
  shutil.copytree(Path('experiments')/sub,src/'experiments'/sub,ignore=shutil.ignore_patterns('__pycache__'))
 (src/'artifacts').symlink_to(Path('artifacts').resolve(),target_is_directory=True)
 p=src/'experiments/dsv41_mlx/model.py';s=p.read_text();s=s.replace('        ids=mx.argsort(scores+bias,axis=-1)',"        self.emit(f'layers.{l}.l2_rank',scores+bias)\n        ids=mx.argsort(scores+bias,axis=-1)",1);s=s.replace("        h=self.s.embedding('embed',ids)","        h=self.s.embedding('embed',ids)\n        self.emit('l2_embedding',h)",1);s=s.replace("        logits=h[:,-1].astype(mx.float32)","        self.emit('l2_final',h[:,-1])\n        logits=h[:,-1].astype(mx.float32)",1);p.write_text(s)
 shutil.copy2('experiments/dsv41_analysis/l2_predictor/collect_entry.py',src/'experiments/dsv41_mlx/collect_entry.py')
(ROOT/'source-hashes.json').write_text(json.dumps({str(p.relative_to(src)):hashlib.sha256(p.read_bytes()).hexdigest() for p in src.rglob('*.py')},indent=2))
data=json.loads(Path('artifacts/dsv41-l1-shape-20260915/dataset/dataset-manifest.json').read_text())
selected=[]
for split in ['train','validation']:
 for scope in ['general','coding']:
  selected.append(next(r for r in data['samples'] if r['split']==split and r['scope']==scope and r['language']=='en' and r['kind']=='scope'))
(ROOT/'pilot-plan.json').write_text(json.dumps({'samples':selected,'all_samples':data['samples'],'schema':'dsv41.l2-supervision/v1','alignment':'previous final-normalized hidden + current actual token embedding -> current forward layers5:40 routing'},indent=2))
print([(r['id'],r['split'],r['family_id']) for r in selected])
