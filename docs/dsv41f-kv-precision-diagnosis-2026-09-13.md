# DS4.1F 多轮 KV 数值差异定位

2026-09-13。承接 `dsv41f-multiturn-validation-2026-09-13.md`，本轮只做诊断，没有修改推理、缓存或默认精度配置。

## 结论

已实证首个差异来自 MLX MXFP8 投影的批量/单行执行形状，而非先出现在专家热交换、KV 读取或压缩状态中。可以按已知数值精度差异接受，继续优化，不必以完整重放与增量 KV 的 logits 逐位一致作为阻塞条件。此实验不等于排除了所有长上下文、图像追加或压缩状态问题，也不构成任意输入生成结果相同的证明。

## 实验

完整重放 text-3 的 67 tokens，对比先 Prefill text-1 的 24 tokens，再逐 token 追加至同一个 67-token 前缀；使用完整 Top6、动态 L1=40、Hot=8、Prefill slots=64，原始权重。两模型串行释放后重载，峰值分别 55.931/55.188 decimal GB。

按执行顺序捕获最后一个 token 的线性投影输入/输出、attention 输出、层输出和路由 ID。另在完整重放过程中，对同一个投影输入的最后一行单独调用原始 linear，以隔离历史状态和上游误差。309 个投影调用中，215 个批量/单行复算存在非零差异，包含 FP8 投影和 FP32 累加的压缩投影。

首个差异位于 `layers.0.attn.wq_a`：

- 输入完全相同。
- 输出最大差异 0.0009765625，RMSE 0.0001894396，1280 个值中 538 个不同。
- 同输入单行复算与真实增量路径产生相同差异指标。
- `layers.0.attn.wkv` 同输入最大差异 0.001953125。
- 第 0 层没有压缩和 Engram；wq_a 的差异发生在注意力访问 KV 和 MoE 之前。

进一步将同一行重复为 67 行，直接调用 `quant` 和 `mx.quantized_matmul(mode='mxfp8')`：

|算子|量化输入 batch/row 差异|QMM batch/row 最大差异|batch 对 FP32 RMSE|row 对 FP32 RMSE|
|---|---:|---:|---:|---:|
|第 0 层 wq_a|0|0.0009765625|0.0001696026|0.0001101460|
|第 0 层 wkv|0|0.001953125|0.0002548614|0.0001320677|

重复行 batch 结果与原完整重放捕获的投影输出逐位相同。FP32 对照使用同一量化后的激活和解量化的原 FP8 权重；只用于单算子诊断，不是全模型 FP32 基线。由此可把这两个算子的差异定位到矩阵乘法数值执行路径，不能归因于激活量化输入不同，更不能简单称为 SSD 读取错误。实验没有进一步拆解 Metal 内核内部各次累加和转换。

小误差经过归一化、再次量化和 MoE 路由放大：最后一个 token 从第 4 层起出现路由集合变化，总计 11/40 层路由 ID 不同；最终 logits 最大差异 4.0944595，RMSE 0.7756011。这与之前多轮增量审计该位置的最大差异一致。

此前 41 个 logits 对照位置 Top1 全部一致，9 轮语义检查通过，但包含初始 Prefill 对照，且一个位置 KL 达 0.10375。因此可以接受数值容差，不能把这些数据改称逐位无损，也不能保证长生成永不分叉。完整历史重放的重复运行仍逐位一致。

## 复现和产物

```sh
.venv/bin/python experiments/dsv41_analysis/diagnose_kv_precision.py --out artifacts/dsv41-kv-precision-20260913
.venv/bin/python experiments/dsv41_analysis/isolate_fp8_shape.py
```

输出目录必须不存在；第二条读取第一条产物。第一条比较的是 text-1 到 text-3 的同一最终前缀，未单独复测图像路径。

- `artifacts/dsv41-kv-precision-20260913/report.json`：按执行顺序的逐算子差异和同输入对照。
- `artifacts/dsv41-kv-precision-20260913/isolated_fp8.json`：独立 QMM/FP32 对照。
- `replay.npz`：完整重放最后位置的投影及层输出；`incremental.npz`：增量最终 logits。
- `artifacts/dsv41-kv-precision-20260913.log`：运行记录。

哈希值等离散状态不以此脚本的浮点转换结果作为逐位正确性证据；本轮数值定位依赖投影输入/输出。
