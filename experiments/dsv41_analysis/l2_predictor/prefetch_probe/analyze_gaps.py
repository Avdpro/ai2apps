"""Decompose true miss coverage without counting late data as timely."""
import argparse,json
from pathlib import Path
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);a=ap.parse_args()
f=json.loads((a.run/'prefetch.json').read_text());probe=json.loads((a.run/'probe.json').read_text());block=int(probe['mode'][5:]);z=np.load(a.run/'routing.npz');resident=z['resident'];actual=z['actual'];pred=np.argsort(z['predictions'],axis=-1)[...,-6:]
records={(r['step']-1,r['layer']):r for r in f['records']};reads={(r['step']-1,r['layer'],r['expert']) for r in f['reads']};rows=[]
for t in range(len(actual)):
 for l in range(40):
  misses={int(e) for e in actual[t,l] if not resident[t,l,e]};predicted=misses&set(map(int,pred[t,l]));loaded={e for e in predicted if (t,l,e) in reads};r=records.get((t,l),dict(requested=0,timely=0,late=0,foreground=0));assert len(misses)==r['requested']
  assert len(loaded)==r['timely']+r['late']
  rows.append(dict(layer=l,offset=l%block,misses=len(misses),prediction_error=len(misses-predicted),predicted_not_read=len(predicted-loaded),timely=r['timely'],late=r['late']))
keys=['misses','prediction_error','predicted_not_read','timely','late']
def group(rows):
 out={k:sum(r[k] for r in rows) for k in keys};assert out['misses']==sum(out[k] for k in keys[1:]);out['timely_coverage']=out['timely']/max(out['misses'],1);return out
result=dict(total=group(rows),by_offset={str(i):group([r for r in rows if r['offset']==i]) for i in range(block)},by_layer={str(i):group([r for r in rows if r['layer']==i]) for i in range(40)},budget_exhausted_tokens=sum(r['reserved_reads']==64 for r in f['tokens']),tokens=len(actual),scope='Development diagnostic; predicted_not_read may be cancellation or request-budget loss and is not causally separated by old records.')
(a.run/'gap-analysis.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='by_layer'},indent=2))
