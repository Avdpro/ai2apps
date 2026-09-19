"""Forward-only full-token Metal continuation; exact Top6, no L2 predictor."""
import os,subprocess,sys
from pathlib import Path
repo=Path(__file__).resolve().parents[4]
env=dict(os.environ,DYLD_LIBRARY_PATH=str(repo/'artifacts/dsv41-resume-replay-mlx-build'),L2_NATIVE_BUILD=str(repo/'artifacts/dsv41-l2-replay-resume-native-build'),L2_CAPTURE_REPLAY='1',L2_WINDOW_EXECUTOR='resume',L2_WINDOW_BLOCK='40',L2_WINDOW_PREDICTOR='none',DSV41_NATIVE_WINDOW='0',DSV41_NATIVE_PREFIX='1')
raise SystemExit(subprocess.call([sys.executable,str(Path(__file__).with_name('entry.py')),*sys.argv[1:],'--inference-mode','legacy'],cwd=repo,env=env))
