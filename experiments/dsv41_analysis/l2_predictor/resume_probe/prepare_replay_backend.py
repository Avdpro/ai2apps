"""Create the isolated replay backend; never alter installed MLX."""
from pathlib import Path
import shutil,subprocess
src=Path('artifacts/dsv41-resume-fast-mlx-src')
dst=Path('artifacts/dsv41-resume-replay-mlx-src')
shutil.copytree(src,dst,dirs_exist_ok=True)
patch=Path(__file__).with_name('replay-backend.patch').resolve()
subprocess.run(['patch','-p1','-i',str(patch)],cwd=dst,check=True)
print(dst)
