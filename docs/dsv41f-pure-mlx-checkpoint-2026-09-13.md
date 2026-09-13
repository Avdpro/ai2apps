# DS4.1 Flash 完整 MLX 文本前向检查点

2026-09-13。入口：`experiments/dsv41_mlx/run.py`。实验分支
`experiment/moe-cache`，基础提交 `11b5b9ac537e42b1029d1f0148bbbe6a33307f8e`；
当前实验源文件尚未提交，实际源码 SHA-256 写入各运行 manifest。

## 已完成的迁移

独立 MLX 模型替代混合 runner 的 CPU 张量前向：40 层 attention、KV
compression、indexer、router、共享与路由专家、mHC/Sinkhorn、Engram
哈希与门控、norm、RoPE、最终输出头均为 MLX/Metal。推理入口在初始化后和
完成后检查 `sys.modules`，本次所有成功运行均记录 `torch_imported: false`。
Torch 仅用于独立的离线比较和单元测试。

CPU 仍负责分词、文件读取、缓存元数据、SSD 行地址和保存结果。专家全命中时
仅回传命中状态，路由 ID 保留在 GPU；未命中时获取替换所需的 ID。
Engram 原始权重保留 SSD，读取选中行后在 GPU 解量化。未改变原始权重或裁剪专家。

L1/Main 每层 40 个专家，按当前 Prefill 频次选择；L0/Hot 每层 8 个。
复用 GLM 的 native expert loader 与现有 Metal bank，保留 GPU 消费与覆盖间的
同步保护。Prefill 先算驻留专家，冷专家按 Hot 容量分组；至少 128 个 token
的专家使用矩阵乘，小组使用 gather QMM。所有专家输出在 GPU 汇总。

当前支持 batch=1 的一次完整 Prefill 和逐 token Decode。多模态、MTP、
分块 Prefill 与生产 oMLX 集成不在本次实现范围内。

## 最终测量

机器：M5 Max，128 GiB 统一内存。原始官方检查点索引 SHA-256：
`74b0686a3d2891980d5e303251b075a3bccae2c2ff650747db2620a649b98fa8`。

```sh
.venv/bin/python experiments/dsv41_mlx/run.py \
  --prompt-json artifacts/dsv41-benchmark2048-prompt.json \
  --decode 32 --output artifacts/dsv41-pure-mlx-final2048-20260913
```

| 指标 | 最终运行 |
| --- | ---: |
| Prefill 输入 | 2048 tokens |
| Prefill | 19.5399 秒 / 104.81 TPS |
| Decode（32 步总时间计） | 6.63 TPS |
| 第一 Decode 步 | 0.4767 秒 |
| 进程 physical footprint 采样峰值 | 54.895 GB（十进制） |
| Decode L1 命中 / L0 命中 / 未命中 | 6624 / 127 / 929 |
| Decode 合计命中率 | 87.90% |

MLX 空闲缓存限制 2 GiB，分配器 memory limit 为 60 GB；进程 footprint
每 20 ms 采样，层/步边界检查 65 GB。采样结果不等于操作系统瞬时硬限制。
这是单次、已进行多轮读取后的测量，未清除 OS 文件缓存；不能称为冷 SSD 性能。
仍未达到 Decode 10 TPS / Prefill 300 TPS 目标。

## 精度与回归

- `test_kernels.py`：三类激活量化的随机 BF16 样本与 CPU 参考逐值一致，
  有限 FP8 编码解码一致。
- `test_core.py`：RoPE cos/sin 最大误差 1.526e-5；mHC 源/目标方向测试通过；
  2048 Prefill + 2 步 Decode 的两层 Engram 哈希与保存参考完全一致。
- 最终 2048 + 32 运行的 33 个生成 token 与之前混合矩阵版本
  `dsv41-matrix-prefill-main40-20260913` 一致；33 步最大 KL 0.001763，
  最低 Top-10 重合 7/10。Prefill logits RMSE 0.3896、cosine 0.9937。
- `dsv41-pure-mlx-finalshort-20260913` 保存逐层 safetensors；France 短输入
  输出 ` Paris. The E` 与 CPU 一致，但首步 logits RMSE 1.465、KL 0.3363，
  不能称为逐值无损。
- `dsv41-pure-mlx-final26-20260913` 的 26-token 天空问题输出 ` (3`，
  CPU 参考为 ` (4`，第二个输出 token 分歧。该记录保留在 `numerics.json`，
  不用长输入单一用例的生成一致掩盖短输入差异。
- `dsv41-pure-mlx-finalheldout-20260913` 的 hot/cold 输入输出
  `\ncold\n`，CPU 参考为 ` cold. The`；从第一个输出 token 即有分歧，
  后续 logits 已不是相同上下文比较。比较器逐步记录 `same_context`。

因此，完整 MLX 前向迁移和运行验收已完成，但这些有限样本不能证明整体质量
等价或“无损”验收。CPU 参考本身也是官方 TileLang 算子的 CPU 翻译，未独立
验证 CUDA 一致性。后续应在当前 MLX 路径继续做多输入数值评估与性能优化。

所有最终运行均保留完整 logits、源码/权重索引哈希、生成 IDs、内存、每步耗时，
离线比较结果位于各 artifact 的 `numerics.json`。性能运行未开启中间层落盘；
France 短输入开启 `--trace`，其耗时不能作为纯推理性能使用。
