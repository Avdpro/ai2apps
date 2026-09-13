import json,sys
from pathlib import Path
import native_mx,metal_expert,run_native_mx

def main():
    native_mx.expert=metal_expert.expert
    try:run_native_mx.main()
    finally:
        p=Path(sys.argv[sys.argv.index('--output')+1])/'manifest.json'
        if p.exists():
            r=json.loads(p.read_text());r['native_mx']['scope']='diagnostic native FP8 only; original routed expert kernel';p.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
