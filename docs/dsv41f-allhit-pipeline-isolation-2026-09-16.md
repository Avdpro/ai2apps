# DS4.1F 连续命中与异步流水隔离测试

2026-09-16。诊断基于同一真实 token、同一份 KV/Engram/频次状态，预先加载它的全部 Top6 专家。重复计算前恢复状态，验证每次 logits 完全一致、缓存 miss 为零、专家 SSD 读取为零。缓存准备和恢复在计时外，这不是生成 TPS，也不是 L2 端到端性能。

每个配置预热2次，再按正反顺序交错测量12次。输入上下文2048，使用标准自然 Top6，原生权重和模型计算不变。

| 执行方式 | 中位时间（ms） |
|---|---:|
| 原始逐层路由同步 | 94.73 |
| packet 逐层同步 | 93.85 |
| 原生连续2层 | 88.98 |
| 原生连续4层 | 90.61 |
| 原生整40层构图后执行 | 84.83 |
| 每层异步提交、不等待，继续构建下一层 | 75.05 |
| 每2层异步提交 | 76.88 |
| 每4层异步提交 | 79.44 |
| window40（恢复状态与Gate仍在） | 87.74 |
| guarded40（真正GPU停止） | 159.51 |

直接发现：

1. guarded 的逐算子 ICB 包装有明显额外成本；全命中也不能消除。不能用这个实现推断连续执行或L2的上限。
2. 先构建完整40层图、再执行，没充分发挥 CPU 构图与 GPU 计算的重叠。逐层 `mx.async_eval` 不增加主机等待，相对旧版把时间降低20.8%，等效吞吐提高26.2%。相对整图构建方式的等效吞吐也提高约13%。
3. 因此，上次仅根据window的约5.7%收益就下调L2预期，证据不足。异步流水值得继续，但75.05ms仍是固定token、预先驻留专家的诊断值，不是训练预测器后可直接得到的速度。

实现：`experiments/dsv41_analysis/miss_resume/allhit_isolation.py`。
完整数据：`artifacts/dsv41-allhit-isolation-20260916/async/isolation.json`；首次独立重复：同目录上一级的 `isolation.json`。

已将逐层异步提交加入原生window，窗口结尾仍由原有主机边界确认首个miss并恢复。没有增加主机等待调用或 bank fence。Top2/Top4 的8步 logits、KV/shared/频次/年龄/计数均与参考精确一致。

## 真实有miss时的配对

固定历史2048输入、128 Decode、Top2、Main40/Hot8、eviction_dual、Prefill64、window4，使用正式CLI，按同步→异步→异步→同步运行：

| 配置 | 完整 Decode TPS | 后112步 TPS |
|---|---:|---:|
| 同步提交 A | 8.100 | 9.337 |
| 异步提交 A | 8.809 | 10.291 |
| 异步提交 B | 8.777 | 10.233 |
| 同步提交 B | 8.024 | 9.266 |

两轮合并约8.062→8.793 TPS，提升约9.1%。所有129份 logits、SSD读取字节、晋升、每层统计、bank fence 完全一致。峰值约57.3GB。

这是同组window4的改动前后对照，不是对legacy或历史最快window2的重新排名；不要与之前不同轮次的百分比相加。零miss的26.2%是潜力诊断，真实有miss时这轮为9.1%，两者必须分开。

实验开关 `DSV41_ASYNC_WINDOW=1`；它只用于原生window，不改变guarded执行方式，也不改变默认packet。例如：

```sh
DSV41_ASYNC_WINDOW=1 .venv/bin/python experiments/dsv41_mlx/run.py \
  --inference-mode window --burst-top 2 --resume-block 4 \
  --prompt-json artifacts/dsv41-tps-anchor-20260916/prompt.json \
  --prefill-slots 64 --decode 128 --logits-mode hash \
  --output artifacts/my-async-window
```

正式对照数据：`artifacts/dsv41-allhit-isolation-20260916/real-window4/final-results.json`。复测脚本 `experiments/dsv41_analysis/miss_resume/benchmark_async_window.py` 支持通过 `DSV41_WINDOW_BENCH_DIR` 指定新目录，避免覆盖已有结果。实验仍只覆盖标准文本window；真实GPU停止的低成本实现仍未完成，不能宣称L2端到端收益已经得到验证。
