"""Create compact expert-major records for actual routes in one baseline layer."""
import argparse,json,hashlib
from pathlib import Path
import torch
from run_reference import Store

def main():
    p=argparse.ArgumentParser();p.add_argument('--layer',type=int,default=0);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    root=Path('artifacts/dsv41-reference-baseline-20260913')
    ids=set()
    for step in range(4):
        weights,routes=torch.load(root/f'{step:02d}_layers.{a.layer}.ffn.gate.pt',weights_only=True);ids.update(routes.flatten().tolist())
    store=Store(Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD'));shapes=[];record_bytes=None
    with a.output.open('xb') as f:
        for e in sorted(ids):
            start=f.tell()
            for w in ('w1','w2','w3'):
                for part in ('weight','scale'):
                    x=store.read(f'layers.{a.layer}.ffn.experts.{e}.{w}.{part}').view(torch.uint8)
                    if len(shapes)<6: shapes.append(list(x.shape))
                    f.write(x.numpy().tobytes())
            size=f.tell()-start
            if record_bytes is not None: assert size==record_bytes
            record_bytes=size
    info={'layer':a.layer,'expert_to_record':{e:i for i,e in enumerate(sorted(ids))},'record_bytes':record_bytes,'shapes':shapes,'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()}
    Path(str(a.output)+'.json').write_text(json.dumps(info,indent=2));store.close();print(info)
if __name__=='__main__':main()
