"""Device-side routed expert reduction for Prefill and Decode."""
import hashlib,json,sys
from pathlib import Path
import mlx.core as mx
import run_metal_moe,run_device_prefill
stats=dict(calls=0,host_result_elements=0,previous_host_elements=0)
def reduce(out):
    y=mx.zeros((out.shape[-1],),dtype=mx.float32)
    for i in range(out.shape[0]):y=y+out[i].astype(mx.float32)
    stats['calls']+=1;stats['host_result_elements']+=out.shape[-1];stats['previous_host_elements']+=out.size
    return y

def main():
    output=Path(sys.argv[sys.argv.index('--output')+1]);run_metal_moe.decode_reducer=reduce
    try:run_device_prefill.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['device_decode']={'statistics':stats,'scope':'ordered FP32 sum of all original expert outputs on GPU before host transfer; router still CPU','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
