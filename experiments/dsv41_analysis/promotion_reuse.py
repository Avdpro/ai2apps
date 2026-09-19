"""Verify Hot promotion copies, then small fresh ABBA throughput comparisons."""
import hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parent/'l1_shape'))
from batch import pause_uploads
ROOT=Path('artifacts/dsv41-promotion-reuse-20260915')
DATA=Path('artifacts/dsv41-l1-shape-20260915/dataset/dataset-manifest.json')

def run(row,variant,repeat=0,capture=False,burst=None):
    group=f'burst-top{burst[0]}-block{burst[1]}' if burst else ('diagnostic' if capture else 'performance')
    out=ROOT/group/variant/(row['id']+f'-r{repeat}');out.parent.mkdir(parents=True,exist_ok=True)
    assert hashlib.sha256(Path(row['fixture']).read_bytes()).hexdigest()==row['fixture_sha256']
    if (out/'manifest.json').exists():
        m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete' and m['promotion_reuse']==(variant=='reuse') and m['collect_routes']==capture
        return m
    command=[sys.executable,'experiments/dsv41_mlx/run.py','--prompt-json',row['fixture'],'--output',str(out),'--decode',str(row['decode_steps']),'--prefill-slots','64','--main-slots','40','--logits-mode','all' if capture else 'hash']
    if variant=='reread':command+=['--promotion-reread']
    if burst:command+=['--burst-top',str(burst[0]),'--block-layers',str(burst[1])]
    if capture:command+=['--collect-routes']
    with out.with_suffix('.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
    m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete';return m

def parity(a,b):
    for k in ['input_ids','generated_ids','logits_sha256','cache_stats']:
        assert a[k]==b[k],k
    assert a['adaptive_l1']['promotions']==b['adaptive_l1']['promotions']
    assert a['adaptive_l1']['per_layer_counts']==b['adaptive_l1']['per_layer_counts']
    copies=b['adaptive_l1']['promotion_reuse']
    assert copies['enabled'] and copies['copied_experts']>0
    assert a['expert_total_read_bytes']-b['expert_total_read_bytes']==copies['copied_bytes']
    assert max(a['sampled_physical_footprint_peak_bytes'],b['sampled_physical_footprint_peak_bytes'])<=65_000_000_000

def verify_events(row):
    paths=[ROOT/'diagnostic'/v/(row['id']+'-r0') for v in ['reread','reuse']]
    traces=[json.loads((p/'routes.json').read_text()) for p in paths]
    with np.load(paths[0]/'routes.npz') as a,np.load(paths[1]/'routes.npz') as b:
        assert all(np.array_equal(a[k],b[k]) for k in ['prefill','decode'])
    assert traces[0]['initial']==traces[1]['initial']
    legacy=json.loads((paths[0]/'manifest.json').read_text());promotions={(p['step'],p['layer']):p['pairs'] for p in legacy['adaptive_l1']['promotions']}
    hot={int(l):dict(s['hot']) for l,s in traces[0]['initial'].items()};copied=0
    for step,(a,b) in enumerate(zip(traces[0]['events'],traces[1]['events']),1):
        assert a['counts']==b['counts'];reads=[];copies=[]
        for layer in range(40):
            pairs=promotions.get((step,layer),[]);disk=[];dest=[]
            for new,old,slot in pairs:
                if new in hot[layer]:copies.append((hot[layer][new],slot))
                else:disk.append(new);dest.append(slot)
            if pairs:
                selected=[(hot[layer][new],slot) for new,old,slot in pairs if new in hot[layer]]
                if selected:copied+=len(selected)
                for new,old,slot in pairs:hot[layer].pop(new,None)
            if disk:reads.append({'layer':layer,'experts':disk,'slots':dest})
            for read in a['reads']:
                if read['layer']!=layer or all(s<40 for s in read['slots']):continue
                reads.append(read)
                for expert,slot in zip(read['experts'],read['slots']):
                    hot[layer]={e:s for e,s in hot[layer].items() if s!=slot};hot[layer][expert]=slot
        assert b['reads']==reads,('SSD events',step)
        observed=[(s,d) for item in b['copies'] for s,d in zip(item['sources'],item['slots'])]
        assert observed==copies,('copy events',step)
    return {'event_parity':True,'steps':len(traces[0]['events']),'copied_experts':copied,'hot_promotions_read_from_ssd':0}

def main():
    ROOT.mkdir(exist_ok=True);data=json.loads(DATA.read_text());by_id={r['id']:r for r in data['samples']}
    diagnostic=by_id['general-zh-train-20'];rows=[by_id[i] for i in ['coding-en-train-18','long-math_logic-zh-test']]
    paused=pause_uploads();state={'status':'running','stage':'diagnostic','completed_performance_runs':0,'started':time.time()}
    try:
        (ROOT/'state.json').write_text(json.dumps(state,indent=2))
        a=run(diagnostic,'reread',capture=True);b=run(diagnostic,'reuse',capture=True);parity(a,b)
        (ROOT/'diagnostic-check.json').write_text(json.dumps(verify_events(diagnostic),indent=2))
        state['stage']='performance'
        for row in rows:
            results={}
            for repeat in range(2):
                for variant in (['reread','reuse'] if repeat==0 else ['reuse','reread']):
                    m=run(row,variant,repeat);results[(variant,repeat)]=m;state['completed_performance_runs']+=1
                    (ROOT/'state.json').write_text(json.dumps(state,indent=2))
            for repeat in range(2):parity(results[('reread',repeat)],results[('reuse',repeat)])
            assert results[('reread',0)]['logits_sha256']==results[('reread',1)]['logits_sha256']
        state['status']='complete'
    except BaseException as e:state.update(status='failed',error=repr(e));raise
    finally:
        state['updated']=time.time();(ROOT/'state.json').write_text(json.dumps(state,indent=2))
        for pid in paused:
            try:os.kill(pid,signal.SIGCONT)
            except ProcessLookupError:pass

if __name__=='__main__':main()
