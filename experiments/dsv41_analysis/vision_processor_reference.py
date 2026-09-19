import importlib.util,json
from pathlib import Path
from types import SimpleNamespace
from safetensors.torch import save_file
root=Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD')
spec=importlib.util.spec_from_file_location('official_processor',root/'inference/image_processor.py');p=importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name]=p;spec.loader.exec_module(p)
c=SimpleNamespace(**json.load(open(root/'inference/config.json')));c.vision_max_n_token=256
x,nh,nw,lh,lw=p.load_image({'url':str(root/'inference/examples/images/carrots.jpeg')},c)
out=Path('artifacts/dsv41-vision-processor-reference-20260913');out.mkdir(exist_ok=False)
save_file({'patches':x.float()},str(out/'patches.safetensors'));(out/'grid.json').write_text(json.dumps([nh,nw,lh,lw]))
print('Official processor reference saved')
