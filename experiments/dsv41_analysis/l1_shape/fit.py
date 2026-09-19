"""Train-only macro-family cost curves and exact multiple-choice budget DP."""
import hashlib,json
from pathlib import Path
from collections import defaultdict
import numpy as np
from replay import replay_file
ROOT=Path('artifacts/dsv41-l1-shape-20260915');CAPS=[32,36,40,44,48]

def solve(cost):
    # tuple objective: measured cost, then distance from uniform, then vector.
    dp={0:(0.,0,())}
    for layer in range(40):
        nxt={}
        for used,(value,regularizer,vector) in dp.items():
            for i,cap in enumerate(CAPS):
                units=used+i
                if units>80:continue
                candidate=(value+float(cost[layer,i]),regularizer+abs(cap-40),vector+(cap,))
                if units not in nxt or candidate<nxt[units]:nxt[units]=candidate
        dp=nxt
    assert 80 in dp
    return list(dp[80][2])

def macro(rows,metrics):
    families=defaultdict(list)
    for r in rows:families[(r['scope'],r['language'],r['family_id'])].append(metrics[r['id']])
    strata=defaultdict(list)
    for (scope,lang,f),values in families.items():strata[(scope,lang)].append(np.mean(values,axis=0))
    return np.mean([np.mean(v,axis=0) for v in strata.values()],axis=0)

def main():
    manifest=ROOT/'dataset/dataset-manifest.json';data=json.loads(manifest.read_text());rows=[r for r in data['samples'] if r['split']!='test']
    checkpoint=Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD')
    assert hashlib.sha256((checkpoint/'model.safetensors.index.json').read_bytes()).hexdigest()==data['checkpoint_index_sha256']
    marker_sha=hashlib.sha256((checkpoint/'ssd-checkpoint.json').read_bytes()).hexdigest()
    out=ROOT/'replay';out.mkdir(exist_ok=True);metrics={};hot_rereads={}
    for r in rows:
        result=[];hot=[]
        for cap in CAPS:
            layers=replay_file(ROOT/'trace40'/(r['id']+'-r0')/'routes.npz',[cap]*40)
            hot.append([l['hot_promotion_reads']/r['decode_steps'] for l in layers])
            result.append([[l['loads']/r['decode_steps'],l['miss_steps']/r['decode_steps'],l['counts'][2]/r['decode_steps']] for l in layers])
        hot_rereads[r['id']]=np.array(hot).T
        metrics[r['id']]=np.array(result).transpose(1,0,2)
    np.savez_compressed(out/'curves.npz',**metrics)
    np.savez_compressed(out/'hot-promotion-rereads.npz',**hot_rereads)
    train=[r for r in rows if r['split']=='train'];validation=[r for r in rows if r['split']=='validation']
    train_cost=macro(train,metrics);val_cost=macro(validation,metrics)
    (ROOT/'candidate').mkdir(exist_ok=True)
    candidates=[]
    optimal_load_shape=solve(train_cost[:,:,0])
    optimal_load=sum(train_cost[l,CAPS.index(c),0] for l,c in enumerate(optimal_load_shape))
    for name,cost in [('loads',train_cost[:,:,0]),('loads_sync',train_cost[:,:,0]+.1*train_cost[:,:,1])]:
        shape=solve(cost)
        proposed_load=sum(train_cost[l,CAPS.index(c),0] for l,c in enumerate(shape))
        if proposed_load>optimal_load*1.01:shape=optimal_load_shape # never trade >1% loads for sync heuristic
        ix=[CAPS.index(c) for c in shape]
        group_changes={}
        for split,subset in [('train',train),('validation',validation)]:
            group_changes[split]={}
            for scope in sorted({r['scope'] for r in subset}):
                g=macro([r for r in subset if r['scope']==scope],metrics)[:,:,0]
                group_changes[split][scope]=float(g[np.arange(40),ix].sum()/g[:,2].sum()-1)
        selected=val_cost[np.arange(40),ix].sum(axis=0);baseline=val_cost[:,2].sum(axis=0)
        payload={'schema':'dsv41.l1-shape/v1','family':'deepseek_v41','checkpoint_index_sha256':data['checkpoint_index_sha256'],'checkpoint_manifest_sha256':marker_sha,'dataset_manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'capacities':shape,'hot_slots':8,'policy':'dynamic-16-4-decay0.5-hysteresis2-v1','name':name,'objective':'mean expert loads/token' if name=='loads' else 'mean loads/token + 0.1 * miss layer-steps/token (heuristic, not latency prediction)','validation_replay':{'candidate':selected.tolist(),'baseline40':baseline.tolist()},'per_layer_training_costs':train_cost.tolist(),'per_scope_load_change':group_changes,'capacity_histogram':{str(c):shape.count(c) for c in CAPS},'scope':'text full Top6; static capacities, dynamic identities; synthetic long-context qualification'}
        path=ROOT/'candidate'/f'{name}.json';path.write_text(json.dumps(payload,indent=2));candidates.append((selected[0],selected[1],name))
    # Validation route cost selects one before opening held-out performance.
    selected=min(candidates)[2];p=ROOT/'candidate'/f'{selected}.json'
    (ROOT/'candidate/frozen.json').write_bytes(p.read_bytes())
    (ROOT/'candidate/selection.json').write_text(json.dumps({'selection':'validation causal load cost; miss steps tie-break','selected':selected,'candidates':candidates,'frozen_sha256':hashlib.sha256(p.read_bytes()).hexdigest()},indent=2))
    print((ROOT/'candidate/selection.json').read_text())
if __name__=='__main__':main()
