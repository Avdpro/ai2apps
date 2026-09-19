"""Render reproducible study receipt only after all required stages have results."""
import hashlib,json
from pathlib import Path
import numpy as np
from batch import ROOT,DATA
from report import measure

def main():
    data=json.loads(DATA.read_text());result=json.loads((ROOT/'results.json').read_text());shape=json.loads((ROOT/'candidate/frozen.json').read_text());selection=json.loads((ROOT/'candidate/selection.json').read_text());cal=json.loads((ROOT/'calibration.json').read_text());qual=json.loads((ROOT/'qualification.json').read_text())
    assert len(cal)==60 and all(x['event_parity'] for x in cal)
    captures=[ROOT/'trace40'/(r['id']+'-r0') for r in data['samples']]
    manifests=[json.loads((p/'manifest.json').read_text()) for p in captures];assert all(m['status']=='complete' for m in manifests)
    traces=[json.loads((p/'routes.json').read_text()) for p in captures]
    eos_cases=[str(p) for p,m in zip(captures,manifests) if 1 in m['generated_ids'][:-1]]
    size=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())
    lines=['# DS4.1F 按层 L1 形状执行报告','', '2026-09-15 启动；完成时间见 pipeline.json。', '', '**结论：'+('候选达到预设采用门槛，默认仍保留Main40，供评审选择。' if result['adopt'] else '候选未达到全部预设采用门槛，保留Main40默认；不以个别最快结果替换默认。')+'**','', '## 1. 数据冻结与覆盖','', f"冻结{len(data['samples'])}条：训练180、验证60、测试60。原始740条精确去重后审计，中英文同题材统一family；排除140条跨题材组合题，331条原始划分调整。训练/验证/测试分别30/10/10个题材家族。",'', '240条短任务使用官方chat编码，21～74输入tokens；60条长任务约2048/4096 tokens，以独立编号、不同事实的虚构证据记录构造。长短同题材归同一家族。中文长任务512步Decode，其余128步。验证长组含固定历史换题；不等同于持续服务会话验证。','', '**适用范围限制：** 长任务是合成证据审查材料，不能证明真实代码长文、医疗/法律实际业务、多模态或64K上下文表现。模板框架仍有共性，Bootstrap仅10个独立测试题材家族，不能夸大泛化。','', '## 2. 采集与回放','',f"完成{len(manifests)}条Main40采集；20条×32/40/48共60次校准，逐层逐步计数、读取专家与物理slot完全对齐。校准覆盖{sum(x['layers']*x['steps'] for x in cal):,}个layer-step。长输入资格验证另覆盖{sum(x['layers']*x['steps'] for x in qual):,}个layer-step。",'',f"采集器仅在完成step边界提取路由，边界处理总计{sum(t['collector_boundary_seconds'] for t in traces):.3f}秒。记录初始Main/Hot，不用最终Main倒推；回放32/36/40/44/48，遵守16步晋升、最多4项、0.5衰减、2分迟滞以及Hot recency。整个研究产物当前约{size/1e9:.3f}GB，没有复制模型权重。",'', '## 3. 同预算候选','', f"验证集选定 `{selection['selected']}`；目标使用训练集任务/语言及家族宏平均。多选背包强制40层合计1600 Main槽，每层Hot8。候选冻结SHA256：`{selection['frozen_sha256']}`。",'', '```json',json.dumps(shape['capacities']),'```','', '容量是每层可驻留数量，专家身份仍来自当前Prefill和动态晋升。未引入机动池、预测L2、Burst或Block。','', '## 4. 独立验收','', '测试集每条基线/候选按AB/BA各2次；超过5%单例回退另做两组配对复测，所有复测纳入同一单例平均。关闭route采集，逐步logits SHA256与生成token必须完全一致；中英文长资格样本均运行512步并保留完整logits。','', '| 指标 | 结果 |','|---|---:|',f"| Main40宏平均Decode | {result['decode_macro_tps']['main40']:.4f} TPS |",f"| 候选宏平均Decode | {result['decode_macro_tps']['shape']:.4f} TPS |",f"| Decode变化 | {result['decode_gain']*100:+.2f}% |",f"| 家族Bootstrap95%区间 | [{result['family_bootstrap95'][0]*100:+.2f}%, {result['family_bootstrap95'][1]*100:+.2f}%] |",f"| Prefill宏平均变化 | {result['prefill_gain']*100:+.2f}% |",f"| 候选最大physical footprint | {result['peak_gb']:.3f} GB |",'','预设门槛：Decode≥3%、Prefill回退≤3%、任务组无稳定>5%回退、Bootstrap下界>0、footprint≤65十进制GB。统一Main40仍是默认。','', '| 任务组 | Decode变化 |','|---|---:|']
    metric_rows=['','| 指标（样本宏平均） | Main40 | 候选 |','|---|---:|---:|']
    eos_note=(f'固定步数采样中有{len(eos_cases)}条提前EOS；其EOS后路由不能作为自然回答路径解释，详见capture-audit.json。' if eos_cases else '300条固定步数采样均未出现提前EOS；未将EOS后继续生成的路由混入本批统计。')
    at=lines.index('## 3. 同预算候选');lines[at:at]=[eos_note,'']
    segments=result['long_decode_segments']
    for key,label in [('first128_tps','512步样本：前128步TPS'),('later384_tps','512步样本：后384步TPS')]:
        metric_rows.append(f"| {label} | {segments['main40'][key]:.4f} | {segments['shape'][key]:.4f} |")
    for group,label in [('short','短输入'),('approximately_2048','约2048输入')]:
        values=result['length_groups'][group]
        for key,metric in [('decode','Decode'),('prefill','Prefill')]:
            metric_rows.append(f"| {label} {metric} TPS（{values['cases']}例） | {values['main40'][key]:.4f} | {values['shape'][key]:.4f} |")
    for key,label in [('cold_decode','前16步 Decode TPS'),('tail','尾段 Decode TPS（128步取后64；512步取后128）'),('prefill','首次 Prefill TPS'),('cold_ttft','模型初始化＋首次前向秒数'),('hit_pct','路由命中率 %'),('all_hit_pct','全命中layer-step比例 %'),('promotion_loads','每样本晋升额外读取专家数'),('miss','每样本 Miss专家数'),('all_hit','每样本全命中layer-step数'),('kernel_decode_read_gb','每样本Decode系统记账磁盘读GB'),('io','每样本Decode native读取秒数')]:
        metric_rows.append(f"| {label} | {result['macro_metrics']['main40'][key]:.4f} | {result['macro_metrics']['shape'][key]:.4f} |")
    from fit import macro
    with np.load(ROOT/'replay/hot-promotion-rereads.npz',allow_pickle=False) as raw:
        hot=macro([r for r in data['samples'] if r['split']=='train'],{k:raw[k] for k in raw.files})
    selected_hot=sum(hot[l,[32,36,40,44,48].index(c)] for l,c in enumerate(shape['capacities']))
    metric_rows+=['',f'训练家族宏平均：晋升时已在Hot但仍走native重读的专家记录数为 Main40 {hot[:,2].sum():.4f}/token，候选 {selected_hot:.4f}/token。这是现有维护路径的观测，本轮未改为GPU复制，也不将其直接换算为TPS收益。']
    insert=lines.index('预设门槛：Decode≥3%、Prefill回退≤3%、任务组无稳定>5%回退、Bootstrap下界>0、footprint≤65十进制GB。统一Main40仍是默认。')
    lines[insert:insert]=metric_rows+['','维护开销以晋升额外读取数表示；native读取时间包含Miss和晋升读取，不包含全部GPU等待或Python调度，不与其他wall时间直接相加。系统磁盘读使用Darwin ri_diskio_bytesread增量，是OS记账口径，不宣称等同于SSD设备总物理流量。','']
    from plot import render
    figure=render(ROOT)
    at=lines.index('## 4. 独立验收')
    lines[at:at]=[f'![逐层容量与训练加载收益]({figure})','']
    at=lines.index('## 4. 独立验收')
    detail=['| 层 | Main容量 | 训练加载数/token：40→候选 |','|---|---:|---:|']
    choices=[32,36,40,44,48]
    for layer,cap in enumerate(shape['capacities']):
        costs=shape['per_layer_training_costs'][layer]
        detail.append(f'| {layer} | {cap} | {costs[2][0]:.4f} → {costs[choices.index(cap)][0]:.4f} |')
    detail+=['','各层选择由全局1600槽约束共同决定；不能把单层增益排序当作独立贪心选择。','']
    lines[at:at]=detail
    for scope,gain in result['task_decode_gain'].items():lines.append(f'| {scope} | {gain*100:+.2f}% |')
    lines+=['','### 文件缓存控制','', 'F_NOCACHE仅对专家文件描述符启用，不清系统缓存。它是请求绕过文件缓存的控制实验，不能保证操作系统已缓存数据被物理驱逐；不将所有返回字节宣称为物理SSD字节。','', '| 样本 | Main40 Decode | Shape Decode |','|---|---:|---:|']
    persistent=json.loads((ROOT/'persistent-qualification.json').read_text());assert len(persistent)==4 and all(p['event_parity'] for p in persistent)
    persistent_text=['','持续会话额外验证：中英文各四轮，固定历史包含同主题续问、切换到二分查找后返回缓存话题；单个Model持续保留KV、Engram和专家bank，输入逐token追加，并跨过128-token注意力窗口。两个容量方案的每步logits、最终最多16步自由生成和因果缓存事件须完全一致。这是独立推理引擎的增量审计，不是Runtime服务或chunked incremental Prefill的性能验收。','']
    at=lines.index('### 文件缓存控制');lines[at:at]=persistent_text
    ids=sorted({r['id'] for r in qual})
    for ident in ids:
        values=[]
        for v in ['40','shape']:
            ms=[measure(json.loads((ROOT/('nocache-'+v)/(ident+f'-r{i}')/'manifest.json').read_text())) for i in range(2)]
            values.append(np.mean([m['decode'] for m in ms]))
        lines.append(f'| {ident} | {values[0]:.3f} | {values[1]:.3f} |')
    lines+=['','## 复现与产物','', '- 执行步骤：`experiments/dsv41_analysis/l1_shape/PIPELINE.md`。','- 原始路径、SHA与冻结样本：`artifacts/dsv41-l1-shape-20260915/dataset/dataset-manifest.json`。','- 校准：`calibration.json`；完整资格：`qualification.json`；曲线：`replay/curves.npz`。','- 候选及验证选择：`candidate/`；全部案例、复测与TPS/TTFT/内存/命中：`results.json`。','- 每个运行manifest包含源码/量化checkpoint/Native版本、生成、时间、物理内存、晋升及I/O计数；早期pilot源码版本变动由其自身SHA记录。','- 默认checkpoint仍为已校验的SSD版本；没有重下原权重、签名发布Runtime或生成Package。','','## 后续判断','', '若收益不达门槛，优先扩大真实独立题材与长文样本，而不是反复调整到当前测试集通过。移动L1配额属于后续独立内存架构工作，本轮未实施。','']
    path=Path('docs/dsv41f-l1-shape-results-2026-09-15.md');path.write_text('\n'.join(lines));print(path)
if __name__=='__main__':main()
