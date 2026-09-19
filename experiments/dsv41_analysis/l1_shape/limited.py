"""User-requested reduced performance check; five cases, twenty paired runs."""
import hashlib,json,os,signal,time
from batch import ROOT,DATA,run_sample,pause_uploads

def main():
    selection_path=ROOT/'limited-selection.json'
    data=json.loads(DATA.read_text());shape=ROOT/'candidate/frozen.json'
    frozen_sha=hashlib.sha256(shape.read_bytes()).hexdigest()
    if not selection_path.exists():
        completed={p.parent.name.rsplit('-r',1)[0] for label in ['test-main40','test-shape'] for p in (ROOT/label).glob('*/manifest.json') if json.loads(p.read_text())['status']=='complete'}
        rows=[r for r in data['samples'] if r['id'] in completed]
        assert len(rows)==3 and all(r['split']=='test' for r in rows)
        scopes={r['scope'] for r in rows}
        for language in ['zh','en']:
            choices=[r for r in data['samples'] if r['split']=='test' and r['kind']=='synthetic_evidence_long' and r['language']==language and r['scope'] not in scopes]
            chosen=min(choices,key=lambda r:hashlib.sha256(('limited-length:'+r['id']).encode()).hexdigest())
            rows.append(chosen);scopes.add(chosen['scope'])
        selection={'reason':'User judged 240-run performance test excessive; reuse three started cases and add two approximately2048 cases in unused scopes, one per language, selected by fixed ID hash without timing metrics. No full statistical adoption claim.','candidate_sha256':frozen_sha,'ids':[r['id'] for r in rows],'selected_at':time.time(),'expected_runs':20}
        selection_path.write_text(json.dumps(selection,indent=2))
    selection=json.loads(selection_path.read_text());assert frozen_sha==selection['candidate_sha256']
    rows=[next(r for r in data['samples'] if r['id']==ident) for ident in selection['ids']]
    state={'status':'running','case_ids':selection['ids'],'completed_runs':0};paused=pause_uploads()
    try:
        for index,row in enumerate(rows):
            baseline=None
            for repeat in range(2):
                for variant in (['main40','shape'] if (index+repeat)%2==0 else ['shape','main40']):
                    m=run_sample(row,'test-'+variant,shape=shape if variant=='shape' else None,capture=False,repeat=repeat)
                    if baseline is None:baseline=m
                    assert m['input_ids']==baseline['input_ids'] and m['generated_ids']==baseline['generated_ids'] and m['logits_sha256']==baseline['logits_sha256'],row['id']
                    state['completed_runs']+=1
                    (ROOT/'limited-state.json').write_text(json.dumps(state,indent=2))
        state['status']='complete'
    except BaseException as e:state.update(status='failed',error=repr(e));raise
    finally:
        state['updated']=time.time();(ROOT/'limited-state.json').write_text(json.dumps(state,indent=2))
        for pid in paused:
            try:os.kill(pid,signal.SIGCONT)
            except ProcessLookupError:pass

if __name__=='__main__':main()
