"""Frozen held-out randomized AB/BA, identical route math; no sampling callback."""
import hashlib,json,random
from pathlib import Path
from batch import ROOT,DATA,run_sample,pause_uploads
import os,signal

def main():
    data=json.loads(DATA.read_text());shape=ROOT/'candidate/frozen.json'
    selection=json.loads((ROOT/'candidate/selection.json').read_text())
    assert hashlib.sha256(shape.read_bytes()).hexdigest()==selection['frozen_sha256']
    rows=[r for r in data['samples'] if r['split']=='test']
    rows.sort(key=lambda r:hashlib.sha256(('evaluation:'+r['id']).encode()).hexdigest())
    results=[];paused=pause_uploads()
    try:
        for i,row in enumerate(rows):
            baseline=None
            for repeat in range(2):
                order=['main40','shape'] if (i+repeat)%2==0 else ['shape','main40']
                for variant in order:
                    r=run_sample(row,'test-'+variant,shape=shape if variant=='shape' else None,capture=False,repeat=repeat)
                    if baseline is None:baseline=r
                    if r['generated_ids']!=baseline['generated_ids'] or r['logits_sha256']!=baseline['logits_sha256']:
                        raise RuntimeError('Numerical mismatch requires detailed re-run: '+row['id'])
                    results.append({'id':row['id'],'variant':variant,'repeat':repeat,'exact_logit_hashes':True})
            (ROOT/'test-progress.json').write_text(json.dumps(results,indent=2))
    finally:
        for pid in paused:
            try:os.kill(pid,signal.SIGCONT)
            except ProcessLookupError:pass
if __name__=='__main__':main()
