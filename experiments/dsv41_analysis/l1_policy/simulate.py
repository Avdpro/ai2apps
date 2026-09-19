"""Causal Main40/Hot8 policy replay; replacement I/O charged at current runtime cost."""
import sys
from pathlib import Path
from collections import deque
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'l1_shape'))
from replay import initial

POLICIES=[
    dict(name='baseline',kind='frequency',interval=16,decay=.5),
    dict(name='frequency8_short',kind='frequency',interval=8,decay=.5),
    dict(name='frequency8_same_half_life',kind='frequency',interval=8,decay=2**-.5),
    dict(name='frequency16_eight_moves',kind='frequency',interval=16,decay=.5,moves=8),
    dict(name='dual_fast75',kind='dual',interval=8,weight=.75),
    dict(name='dual_fast50',kind='dual',interval=8,weight=.5),
    dict(name='probation32_8',kind='probation',interval=8,weight=.75),
    dict(name='shadow_cost32',kind='shadow',interval=16,decay=.5),
]

def shadow_loads(main,history):
    # Retrospective static-bank counterfactual, empty Hot for both alternatives.
    # Used solely as an admission estimate, never as an oracle/future trace.
    hot={};tick=0;loads=0
    for ids in history:
        missing=[e for e in ids if e not in main and e not in hot]
        loads+=len(missing)
        for e in missing:
            if len(hot)==8:
                victim=min((v for v in hot if v not in ids),key=lambda v:(hot[v],v));del hot[victim]
            hot[e]=tick
        for e in ids:
            tick+=1
            if e in hot:hot[e]=tick
    return loads

def simulate(prefill,decode,policy,events=False):
    main,hot=initial(prefill,40);protected=set(list(main)[:32])
    scores=np.bincount(prefill.reshape(-1).astype(int),minlength=384).astype(np.float32)*np.float32(12/len(prefill))
    fast=scores.astype(float)/(32*(1-2**(-1/8)));slow=scores.astype(float)/(32*(1-2**(-1/64)))
    ages=np.zeros(48,dtype=np.int64)
    for age,slot in enumerate(hot.values()):ages[slot]=age+1
    ticks=48;counts=np.zeros(3,dtype=np.int64);history=deque(maxlen=32)
    miss_steps=loads=promotion_loads=hot_rereads=checks=role_swaps=0;record=[]
    per_step=[];interval=policy['interval'];kind=policy['kind']
    for step,raw in enumerate(decode,1):
        ids=list(map(int,raw.reshape(-1)));pairs=[];reads=[]
        if step>1 and (step-1)%interval==0:
            checks+=1
            if kind in ('dual','probation'):
                weight=policy['weight'];rank=weight*fast*(32*(1-2**(-1/8)))+(1-weight)*slow*(32*(1-2**(-1/64)))
            else:rank=scores
            if kind=='probation':
                # Exchange logical protected/probation roles without moving payload.
                trial=sorted(set(main)-protected,key=lambda e:(-rank[e],e))
                old=sorted(protected,key=lambda e:(rank[e],e))
                for new,victim in zip(trial[:4],old[:4]):
                    if rank[new]>rank[victim]+2:
                        protected.remove(victim);protected.add(new);role_swaps+=1
                recent=np.bincount([e for h in history for e in h],minlength=384)
                candidates=sorted((e for e in hot if recent[e]>=2),key=lambda e:(-rank[e],e))
                victims=sorted(set(main)-protected,key=lambda e:(rank[e],e))
                threshold=1
            else:
                candidates=sorted((e for e in range(384) if e not in main),key=lambda e:(-rank[e],e))
                victims=sorted(main,key=lambda e:(rank[e],e));threshold=2
            limit=policy.get('moves',4)
            pairs=[(new,old,main[old]) for new,old in zip(candidates[:limit],victims[:limit]) if float(rank[new])>=3 and float(rank[new])>float(rank[old])+threshold]
            if kind=='shadow' and pairs:
                # Joint move: last32 loads saved, projected one16-token interval,
                # must pay all promotion rereads plus one-record safety margin.
                proposed=(set(main)-{p[1] for p in pairs})|{p[0] for p in pairs}
                benefit=(shadow_loads(set(main),history)-shadow_loads(proposed,history))*interval/len(history)
                if benefit<=len(pairs)+1:pairs=[]
            if pairs:
                hot_rereads+=sum(new in hot for new,_,_ in pairs);promotion_loads+=len(pairs)
                reads.append({'experts':[p[0] for p in pairs],'slots':[p[2] for p in pairs]})
                for new,old,slot in pairs:del main[old];main[new]=slot;hot.pop(new,None)
            if kind in ('frequency','shadow'):scores*=np.float32(policy['decay'])
        scores[ids]+=np.float32(1)
        fast*=2**(-1/8);slow*=2**(-1/64);fast[ids]+=1;slow[ids]+=1
        missing=[e for e in ids if e not in main and e not in hot]
        counts+=np.array([sum(e in main for e in ids),sum(e in hot for e in ids),len(missing)])
        if missing:
            miss_steps+=1;hot=dict(sorted(hot.items(),key=lambda p:ages[p[1]]))
            free=[s for s in range(40,48) if s not in hot.values()];slots=free[:len(missing)]
            victims=[(e,s) for e,s in hot.items() if e not in ids]
            for e,s in victims[:len(missing)-len(slots)]:del hot[e];slots.append(s)
            reads.append({'experts':missing,'slots':slots});hot.update(zip(missing,slots))
            for e in ids:
                if e in hot:hot[e]=hot.pop(e)
        slots=[main[e] if e in main else hot[e] for e in ids];ticks+=6
        for j,s in enumerate(slots):ages[s]=ticks+j
        loaded=sum(len(r['experts']) for r in reads);loads+=loaded
        per_step.append([loaded,int(bool(missing)),len(missing),len(pairs)])
        if events:record.append({'counts':counts.tolist(),'reads':reads})
        history.append(ids)
    return dict(loads=loads,miss_steps=miss_steps,misses=int(counts[2]),promotion_loads=promotion_loads,hot_rereads=hot_rereads,checks=checks,role_swaps=role_swaps,counts=counts.tolist(),events=record,per_step=per_step)
