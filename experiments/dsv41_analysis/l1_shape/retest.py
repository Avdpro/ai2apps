"""Two additional paired repetitions for every >5% case regression; no retuning."""
import json,os,signal
from batch import ROOT,DATA,run_sample,pause_uploads

def main():
    initial=json.loads((ROOT/'results.json').read_text());ids=initial['regressions_over5pct']
    path=ROOT/'initial-test-results.json'
    if not path.exists():path.write_text(json.dumps(initial,ensure_ascii=False,indent=2))
    else:ids=json.loads(path.read_text())['regressions_over5pct']
    rows=[r for r in json.loads(DATA.read_text())['samples'] if r['id'] in ids];paused=pause_uploads()
    try:
        for row in rows:
            for repeat in (2,3):
                pair=[]
                for v in (['main40','shape'] if repeat==2 else ['shape','main40']):
                    pair.append(run_sample(row,'test-'+v,shape=ROOT/'candidate/frozen.json' if v=='shape' else None,capture=False,repeat=repeat))
                original=json.loads((ROOT/'test-main40'/(row['id']+'-r0')/'manifest.json').read_text())
                assert pair[0]['logits_sha256']==pair[1]['logits_sha256']==original['logits_sha256'],('retest parity',row['id'])
    finally:
        for pid in paused:
            try:os.kill(pid,signal.SIGCONT)
            except ProcessLookupError:pass
if __name__=='__main__':main()
