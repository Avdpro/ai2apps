import sys,json
from pathlib import Path
sys.path.insert(0,str(Path('experiments/dsv41_mlx').resolve()))
import run
import mlx.core as mx
import numpy as np
class Profile(run.Model):
 def __init__(self,*a,**kw):
  self.routes={};original=kw.get('trace')
  def trace(name,x):
   if name.endswith('.gate'):self.routes.setdefault(int(name.split('.')[1]),[]).append(x)
   if original:original(name,x)
  kw['trace']=trace;super().__init__(*a,**kw)
 def close(self):
  mx.eval(self.cache_counters);counts=self.cache_counters.tolist();rows=[]
  for l,route in sorted(self.routes.items()):
   pre=np.array(route[0]);dec=np.concatenate([np.array(x) for x in route[1:]],axis=0);main=set(self.banks[l].main)
   overlaps=[len(set(a)&set(b)) for a,b in zip(dec[:-1],dec[1:])]
   rows.append(dict(layer=l,l1_hits=counts[l][0],l0_hits=counts[l][1],misses=counts[l][2],decode_unique=len(np.unique(dec)),prefill_unique=len(np.unique(pre)),prefill_main_coverage=float(np.isin(pre,list(main)).mean()),successive_route_overlap=float(np.mean(overlaps)),main_ids=sorted(main),decode_routes=dec.tolist()))
  out=Path(sys.argv[sys.argv.index('--output')+1]);(out/'layer-cache-profile.json').write_text(json.dumps(rows,indent=2))
  super().close()
run.Model=Profile
run.main()
