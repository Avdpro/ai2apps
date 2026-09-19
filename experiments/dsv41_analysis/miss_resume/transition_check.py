"""Diagnostic: alternate packet and guarded entry to exercise state handoff.

Auto's first-miss native-tail exit is retained. This is not a TPS benchmark.
"""
import sys,json,os
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(root/'experiments/dsv41_mlx'),str(root/'artifacts/dsv41-miss-resume-native-build'),str(Path(__file__).parent)]
from packet import PacketMixin
PacketMixin.choose_guarded=lambda self,start:self.decode_step%2==1
os.environ['DSV41_RESUME_MODE']='auto';os.environ['DSV41_RESUME_EAGER']='0';os.environ['DSV41_RESUME_STRESS_ALL_MISS']='0'
import entry
p=Path(sys.argv[sys.argv.index('--output')+1])/'manifest.json';d=json.loads(p.read_text());d['miss_resume']['diagnostic_alternate_entry']=True;p.write_text(json.dumps(d,indent=2))
