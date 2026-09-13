"""Teacher-forced evaluation on a recorded exact-model continuation."""
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dsv41_mlx'))
import mlx.core as mx
import run
from burst import BurstModel
ix=sys.argv.index('--reference');reference=Path(sys.argv[ix+1]);del sys.argv[ix:ix+2]
r=json.loads((reference/'manifest.json').read_text());assert r['status']=='complete'
original=BurstModel.__call__;step=0

def forward(self,ids,start=0):
    global step
    if start:
        ids=mx.array([[r['generated_ids'][step]]],dtype=mx.int32);step+=1
    return original(self,ids,start)
BurstModel.__call__=forward
run.main()
out=Path(sys.argv[sys.argv.index('--output')+1]);m=json.loads((out/'manifest.json').read_text());assert m['input_ids']==r['input_ids']
m.update(evaluation_mode='teacher-forced; generated IDs are per-step predictions, not a free-running completion',replay_reference=str(reference),decode_input_ids=r['generated_ids'][:step],probe_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(out/'manifest.json').write_text(json.dumps(m,indent=2))
