"""Fresh paired measurements: grow eight selected layers without reducing any."""
import hashlib,json,os,signal,time
from pathlib import Path
import batch

ROOT=Path('artifacts/dsv41-l1-growth-20260915')
OLD=Path('artifacts/dsv41-l1-shape-20260915')
LAYERS=[19,0,23,3,15,39,13,4]

def main():
    ROOT.mkdir(exist_ok=True)
    old=json.loads((OLD/'candidate/frozen.json').read_text())
    shape={k:old[k] for k in ['family','checkpoint_index_sha256','checkpoint_manifest_sha256','dataset_manifest_sha256','hot_slots','policy']}
    shape.update(schema='dsv41.l1-shape/growth-v1',capacities=[48 if l in LAYERS else 40 for l in range(40)],grown_layers=LAYERS,selection='Previously announced eight highest training 40-to48 load savings; no layers reduced',extra_expert_payload_bytes=64*18800640)
    path=ROOT/'growth.json'
    if path.exists():assert json.loads(path.read_text())==shape
    else:path.write_text(json.dumps(shape,indent=2))
    data=json.loads(batch.DATA.read_text());selection=json.loads((OLD/'limited-selection.json').read_text());rows=[next(r for r in data['samples'] if r['id']==i) for i in selection['ids']]
    batch.ROOT=ROOT
    state={'status':'running','completed_runs':0,'expected_runs':20,'case_ids':selection['ids'],'shape_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'started':time.time()}
    paused=batch.pause_uploads()
    try:
        for index,row in enumerate(rows):
            reference=None
            for repeat in range(2):
                for variant in (['main40','growth'] if (index+repeat)%2==0 else ['growth','main40']):
                    m=batch.run_sample(row,variant,shape=path if variant=='growth' else None,capture=False,repeat=repeat)
                    if reference is None:reference=m
                    for key in ['input_ids','generated_ids','logits_sha256','source_sha256']:
                        assert m[key]==reference[key],(row['id'],key)
                    assert m['sampled_physical_footprint_peak_bytes']<=65_000_000_000
                    state['completed_runs']+=1
                    (ROOT/'state.json').write_text(json.dumps(state,indent=2))
        state['status']='complete'
    except BaseException as e:state.update(status='failed',error=repr(e));raise
    finally:
        state['updated']=time.time();(ROOT/'state.json').write_text(json.dumps(state,indent=2))
        for pid in paused:
            try:os.kill(pid,signal.SIGCONT)
            except ProcessLookupError:pass

if __name__=='__main__':main()
