import json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[2];reports=[]
for name in ['carrots256','carrots1024','two1024','matched-text','text-regression']:
 p=root/f'artifacts/dsv41-vision-{name}-20260913';m=json.loads((p/'manifest.json').read_text());assert m['status']=='complete' and m['torch_imported'] is False
 for filename,h in m['trace_files'].items():assert hashlib.sha256((p/filename).read_bytes()).hexdigest()==h
 r=dict(name=name,manifest=str(p/'manifest.json'),manifest_sha256=hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest(),tokens=len(m['input_ids']),decode_steps=m['decode_forwards'],peak_gb=m['sampled_physical_footprint_peak_bytes']/1e9,image_inputs=m.get('image_inputs',[]),vision_weight_bytes=m.get('vision_weight_bytes',0),first_completion=m['generated_text'].split('<｜end▁of▁sentence｜>')[0])
 if m.get('vision_stages'):
  stages=m['vision_stages'];r['weight_load_footprint_delta_gb']=(stages[1]['footprint_bytes']-stages[0]['footprint_bytes'])/1e9;r['decode_final_footprint_gb']=stages[-1]['footprint_bytes']/1e9;r['stages']=stages
 reports.append(r)
summary=dict(runs=reports,matched_single_image_peak_increase_gb=reports[1]['peak_gb']-reports[3]['peak_gb'],scope='MLX text+vision experiment; initial vision run manifests retain an obsolete generic no-vision scope label; images/config/vision_stages and this summary describe actual execution. No video or production integration.')
(root/'artifacts/dsv41-vision-summary-20260913.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print('single image peak increase GB',summary['matched_single_image_peak_increase_gb'])
