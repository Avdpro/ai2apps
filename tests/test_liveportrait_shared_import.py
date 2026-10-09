"""The shared motion pipeline must not initialize MLX just to import its math."""
import subprocess
import sys
from pathlib import Path


def test_shared_pipeline_import_does_not_require_mlx():
    root=Path(__file__).resolve().parents[1]
    program='''
import importlib.abc, sys
class DenyMLX(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'mlx' or fullname.startswith('mlx.'):
            raise AssertionError('Unexpected MLX import: '+fullname)
sys.meta_path.insert(0,DenyMLX())
sys.path.insert(0,sys.argv[1])
from mlx_liveportrait.native_liveportrait import NativeMLXLivePortrait
from mlx_liveportrait.detector import MLXYuNet
import numpy as np
zero=np.zeros((1,1),dtype=np.float32)
assert np.array_equal(NativeMLXLivePortrait._rotation_matrix(zero,zero,zero),np.eye(3,dtype=np.float32)[None])
'''
    subprocess.run([sys.executable,'-c',program,str(root/'packages/omlx-model-liveportrait/src')],cwd=root,check=True,capture_output=True,text=True)
