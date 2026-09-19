# DS4.1F miss/resume 退化路径优化（2026-09-16）

最新默认策略：自动 guarded 的高命中性能门槛未通过，auto 已保持原生 packet，guarded 仅显式选择。见 [历史 TPS 复核](dsv41f-tps-anchor-recheck-2026-09-16.md)。下文的自动触发描述为先前阶段记录。

后续更新：原先图像/诊断等回退 legacy 的限制已解除，见 [packet 兼容性扩展](dsv41f-packet-compatibility-2026-09-16.md)。本文保留分阶段验收记录。

本轮已将频繁 miss 时的性能恢复到旧路径水平。此前逐算子 ICB 包装造成的约 30% TPS 回退不再出现在轻量路径。新实验入口默认 `auto`；后续已将独立纯文本 `experiments/dsv41_mlx/run.py` 也设为默认 auto，保留 `--inference-mode legacy`。正式 Runtime/Worker 尚未集成，不涉及发布。

## 改动

- 新增原生 `MissResumePacket` GPU kernel：MoE 入口一次完成槽查找、required miss 判断及 miss 元数据打包。CPU 等待该边界后只需读取一次状态；不再先读 bool、miss 后再另读 IDs/ages/rank。
- 普通 Attention、router、专家计算和 head 全部走原生 MLX dispatch。此路径没有每算子 ICB、额外全局 barrier、全局串行 encoder、禁用 donation 或整树快照，也不复制 hidden。
- Attention 完成后当前 MoE 的输入、权重和残差自然保留在调用栈/MLX 图里。SSD 准备好后直接继续计算，无需回滚或重算 Attention。
- 保留现有 `LRUMetalBank.prepare`、GLM 派生 `preadv_fused_experts`、L0 eviction 双频次晋升和既有 bank fence。命中时专家 ID 不读到 CPU；miss 包包含当前层、缺失专家和维护信息。
- `auto` 从逐层 packet 路径开始；连续四个 token 各至多两个层 miss 时才允许跨层提交。跨层阶段一旦 miss，保留已完成前缀，从当前层 MoE 开始用原生 dispatch，当前 token 后续层全部改用 packet。策略判断使用已有主机计数，不增加 GPU 回读。
- `packet` 可强制轻量路径；`guarded` 保留旧 ICB 路径供诊断。`resume-block` 只影响跨层窗口。高命中下 auto 的最优阈值和性能收益尚未验收。

## 性能对照

同一个 32-token coding 输入、Main40/Hot8、eviction_dual、Prefill64。单 GPU 进程顺序测试，旧路径使用已验证与安装 wheel 精度/TPS 一致的隔离 eager 后端。使用原安装 wheel 的 mlx.metallib。表中 TPS 包含第一次 Decode，不含 Prefill。

| 测试 | 旧路径两轮 TPS | 新路径两轮 TPS | 均值旧 → 新 |
|---|---|---|---|
| 正常缓存，64 Decode | 3.944 / 3.994 | 4.007 / 4.058 | 3.969 → 4.032 |
| 每层必 miss，16 Decode | 2.160 / 2.232 | 2.245 / 2.252 | 2.196 → 2.248 |

正常缓存按新/旧/新/旧顺序采样；必 miss 压力测试按旧/新/新/旧顺序采样。前者新路径约 +1.6%，后者约 +2.4%；这种小幅差异应视为基本等价，不作为稳定加速的承诺。两组均未观察到原来约 30% 的退化。

必 miss 测试剔除首次 Decode 后，旧路径 3.293 / 3.353 TPS，新路径 3.380 / 3.393 TPS，也保持等价。未清除 OS 文件缓存，专家 loader 请求字节数不等同于物理介质读取字节数。

“每层必 miss”不是伪造状态标志：诊断在每层 MoE 前使全部专家 tag 失效，旧/新路径均真实调用原 loader 重载该层全部六个专家。每轮 16×40=640 个层全部 miss，3,840 个专家请求，合计 108,291,686,400 bytes。所有 40 层的计数均为 `[L1=0,L0=0,miss=96]`。该人为 cache 配置仅用于退化验收，不能当正常模型 TPS。

Burst 兼容性测试（64 Decode，旧数据来自前次相同 fixture 的安装引擎参考，非本轮交替测速）：

| 模式 | 原参考 TPS | 新 packet TPS |
|---|---:|---:|
| Top2 | 5.456 | 5.635 |
| Top4 | 4.552 | 4.643 |

这些 Burst 数据说明没有复现旧 ICB 的巨大回退；小幅收益仍需更多重复测试才能定量。

## 同步与正确性

- 必 miss 每轮旧路径为 640 次命中检查＋640 次 miss 元数据回读；新路径为 640 次 packet 边界回读。旧/新 bank fence 都为 720（含 80 次 Prefill），没有新增晋升 fence。
- 正常 64 Decode 旧路径为 2,560 次命中检查＋2,099 次 miss 元数据回读；新路径为 2,560 次 packet 回读。Bank fence 均为 2,179，专家请求量均为 119,854,080,000 bytes。
- 上述是代码路径中的边界/回读计数，不把它等同于硬件 stall 的次数或时长；原来的其它同步没有被冒称消除。
- 两轮正常新路径各 65 份 logits、两轮必 miss 新路径各 17 份 logits、Burst Top2/4 各 65 份 logits，与对应旧路径逐字节一致。必 miss 的 logits 也与正常缓存原参考前 17 份完全一致。
- 逐层命中计数、专家请求字节数、晋升记录、slot-swap 次数和 bank fence 对照完全一致。
- 刻意交替 packet/guarded 入口的 8-step 状态验收：4 次进入 guarded、4 次从首个 miss 转入 native tail，320 层完成，attention_replays=0；9 个状态文件、1,580 个张量与旧 eager 逐字节一致，包含 KV、共享状态、频次、年龄及 logits。该测试强制切换，仅用于正确性，不用于性能结论。
- Burst Top2/4 各补测 8 步交替切换，各 9 份 logits 与对应原 Burst 参考完全一致，均为 4 次 guarded → native-tail，Attention 重算为零。见 `burst-transition-verification.json`。
- 峰值物理 footprint 约 55.3 GB，低于 65 GB 预算。

## 使用与复现

```sh
.venv/bin/python experiments/dsv41_analysis/miss_resume/build.py
.venv/bin/python experiments/dsv41_analysis/miss_resume/launch.py \
  --resume-mode auto --resume-block 4 \
  --prefill-slots 64 --decode 64 --logits-mode hash \
  --output artifacts/my-native-packet-run
```

强制退化诊断需显式加 `--resume-stress-all-miss`；用 `--resume-eager-control` 跑同样诊断下的旧路径。不得在一般模型运行中使用该诊断。

代码：`experiments/dsv41_analysis/miss_resume/packet.py`、`native.cpp`、`model.py`。测试：`packet_smoke.py`、`benchmark_packet.py`、`transition_check.py`。原有 `benchmark.py` / `benchmark_final.py` 已显式固定 `guarded`，避免旧测试脚本悄悄改成 auto。

证据：`artifacts/dsv41-miss-resume-20260916/packet-results.json`、`additional-verification.json`、`transition-state-verification.json` 和对应各 run 的 manifest。`packet-natural` 是首轮正常新路径结果，后续配对由 `benchmark_packet.py` 执行。测试期间新增的 native-tail 分支不影响正常/必 miss 的 packet 性能路径；最终切换检查覆盖该分支。

范围仍是 batch-one 纯文本 Decode、Natural Top6 / Burst Top2/4 cold-tail-zero。Prefill 沿用原实现；未升级多模态、并发 Runtime 或 Package。L2 训练仍未启动。

## 独立推理入口默认值落地

`experiments/dsv41_mlx/run.py` 直接运行时，已默认选择新 `auto` / block4。通过独立子进程加载匹配的后端，不修改安装 wheel；`--inference-mode legacy` 明确选择旧引擎。无法加载新后端时给出构建命令，不悄悄退回旧引擎。图像/消息输入、诊断和未验收的参数组合保留原路径，打印原因并写入 `inference_selection`。显式要求新引擎却使用不支持组合时直接报错。

入口验证使用默认 5-token 文本和默认 Prefill（0），分别运行默认命令与 `--inference-mode legacy`，8 次 Decode、9 份 logits 全相同，SSD 请求、cache、晋升与 fence 一致。收据：`artifacts/dsv41-miss-resume-20260916/default-entry-verification.json`。4 项 CPU 选择/参数转发/缺少后端错误测试通过。此短测试仅验证入口选择，不替代前述 64-step 性能测试。

正式 Runtime/Worker 尚未集成，这次没有修改已发布产品，也没有生成或发布 Package。高命中下跨层窗口的净性能收益仍需单独验收。
