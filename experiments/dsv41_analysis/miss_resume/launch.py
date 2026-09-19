"""Opt-in isolated Decode controller; all ordinary runner options pass through."""
import argparse,os,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(add_help=False);p.add_argument('--resume-block',type=int,choices=(1,2,4,40),default=4);p.add_argument('--resume-burst-top',type=int,choices=(2,4));p.add_argument('--resume-eager-control',action='store_true');p.add_argument('--resume-mode',choices=('auto','packet','guarded','window'),default='packet');p.add_argument('--resume-stress-all-miss',action='store_true',help='Diagnostic: really reload all six experts at every layer');args,rest=p.parse_known_args()
root=Path(__file__).resolve().parents[3];env=os.environ.copy();env['DYLD_LIBRARY_PATH']=str(root/'artifacts/dsv41-miss-resume-mlx-build');env['DSV41_RESUME_STRESS_ALL_MISS']='1' if args.resume_stress_all_miss else '0';env['DSV41_RESUME_MODE']=args.resume_mode;env['DSV41_RESUME_BLOCK']=str(args.resume_block);env['DSV41_RESUME_BURST']=str(args.resume_burst_top or 0);env['DSV41_RESUME_EAGER']='1' if args.resume_eager_control else '0'
raise SystemExit(subprocess.call([sys.executable,str(Path(__file__).with_name('entry.py')),*rest],env=env,cwd=root))
