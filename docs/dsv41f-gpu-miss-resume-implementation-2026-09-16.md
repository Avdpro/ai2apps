# DS4.1F GPU miss/resume 实现与验收（2026-09-16）

后续更新：频繁 miss 的原生 packet 路径已恢复旧路径性能，见 [退化路径优化报告](dsv41f-miss-resume-native-packet-2026-09-16.md)。以下保留旧 guarded 实现的原始负收益记录。

真实 GPU 暂停/恢复机制已完成实验实现，正确性通过，性能门槛未通过。默认保持原有逐层执行路径、L0 Hot8 / L1 Main40、eviction_dual；没有替换已安装 MLX，也没有发布 Runtime/Package。

## 实现

代码：`experiments/dsv41_analysis/miss_resume/`，使用独立构建的 MLX 0.32.0 后端补丁和 native bridge。GPU Gate 检查实际 router 选择与槽映射，首个 required miss 将 Metal ICB 执行范围置零，真正跳过后续 dispatch。完成本次提交后，CPU 从同一个状态包读取失配层与专家，使用现有 GLM 派生极速 SSD loader 补齐，再从该层 MoE 恢复。Attention 不重算，已完成前缀保留，未执行后缀的 KV/频次/年龄状态不提交。

支持 1/2/4/40 层提交窗口，以及原有 Burst Top2/4 的 cold-tail-zero、原权重策略。Block1 恢复时可衔接下一层 router，避免每次只提交孤立的恢复 MoE。最终 norm/head 也进入最后一个受保护窗口。全命中时 router IDs 保留在 GPU；Block40 可以覆盖整条 Decode 链。

本入口限定 batch-one 纯文本 Decode；Prefill 沿用原实现。视觉、并发请求、多流、其它 Burst 尾部策略、L2 预测和产品 Runtime 集成不在此次验收范围。

## 正确性与资源

- 同后端 eager 与恢复路径的 8 步保存状态对照：9 个文件、1,580 个张量逐字节一致，覆盖 logits、KV/共享状态、频次和年龄等。
- 最终原安装引擎对照：8 组配置，每组 32-token 输入、64 次 Decode，含 Prefill 共 65 份 logits；合计 520 份全部逐字节一致。Burst 与其对应旧 Burst 模式对照，不代表 Burst 无损。
- 8 组的专家请求字节数、逐层缓存计数、晋升记录、slot-swap 晋升和 bank fence 次数均与对应旧路径完全一致。
- 40 层窗口补测：1 次 Decode、34 次 miss、35 次提交，完成 40 层且 attention_replays=0；两份 logits 与旧路径一致。
- 最终 native hit/miss smoke 和连续四阶段 GEMM 每阶段 miss 恢复检查通过。
- 最终 8 组物理 footprint 峰值约 55.22–55.27 GB，低于 65 GB 预算。

早期启用 JIT 重编译全部 Metal kernel 时，连 eager Prefill 都与安装 wheel 不一致；已废弃其跨后端性能结论。最终构建直接复用安装 wheel 的原始 mlx.metallib。隔离后端 eager 对照与安装引擎 65 份 logits 全相同，Decode 3.997 vs 4.002 TPS。

## 性能

同一个 coding fixture，单 GPU 进程依次运行；总 Decode TPS 包含第一次 Decode，不含 Prefill。不宣称清除了 OS 文件缓存。这是单用例比较，不是广泛业务性能结论。

| 模式 | 原路径 TPS | 新 Block1 | 新 Block2 | 新 Block4 |
|---|---:|---:|---:|---:|
| 无损 Top6 | 4.002 | 2.803 | 2.695 | 2.139 |
| Burst Top2 | 5.456 | 3.347 | 3.259 | 2.874 |
| Burst Top4 | 4.552 | 3.002 | 未测 | 2.404 |

无损最后 32 步：旧路径 4.742 TPS，新 Block1 3.131、Block2 3.011、Block4 2.269 TPS。负收益不是只来自第一次 Decode。

无损 64-token 测试中，旧路径有 2,560 次逐层命中检查，加 2,099 次 miss 元数据读取；新 Block1/2/4 分别为 2,614 / 2,517 / 2,197 次提交状态回读。Bank fence 都是 2,179 次（包含 Prefill），没有新增晋升 fence。这里是代码路径的回读/提交计数，不能等同于硬件 stall 次数或时长。

因此，“每层都 miss 时应当与旧路径差不多快”尚未得到该实现支持。当前每个算子增加间接执行封装、资源声明和屏障，受保护 encoder 使用 serial dispatch；miss 后虽不执行后缀 kernel，但构图、编码以及重新提交仍有成本。尚未取得细粒度 CPU/GPU 归因 profile，不能把全部损耗定量归到某一个因素。

下一步应先降低每算子的间接调度成本，例如将多个 kernel 组织为可复用的命令段，并测量构图/编码、GPU 控制、被跳过后缀及恢复时间；不能仅因减少回读就开启默认，也不能把本结果当作 L2 必然获益的证明。

## 复现与证据

构建和运行命令见 `experiments/dsv41_analysis/miss_resume/README.md`。最终测试入口为 `benchmark_final.py`，基线在 `bench-wheel`，候选在 `bench-final`。

证据目录：`artifacts/dsv41-miss-resume-20260915/`：

- `bench-final/results.json`：逐组 TPS、峰值、cache 与提交计数。
- `final-verification.json`：逐组 logits、SSD 请求字节和缓存维护一致性。
- `handles-verification.json`：保存状态逐字节对照。
- `block40-final/manifest.json`：完整链恢复边界测试。
- `final-provenance.json`：仓库 commit、MLX 固定 commit、后端/bridge/metallib/补丁 SHA256。仓库有其它未提交工作，commit 不能单独代表本实验源代码。

SSD 字节是专家 loader 请求量，不等同于物理介质实际读取量；OS 缓存可能吸收请求。

## 补充归因：旧流程仅开启执行包装

用户质疑频繁 miss 不应有如此大退化后，增加 `dispatch_control.py` 对照：仍运行旧 AdaptiveModel 的逐层检查/加载算法，不插入 Gate、不触发暂停恢复，只在 Decode 启用受保护后端（逐算子 ICB、serial encoder、buffer barrier、资源声明和禁用 donation）。使用最终原 wheel metallib、相同 32-token 输入和 64 次 Decode。

| 路径 | TPS | 每 token 毫秒 |
|---|---:|---:|
| 原安装引擎 | 4.002 | 249.856 |
| 旧流程，仅启用后端包装 | 2.758 | 362.603 |
| 完整 miss/resume Block1 | 2.803 | 356.804 |

65 份 logits 逐字节一致，专家读取请求量均为 119,854,080,000 bytes。结果显示，即使完全不触发暂停恢复，执行包装本身也已出现同量级损耗。因此当前退化主要应先从后端包装调查，不能当作 miss/resume 算法本身的固有代价。两个候选之间约 1.6% 的 TPS 差别不足以据单次测量宣称恢复带来净收益。

这是整套包装的消融对照，尚未分离 ICB、barrier、serial 调度和 donation 各项占比。下一步优先做这些开销的分项消融，以及让已知安全的恢复段使用原生 dispatch；维持 GPU 真实停止、依赖正确性与现有精度门槛，不直接删除屏障后就设为默认。

原始记录：`artifacts/dsv41-miss-resume-20260915/dispatch-final-control/manifest.json`；汇总：`dispatch-final-control-comparison.json`。
