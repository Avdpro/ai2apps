"""Owner-owned extraction, try-on and product photography prompt contract."""
from functools import lru_cache
import json
from pathlib import Path

@lru_cache(maxsize=1)
def contract():
    return json.loads((Path(__file__).resolve().parents[1]/'web/static/data/imagine_workflows.json').read_text())


def compose(mini, values):
    c=contract(); prompt=values.get('prompt','').strip()
    if mini.endswith('extract-items'):
        spec=c['extract'];target=values.get('target','outfit')
        text=values.get('target_description','').strip() if target=='custom' else spec['targets'][target]
        parts=[spec['base'],'Target: '+text+'.',spec['rules'],prompt]
    elif mini.endswith('try-on'):
        spec=c['try_on']
        pose=values.get('pose','keep');bg=values.get('background','keep')
        parts=[spec['base'],spec['interaction'][values.get('interaction','wear')],
            'Pose: '+(values.get('pose_description','').strip() if pose=='custom' else spec['pose'][pose]),
            'Background: '+(values.get('background_description','').strip() if bg=='custom' else spec['background'][bg]),prompt]
    else:
        spec=c['product'];scene=values.get('scene','white')
        parts=[spec['base'],'' if scene=='custom' else spec['scene'][scene],values.get('scene_description','').strip(),
               spec['light'][values.get('lighting','soft')],spec['composition'][values.get('composition','center')],
               ('Apply the following style only to the setting, not the product: '+values['setting_style']) if values.get('setting_style') else '',prompt]
    return '\n\n'.join(p for p in parts if p)
