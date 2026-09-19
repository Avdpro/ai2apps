import json
from pathlib import Path
r=Path('artifacts/dsv41-l0-capacity-20260915');assert json.loads((r/'complete.json').read_text())['all_logits_exact'];rows=json.loads((r/'results.json').read_text())
lines=['# DS4.1F L0 容量对照（2026-09-15）','','旧前向归档＋eviction_dual新L1策略，L1每层40槽，40层，完整Top6，Prefill64，legacy dispatch，无逐层回调，逐进程65十进制GB硬限制。仅L0容量8/12/16不同。未修改活动Runtime默认。','','短代码32输入/128Decode按8→12→16运行，长记录分析2083输入/512Decode按16→12→8运行，各单元一次。不是冷SSD测试，允许OS页缓存。完整TPS包含首个Decode；尾段排除前16个Decode。各输入的tokens和所有logits摘要精确一致。','','| 输入 | L0 | 完整TPS | 尾段TPS | 专家命中率 | 全命中层步比例 | miss | native Decode IO秒 | 峰值GB | 晋升数 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for case in ['coding-en-train-18','long-math_logic-zh-test']:
 for x in sorted([x for x in rows if x['case']==case],key=lambda x:x['l0']):
  lines.append(f"| {case} | {x['l0']} | {x['tps']:.3f} | {x['tail_tps']:.3f} | {x['hit_pct']:.3f}% | {x['all_hit_pct']:.3f}% | {x['misses']} | {x['io_s']:.3f} | {x['peak_gb']:.3f} | {x['promotions']} |")
lines+=['','## 相对 L0=8','','| 输入 | L0 | TPS变化 | miss变化 | 峰值增加GB | 缓存回读API次数 | bank fence次数 |','|---|---:|---:|---:|---:|---:|---:|']
for x in rows:
 b=next(z for z in rows if z['case']==x['case'] and z['l0']==8)
 lines.append(f"| {x['case']} | {x['l0']} | {(x['tps']/b['tps']-1)*100:+.2f}% | {(x['misses']/b['misses']-1)*100:+.2f}% | {x['peak_gb']-b['peak_gb']:+.3f} | {x['readbacks']} | {x['fences']} |")
lines+=['','## 解释边界','','L0每层增加4/8槽，额外专家载荷约3.008/6.016GB，实际峰值单独采样。新L1在L0淘汰时晋升，容量变化既保留更多近期专家，也改变晋升时机；Prefill结束时保留的Hot尾部同样随容量改变。这是完整配置的效果，不是单独隔离某一个因素。','','缓存回读API数按观测到的全命中层步与代码调用点重建；不等于GPU驱动提交次数或实际等待时间。bank fence包含初始化/Prefill。native IO只列Decode请求时间，并非物理SSD设备读取时间。','','每单元一次、小样本且未隔离其它用户应用；TPS小幅差异不能认定稳定收益。不把旧批次数据混入本批提升率。','','执行入口：`experiments/dsv41_analysis/l1_policy/benchmark_l0_capacity.py`；汇总入口：`report_l0_capacity.py`。证据：`artifacts/dsv41-l0-capacity-20260915/` 的source-hashes、每次manifest/日志、results及complete。']
Path('docs/dsv41f-l0-capacity-2026-09-15.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
repeats=json.loads((r/'repeat-results.json').read_text())
p=Path('docs/dsv41f-l0-capacity-2026-09-15.md');s=p.read_text();extra=['','## 短测反序复核与建议','','追加16→8两次短测，共8次运行；重复结果的cache_stats、tokens、logits均与首轮一致，峰值<65GB。','','| L0 | 首次完整TPS | 反序完整TPS | 首次尾段TPS | 反序尾段TPS |','|---|---:|---:|---:|---:|']
for x in sorted(repeats,key=lambda z:z['l0']):
 b=next(z for z in rows if z['case']=='coding-en-train-18' and z['l0']==x['l0'])
 extra.append(f"| {x['l0']} | {b['tps']:.3f} | {x['tps']:.3f} | {b['tail_tps']:.3f} | {x['tail_tps']:.3f} |")
extra+=['','**建议继续L0=8，不默认扩大。** 长测L0=12/16相对8的完整TPS约+0.05%/−0.63%，基本持平，峰值额外约2.95/6.02GB。短测16两次完整TPS均低于8，但尾段反序时已接近，不能把首次−17%认定为稳定的持续Decode回退。','','新L1的L0淘汰触发机制与容量相互影响：长测8→16时L1 hits77605→73573，L0 hits12477→19452，晋升5212→2078，总命中率73.31%→75.70%。这说明实际净收益小于仅看L0保留量的预期。读取减少未对应等比例I/O耗时减少，具体时间归因尚未通过专项profile确认。','','最高峰值63.352GB，全部八次精度检查通过；测试只修改隔离源码和分析脚本，未改活动Runtime、Package或默认参数。后续若继续研究大L0，应独立验证晋升触发与容量的耦合，不能直接预设有TPS收益。','','反序入口：`experiments/dsv41_analysis/l1_policy/repeat_l0_capacity.py`；`repeat-results.json`、`final-verification.json`保存复核结果。']
p.write_text(s+'\n'.join(extra)+'\n')
