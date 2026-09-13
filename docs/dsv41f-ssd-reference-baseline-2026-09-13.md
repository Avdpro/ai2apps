# DS4.1F SSD 精度参考基准

日期：2026-09-13。代码位于 `experiments/dsv41_reference/`，仅用于研究，不修改官方下载源码或已发布推理运行时。仓库 HEAD 为 `11b5b9ac537e42b1029d1f0148bbbe6a33307f8e`；实验新增文件尚未提交，运行器和算子实际 SHA-256 记录在 manifest。

## 参考的性质

本机无 CUDA。此版本直接执行官方 `model.py` 和 `engram.py`，以 CPU PyTorch 实现替代官方 TileLang 算子。它是**官方模型代码 + CPU 算子移植的 SSD 数值参考**，不是已验证与 CUDA 逐位相同的官方 GPU golden。后续存储/缓存实现可先对照它；跨后端优化仍须分别评估 kernel 数值误差，不能由本次复跑一致性推导 CUDA parity。

执行原始精度完整 40 层 Prefill 与 Decode。关闭未调用的视觉构建、DSpark/MTP 构建，文本路径保留原始路由和算术。无 CED bounded replay、专家裁剪、2-bit 或动态缓存。原始 checkpoint 不复制、不整模型反量化。

每个模块执行前从 safetensors 的 offset 用 `pread` 读参数，执行后释放为 meta 占位。官方 MoE 按 expert ID 遍历并仅执行实际命中的专家，因此未命中专家不会读盘。Engram 和 token embedding 按行读取。`wo_a` 按官方 convert.py 转 BF16，head 按官方模型要求升 FP32。保留 FP8 激活量化、router 权重在 w2 之前相乘、FP32 专家归约及 mHC 顺序。

## 输入和已完成的主运行

- 原始 completion prompt：`The capital of France is`，不套聊天模板。
- 输入 IDs：`[671, 6102, 294, 8760, 344]`，5 tokens。
- Prefill 一次产生第一个输出，然后在位置 5、6、7 各执行一次 Decode；覆盖 ratio-2 完整与未完整分组。
- Greedy 输出 IDs：`[11111, 16, 455, 446]`。
- 输出文本：` Paris. The E`。按固定长度结束，不代表完整回答。
- PyTorch 2.13.0，CPU 4 threads，batch 1，最大缓存长度 256，默认 BF16。
- Prefill 54.028 s；三个 Decode forward 分别 18.288、49.903、46.602 s。包含同步 trace/权重 I/O，不作为优化后的模型 TPS 预期。
- 峰值 RSS：8,855,814,144 bytes，约 8.25 GiB。
- 逻辑 `pread`：62,254,584,832 bytes，约 57.98 GiB。可能由 OS 页缓存提供，不是测得的物理 SSD 流量。

主数据目录：`artifacts/dsv41-reference-baseline-20260913/`。

共 832 个 `.pt` 文件：160 组完整层输入/输出、Attention/MoE 输出、Top-6 路由 IDs 与 weights、两层 Engram 命中行及输出、每步全词表 logits/Top-10、KV/Engram buffers、共享 attention 状态。各文件 SHA-256、输入输出、完整配置、官方源文件 SHA-256、运行器/CPU kernel SHA-256、checkpoint 索引 SHA-256 均保存在 `manifest.json`。`trace-summary.json` 提供逐层数值范围、RMS、路由及每步 Top-10 的 JSON 摘要。

完整 tensor 留在 `.pt` 文件中，摘要不能替代精度对照。buffer 快照保存值，不承诺可直接恢复原来的共享别名关系。

## 验证

- 7 项 CPU/SSD 单元测试通过：FP4 全部编码和 ties-to-even、FP8 scale/零输入、FP4 GEMM、非均匀 FP8 block scales、SWA mask/sink/全无效行、跨 64 边界 attention、SSD 重复行/边界检查。
- 真实 checkpoint 的 FP4 expert weight/scale 和 FP8 Engram weight/scale，各抽取 3 行，与独立 safetensors reader 比较，字节完全一致。结果在 `artifacts/dsv41-reference-storage-validation.json`。
- 所有保存的层输出、Engram 输出、路由和 logits 都经过有限值检查；KV mask buffer 中合法的 `-inf` 不当作错误。
- 独立进程复跑：832 个文件、1,576 个 tensor、30,722,252 个元素逐位一致，最大有限数值差为 0。结果见 `artifacts/dsv41-reference-repeat-comparison.json`。
- 首次比较仅发现 `engram_hash.cache` 未使用尾部不同：官方以 `torch.empty` 创建，未写入区域无定义。独立后处理仅把这一区域清零，分别保留每步前 5/6/7/8 个有效 token，未修改模型运行或任何有效状态。前后文件哈希、处理脚本哈希和有效长度均记入 manifest 的 `snapshot_canonicalization`。以上逐位一致结论针对规范化快照；原始层输出、路由和 logits 无需修改就已逐位一致。

CPU kernel 的 block-32 scaled GEMM 和 block-64 online attention 保留显式舍入位置，但 CPU/GPU GEMM 归约、exp、sigmoid、softmax 可能仍有差异。尚未运行 NVIDIA TileLang 数值对照；亦未验证长上下文、视觉、多请求、取消或 MTP。本次结果不能当作这些场景的验收。

## 复现

```sh
.venv/bin/python experiments/dsv41_reference/test_reference.py
.venv/bin/python experiments/dsv41_reference/run_reference.py \
  --output artifacts/dsv41-reference-baseline-20260913 --decode 3
.venv/bin/python experiments/dsv41_reference/run_reference.py \
  --output artifacts/dsv41-reference-repeat-20260913 --decode 3
.venv/bin/python experiments/dsv41_reference/canonicalize_snapshots.py \
  artifacts/dsv41-reference-baseline-20260913 \
  artifacts/dsv41-reference-repeat-20260913
.venv/bin/python experiments/dsv41_reference/compare_traces.py \
  artifacts/dsv41-reference-baseline-20260913 \
  artifacts/dsv41-reference-repeat-20260913 \
  --output artifacts/dsv41-reference-repeat-comparison.json
```

运行器拒绝覆盖已有输出目录；再次复现请换新的目录名。比较脚本检查 tensor 的原始位及配置/源码身份，不比较 PyTorch 序列化容器字节。需要容差的跨后端比较应使用独立、明确容差的验收规则，不能放宽本次同实现复跑检查来掩盖差异。
