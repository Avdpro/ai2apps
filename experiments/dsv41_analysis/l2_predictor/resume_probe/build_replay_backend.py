"""Reproducibly build the opt-in replay backend from existing pinned MLX assets."""
from pathlib import Path
import hashlib,shutil,subprocess,sys
repo=Path(__file__).resolve().parents[4]
def run(cmd):subprocess.run([str(x) for x in cmd],cwd=repo,check=True)
run([sys.executable,Path(__file__).with_name('prepare_replay_backend.py')])
src=repo/'artifacts/dsv41-resume-replay-mlx-src';build=repo/'artifacts/dsv41-resume-replay-mlx-build';old=repo/'artifacts/dsv41-miss-resume-mlx-build';fast=repo/'artifacts/dsv41-resume-fast-mlx-src'
# Reuse generated JIT sources only when the mathematical kernel inputs are equal.
for p in (src/'mlx/backend/metal/kernels').rglob('*'):
 if p.is_file():assert p.read_bytes()==(fast/p.relative_to(src)).read_bytes(),p
run(['cmake','-S',src,'-B',build,'-DMLX_BUILD_TESTS=OFF','-DMLX_BUILD_EXAMPLES=OFF','-DBUILD_SHARED_LIBS=ON','-DMLX_METAL_JIT=OFF','-DMLX_USE_EXISTING_METALLIB=ON',f'-DMLX_METAL_PATH={repo}/.venv/lib/python3.13/site-packages/mlx/lib','-DCMAKE_BUILD_TYPE=Release',*[f'-DFETCHCONTENT_SOURCE_DIR_{key}={old}/_deps/{name}-src' for key,name in [('METAL_CPP','metal_cpp'),('JSON','json'),('FMT','fmt'),('GGUFLIB','gguflib')]]])
dst=build/'mlx/backend/metal/jit';dst.mkdir(parents=True,exist_ok=True)
for p in (old/'mlx/backend/metal/jit').glob('*.cpp'):shutil.copyfile(p,dst/p.name)
run(['cmake','--build',build,'-j','8'])
bridge=repo/'artifacts/dsv41-l2-replay-resume-native-build'
run(['cmake','-S',Path(__file__).parent,'-B',bridge,f'-DPython_EXECUTABLE={sys.executable}',f'-DMLX_SOURCE={src}',f'-DMLX_BUILD={build}','-DRESUME_BACKEND_ABI=icb-replay-v4-mlx0320','-DRESUME_NATIVE_SOURCE=native_replay.cpp','-DCMAKE_BUILD_TYPE=Release',f'-DCMAKE_CXX_FLAGS=-I{old}/_deps/metal_cpp-src'])
run(['cmake','--build',bridge,'-j','8'])
