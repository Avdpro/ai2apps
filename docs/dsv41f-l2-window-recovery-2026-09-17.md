# L2 多层推进退化修复（2026-09-17）

后续更正：用户要求始终多层、仅miss暂停；本报告采用packet回退，**不满足该要求**。真正GPU停止版本的语义验收及尚未达标的性能见`docs/dsv41f-always-resume-2026-09-17.md`。

已恢复旧多层实现的准入与首次miss退出机制。正常缓存和每层真实miss的配对性能恢复到packet水平；全命中仍能连续推进并降低耗时。修改仅在`experiments/dsv41_analysis/l2_predictor/resume_probe/`，未发布Runtime或Package。

## 对照旧实现后的修复

完整阅读旧`miss_resume/packet.py`、`model.py`、`entry.py`及退化/全命中实验记录后确认，之前的保证来自两条路径：频繁miss直接用轻量packet；高命中才进入window，并在首个miss后保留本层Attention、直接续算MoE，后续层转packet。它不等于强制投机窗口在任何命中率都更快。

旧L2入口直接继承MissResumeModel，绕过PacketMixin。虽然复制了首个miss退出分支，却没有设置resume_mode及提供完整native_tail策略，因此该分支没有执行。native window只是记录首个miss，仍然执行安全槽后缀；4层窗口对32token构建2979个完整层图，而逻辑层只有1280。

本次L2WindowModel接回PacketMixin：

- window入口默认从packet开始，沿用上一token至多2个required-miss层的准入规则，不读取压力测试标志决定策略；高miss请求不先投机再回退。
- 进入window后首次miss立刻转native_tail，保留当前层Attention现场，不在同一token反复重新组成失败窗口。显式force诊断仍可绕过保护，不能据该模式承诺无退化。
- 无L2时跳过特征堆叠、调度与READY快照等L2成本。
- 有L2的packet回退继续发布READY、直接消费独立暂存槽；预测提案合并进既有route完成边界。rank64融合提案显式转换int32，未增加每层通知。
- 原生probe增加暂存槽使用位；新增discarded_suffix_layers和discarded_moe_attempts，不再用旧attention_replays=0推断后缀没有重算。
- 保留局部根、延迟计数与逐层异步提交。恢复的是自适应执行器，不声称已实现低成本GPU硬停止。

## 配对性能与正确性

同一9-token提示、固定历史输入轨迹、L0=8/L1=40、严格F_NOCACHE；正常32decode、每层必miss16decode；单进程串行ABBA。下表包含全部decode步，不能与历史2048/128的7–10TPS跨提示比较。

| 测试 | 单层packet TPS | 修复后自适应 TPS | 差异 |
|---|---:|---:|---:|
| 正常缓存，两轮合并 | 4.589 | 4.650 | +1.33% |
| 每层必miss，两轮合并 | 2.034 | 2.027 | −0.35% |

排除前4步分别4.882→4.952、2.076→2.056 TPS。该波动量级视为基本等价，不宣称必miss稳定加速。每轮压力测试640层全部真实miss，cache tags真的失效并通过原loader重新加载；两条路径专家请求字节完全一致。正常与压力测试均零窗口构图、零废弃后缀、逐层packet执行，证明低命中准入生效，并非测到强制多层的优势。

Burst单轮完整decode：Top2为7.401→7.442，Top4为5.791→5.738 TPS；排除前4步为8.073→8.089和6.231→6.224。均属小幅波动，不据此宣称稳定收益。两组同Burst所有logits哈希一致。

全部无损对照与原legacy golden的logits哈希完全一致；正常/压力组峰值约60.88–60.90GB。

## 真正多层与状态交接

全命中采用同一个真实token、相同状态、预加载本token专家，恢复及cache准备不计时。每种形状预热2次，之后正反序采样4次；这是执行器诊断，不是生成TPS。

| 执行 | 中位耗时 | router提交数/token |
|---|---:|---:|
| packet | 92.017 ms | 40 |
| 连续2层 | 86.463 ms | 20 |
| 连续4层 | 81.639 ms | 10 |

2层耗时降低6.04%，4层降低11.28%；全部样本输出逐字节一致、零miss、零SSD读取、bank映射不变。连续推进能力未被关闭。

另对none/state/rank64/Block6四种预测器各跑8decode，诊断强制第一token进入2层窗口。均恰好1次窗口、1次native-tail转移，之后回packet；仅首次窗口丢弃1个后缀层，不再反复累积。Top6全部与原golden一致，L2读取≤64/token、统计的提交+通知≤41/token，峰值≤61.01GB。Block6/state回退期间分别记录202/65次暂存专家使用，说明没有通过关闭L2规避问题。rank64首次因提案dtype失败，修复后独立重跑通过；失败日志保留。

## 证据与边界

产物`artifacts/dsv41-l2-window-recovery-v1-20260917/`：plan冻结初版源码及native哈希；report包含15个成功case；lookahead-fix-verification记录最终case修复验收；allhit/allhit.json为全命中样本；completion.json整合结论及最终源码哈希。原driver/status保留最后case失败历史，不冒充一次全绿。

入口`benchmark_recovery.py`执行成对/压力/转移验收；`recovery_allhit.py`执行全命中隔离诊断。最终补lookahead整型转换、与已测环境一致的window默认开关，并在每token清除上一token的L2标签，防止全局预测器驻留特征使用已过期槽。state-fresh独立8步复测通过golden/预算门禁；既有无L2性能路径不受该清理影响。没有重跑无关训练。

本次首先解决执行器回退，不重新声称L2整体70%覆盖或端到端加速成立。低命中时实际为packet，高命中时才是多层；窗口首次失败仍有至多一个窗口的废弃计算。自适应准入不能数学保证任意突发工作负载永远不变慢，尤其命中率突变或force模式。未重新完成L2×Burst长context矩阵或生产Runtime集成。
