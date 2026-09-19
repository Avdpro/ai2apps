"""Apply only to the pinned, isolated MLX source checkout; never to site-packages."""
from pathlib import Path
import subprocess,sys
COMMIT='7a1d4f5c12ac82f4b4d0a6e71538d89ca0605247'
root=Path(sys.argv[1]).resolve();patch=Path(__file__).with_name('mlx0320-miss-resume.patch').resolve()
head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
if head!=COMMIT:raise SystemExit('Refusing patch: MLX source commit does not match '+COMMIT)
base=['git','-C',str(root),'apply']
if subprocess.run([*base,'--reverse','--check',str(patch)],capture_output=True).returncode==0:
    print('Exact patch already applied')
else:
    subprocess.run([*base,'--check',str(patch)],check=True)
    subprocess.run([*base,str(patch)],check=True)
