"""Offline-only policy sweep on frozen train/validation traces, never held-out tests."""
import hashlib,json,time
from pathlib import Path
import numpy as np
from simulate import POLICIES,simulate
from fit import macro

ROOT=Path('artifacts/dsv41-l1-policy-20260915');TRACES=Path('artifacts/dsv41-l1-shape-20260915');DATA=TRACES/'dataset/dataset-manifest.json'
FIELDS=['loads','miss_steps','misses','promotion_loads','hot_rereads','checks','role_swaps']

def main():
    ROOT.mkdir(exist_ok=True);data=json.loads(DATA.read_text());rows=[r for r in data['samples'] if r['split'] in ('train','validation')]
    config={'policies':POLICIES,'main':40,'hot':8,'dataset_sha256':hashlib.sha256(DATA.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256((Path(__file__).parent/'simulate.py').read_bytes()).hexdigest(),'splits':['train','validation'],'selection':'Train: two lowest-load challengers, then validation loads with miss-step tie-break. Report all frozen candidates as exploratory, no test-set adoption claim.'}
    p=ROOT/'config.json'
    if p.exists():assert json.loads(p.read_text())==config
    else:p.write_text(json.dumps(config,indent=2))
    calibration=[]
    for row in rows:
        if row['id'] not in data['calibration_ids']:continue
        out=TRACES/'trace40'/(row['id']+'-r0');actual=json.loads((out/'routes.json').read_text())
        with np.load(out/'routes.npz') as a:
            for layer in range(40):
                replay=simulate(a['prefill'][layer],a['decode'][:,layer],POLICIES[0],events=True)
                for step,e in enumerate(replay['events']):
                    event=actual['events'][step]
                    reads=[{k:v for k,v in r.items() if k!='layer'} for r in event['reads'] if r['layer']==layer]
                    assert e['counts']==event['counts'][layer] and e['reads']==reads,(row['id'],layer,step)
        calibration.append(row['id'])
    assert len(calibration)==20
    (ROOT/'calibration.json').write_text(json.dumps({'samples':20,'layer_steps':20*40*128,'events_exact':True,'ids':calibration},indent=2))
    state={'status':'running','completed_policies':0,'started':time.time()};all_results={}
    try:
        for policy in POLICIES:
            path=ROOT/(policy['name']+'.json')
            if path.exists():all_results[policy['name']]=json.loads(path.read_text());state['completed_policies']+=1;continue
            cases={};state['active']=policy['name']
            for index,row in enumerate(rows):
                with np.load(TRACES/'trace40'/(row['id']+'-r0')/'routes.npz') as a:
                    layers=[simulate(a['prefill'][l],a['decode'][:,l],policy) for l in range(40)]
                total=np.array([[r[k] for k in FIELDS] for r in layers],dtype=float)
                step=np.array([r['per_step'] for r in layers]).sum(axis=0)
                cases[row['id']]={'per_layer_per_token':(total/row['decode_steps']).tolist(),'first128_per_token':(step[:128].mean(axis=0)).tolist(),'later384_per_token':step[128:].mean(axis=0).tolist() if len(step)>128 else None}
                state['completed_cases']=index+1;(ROOT/'state.json').write_text(json.dumps(state,indent=2))
            payload={'policy':policy,'fields':FIELDS,'cases':cases,'macro':{}}
            metrics={ident:np.array(c['per_layer_per_token']).sum(axis=0) for ident,c in cases.items()}
            for split in ['train','validation']:
                subset=[r for r in rows if r['split']==split];m=macro(subset,metrics)
                payload['macro'][split]=dict(zip(FIELDS,m.tolist()))
            path.write_text(json.dumps(payload,indent=2));all_results[policy['name']]=payload;state['completed_policies']+=1;print(json.dumps({'policy':policy['name'],'macro':payload['macro']}),flush=True)
        shortlist=sorted((p['name'] for p in POLICIES if p['name']!='baseline'),key=lambda n:(all_results[n]['macro']['train']['loads'],all_results[n]['macro']['train']['miss_steps']))[:2]
        selected=min(shortlist,key=lambda n:(all_results[n]['macro']['validation']['loads'],all_results[n]['macro']['validation']['miss_steps']))
        selection={'shortlist_from_train':shortlist,'selected_challenger':selected,'baseline_validation':all_results['baseline']['macro']['validation'],'challenger_validation':all_results[selected]['macro']['validation'],'note':'Offline route replay only; no end-to-end TPS claim and no runtime default change.'}
        (ROOT/'selection.json').write_text(json.dumps(selection,indent=2));state['status']='complete'
    except BaseException as e:state.update(status='failed',error=repr(e));raise
    finally:state['updated']=time.time();(ROOT/'state.json').write_text(json.dumps(state,indent=2))

if __name__=='__main__':main()
