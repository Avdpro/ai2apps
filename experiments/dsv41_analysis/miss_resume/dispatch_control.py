import sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(root/'experiments/dsv41_mlx'),str(root/'artifacts/dsv41-miss-resume-native-build')]
import mlx.core as mx
import run
from adaptive import AdaptiveModel
import _miss_resume as native
class Control(AdaptiveModel):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.session=native.Session()
    def __call__(self,ids,start=0):
        if not start:return super().__call__(ids,start)
        self.session.begin()
        try:
            y=super().__call__(ids,start);mx.eval(y,self.cache_counters,*self.ages.values());return y
        finally:self.session.finish()
run.Model=Control
run.main()
