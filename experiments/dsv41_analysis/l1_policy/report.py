"""Summarize frozen offline candidates; no claimed runtime TPS or free promotions."""
import json,sys
from pathlib import Path
import numpy as np
from simulate import POLICIES
from fit import macro
ROOT=Path('artifacts/dsv41-l1-policy-20260915');DATA=Path('artifacts/dsv41-l1-shape-20260915/dataset/dataset-manifest.json')

def main():
    state=json.loads((ROOT/'state.json').read_text());assert state['status']=='complete'
    selection=json.loads((ROOT/'selection.json').read_text());data=json.loads(DATA.read_text());rows=[r for r in data['samples'] if r['split'] in ('train','validation')]
    results={p['name']:json.loads((ROOT/(p['name']+'.json')).read_text()) for p in POLICIES};baseline=results['baseline'];winner=results[selection['selected_challenger']]
    val=[r for r in rows if r['split']=='validation'];b=baseline['macro']['validation'];w=winner['macro']['validation']
    comparisons=[]
    for name,result in results.items():
        t=result['macro']['train'];v=result['macro']['validation']
        comparisons.append({'name':name,'train_load_gain':1-t['loads']/baseline['macro']['train']['loads'],'validation_load_gain':1-v['loads']/b['loads'],'validation_miss_step_gain':1-v['miss_steps']/b['miss_steps'],'validation_hit_pct':100*(1-v['misses']/240),'validation_all_hit_pct':100*(1-v['miss_steps']/40),'metrics':v})
    groups={}
    for scope in sorted({r['scope'] for r in val}):
        subset=[r for r in val if r['scope']==scope];values={}
        for name in ['baseline',selection['selected_challenger']]:
            metrics={i:np.array(c['per_layer_per_token']).sum(axis=0) for i,c in results[name]['cases'].items()}
            values[name]=macro(subset,metrics).tolist()
        groups[scope]={'baseline':values['baseline'],'challenger':values[selection['selected_challenger']],'load_gain':1-values[selection['selected_challenger']][0]/values['baseline'][0],'miss_step_gain':1-values[selection['selected_challenger']][1]/values['baseline'][1]}
    summary={'status':'complete','selection':selection,'comparisons':comparisons,'validation_scope_results':groups,'runtime_measured':False,'default_changed':False}
    (ROOT/'summary.json').write_text(json.dumps(summary,indent=2))
    lines=['# DS4.1F L1策略离线比较','', '## 结论','',f"固定Main40＋Hot8，使用已有180训练＋60验证路由，比较8种预先固定策略。训练集选前两名，再用验证集读取量选择，最终候选为 **{selection['selected_challenger']}**。验证集每token总专家读取 **{b['loads']:.3f} → {w['loads']:.3f}（减少{(1-w['loads']/b['loads'])*100:.2f}%）**；含miss的层步数 **{b['miss_steps']:.3f} → {w['miss_steps']:.3f}（减少{(1-w['miss_steps']/b['miss_steps'])*100:.2f}%）**。",'', '**这是固定路由下的离线缓存结果，不是实测TPS，也尚未把候选接入推理引擎。** 未读取封存测试集路由来选择参数，默认Main40及其现有晋升策略未改变。','', '## 方法与校准','', '新模拟器先与20条Main40真实记录逐步比对：102,400个layer-step的累计命中计数、SSD读取专家及物理slot完全一致。3项CPU测试通过，包括所有候选的未来路由扰动不影响此前决策。既有回放器此前也完成过32/40/48三档真实校准。','', '每例使用自己的Prefill初始化Main和Hot，保留当前prior、Hot recency及请求批次的淘汰保护。候选决策只使用已发生的Decode。按主题家族内平均，再按任务/语言宏平均，避免长任务或近重复模板占据过大权重。长上下文仍是合成证据任务，不能替代真实生产长文。','', '所有晋升都按当前引擎重新读取专家收费，包括专家已在Hot中的情况。没有把尚未实现的Hot→Main GPU复制当作免费收益；试用区只是逻辑身份分组，不扩容。只模拟缓存事件，不模拟CPU/Metal调度耗时、GPU覆写安全等待或额外临时内存。','', '## 全部候选','', '| 策略 | 训练读取减少 | 验证读取减少 | 验证miss层步减少 | 验证命中率 |','|---|---:|---:|---:|---:|']
    for c in comparisons:lines.append(f"| {c['name']} | {c['train_load_gain']*100:+.2f}% | {c['validation_load_gain']*100:+.2f}% | {c['validation_miss_step_gain']*100:+.2f}% | {c['validation_hit_pct']:.3f}% |")
    lines+=['', '策略说明：','', '- baseline：16步一次，频次减半，每层最多4个晋升，最低分3、迟滞2。','- frequency8_short：每8步减半并更新4个，缩短记忆。','- frequency8_same_half_life：每8步更新，衰减sqrt(0.5)，保留16步半衰期；仍使用相同准入阈值。','- frequency16_eight_moves：16步更新，但单次允许8个晋升。','- dual_fast75 / dual_fast50：8/64-token半衰期双EMA，频次归一到相同参考尺度，短期权重75%/50%；每8步最多4个晋升。','- probation32_8：Main内部32个保护位＋8个试用位；双EMA，试用专家达到更高频次后仅交换逻辑保护身份；新专家必须在Hot且最近32步至少出现两次，最多4次替换。','- shadow_cost32：沿用基线候选，以过去32步对替换前后Main做静态Hot8反事实回放；历史节省按下一16步缩放，须覆盖所有晋升读取＋1次余量才执行。历史窗口两边均从空Hot开始，是成本估计，不能解释为未来预测真值。','', '## 验证集维护成本','', '| 策略 | 读取/token | 晋升读取/token | Hot重复读取/token | 更新检查/token | 全命中层步% |','|---|---:|---:|---:|---:|---:|']
    for c in comparisons:
        m=c['metrics'];lines.append(f"| {c['name']} | {m['loads']:.3f} | {m['promotion_loads']:.3f} | {m['hot_rereads']:.3f} | {m['checks']:.3f} | {c['validation_all_hit_pct']:.3f}% |")
    lines+=['', '更新检查数量是策略维护频率，不等于已测GPU→CPU同步次数。双EMA、历史窗口与成本回放都可能增加真实实现开销；离线命中更高也可能被这些开销抵消。','', '## 选中候选的分组变化','', '| 验证任务组 | 读取减少 | miss层步减少 |','|---|---:|---:|']
    adjusted_base=b['loads']-b['hot_rereads']
    counterfactual=[]
    for c in comparisons:
        m=c['metrics'];ssd=m['loads']-m['hot_rereads'];counterfactual.append({'name':c['name'],'ssd_loads_if_hot_promotions_copy':ssd,'reduction_vs_equally_optimized_baseline':1-ssd/adjusted_base})
    summary['hot_copy_counterfactual']={'baseline_ssd_loads':adjusted_base,'candidates':counterfactual,'assumption':'Every Hot-resident promotion copies the existing payload instead of rereading SSD, with unchanged cache decisions. GPU copy, synchronization, temporary allocations and policy CPU cost excluded; not an implemented or end-to-end result.'}
    (ROOT/'summary.json').write_text(json.dumps(summary,indent=2))
    extra=['## 晋升重读的单独核算','', '当前adaptive.py晋升会调用bank._load，即使专家已在Hot。这里单独做读取账目反事实：假设该类晋升改用已有Hot数据复制，缓存决策和容量不变，比较双方都消除该重读后的SSD记录数。**这不是免费复制，不计GPU复制、同步和临时内存成本，也不作为已实现收益或TPS预测。**','', '| 策略 | 假设复用Hot后的SSD记录/token | 相对同样优化的基线减少 |','|---|---:|---:|']
    for c in counterfactual:extra.append(f"| {c['name']} | {c['ssd_loads_if_hot_promotions_copy']:.3f} | {c['reduction_vs_equally_optimized_baseline']*100:+.2f}% |")
    extra+=['', '该核算只定位后续工作价值：频繁晋升的策略被Hot重读明显拖累。应先验证安全的Hot→Main复用是否能降低真实开销，再决定是否使用双频次或试用区策略；不能直接把这一列当作已经获得的加速。','']
    at=lines.index('## 选中候选的分组变化');lines[at:at]=extra
    for scope,g in groups.items():lines.append(f"| {scope} | {g['load_gain']*100:+.2f}% | {g['miss_step_gain']*100:+.2f}% |")
    lines+=['','### 短输入与长Decode','', '| 子集 | 基线读取/token | 候选读取/token | 变化 |','|---|---:|---:|---:|']
    subsets=[('短输入',[r for r in val if r['kind']=='scope'],None),('4096左右输入',[r for r in val if r['kind']=='synthetic_evidence_long'],None),('512步任务前128步',[r for r in val if r['decode_steps']==512],'first128_per_token'),('512步任务后384步',[r for r in val if r['decode_steps']==512],'later384_per_token')]
    for label,subset,field in subsets:
        values=[]
        for result in [baseline,winner]:
            metrics={r['id']:(np.array(result['cases'][r['id']][field]) if field else np.array(result['cases'][r['id']]['per_layer_per_token']).sum(axis=0)) for r in subset}
            values.append(float(macro(subset,metrics)[0]))
        lines.append(f'| {label} | {values[0]:.3f} | {values[1]:.3f} | {(values[1]/values[0]-1)*100:+.2f}% |')
    lines+=['', '## 下一步边界','', '这8种固定候选不是所有算法的上限。验证集用于候选选择，结果属于探索性比较，没有新的独立测试集泛化保证。若值得接入，只选一个候选，在不新增逐层同步的前提下实现，再做少量配对精度和TPS验证；本次没有启动GPU测试、重新采样、改变Runtime或修改默认。','', '## 产物','',f'- [配置及源码SHA]({(ROOT/"config.json").resolve()})',f'- [选择和汇总]({(ROOT/"summary.json").resolve()})',f'- [真实记录校准]({(ROOT/"calibration.json").resolve()})',f'- [运行进度]({(ROOT/"state.json").resolve()})','- `experiments/dsv41_analysis/l1_policy/run.py` 执行；`report.py` 汇总。每个候选JSON保留全部240例逐层指标。','']
    path=Path('docs/dsv41f-l1-policy-offline-2026-09-15.md');path.write_text('\n'.join(lines));print(json.dumps({'selected':selection['selected_challenger'],'train_shortlist':selection['shortlist_from_train'],'baseline':b,'challenger':w},indent=2))

if __name__=='__main__':main()
