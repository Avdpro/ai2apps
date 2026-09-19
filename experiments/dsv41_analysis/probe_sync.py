"""Diagnostic A/B: remove per-layer output eval, retain router/I/O safety waits."""
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dsv41_mlx'))
import run
KEEP='--keep-layer-eval' in sys.argv
if KEEP:
    sys.argv.remove('--keep-layer-eval')
    sys.argv.append('--layer-progress')
if '--trace' in sys.argv:raise ValueError('Timing probe must not use --trace')
class Probe(run.Model):
    def emit(self,name,x):
        if not KEEP and len(name.split('.'))==2:return
        return super().emit(name,x)
    def close(self):
        super().close()
        out=Path(sys.argv[sys.argv.index('--output')+1]);(out/'sync-probe.json').write_text(json.dumps(dict(layer_output_eval=KEEP,router_and_loader_safety_waits='unchanged',budget='20 ms sampling; step-boundary guard; per-layer guard omitted when output eval disabled',source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2))
run.Model=Probe
run.main()
