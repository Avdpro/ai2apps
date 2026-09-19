"""Finalize the user-requested small performance check without adoption statistics."""
import hashlib,json,math,time
from pathlib import Path
import numpy as np
from batch import ROOT,DATA
from report import measure

def main():
    assert json.loads((ROOT/'limited-state.json').read_text())['status']=='complete'
    selected=json.loads((ROOT/'limited-selection.json').read_text())
    shape=json.loads((ROOT/'candidate/frozen.json').read_text())
    assert hashlib.sha256((ROOT/'candidate/frozen.json').read_bytes()).hexdigest()==selected['candidate_sha256']
    assert hashlib.sha256(DATA.read_bytes()).hexdigest()==shape['dataset_manifest_sha256']
    data=json.loads(DATA.read_text());rows=[next(r for r in data['samples'] if r['id']==i) for i in selected['ids']]
    cal=json.loads((ROOT/'calibration.json').read_text());qual=json.loads((ROOT/'qualification.json').read_text());persistent=json.loads((ROOT/'persistent-qualification.json').read_text())
    assert len(cal)==60 and len(qual)==4 and len(persistent)==4
    assert all(r['event_parity'] for r in cal+qual+persistent)
    cases=[];peaks=[];hash_count=0;sources=[]
    for row in rows:
        variants={};reference=None
        for variant in ['main40','shape']:
            measures=[];runs=[]
            for repeat in range(2):
                path=ROOT/('test-'+variant)/(row['id']+f'-r{repeat}')/'manifest.json'
                m=json.loads(path.read_text());assert m['status']=='complete'
                assert m['main_capacities']==(shape['capacities'] if variant=='shape' else [40]*40)
                assert not m['collect_routes'] and not m['expert_no_cache']
                assert m['checkpoint_index_sha256']==shape['checkpoint_index_sha256']
                assert m['ssd_checkpoint_manifest_sha256']==shape['checkpoint_manifest_sha256']
                assert len(m['step_seconds'])==row['decode_steps']+1
                if reference is None:reference=m
                for key in ['input_ids','generated_ids','logits_sha256']:
                    assert m[key]==reference[key],(row['id'],key)
                assert m['source_sha256']==reference['source_sha256'],row['id']
                assert m['sampled_physical_footprint_peak_bytes']<=65_000_000_000
                metrics=measure(m);assert all(math.isfinite(v) for v in metrics.values())
                measures.append(metrics);peaks.append(metrics['peak']);hash_count+=len(m['logits_sha256']);runs.append({'path':str(path.resolve()),'metrics':metrics})
                sources.append(m['source_sha256'])
            variants[variant]={'mean':{k:float(np.mean([m[k] for m in measures])) for k in measures[0]},'runs':runs}
        cases.append({'id':row['id'],'scope':row['scope'],'language':row['language'],'input_tokens':row['tokens'],'decode_steps':row['decode_steps'],'variants':variants})
    macro={v:{k:float(np.mean([c['variants'][v]['mean'][k] for c in cases])) for k in cases[0]['variants'][v]['mean']} for v in ['main40','shape']}
    result={'status':'complete','scope':'exploratory five cases, two repetitions per variant; no full independent statistical adoption gate','default':'Main40','case_count':5,'run_count':20,'logit_hashes_checked':hash_count,'all_exact':True,'macro':macro,'decode_gain':macro['shape']['decode']/macro['main40']['decode']-1,'peak_gb_both_variants':max(peaks),'cases':cases,'candidate_sha256':selected['candidate_sha256'],'completed_at':time.time()}
    (ROOT/'limited-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    cap_audit=json.loads((ROOT/'capture-audit.json').read_text());assert cap_audit['captures']==300 and not cap_audit['early_eos']
    (ROOT/'final-audit.json').write_text(json.dumps({'status':'passed','mode':'user-reduced performance scope','route_captures':300,'calibration_runs':60,'long_qualification_runs':4,'persistent_runs':4,'heldout_runs':20,'all_exact':True,'logit_hashes_checked':hash_count,'peak_gb_both_variants':max(peaks),'candidate_sha256':selected['candidate_sha256']},indent=2))
    val=shape['validation_replay'];root=ROOT.resolve()
    lines=['# DS4.1F 逐层L1形状执行报告','', '## 结论','',f"按用户要求完成采样、回放、形状求解和接入验证。性能验收由原60例×4次缩减为5例×4次；候选与Main40逐步输出完全一致。小样本宏平均Decode为 **{macro['main40']['decode']:.3f} → {macro['shape']['decode']:.3f} TPS（{result['decode_gain']*100:+.2f}%）**。保留Main40默认；本轮不宣称通过完整统计采用门槛。",'',
      '## 完成范围','', '| 项目 | 结果 |','|---|---|','| 1. 数据清单与冻结 | 300条：180训练、60验证、60封存测试；10任务组、中英文 |','| 2. 路由采样与因果回放 | 300条Main40采集；20例×32/40/48共60次真实校准；五档容量回放 |','| 3. 初始L1形状 | 40层各32/36/40/44/48，总Main1600；Hot每层8；验证集选择后冻结 |','| 4. 接入与检查 | opt-in形状加载、长Decode精度、持续对话、20次缩减性能测试；默认未改变 |','',
      '原240次运行主要用于跨任务性能稳定性与回退统计，并非精度检查所必需。用户指出成本偏高后，停止大批次，保留11次完成结果，补齐1次短任务和8次长输入对照。被用户主动中断的1次运行单独归档，不计作推理故障。未查看性能成绩来挑选新增用例：从未覆盖任务组中按固定ID哈希选择中英文各一个2048输入，选择理由与SHA已落盘。没有在测试后重新拟合候选。','',
      '## 候选形状与回放','', '```json',json.dumps(shape['capacities']),'```','',f"总Main槽位{sum(shape['capacities'])}，Hot320槽，专家有效载荷约36.098GB；该数不包含主干、KV、scratch等。专家身份继续根据当前Prefill初始化并动态晋升，容量固定。未引入机动池、预测L2、Burst或Block。",'',f"验证集每token加载量变化 **{(val['candidate'][0]/val['baseline40'][0]-1)*100:+.3f}%**，含miss的layer-step变化 **{(val['candidate'][1]/val['baseline40'][1]-1)*100:+.3f}%**。减少少量读取不代表减少GPU到CPU等待，这也是不能仅靠命中率判断吞吐的原因。",'',f'![容量与训练集读取取舍]({root}/candidate/allocation.png)','',
      '## 精度与内存','',f"60次校准覆盖307,200个layer-step，真实计数、读取专家和物理slot与因果回放完全一致；三档容量的路由和全部logits摘要一致。中英文各4096左右输入、512步Decode，Main40/候选共4次，保留全部logits并通过一致性检查；再完成8次F_NOCACHE控制。",'',f"中英文四轮持续会话各验证Main40/候选：同Model保留KV、Engram和bank，跨过128-token注意力窗口，每步输出与缓存事件一致。这是实验引擎逐token追加验证，尚不是Runtime服务或chunked incremental Prefill验收。",'',f"20次性能运行共核对{hash_count:,}份logits摘要，生成token全部相同。采样峰值{cap_audit['max_footprint_gb']:.3f}GB，20次性能运行两种方案最大峰值{max(peaks):.3f}GB，均低于65十进制GB。",'',
      '## 小样本配对性能','', '每个用例两轮AB/BA，表中TPS为两轮均值。所有完整运行保留；没有挑选最快成绩。总体按五例等权平均，仅作初步判断。','', '| 用例 | 输入/Decode | Main40 TPS | 候选TPS | 变化 |','|---|---:|---:|---:|---:|']
    for c in cases:
        a=c['variants']['main40']['mean']['decode'];b=c['variants']['shape']['mean']['decode']
        lines.append(f"| {c['scope']} / {c['language']} | {c['input_tokens']} / {c['decode_steps']} | {a:.3f} | {b:.3f} | {(b/a-1)*100:+.2f}% |")
    lines+=['','**重复运行波动：** medical_health基线两轮约3.999/4.756TPS，math_logic基线约5.077/4.363TPS。相同方案内部已出现明显波动，因此表中的−11.52%和+7.18%不应被解释为稳定回退或提升；现有native I/O计时与OS读取量不足以解释全部差异。按用户缩减要求不继续扩测，不给因果归因或置信区间。五例−0.82%也只是本批描述值。','', '本表使用实验runner的自然完整Top6路径、Prefill bank64、Main40/分层容量、Hot8，其他参数一致。它是此组真实题材fixture的缓存容量对照，不代表Burst或重复提示fixture下的最高TPS。']
    lines+=['','| 五例宏平均指标 | Main40 | 候选 |','|---|---:|---:|']
    for k,label in [('cold_decode','前16步Decode TPS'),('tail','尾段Decode TPS'),('hit_pct','路由命中率%'),('all_hit_pct','全命中layer-step%'),('promotion_loads','每例晋升读取专家数'),('miss','每例路由miss数'),('io','每例native Decode读取秒数'),('kernel_decode_read_gb','每例OS记账Decode读取GB')]:lines.append(f"| {label} | {macro['main40'][k]:.4f} | {macro['shape'][k]:.4f} |")
    lines+=['','尾段：128步取后64步，512步取后128步。native读取时间含miss与晋升I/O，不是完整GPU/CPU同步成本；不与其他wall时间直接相加。Darwin磁盘读计数是OS记账流量，不代表SSD设备总物理字节。','', '### 2048输入Prefill与长Decode','', '| 用例 | Main40 Prefill TPS | 候选Prefill TPS | Main40 Decode TPS | 候选Decode TPS |','|---|---:|---:|---:|---:|']
    for c in cases:
        if c['input_tokens']<1000:continue
        a=c['variants']['main40']['mean'];b=c['variants']['shape']['mean'];lines.append(f"| {c['scope']} / {c['language']} | {a['prefill']:.3f} | {b['prefill']:.3f} | {a['decode']:.3f} | {b['decode']:.3f} |")
    lines+=['','### F_NOCACHE控制','', '仅对专家文件描述符设置Darwin F_NOCACHE，不清全局文件缓存；不能保证所有读取都是物理SSD读取。每个用例每方案两次，结果与正常路径输出一致。','', '| 用例 | Main40 Decode TPS | 候选Decode TPS |','|---|---:|---:|']
    for ident in sorted({q['id'] for q in qual}):
        values=[]
        for variant in ['40','shape']:
            values.append(float(np.mean([measure(json.loads((ROOT/('nocache-'+variant)/(ident+f'-r{i}')/'manifest.json').read_text()))['decode'] for i in range(2)])))
        lines.append(f'| {ident} | {values[0]:.3f} | {values[1]:.3f} |')
    lines+=['','## 局限与后续','', '240条原生短输入21～74tokens；60条长输入为不同编号事实记录组成的合成证据审查任务，约2048/4096tokens，不能代表真实长代码、完整生产业务或多模态。300条采样均无提前EOS。原740条中排除140条跨题材组合题，按中英文主题家族重分，避免父任务泄漏；模板仍有共性。旧ID保留原split字样，冻结manifest中的split字段才是最终划分。','', '当前只做5个封存用例的初步测速，没有完成60用例统计验收，不给置信区间、不声称跨任务稳定提升。保持统一Main40默认，候选仅可显式加载。若未来要改默认，再使用新的独立数据确认收益；本轮不再扩测来追逐微小差异。','', '机动L1需要独立的共享内存池设计；本轮静态配额的读取改善较小，尚不足以证明它值得优先实现。没有发布Runtime或模型Package。','', '## 产物与复现','', f'- [冻结数据清单]({root}/dataset/dataset-manifest.json)',f'- [候选及SHA]({root}/candidate/frozen.json)',f'- [完整20次性能指标]({root}/limited-results.json)',f'- [最终审计]({root}/final-audit.json)',f'- [缩减理由与选样规则]({root}/limited-selection.json)',f'- [校准]({root}/calibration.json)、[长精度]({root}/qualification.json)、[持续会话]({root}/persistent-qualification.json)',f'- [源码快照]({root}/source-snapshot/manifest.json)', '', '运行入口：`experiments/dsv41_analysis/l1_shape/limited.py`复用完成结果并补齐缩减测试；`limited_report.py`生成本报告。原`pipeline.py`保留完整240次方案，不应为复现本次小样本结果直接重启它。','']
    path=Path('docs/dsv41f-l1-shape-results-2026-09-15.md');path.write_text('\n'.join(lines));print(json.dumps({k:v for k,v in result.items() if k not in ['cases','macro']},indent=2));print(path)

if __name__=='__main__':main()
