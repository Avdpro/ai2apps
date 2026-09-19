import json
from pathlib import Path
from collections import Counter
root=Path('artifacts/dsv41-l1-shape-20260915')
p=root/'pipeline.json';state=json.loads(p.read_text()) if p.exists() else {}
counts={}
for label in ['trace32','trace40','trace48','qualification40','qualification-shape','nocache-40','nocache-shape','test-main40','test-shape']:
    counts[label]=dict(Counter(json.loads(p.read_text())['status'] for p in (root/label).glob('*/manifest.json')))
counts['persistent']={}
for path in sorted(root.glob('persistent-*/manifest.json')):
    counts['persistent'][path.parent.name]=json.loads(path.read_text())['status']
print(json.dumps({'status':state.get('status'),'stage':state.get('active'),'calibration_checks':len(json.loads((root/'calibration.json').read_text())) if (root/'calibration.json').exists() else 0,'runs':counts},ensure_ascii=False))
