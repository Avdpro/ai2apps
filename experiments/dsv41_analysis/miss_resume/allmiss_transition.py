"""Diagnostic seed: simulate entering a window after a preceding all-hit token."""
import os,sys,json
from pathlib import Path
here=Path(__file__).parent;root=here.resolve().parents[2]
sys.path[:0]=[str(root/'experiments/dsv41_mlx'),str(root/'artifacts/dsv41-miss-resume-native-build'),str(here)]
from packet import PacketMixin
original=PacketMixin.__init__
def seeded(self,*a,**kw):
    original(self,*a,**kw);self.window_ready=True
PacketMixin.__init__=seeded
import entry
p=entry.settings['output']/'manifest.json';d=json.loads(p.read_text());d['diagnostic_seeded_window_ready']=True;p.write_text(json.dumps(d,indent=2))
