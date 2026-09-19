import json
from pathlib import Path
r=Path('artifacts/dsv41-old-l1-transplant-20260915');rows=[]
for case in ['science','coding']:
 ref=None
 for suffix in (['old','transplant'] if case=='science' else ['old','transplant','old-repeat','transplant-repeat']):
  m=json.loads((r/f'{case}-{suffix}'/'manifest.json').read_text());assert m['status']=='complete'
  sig=[m[k] for k in ['input_ids','generated_ids','logits_sha256']]
  if ref is None:ref=sig
  else:assert sig==ref
  t=m['step_seconds'];c=m['cache_stats'];a=m['adaptive_l1']
  row=dict(case=case,variant=suffix,tps=128/sum(t[1:]),tail112_tps=112/sum(t[17:]),first_decode_s=t[1],hit_pct=100*(c['l1_hits']+c['l0_hits'])/c['route_requests'],misses=c['misses'],io_s=sum(a['decode_io_seconds'].values()))
  if 'transplant' in suffix:assert a['policy']=='eviction_dual' and a['promotion_reuse']['copied_bytes']==0
  rows.append(row)
(r/'verified-results.json').write_text(json.dumps({'runs':rows,'exact_logits':True},indent=2))
lines=['# 旧源码移植新 L1 对照（2026-09-15）','','## 结论边界','','当前 baseline 开关并不等于优化前源码。默认策略虽保持16步/最多4晋升，但仍有新增函数分派、通用槽位扫描、统计封装及Hot晋升复用。不能再把当前 baseline 测试称为完整旧代码测试。','','本次直接使用 L1 shape 初期归档源码，构建独立副本，仅移植新 L1 及必须的缓存bank、miss元数据和物理槽位统计支持。旧 runner、attention、kernels、router、专家计算、Prefill 等文件保留；脚本验证未改模块逐字节一致。该归档早于近期L1工作，但并非已验证逐文件匹配9月14日7.36 TPS的完整源码；不能声称完全复现那个版本。','','完整Top6，Main40/Hot8，Prefill64，legacy dispatch；同checkpoint与输入，Decode128。完整TPS包含首个Decode；后112步为另列指标。所有成对129份logits及生成token精确一致。science输入2048tokens，coding输入约32tokens。science旧→新一次；coding新→旧、旧→新两次。','','| 输入 | 版本 | Decode TPS | 后112步TPS | 命中率 | miss | native IO 秒 |','|---|---|---:|---:|---:|---:|---:|']
for x in rows:lines.append(f"| {x['case']} | {x['variant']} | {x['tps']:.3f} | {x['tail112_tps']:.3f} | {x['hit_pct']:.3f}% | {x['misses']} | {x['io_s']:.3f} |")
old=[x['tps'] for x in rows if x['case']=='coding' and x['variant'].startswith('old')];new=[x['tps'] for x in rows if x['case']=='coding' and x['variant'].startswith('transplant')]
lines+=['',f'coding 两次均值：{sum(old)/2:.3f} → {sum(new)/2:.3f} TPS，变化 {(sum(new)/sum(old)-1)*100:+.2f}%。','', '- 新策略在低命中coding提高命中率约1.92个百分点；在高命中science反而下降约0.13个百分点。不存在所有输入都提高命中率的证据。','- 新策略不仅更改内存指针：GPU频次衰减/累加、miss候选评分、槽位角色掩码统计仍有开销；没有增加回读API次数不代表零额外成本。','- science此次速度略升，与前一轮旧源码/当前新策略对照方向不同；不视为稳定收益，不能仅据一对宣称回退或提升。','- 两种输入为诊断小样本，不能推广为生产总体收益。系统页缓存允许，未隔离用户其他应用，不把进程负载观测当作因果解释。','- 未修改活动Runtime或默认策略。旧历史完整7.36TPS仍未恢复，该问题不能以更换样本或尾段吞吐消解。','','复现入口：`experiments/dsv41_analysis/l1_policy/benchmark_old_transplant.py`；反序coding追加使用相同命令，输出后缀`-repeat`。汇总入口：`report_old_transplant.py`。独立源码、哈希、日志、逐次manifest位于 `artifacts/dsv41-old-l1-transplant-20260915/`。']
Path('docs/dsv41f-old-source-l1-transplant-2026-09-15.md').write_text('\n'.join(lines)+'\n');print(json.dumps(rows,indent=2));print('coding change',sum(new)/sum(old)-1)
