"""Render the bounded four-way growth/policy comparison."""
import json
from pathlib import Path
r=Path('artifacts/dsv41-growth-transplant-20260915');done=json.loads((r/'complete.json').read_text());assert done['runs']==8 and done['all_logits_exact'];rows=json.loads((r/'results.json').read_text())
labels={'old40':'旧代码 / 全40','new40':'旧代码＋新L1 / 全40','old48':'旧代码 / 指定8层48','new48':'旧代码＋新L1 / 指定8层48'}
lines=['# 固定层扩容与新 L1 四组对照（2026-09-15）','','固定扩容层为0、3、4、13、15、19、23、39（从0编号），各40→48；其它32层40，L0每层8。复用历史growth.json，额外64槽×18,800,640字节=1.203241GB专家载荷。没有重新挑层或引入机动槽。','','四组均使用L1优化前归档源码；新L1组仅移植缓存策略及必要的miss/槽位角色支持。扩容仅移植形状验证，不改前向。四组保留同一旧runner、attention、router、kernels、Prefill、native preadv；活动Runtime未修改。归档不等于已经逐文件恢复9月14日7.36TPS源码。','','完整Top6、Prefill64、legacy dispatch、无逐层回调、同SSD checkpoint。coding32/128、记录分析2083/512，各四组一次；短例按表顺序运行，长例反序。共8次，所有配对输入/输出及logits摘要完全一致，峰值<65十进制GB。完整Decode TPS包含首个Decode；尾段排除前16步，不能代替完整指标。','','| 用例 | 配置 | Decode TPS | 尾段TPS | 命中率 | miss | Decode native IO秒 | 峰值GB |','|---|---|---:|---:|---:|---:|---:|---:|']
for case in ['coding-en-train-18','long-math_logic-zh-test']:
 for variant in labels:
  x=next(x for x in rows if x['case']==case and x['variant']==variant)
  lines.append(f"| {case} | {labels[variant]} | {x['tps']:.3f} | {x['tail_tps']:.3f} | {x['hit_pct']:.3f}% | {x['misses']} | {x['io_s']:.3f} | {x['peak_gb']:.3f} |")
lines+=['','## 分离两项收益','','| 用例 | 新L1 / 全40 | 固定扩容 / 旧策略 | 扩容后再加新L1 | 新L1后再扩容 | 组合 / 原始旧代码 |','|---|---:|---:|---:|---:|---:|']
for case in ['coding-en-train-18','long-math_logic-zh-test']:
 d={x['variant']:x for x in rows if x['case']==case};v=[d[a]['tps']/d[b]['tps']-1 for a,b in [('new40','old40'),('old48','old40'),('new48','old48'),('new48','new40'),('new48','old40')]]
 lines.append('| '+case+' | '+' | '.join(f'{x:+.2%}' for x in v)+' |')
lines+=['','## 证据边界','','- 各单元仅一次，不把小幅TPS变化解释成稳定提升；本次主要回答固定扩容与替换策略是否能叠加。精确命中率和miss属于同token轨迹的确定性结果，吞吐受运行波动影响。','- 不把此前不同时间、输入或当前baseline开关的成绩混入本表。此前固定扩容在512-step样本约+0.57%，五例整体约−0.10%，并非已确认普遍增益。','- 新L1减少晋升SSD重读与内存复制，但增加频次/评分及角色统计GPU运算；回读API数量不是实际GPU阻塞时间。','- OS页缓存允许；native IO为请求计时，requested_gb包含初始化与Prefill，不代表物理SSD读取量。','- 本次不修改默认缓存策略，不发布Runtime/Package。','','## 产物','','执行：`experiments/dsv41_analysis/l1_policy/benchmark_growth_transplant.py`。汇总：`experiments/dsv41_analysis/l1_policy/report_growth_transplant.py`。独立源码哈希、每次manifest/日志、结果和完成标记位于 `artifacts/dsv41-growth-transplant-20260915/`。']
Path('docs/dsv41f-growth-l1-combination-2026-09-15.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines[8:]))

# Keep the anomalous first pass and the reverse-order evidence together.
repeats=json.loads((r/'repeat-results.json').read_text())
p=Path('docs/dsv41f-growth-l1-combination-2026-09-15.md')
s=p.read_text()
append=['','## 反序复测与最终判断','','长输入首次new48→old48→new40→old40；发现new40明显偏慢后，另跑new40→new48。所有复测logits与缓存计数一致，峰值仍低于65GB。共10次运行。','','| 新策略容量 | 首次TPS | 反序复测TPS |','|---|---:|---:|']
for x in repeats:
 first=next(z for z in rows if z['case']=='long-math_logic-zh-test' and z['variant']==x['variant'])
 append.append(f"| {x['variant']} | {first['tps']:.3f} | {x['tps']:.3f} |")
append+=['','**命中率收益可以叠加，但本轮没有证明稳定的TPS叠加收益。** 短输入在新L1上扩容：命中率73.018%→73.428%，TPS4.663→4.629（−0.73%）。长输入命中率73.309%→74.018%，miss32798→31927；首次TPS4.360→4.980（+14.22%），反序4.703→4.467（−5.02%），方向反转。不能把首次14%或两轮混合均值宣传为确定收益。','','扩容额外载荷1.203GB，实测峰值增加约1.19GB，组合最大峰值以所有manifest为准。现有证据不足以把固定扩容设为默认；保留为可选，并维持全40槽容量默认。前述首轮百分比表仅为原始记录，必须结合本节解读。','','反序脚本：`experiments/dsv41_analysis/l1_policy/repeat_growth_transplant.py`；额外结果：`repeat-results.json`；最终验证：`final-verification.json`。']
p.write_text(s+'\n'.join(append)+'\n')
