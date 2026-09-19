"""Build a pinned, isolated MLX backend and bridge. Does not install into .venv."""
from pathlib import Path
import importlib.metadata,subprocess,sys
root=Path(__file__).resolve().parents[3];here=Path(__file__).parent
src=root/'artifacts/dsv41-miss-resume-mlx-src';build=root/'artifacts/dsv41-miss-resume-mlx-build';native=root/'artifacts/dsv41-miss-resume-native-build'
if importlib.metadata.version('mlx')!='0.32.0':raise SystemExit('Requires the matching MLX 0.32.0 Python wheel')
def run(*args):subprocess.run([str(x) for x in args],check=True,cwd=root)
if not src.exists():run('git','clone','--depth','1','--branch','v0.32.0','https://github.com/ml-explore/mlx.git',src)
run(sys.executable,here/'patch_mlx.py',src)
metal=Path(importlib.metadata.distribution('mlx').locate_file('mlx/lib')).resolve()
run('cmake','-S',src,'-B',build,'-DMLX_BUILD_TESTS=OFF','-DMLX_BUILD_EXAMPLES=OFF','-DBUILD_SHARED_LIBS=ON','-DMLX_METAL_JIT=OFF','-DMLX_USE_EXISTING_METALLIB=ON','-DMLX_METAL_PATH='+str(metal),'-DCMAKE_BUILD_TYPE=Release')
run('cmake','--build',build,'-j','8')
run('cmake','-S',here,'-B',native,'-DPython_EXECUTABLE='+str(Path(sys.executable).absolute()),'-DMLX_SOURCE='+str(src),'-DMLX_BUILD='+str(build),'-DCMAKE_BUILD_TYPE=Release')
run('cmake','--build',native,'-j','8')
