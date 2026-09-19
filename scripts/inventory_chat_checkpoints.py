#!/usr/bin/env python3
"""Read-only manifest inventory for the chat checkpoint migration."""
import argparse,json
from pathlib import Path
import yaml

def inventory(root):
    rows=[]
    for p in sorted((root/'packages').glob('*/service.yaml')):
        d=yaml.safe_load(p.read_text())
        for m in d.get('models',[]):
            if not set(m.get('capabilities',[])) & {'conversation','work'}:continue
            w=m.get('weights',{});prep=w.get('preparation',{})
            rows.append({'package_source':str(p.parent.relative_to(root)),'service_id':d['id'],'package_version':str(d['version']),
                         'model_id':m['id'],'source_repo':w.get('repo_id'),'source_revision':w.get('revision'),
                         'distribution_id':w.get('distribution_id'),'family':prep.get('family',m.get('metadata',{}).get('family')),
                         'migration':'ssd_ready' if prep.get('family') else 'byte_identical_mirror',
                         'execution_modes':prep.get('execution_modes',[]),'runtime':d.get('runtime',{}).get('provider'),
                         'status':'pending','target_repo':None,'target_revision':None,'target_distribution':None})
    return {'schema':'ai2apps.chat-checkpoint-migration/v1','models':rows}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    with a.output.open('x') as f:json.dump(inventory(a.root),f,indent=2,ensure_ascii=False)
