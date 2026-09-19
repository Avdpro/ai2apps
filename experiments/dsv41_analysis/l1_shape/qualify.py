"""Full logits and step-event parity on long cases; separate F_NOCACHE controls."""
import json,os,signal,subprocess,sys
from batch import ROOT,DATA,run_sample,pause_uploads
from replay import verify

def main():
    data=json.loads(DATA.read_text());shape=ROOT/'candidate/frozen.json';caps=json.loads(shape.read_text())['capacities']
    rows=[next(r for r in data['samples'] if r['split']=='validation' and r['language']==lang and r['kind']=='synthetic_evidence_long') for lang in ('zh','en')]
    paused=pause_uploads();report=[]
    try:
        for row in rows:
            base=run_sample(row,'qualification40',capture=True,full_logits=True,decode=512)
            candidate=run_sample(row,'qualification-shape',shape=shape,capture=True,full_logits=True,decode=512)
            assert base['generated_ids']==candidate['generated_ids'] and base['logits_sha256']==candidate['logits_sha256'],('full precision',row['id'])
            for label,capacity in [('qualification40',40),('qualification-shape',caps)]:
                report.append({'id':row['id'],'label':label,**verify(ROOT/label/(row['id']+'-r0'),capacity)})
            for repeat in range(2):
                for label in (['40','shape'] if repeat==0 else ['shape','40']):
                    r=run_sample(row,'nocache-'+label,shape=shape if label=='shape' else None,capture=False,no_cache=True,repeat=repeat,decode=128)
                    assert r['logits_sha256']==base['logits_sha256'][:len(r['logits_sha256'])],('nocache precision',row['id'])
            (ROOT/'qualification.json').write_text(json.dumps(report,indent=2))
        persistent=[]
        for language in ['zh','en']:
            records=[]
            for variant in ['40','shape']:
                with (ROOT/f'persistent-{language}-{variant}.log').open('a') as log:
                    subprocess.run([sys.executable,'experiments/dsv41_analysis/l1_shape/persistent.py','--language',language,'--variant',variant],stdout=log,stderr=subprocess.STDOUT,check=True)
                out=ROOT/f'persistent-{language}-{variant}'
                record=json.loads((out/'manifest.json').read_text());assert record['status']=='complete';records.append(record)
                persistent.append({'language':language,'variant':variant,**verify(out,40 if variant=='40' else caps)})
            assert records[0]['logits_sha256']==records[1]['logits_sha256'] and records[0]['generated_ids']==records[1]['generated_ids'],('persistent precision',language)
        (ROOT/'persistent-qualification.json').write_text(json.dumps(persistent,indent=2))
    finally:
        for pid in paused:
            try:os.kill(pid,signal.SIGCONT)
            except ProcessLookupError:pass
if __name__=='__main__':main()
