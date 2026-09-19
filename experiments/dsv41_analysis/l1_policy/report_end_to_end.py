"""Direct old/new L1 results; do not substitute a component-level comparison."""
import json,statistics
from pathlib import Path
root=Path('artifacts/dsv41-l1-end-to-end-20260915');r=json.loads((root/'results.json').read_text());assert len(r)==8
summary=[]
for case in dict.fromkeys(x['case'] for x in r):
 variants={}
 for policy in ['baseline','eviction_dual']:
  a=[x for x in r if x['case']==case and x['policy']==policy];assert len(a)==2
  assert a[0]['read_bytes']==a[1]['read_bytes']
  assert a[0]['adaptive']['per_layer_counts']==a[1]['adaptive']['per_layer_counts']
  c=a[0]['adaptive']['per_layer_counts']
  variants[policy]=dict(tps=statistics.mean(x['tps'] for x in a),runs=[x['tps'] for x in a],hit=100*sum(v[0]+v[1] for v in c)/sum(sum(v) for v in c),read_gb=a[0]['read_bytes']/1e9,readbacks=a[0]['readbacks'],fences=a[0]['adaptive']['bank_fence_calls'],copy_gb=a[0]['adaptive']['promotion_reuse']['copied_bytes']/1e9,io_seconds=statistics.mean(sum(x['adaptive']['decode_io_seconds'].values()) for x in a),peak_gb=max(x['peak'] for x in a)/1e9)
 for policy in ['baseline','eviction_dual']:
  tails=[]
  for repeat in range(2):
   m=json.loads((root/f'{case}-{policy}-{repeat}'/'manifest.json').read_text());times=m['step_seconds'][17:];tails.append(len(times)/sum(times))
  variants[policy]['after16_tps']=statistics.mean(tails)
 b,n=variants['baseline'],variants['eviction_dual'];summary.append(dict(case=case,old=b,new=n,tps_gain_percent=100*(n['tps']/b['tps']-1),paired_gain_percent=[100*(n['runs'][i]/b['runs'][i]-1) for i in range(2)]))
(root/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
text='''# DS4.1F 完整新旧 L1 直接对照 — 2026-09-15

结论：这轮直接对照测到约1.1%–1.2%的端到端净收益，四个配对方向均为正；属于小幅改善，不是此前局部零复制对照的4.0%/2.4%。样本为两例各两轮，尚不能当作普遍或统计显著的加速保证。

本报告直接回答“整套新 L1 相对旧 L1 有没有收益”，不使用跨批次数字相减，也不把复制与零复制的局部对照当成整体收益。

- 旧策略：baseline，每16步频次维护；Hot晋升已复用内存，但仍复制到固定L1槽。
- 新策略：eviction_dual，双频次、仅L0淘汰时晋升、零复制逻辑槽位交换。
- 固定Main40/Hot8、同一SSD checkpoint、原生preadv、Prefill64槽、Natural无损Decode；没有Burst。
- 短输入coding-en-train-18、128步Decode；长输入long-math_logic-zh-test、2083输入/512步Decode。
- 每例两轮，顺序旧/新、新/旧；共8个新进程。结果没有复用旧批次的测量。
- TPS计时排除Prefill，包含全部Decode前向。所有生成ID及逐步logits SHA完全一致。

| 用例 | 旧TPS（两次） | 新TPS（两次） | 旧均值 | 新均值 | 均值变化 |
|---|---|---|---:|---:|---:|
'''
for x in summary:
 b,n=x['old'],x['new'];text+=f"| {x['case']} | {b['runs'][0]:.3f}, {b['runs'][1]:.3f} | {n['runs'][0]:.3f}, {n['runs'][1]:.3f} | {b['tps']:.3f} | {n['tps']:.3f} | {x['tps_gain_percent']:+.2f}% |\n"
text+='\n| 用例 | 命中率 旧→新 | 请求GB 旧→新 | 缓存读回 旧→新 | bank栅栏 旧→新 | 峰值GB 旧→新 |\n|---|---|---|---|---|---|\n'
for x in summary:
 b,n=x['old'],x['new'];text+=f"| {x['case']} | {b['hit']:.3f}%→{n['hit']:.3f}% | {b['read_gb']:.3f}→{n['read_gb']:.3f} | {b['readbacks']}→{n['readbacks']} | {b['fences']}→{n['fences']} | {b['peak_gb']:.3f}→{n['peak_gb']:.3f} |\n"
text+='\n辅助检查（同样排除双方前16个Decode步骤，保留全部后续步骤；不替代上述端到端TPS）：\n'
for x in summary:text+=f"- {x['case']}: {x['old']['after16_tps']:.3f} → {x['new']['after16_tps']:.3f} TPS。\n"
text+='''
以上是两例、各两轮的配对测量，不能当作所有工作负载的保证或统计显著性结论。
读取字节是应用请求量（包括初始化/Prefill），不等于物理SSD流量。
缓存读回按真实miss事件和调用路径核算，不是Metal驱动事务计数；不包含两侧相同的输出/诊断读回。
bank栅栏是实际_fence调用计数，含两侧相同的初始化/Prefill。
每一对均断言新策略读回和栅栏不增加，且内存峰值小于65十进制GB。
本轮只测量，不修改Runtime、策略默认值或发布Package。

复现：`.venv/bin/python experiments/dsv41_analysis/l1_policy/benchmark_end_to_end.py`
数据与源码快照：`artifacts/dsv41-l1-end-to-end-20260915/`。
'''
Path('docs/dsv41f-l1-end-to-end-comparison-2026-09-15.md').write_text(text)
