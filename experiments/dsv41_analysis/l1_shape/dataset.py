"""Read-only Scope audit, bilingual topic-family isolation, reproducible fixtures."""
import ast,hashlib,importlib.util,json,random
from pathlib import Path
from collections import Counter,defaultdict
from tokenizers import Tokenizer
ROOT=Path('artifacts/dsv41-l1-shape-20260915')
CKPT=Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD')
SOURCE=Path('/Users/avdpropang/sdk/dmoe/configs/scope-dataset.phase-long.v1.json')
GEN=Path('/Users/avdpropang/sdk/dmoe/scripts/generate_scope_dataset_v2.py')

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def key(s):return hashlib.sha256(('dsv41-l1-20260915:'+s).encode()).hexdigest()
def main():
    out=ROOT/'dataset';out.mkdir(parents=True,exist_ok=True)
    if (out/'dataset-manifest.json').exists():raise RuntimeError('frozen dataset already exists')
    # Extract only static topic data, never execute or import sibling runtime.
    tree=ast.parse(GEN.read_text());topics=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TOPICS' for t in n.targets))
    tokenizer=Tokenizer.from_file(str(CKPT/'tokenizer.json'))
    spec=importlib.util.spec_from_file_location('official_encoding',CKPT/'encoding/encoding.py');enc=importlib.util.module_from_spec(spec);spec.loader.exec_module(enc)
    source=json.loads(SOURCE.read_text())['samples'];audit=[];eligible=[];families={}
    for scope in topics:
        order=sorted(range(5),key=lambda i:key(f'{scope}:{i}'))
        for j,i in enumerate(order):families[f'{scope}:topic{i}']='train' if j<3 else 'validation' if j==3 else 'test'
    for row in source:
        r=dict(row);r['original_split']=r['split']
        if r['task_type']=='phase_long_composite':
            r.update(selected=False,exclusion='Composite connects multiple topic families; retain as audit only',parent_ids=r['source_sample_ids']);audit.append(r);continue
        index=int(r['id'].rsplit('-',1)[1])-1;topic=index%5;family=f"{r['scope']}:topic{topic}"
        assert topics[r['scope']][r['language']][topic] in r['messages'][-1]['content']
        r.update(family_id=family,split=families[family],topic=topics[r['scope']][r['language']][topic],parent_ids=[])
        eligible.append(r)
    selected=[]
    for scope in topics:
        for lang in ('zh','en'):
            for split,n in [('train',8),('validation',2),('test',2)]:
                rows=[r for r in eligible if (r['scope'],r['language'],r['split'])==(scope,lang,split)]
                # Round-robin families before choosing second task framing.
                groups=defaultdict(list)
                for r in rows:groups[r['family_id']].append(r)
                for rs in groups.values():rs.sort(key=lambda r:key(r['id']))
                ordered=[r for j in range(6) for f,rs in sorted(groups.items()) for r in rs[j:j+1]]
                selected.extend(dict(r,decode_steps=128,kind='scope') for r in ordered[:n])
    # Long variants remain in their source topic family. Evidence records are all
    # distinct, seeded, fictional material, never repeated paragraph padding.
    for scope in topics:
        for lang in ('zh','en'):
            for split,target in [('train',2048),('test',2048),('validation',4096)]:
                parent=next(r for r in selected if (r['scope'],r['language'],r['split'])==(scope,lang,split))
                seed=int(key(parent['family_id'])[:12],16);rng=random.Random(seed)
                title=parent['topic'];lines=[]
                zh=lang=='zh'
                intro=(f'以下是关于“{title}”的虚构案例工作记录。所有数值仅属于本案例，不应当作现实证据。请逐项审查记录，寻找矛盾、缺失数据和优先核查事项。\n' if zh else f'The following fictional case notebook concerns {title}. All values are invented case evidence, not real-world facts. Audit the records for contradictions, missing information and priorities for verification.\n')
                question=('\n请给出有记录编号依据的分析：先列五项关键发现，再区分事实与推测，最后制定三阶段检查计划，保留不确定性。' if zh else '\nProvide an analysis citing record identifiers: give five key findings, distinguish observations from assumptions, and propose a three-stage verification plan with explicit uncertainty.')
                j=0
                while True:
                    if zh:
                        line=f'记录R{j:03d}：第{1+j//7}周，案例{rng.randrange(100,999)}，负责人{rng.choice(["甲","乙","丙","丁"])}；观察值{rng.randrange(10,980)}，参考区间{rng.randrange(5,50)}至{rng.randrange(60,100)}，样本数{rng.randrange(2,70)}。状态：{rng.choice(["尚未复核","与前次冲突","复核后成立","测量方法发生变化","记录缺少时间戳","仅来自单方陈述"])}；约束：{rng.choice(["只能离线检查","需保留原始材料","预算不得增加","先核对定义","避免将相关视为因果","结果需另一位人员验证"])}。'
                    else:
                        line=f'Record R{j:03d}: week {1+j//7}, case {rng.randrange(100,999)}, owner {rng.choice(["A","B","C","D"])}; observed value {rng.randrange(10,980)}, reference interval {rng.randrange(5,50)} to {rng.randrange(60,100)}, sample size {rng.randrange(2,70)}. Status: {rng.choice(["unverified","conflicts with earlier notes","independently confirmed","measurement method changed","timestamp missing","single-party account"])}. Constraint: {rng.choice(["offline checks only","retain original evidence","no budget increase","reconcile definitions first","correlation is not causation","require independent review"])}.'
                    lines.append(line);j+=1
                    messages=[{'role':'user','content':intro+'\n'.join(lines)+question}]
                    prompt=enc.encode_messages(messages,thinking_mode='chat')
                    if len(tokenizer.encode(prompt).ids)>=target:break
                # Validation includes fixed-history topic switching. Full-context
                # replay, not a claim of persistent server-session coverage.
                if split=='validation':messages=[{'role':'user','content':'What is a prime number?'},{'role':'assistant','content':'A prime is an integer greater than one with exactly two positive divisors.'},*messages]
                selected.append(dict(parent,id=f"long-{scope}-{lang}-{split}",messages=messages,kind='synthetic_evidence_long',decode_steps=512 if lang=='zh' else 128,source_generation={'method':'seeded distinct fictional records','seed':seed,'target_tokens':target,'source_topic_id':parent['id']},parent_ids=[parent['id']]))
    chosen={r['id'] for r in selected}
    for r in eligible:r['selected']=r['id'] in chosen;audit.append(r)
    manifest=[]
    for r in selected:
        prompt=enc.encode_messages(r['messages'],thinking_mode='chat');ids=tokenizer.encode(prompt).ids
        fixture=out/(r['id']+'.json');fixture.write_text(json.dumps({'prompt':prompt,'input_ids':ids,'messages':r['messages']},ensure_ascii=False))
        manifest.append({**{k:v for k,v in r.items() if k!='messages'},'tokens':len(ids),'fixture':str(fixture),'fixture_sha256':digest(fixture)})
    # Pilot and calibration are drawn from train only; held-out files never fit.
    pilot=[]
    for scope in topics:
        for lang in ('zh','en'):pilot.append(next(r['id'] for r in manifest if r['scope']==scope and r['language']==lang and r['split']=='train' and r['kind']=='scope'))
    report={'schema':'dsv41.l1-dataset/v1','seed':'dsv41-l1-20260915','sources':{str(SOURCE):digest(SOURCE),str(GEN):digest(GEN)},'checkpoint_index_sha256':digest(CKPT/'model.safetensors.index.json'),'family_rule':'topic identity across languages and task framings; long variants inherit topic family; cross-topic composites excluded','limitations':['Generic instruction templates shared across families','Long evidence notebooks are synthetic, not representative production conversations','Persistent multi-turn service cache reuse excluded; fixed-history replay only'], 'audit':audit,'samples':manifest,'pilot_ids':pilot,'calibration_ids':pilot,'counts':dict(Counter(r['split'] for r in manifest)),'selected_count':len(manifest),'excluded_composites':140,'changed_original_splits':sum(r.get('split')!=r.get('original_split') for r in eligible)}
    assert all(len({r['split'] for r in manifest if r['family_id']==f})==1 for f in {r['family_id'] for r in manifest})
    (out/'dataset-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:report[k] for k in ['counts','selected_count','excluded_composites','changed_original_splits']},ensure_ascii=False))
if __name__=='__main__':main()
