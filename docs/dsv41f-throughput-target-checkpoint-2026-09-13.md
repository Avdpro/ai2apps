# DS4.1F 吞吐目标、常驻缓存与 FP8 归约精度

2026-09-13。目标为无损 Decode 约 10 tokens/s、Prefill 约 300 tokens/s，用户已确认 **Prefill 按 2048 tokens 验收**，**尚未达到**。分别记录首次填充与缓存热身后的吞吐及读取量，避免混淆计时口径。本轮仅修改实验代码和文档；HEAD 为 `11b5b9ac537e42b1029d1f0148bbbe6a33307f8e`，未提交修改的实际源码哈希见每次 manifest。官方权重、官方模型、CPU golden 和 GLM/Qwen 原生 C++ 加载器未修改。

## 当前验收入口

`experiments/dsv41_reference/run_metal_ordered.py`：

- 普通原始权重 admission-only 常驻缓存，限额 12 GiB，实际约 7.938 GiB；稀疏行缓存限额 8 MiB。Engram 大表继续按行读取。
- 末端 CPU 投影按模块身份持有 `[K/32,N,32]` FP32 权重，限额 24 GiB，实际约 8.258 GiB。一次运行只对应一个不可变 checkpoint，未提供切换 checkpoint 或原地更新权重的缓存复用协议。
- 每层固定 L1=8、LRU L0=24，总槽位原始字节约 22.41 GiB。先使用空槽，再淘汰未被本批请求的最久未使用专家；保留原生加载器、lazy consumer 屏障和失败时不发布标签。
- Prefill 按专家合并 token/expert 对，批大小不超过 L0 容量；计算后恢复每个 token 的专家 ID 升序 FP32 累加。26-token 样本的专家 GPU dispatch 从逐 token 的 1,040 次降到 109 次；这不等同于已经使用高吞吐矩阵块 GEMM。
- 内部 FP8 Metal GEMM 按每个 group32 的 K 顺序累加，禁用 contraction/reassociation，以匹配已测 CPU 归约。最终 attention `wo_b` 和共享专家 `w2` 仍在 CPU。
- CPU router、attention 主体、输出头、activation quantization、host 路由和 CPU/GPU 往返仍在；没有声称实现 device-only all-hit 或 SSD/GPU overlap。

普通 GPU FP8 权重缓存、批量 CPU group GEMM、补偿求和均保留为独立实验入口，**未纳入当前入口**。前两者没有建立稳定收益；补偿求和通过了一个反例却改变另一个 CPU 舍入结果，不满足验收。

## 本轮发现并修复的精度问题

之前的两条 5-token 输入通过，不能外推到其他长度。新增 26-token 输入：

`Explain why the sky appears blue during the day and red near sunset, using a simple description of how sunlight interacts with the atmosphere.`

原先 `run_metal_dense.py` 和新增批量调度版本均在第 10 层 attention trace 开始偏离，后续 Top-10 也有差异。隔离实验排除了新增缓存/调度是唯一原因。FP8 审计首次捕获 `layers.9.attn.wq_b` 的 `[1,26,32768]` 输出中一个值不同，绝对差 `1.52587890625e-05`。补偿求和修复此反例，但另一个 `layers.5.attn.wq_b` 值偏离 CPU `5.960464477539063e-08`。

显式按 K 顺序累加同时通过两个完整矩阵反例，并通过全部三条输入的完整 trace。CPU GEMM 归约会受 M/N 形状影响，不能将真实矩阵缩成一个标量 dot 来定义相同参考。两个小型 FP8 样本保存在 `fixtures/fp8-rounding-case*.json`；测试用零填充恢复原 M/N 形状，独立核对 CPU 输出和 Metal 输出。四项 ordered Metal 测试通过（含有限编码、scale、形状和真实舍入边界），CPU 常驻缓存复用/容量回退测试及 LRU 槽位、lazy consumer、失败发布测试通过。

这证明已测输入的 CPU bitwise parity，不是所有输入上的数学证明，也不是独立 CUDA parity。未改变误差阈值、CPU golden 或有效状态来使比较通过。

## 测量结果

Apple M5 Max，128 GiB，CPU 4 threads。所有下列 forward 计时均包含权重获取、缓存首次填充、hooks 和 trace；不含模型构建。OS 页缓存未清空，不能称为物理 SSD 冷测。旧样本间未做严格重复 A/B，不能推广为稳定速度承诺。

| 当前 ordered 路径 | Prefill 秒 | Decode 每步秒 | 峰值 RSS GiB | 逐位对照 |
|---|---:|---|---:|---|
| France，5 tokens + 3 decode | 5.3092 | 1.9597 / 1.5656 / 1.6553 | 37.972 | 832 文件、1,576 张量、30,722,252 元素 |
| opposite，5 tokens + 2 decode | 5.1497 | 1.8933 / 1.5191 | 39.266 | 624 文件、1,182 张量、25,143,792 元素 |
| sky，26 tokens + 1 decode | 9.8137 | 2.5887 | 37.219 | 416 文件、788 张量、63,710,694 元素 |

三个对照均最大有限误差 0，包含子层输出、路由、有效状态、层边界、logits/Top-10。仅规范化官方 `torch.empty` Engram cache 的未使用尾部并记录哈希。

短样本后段 Decode 约 0.6 tokens/s；26-token 首次 Prefill 约 2.65 tokens/s。**都不能当作已达到 10/300。** 已确认的 2048-token 正式吞吐测试尚未运行。

本轮早期常驻缓存、旧 FP8 kernel 路径后两步 Decode 达到 1.479/1.471 s，优于上一轮的约 2.5 s，但此旧 kernel 未通过 26-token 精度验收，因此不选择其较快数字作为当前无损性能。当前原输入的 trace 序列化四步合计约 0.269 s，不能通过关闭 trace 将约 1.6 s 降到目标 0.1 s。

## 到目标仍需解决什么

原输入当前三次 Decode 的 native 专家换入为 1.767/1.692/1.241 GB，读取计时约 0.152/0.147/0.117 s；这些是逻辑读取及当次 OS 缓存条件下的计时。单此路径已接近或超过每 token 100 ms 的预算，仍有大量计算和同步没有重叠。26-token Prefill 逻辑专家读约 44.16 GB，读取 2.396 s；该输入后续 Decode 命中 94/240 个请求，换入约 2.745 GB。

下一步应先按具体模块建立 warm Decode 分解，迁移 CPU 状态和输出投影、减少同步，同时研究可复用的工作集/profile 与读取重叠。扩大 L0 从 6 到 24 只解决部分重复读取，不能单独带来数量级收益。Prefill 则需要真正按专家的矩阵块 GEMM，并确定足够长的验收长度，摊薄首次读取；不能从 26-token 冷缓存样本外推 300 tokens/s。

条件性带宽预算：如果某个 Prefill 实际必须流过完整 268.945 GiB 专家存储，2048 tokens / 300 tokens/s 仅给出 6.827 s，要求约 39.4 GiB/s 的专家数据供应。实际缓存命中和读取量必须测量，不能把 OS 页缓存逻辑带宽当成 SSD 物理带宽。

## 复现和产物

```sh
.venv/bin/python experiments/dsv41_reference/test_resident_projection.py
.venv/bin/python experiments/dsv41_reference/test_lru_metal_bank.py
.venv/bin/python experiments/dsv41_reference/test_metal_ordered.py
.venv/bin/python experiments/dsv41_reference/run_metal_ordered.py \
  --expert-store artifacts/dsv41-full-expert-store \
  --output artifacts/my-ordered-run --decode 3
.venv/bin/python experiments/dsv41_reference/canonicalize_snapshots.py artifacts/my-ordered-run
.venv/bin/python experiments/dsv41_reference/compare_traces.py \
  artifacts/dsv41-reference-baseline-20260913 artifacts/my-ordered-run \
  --output artifacts/my-ordered-run/parity.json
```

GPU 测试/运行需要允许 Metal。输出目录必须是新目录。

- 当前三组数据：`artifacts/dsv41-metal-ordered-20260913/`、`dsv41-metal-ordered-heldout-20260913/`、`dsv41-metal-ordered-prefill26-20260913/`，均含 manifest、parity、trace、run.log。
- 26-token CPU 参考：`artifacts/dsv41-reference-prefill28-20260913/`。目录中的 28 是预估命名，实际 tokenizer 输入为 **26 tokens**，以 manifest 为准；运行计时与部分 GPU 探索重叠，仅用作精度参考。
- 原始 FP8 反例：`artifacts/dsv41-fp8-audit26-v2-20260913/`，补偿反例：`artifacts/dsv41-fp8-precise-audit26-20260913/`，各自保存完整 GEMM 输入和 ordered 比较结果。审计按设计在首个差异处停止，不能当作完整 benchmark。
- `run_metal_resident.py` 保存普通/packed 缓存用量、按模块 inclusive/exclusive 计时及 trace 序列化计时；inclusive 包含 hooks，exclusive 仅减去子模块调用，不代表纯 GPU kernel。
- `run_metal_hot.py` 记录每步命中、miss、淘汰、native 字节和计时；Prefill 按专家合并后 hit/miss 计数为 unique batch 请求，不能和旧逐 token 请求直接计算相同口径的命中率。
