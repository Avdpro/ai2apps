# DS4.1F 全部 FP8 投影迁入 Metal 的精度检查点

2026-09-13。本报告接续 `dsv41f-throughput-target-checkpoint-2026-09-13.md`，以本报告的入口为最新已验收实验路径。目标仍是 Decode 10 tokens/s、2048-token Prefill 300 tokens/s，尚未达到。

## 结果

`experiments/dsv41_reference/run_metal_cpu_order.py` 将所有普通 FP8 GEMM（包括 attention `wo_b` 和共享专家 `w2`）迁入 Metal。移除了约 8.258 GiB 的 CPU FP32 末端投影缓存及相应 CPU GEMM，保留约 7.938 GiB 普通原始权重缓存、每层 L1=8/LRU L0=24，以及专家合并 Prefill。SSD 专家读取仍是未修改的 GLM/Qwen 原生 `preadv_fused_experts`。

CPU attention 主体、router、activation quantization、输出头、非 FP8 算子和 CPU/GPU 往返仍在。因此“全部 FP8 投影”不代表完整 MLX engine，也不代表 device-only all-hit 或 I/O overlap 已完成。普通 FP8 GPU 权重目前每次调用仍上传，累计上传量见 manifest。

## 归约顺序

单纯顺序累加的全 FP8 版本 `run_metal_all_ordered.py` 通过了 26-token 输入，却在短输入的 Decode 失败，不能采用。独立审计在单 token 的 `layers.38.ffn.shared_experts.w2` 捕获一个 BF16 差异。重建其全部 group32 点积发现：CPU 单 token GEMV 使用四路向量归约；八个四通道向量先树形合并，四个通道再从左至右累加。它与 Prefill 的 K 顺序累加不同。

`metal_dense_cpu_order.py` 据此按 M=1 和 M>1 选择归约顺序，并禁用 reassociation/contraction。对三个完整矩阵反例均逐位一致，再通过以下三组全模型 trace。这是当前 PyTorch/CPU 环境和已测形状的实证校准，不是其他 BLAS、硬件或所有可能形状的普遍证明，也不是 CUDA parity。

`test_metal_cpu_order.py` 四项测试通过，包含三个真实舍入边界、有限 FP8 编码、非均匀 scale、非整行块形状与非 group32 拒绝。回归恢复原始 M/N，只把不相关的行置零；缩小为标量 dot 会改变 CPU 归约，不能替代此检查。

## 精度与计时

| 输入 | Prefill 秒 | Decode 每步秒 | 峰值 RSS GiB | CPU bitwise parity |
|---|---:|---|---:|---|
| France，5 tokens + 3 decode | 4.0458 | 1.2146 / 0.9216 / 1.0382 | 31.808 | 832 文件、1,576 张量 |
| opposite，5 tokens + 2 decode | 4.3462 | 1.5175 / 1.2750 | 30.127 | 624 文件、1,182 张量 |
| sky，26 tokens + 1 decode | 8.0401 | 1.7617 | 31.810 | 416 文件、788 张量 |

全部 3,546 张量、119,576,738 元素逐位一致，最大有限绝对差为 0，包括有效状态、路由、子层结果、层边界和 logits/Top-10。对官方未使用 Engram 尾部的规范化与旧基准相同，不修改有效状态。

计时包括 forward、首次缓存填充、读取和 trace，不含模型构建；OS 页缓存未清空，没有严格反复 A/B。原输入三次 Decode 的平均吞吐约 0.945 tokens/s，后两次约 1.02 tokens/s，不能称为长期稳态 TPS。新输入较慢，不能只选最快 token 外推通用性能。26-token Prefill 首次填充约 3.23 tokens/s，不能当作 2048-token Prefill 结果。

相比本轮前半段 CPU 末端投影缓存路径，当前原输入从 1.96/1.57/1.66 秒降到 1.21/0.92/1.04 秒，RSS 从约 37.97 GiB 降到 31.81 GiB。剩余速度差距仍大，CPU attention、输出头、数据往返和专家读取需继续分解。

## 2048-token 验收输入

已生成并验证可 round-trip 的精确 2048-token 原始文本：`artifacts/dsv41-benchmark2048-prompt.json`，包含 token IDs、原文 SHA-256 和目标值。它是可复现吞吐输入，不是质量评估语料。首次 GPU 路径测量使用完整 trace；此长度尚无 CPU golden 对照，不能把一次成功生成当作无损验收。

## 复现

```sh
.venv/bin/python experiments/dsv41_reference/test_metal_cpu_order.py
.venv/bin/python experiments/dsv41_reference/run_metal_cpu_order.py \
  --expert-store artifacts/dsv41-full-expert-store \
  --output artifacts/my-cpu-order-run --decode 3
.venv/bin/python experiments/dsv41_reference/canonicalize_snapshots.py artifacts/my-cpu-order-run
.venv/bin/python experiments/dsv41_reference/compare_traces.py \
  artifacts/dsv41-reference-baseline-20260913 artifacts/my-cpu-order-run \
  --output artifacts/my-cpu-order-run/parity.json
```

Metal 需要 GPU 访问许可；使用新的输出目录。26-token prompt 和参考位置见前述 checkpoint 文档。

当前产物分别位于 `artifacts/dsv41-metal-cpu-order-20260913/`、`dsv41-metal-cpu-order-heldout-20260913/`、`dsv41-metal-cpu-order-prefill26-20260913/`，均含 manifest、trace、parity.json 和 run.log。额外 Decode 反例及完整分组归约枚举位于 `artifacts/dsv41-final-audit-20260913/`。所有实验源码未提交，HEAD 为 `11b5b9ac537e42b1029d1f0148bbbe6a33307f8e`，实际源文件哈希以 manifest 为准。
