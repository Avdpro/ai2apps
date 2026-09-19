# DS4.1F 历史 TPS 锚点复核（2026-09-16）

用户指出历史无损约 7 TPS、Burst Top2 约 10 TPS，而近期报告只有 4/5 TPS。复核确认此前报告混用了不同输入的性能数字，没有充分标注负载；同时，历史完整 Top2 10.11 TPS 在当前运行中仍未完全复现。不能用尾段 10 TPS 代替完整 TPS。

## 先纠正比较口径

| 原始记录 | 输入/Decode | L1 / Prefill | 完整 Decode TPS | Top6 总命中率 | Top2 必需专家加载/token |
|---|---|---|---:|---:|---:|
| 历史 Top2 | 重复科普 2048 / 128 | 旧周期策略 / Prefill0 | 10.107 | 88.714% | 3.211 |
| 近期引用的旧 Top2 | 代码任务 32 / 64 | eviction_dual / Prefill64 | 5.456 | 62.533% | 20.656 |

历史 prompt 重复询问天空颜色，生成也延续重复文本；代码任务是 Rust cache 设计问题。历史无损 7.13/7.26 TPS 同样来自 2048/128 重复科普输入，不能与短代码样本的 4 TPS 跨输入计算退步比例。上述差异也含 L1/Prefill 配置变化，不能将全部 TPS 差距定量归到一个因素。

## 当前代码、同负载新旧对照

以下全部使用历史完全相同的 2048-token 输入，128 次 Decode，Main40/Hot8、无层回调、legacy expert dispatch，单 GPU 进程依次运行。完整 TPS 包含首个 Decode；尾段为排除前 16 步后的 112 步。

| 配置 | 完整 TPS | 首个 Decode 秒 | 后112步 TPS |
|---|---:|---:|---:|
| 无损，当前 eviction_dual/Prefill64，legacy | 7.045 | 1.842 | 8.024 |
| 无损，同配置 auto | 7.168 | 1.823 | 8.166 |
| Top2，当前 eviction_dual/Prefill64，legacy | 8.893 | 1.838 | 10.373 |
| Top2，同配置原 auto（13 token 进入 guarded） | 8.682 | 1.859 | 10.046 |
| Top2，同配置 auto，撤掉自动 guarded | 8.640 | 1.878 | 9.968 |
| Top2，同配置 legacy 反序复测 | 8.743 | 1.985 | 10.259 |
| Top2，历史 baseline/Prefill0 参数，legacy | 8.912 | 1.729 | 10.263 |
| Top2，同历史参数，新 packet | 8.884 | 1.921 | 10.389 |

这些是小样本，不能将百分之一至几的差异直接当稳定加速或精确归因。当前高命中 Top2 的新路径没有证明稳定收益；关闭自动 guarded 后也没有观察到明确提升，不能声称回退全部由那 13 个 guarded token 导致。

由于自动 guarded 的性能门槛尚未通过，现已撤掉“连续高命中自动开启”策略。默认 `auto` 保持原生 packet；显式 `guarded` 与恢复诊断仍保留。无损样本本来没有进入 guarded，撤销该策略不影响其这组结果。

## 尚未消除的历史启动差距

按历史 baseline/Prefill0 配置比较：

| Top2 | 全部128步秒数 | 首16步秒数 | 后112步秒数 |
|---|---:|---:|---:|
| 2026-09-13 历史 | 12.664 | 2.085 | 10.580 |
| 当前 legacy | 14.363 | 3.450 | 10.913 |
| 当前 packet | 14.408 | 3.627 | 10.781 |

当前旧路径比历史多 1.698 秒，其中前16步多 1.365 秒，约占 80%；新 packet 比历史多 1.743 秒，其中前16步多 1.542 秒，约占 88%。历史首个 Decode 为 0.630 秒，当前为 1.729/1.921 秒。尾段只比历史慢约 1.9%–3.1%，但这不能抵消完整 TPS 的约 12% 差距。

这部分差距在当前 legacy 中同样存在；目前只定位到耗时区间，没有通过专项 profile 证明是编译、内存映射、I/O、调度或后台负载中的哪一项。没有完整恢复历史源码/执行环境，不能据同参数复测声称排除了所有代码变化。下一步若追历史完整 10.11，应针对首几个 Decode 做分项 profile，而不是继续混用输入或剔除慢步来报告达标。

## 精度与证据

当前同配置新旧每次 129 份 logits、专家请求字节、逐层缓存计数、晋升记录与 bank fence 全一致。历史参数复测的生成 IDs 也与 2026-09-13 历史一致；未把这一点写成跨历史版本全部 logits 逐字节一致。

旧短代码 5.456 TPS 与历史 10.107 TPS 的原始记录分别为：

- `artifacts/dsv41-miss-resume-20260915/bench-wheel/installed-top2-block0/manifest.json`
- `artifacts/dsv41-burst128-t2-b1-20260913/manifest.json`

本轮证据：`artifacts/dsv41-tps-anchor-20260916/` 下 `results.json`、`followup-results.json`、各次 manifest 与 verification。复现脚本：`experiments/dsv41_analysis/miss_resume/recheck_historical_workload.py`、`recheck_anchor_followup.py`。前者原 auto 的 13-token guarded 结果是撤销策略前的历史记录，今后重新运行默认不会再进入该分支。

未隔离所有用户后台应用，允许 OS 文件缓存；IO 请求与物理 SSD 读取不可混同。本轮未发布 Runtime/Package。
