"""Causal replay of existing Main promotion and physical Hot recency, no oracle."""
from collections import Counter
import numpy as np

def initial(prefill, capacity):
    counts=Counter(map(int,prefill.reshape(-1)))
    chosen=sorted(counts,key=lambda e:(-counts[e],e))[:capacity]
    chosen += [e for e in range(384) if e not in chosen][:capacity-len(chosen)]
    main=dict(zip(chosen,range(capacity)))
    cold=sorted(set(counts)-set(main))[-8:]
    return main,dict(zip(cold,range(capacity,capacity+len(cold))))

def layer_replay(prefill, decode, capacity):
    main,hot=initial(prefill,capacity);initial_state={'main':list(main.items()),'hot':list(hot.items())}
    scores=np.bincount(prefill.reshape(-1).astype(int),minlength=384).astype(np.float32)*np.float32(12/len(prefill))
    ages=np.zeros(capacity+8,dtype=np.int64)
    for age,slot in enumerate(hot.values()):ages[slot]=age+1
    ticks=capacity+8;counts=np.zeros(3,dtype=np.int64);events=[];promotions=[];miss_steps=0;loads=0;hot_promotion_reads=0
    for step,raw in enumerate(decode,1):
        ids=list(map(int,raw.reshape(-1)));reads=[]
        if step>1 and (step-1)%16==0:
            candidates=sorted((e for e in range(384) if e not in main),key=lambda e:(-scores[e],e))[:4]
            victims=sorted(main,key=lambda e:(scores[e],e))[:4]
            pairs=[(new,old,main[old]) for new,old in zip(candidates,victims) if float(scores[new])>=3 and float(scores[new])>float(scores[old])+2]
            if pairs:
                hot_promotion_reads+=sum(new in hot for new,old,slot in pairs)
                reads.append({'experts':[p[0] for p in pairs],'slots':[p[2] for p in pairs]})
                for new,old,slot in pairs:del main[old];main[new]=slot;hot.pop(new,None)
                promotions.append({'step':step,'pairs':pairs})
            scores*=np.float32(.5)
        scores[ids]+=np.float32(1)
        missing=[e for e in ids if e not in main and e not in hot]
        counts+=np.array([sum(e in main for e in ids),sum(e in hot for e in ids),len(missing)])
        if missing:
            miss_steps+=1
            hot=dict(sorted(hot.items(),key=lambda p:ages[p[1]]))
            free=[s for s in range(capacity,capacity+8) if s not in hot.values()]
            slots=free[:len(missing)]
            victims=[(e,s) for e,s in hot.items() if e not in ids]
            for e,s in victims[:len(missing)-len(slots)]:del hot[e];slots.append(s)
            reads.append({'experts':missing,'slots':slots});hot.update(zip(missing,slots))
            for e in ids:
                if e in hot:hot[e]=hot.pop(e)
        slots=[main[e] if e in main else hot[e] for e in ids]
        ticks+=6
        for j,s in enumerate(slots):ages[s]=ticks+j
        loads+=sum(len(r['experts']) for r in reads)
        events.append({'counts':counts.tolist(),'reads':reads})
    return dict(initial=initial_state,events=events,counts=counts.tolist(),miss_steps=miss_steps,loads=loads,promotions=promotions,hot_promotion_reads=hot_promotion_reads)

def replay_file(path,capacities):
    a=np.load(path,allow_pickle=False);pre=a['prefill'];dec=a['decode']
    if pre.ndim!=3 or pre.shape[0]!=40 or pre.shape[-1]!=6 or dec.ndim!=4 or dec.shape[1:]!=(40,1,6):raise ValueError('invalid route dimensions')
    if any(c not in (32,36,40,44,48) for c in capacities) or len(capacities)!=40:raise ValueError('invalid replay capacities')
    for routes in (pre,dec):
        if routes.size and (routes.min()<0 or routes.max()>=384 or np.any(np.diff(routes.astype(np.int32),axis=-1)<=0)):raise ValueError('invalid or duplicate routed experts')
    return [layer_replay(pre[l],dec[:,l],capacities[l]) for l in range(40)]

def verify(path,capacity):
    import json
    actual=json.loads((path/'routes.json').read_text());results=replay_file(path/'routes.npz',[capacity]*40 if isinstance(capacity,int) else capacity)
    for l,r in enumerate(results):
        # JSON represents tuples as arrays.
        assert json.loads(json.dumps(r['initial']))==actual['initial'][str(l)],('initial',l)
        for j,e in enumerate(r['events']):
            a=actual['events'][j]
            assert e['counts']==a['counts'][l],('counts',l,j+1,e['counts'],a['counts'][l])
            reads=[{k:v for k,v in x.items() if k!='layer'} for x in a['reads'] if x['layer']==l]
            assert e['reads']==reads,('reads',l,j+1,e['reads'],reads)
    return {'layers':40,'steps':len(actual['events']),'event_parity':True}
