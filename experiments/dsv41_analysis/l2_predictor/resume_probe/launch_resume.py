"""Always GPU-stop/continue experiment; no packet admission or fallback."""
import argparse,os,subprocess,sys
from pathlib import Path
repo=Path(__file__).resolve().parents[4]
p=argparse.ArgumentParser(add_help=False)
p.add_argument('--predictor',choices=('none','state','lookahead','block6'),default='none')
p.add_argument('--segment-layers',type=int,choices=(2,4,40),default=40)
a,rest=p.parse_known_args()
lib=repo/'artifacts/dsv41-resume-fast-mlx-build'
bridge=repo/'artifacts/dsv41-l2-fast-resume-native-build'
if not (lib/'libmlx.dylib').exists() or not list(bridge.glob('_l2_resume*.so')):
 raise SystemExit('Build the isolated fast resume backend and bridge first; see docs/dsv41f-always-resume-2026-09-17.md')
env=dict(os.environ,DYLD_LIBRARY_PATH=str(lib),L2_NATIVE_BUILD=str(bridge),L2_WINDOW_EXECUTOR='resume',L2_WINDOW_BLOCK=str(a.segment_layers),L2_WINDOW_PREDICTOR=a.predictor,DSV41_NATIVE_WINDOW='0',DSV41_NATIVE_PREFIX='1')
# Keep run_driver in this model factory; all execution uses the explicit resume mode.
cmd=[sys.executable,str(Path(__file__).with_name('entry.py')),*rest,'--inference-mode','legacy']
raise SystemExit(subprocess.call(cmd,cwd=repo,env=env))
