# DS4.1F 新 packet 路径兼容性扩展（2026-09-16）

最新默认策略：自动 guarded 的高命中性能门槛未通过，auto 已保持原生 packet，guarded 仅显式选择。见 [历史 TPS 复核](dsv41f-tps-anchor-recheck-2026-09-16.md)。下文的自动触发描述为先前阶段记录。

此前将图像/消息输入、诊断、非默认 L1、Burst 尾部和实验 dispatch 自动回退 legacy 的限制过于保守，现已解除。它们可以保留原数学前向和缓存策略，只用新的 GPU packet 替换 miss 判断与元数据交接。`auto` 对这些配置选择 `packet`；仅显式 `--inference-mode legacy` 使用旧执行器。

跨层 `guarded` 仍限于原先验证的标准配置。支持新 packet 不代表所有配置均已验证跨层暂停/恢复或得到吞吐提升。现有输入合法性规则仍生效，例如原来就禁止的图像＋Burst 组合，不因本次适配自动变成合法配置。

## 实现

`Model` 提供 `routes_all_hit`、`miss_metadata` 和 `burst_miss_metadata` 三个边界。旧执行器的实现保留原来的检查与打包方式。`RoutePacketMixin` 替换这三个边界：GPU 一次写出 miss 状态、当前层、ID、年龄及需要的晋升评分，CPU 从同一完成包取数据，无需新增第二次 GPU 元数据读取。

新适配器继承所选的原 StaticModel、AdaptiveModel 或顺序 BurstModel。因此以下代码继续使用原实现：

- 视觉编码、带历史消息的 Prefill、attention/KV/indexer/router、专家 kernel、head。
- 静态 L1 和各动态策略的 observe/maintain 顺序、晋升与覆写 fence。
- Burst 冷尾部置零、保留权重归一化、按分数替补及权重分配。
- trace、layer-progress 和 route capture 回调。

维护在 miss 之外发生的旧策略仍保留其已有维护边界，适配器不额外增加维护 readback。图像和诊断配置使用原生逐层 packet，未启用逐算子 ICB、全局串行 barrier 或整个状态树快照。

原来的 Burst `--block-layers 2/4` 在标准配置下映射到新 auto 的 guarded window 大小。选定 packet 适配器的配置使用顺序边界，收据另记 requested_block_layers。旧回滚执行器仍可通过显式 legacy 选择，不能将其请求窗口参数误认为本轮每个 token 都实际执行了跨层窗口。

## 新旧对照

共 11 组、22 次新旧运行；105 份候选 logits 与对应旧路径逐字节一致，专家请求量一致。带动态 L1 的组还逐项核对了计数、晋升、bank fence；静态组核对固定缓存统计。

| 测试组合 | Decode 步数 | 结果 |
|---|---:|---|
| 三轮纯文本历史消息 | 4 | 全部一致 |
| 历史图片＋追问，视觉预算 256 | 4 | 全部一致 |
| 同一图片对话，默认视觉预算 1024 | 2 | 全部一致 |
| L1=32＋attention chunk128＋trace/进度/路由采集 | 4 | 全部一致 |
| 按层 L1 扩容＋fused gate/up | 4 | 全部一致 |
| 静态 L1＋unsorted dispatch＋chunk256 | 4 | 全部一致 |
| baseline L1＋Burst Top2 zero-renorm | 20 | 全部一致 |
| dual_fast75＋Burst Top4 fixed-top | 20 | 全部一致 |
| probation32_8＋Burst Top2 renorm | 20 | 全部一致 |
| Burst Prefill Top2＋L1=24＋shared dispatch | 4 | 全部一致 |
| Burst Top2＋旧 block4 参数迁移至新 auto | 8 | 全部一致 |

20 步测试覆盖周期性维护触发点。尾部策略的完整统计、逐层计数和替补数量也一致：fixed-top 实际替补 598 个，renorm 实际替补 1,176 个，不是未进入分支的空验证。

诊断组共 605 份中间张量逐字节一致，采集的 Prefill/Decode 路由数组也一致。全部新路径峰值物理 footprint 不超过 58.21 GB，低于 65 GB 预算。

默认视觉预算 1024 是配置上限，本用例实际完整输入为 516 tokens；结果没有冒称处理了 1024 个实际视觉 token。历史消息测试使用现有 runner 的完整历史 Prefill，不代表已验收一个新的持久多会话服务端。

旧 Burst block4 样本发生 121 次 Attention 回放，新 auto 样本为零；本用例 auto 未达到高命中切换阈值，因此全程走 packet，不把它计作跨层 guarded 性能验收。旧路径 271 次 checks 加 121 次 miss 元数据读取，新路径 320 次 packet 边界读取；bank fence 相同。这是逻辑交接计数，不等同于硬件 stall 次数。

这些是兼容性测试，不是所有参数的笛卡尔积验证，也不用于宣称每个组合的 TPS 都提高。高命中下跨层 guarded 的净收益仍待独立验收。

## 文件与复现

- 原模型边界：`experiments/dsv41_mlx/model.py`、`burst.py`。
- packet 适配：`experiments/dsv41_analysis/miss_resume/route_packet.py`。
- 默认选择/实例化：`experiments/dsv41_mlx/inference_mode.py`、`run.py` 和 `miss_resume/entry.py`。
- 配对测试：`experiments/dsv41_analysis/miss_resume/validate_combinations.py`。
- 收据：`artifacts/dsv41-miss-resume-20260916/expanded-compat/results.json`、`summary.json`、`burst-policy-verification.json`、`vision-default-verification.json`。

正常命令无需额外选择新模式；manifest 的 `inference_selection` 记录实际选择及原因，`miss_resume` 记录实际执行模式、适配器与边界计数。新后端缺失或过旧时明确要求构建，不静默切回旧模型。

本次为独立推理引擎适配，没有发布 Runtime/Worker 或模型 Package。
