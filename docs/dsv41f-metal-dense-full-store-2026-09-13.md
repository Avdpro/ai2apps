# DS4.1F 内部 FP8 Metal GEMM 与完整专家存储

2026-09-13。本轮在 `experiments/dsv41_reference/` 推进实验，未修改官方模型、CPU golden、GLM/Qwen 原生 C++ 加载器或已发布运行时。精确源码 SHA-256 在每次运行的 manifest；代码尚未提交。

## 当前默认的严格路径

- routed experts：延续 Metal FP8 activation × 原始 FP4、GPU SiLU 查表、每层 L1=8 / L0=6。
- 内部 FP8 线性层：新增 Metal group32 FP8 GEMM，读取原始 E4M3 weight 字节和 UE8M0 scale，FP32 分块累加、BF16 输出。包括共享专家的 gate/up 以及 attention、Engram 等内部 FP8 投影。
- 每层 attention `wo_b`、共享专家 `w2`：继续使用原 CPU GEMM，守住严格的子层输出精度边界。该规则对全部 40 层应用，不按具体失败样本或层号挑选。
- activation quantization、attention 主体、router、mHC、非 FP8 投影、输出头等仍在 CPU。普通参数目前仍在 CPU 读取后传给 Metal，没有声称所有存储和计算都已迁移。

新增实现为 `metal_dense.py` 与 `run_metal_dense.py`。当前是 CPU/Metal 混合路径，不是完整 MLX engine；仍有 CPU/GPU 往返和逐算子 eval，尚未实现 device-only all-hit router 或 I/O overlap。

## 为什么保留末端 CPU 投影

首次把全部 FP8 GEMM 移入 Metal，短基准计时段降至 8.508 s，最终 logits、所有完整层边界均逐位一致，但 4 个保存的子层输出存在差异，最大绝对差 0.000244140625：

- Prefill `layers.0.attn`、`layers.3.ffn`。
- 第 2 次 Decode `layers.32.attn`、`layers.37.attn`。

这是 CPU BLAS 与 GPU 分块归约舍入差异，不能把最终 token 相同当成全张量一致。该版本仅保留诊断数据 `artifacts/dsv41-metal-dense-20260913/`，不作为当前严格默认。保留所有末端投影的 CPU 路径后，已恢复全张量逐位一致。

新增 3 项 GPU 测试通过：全部有限 FP8 weight 编码、非均匀 block scales/非整行块形状、拒绝不支持的非 group32 配置。测试位于 `test_metal_dense.py`。

## 完整原始 FP4 专家存储

`prepare_full_expert_store.py` 已完成 `artifacts/dsv41-full-expert-store/`：

- 40 层 × 384 专家 = 15,360 个完整记录。
- 每个记录 18,800,640 bytes；每层 7,219,445,760 bytes。
- 总计 **288,777,830,400 bytes = 268.945 GiB** 额外磁盘空间。
- 按 `w1.weight/scale, w2.weight/scale, w3.weight/scale` 顺序直接复制原始字节，未重新量化、反量化或裁剪。
- 每层流式 SHA-256、fsync、文件大小、来源 checkpoint index SHA-256 和完成状态均记录。构建计时约 169.10 s；没有声称重新读取全部文件做第二遍校验。
- 启动新 prompt 前核对 40 层完成状态、384 个专家、来源身份及文件大小。

运行时专家仍使用原封不动的 GLM/Qwen `preadv_fused_experts` 直写 Metal 槽位，4 个 I/O workers。之前的 compact fixtures 仍保留作为历史验证数据，但不再限制新输入的路由。

L1 仍用原始基准 Prefill 选出的固定 8 个专家作为 bootstrap，**不针对新输入重新选 L1**；其他任意专家由 L0 加载。完整存储解决的是专家可达性，不等于 profile 已经调优。

## 精度与测量

计时包含 forward、权重读取和 trace 保存，不包含模型构建；OS 页缓存未清空，以下不是物理 SSD 冷启动或服务端端到端 TTFT。CPU 基准与 GPU 测量不是同时严格 A/B。

### 原始短基准

`The capital of France is`，5-token Prefill + 3 次 Decode，输出 ` Paris. The E`。

| 实现 | 计时段合计 |
|---|---:|
| CPU 无缓存复跑 | 148.414 s |
| 上阶段仅 routed experts 在 Metal，复跑 | 17.299 s |
| 本轮严格 FP8 混合路径，compact fixtures | 12.959 s |
| 本轮严格 FP8 混合路径，完整专家存储 | **13.881 s** |

完整存储版本 Prefill 4.557 s，Decode 2.619/3.328/3.377 s，峰值 RSS 约 15.64 GiB。执行 840 次内部 FP8 Metal GEMM；全部 **832 个文件、1,576 个 tensor、30,722,252 个元素**与 CPU golden 逐位一致，最大有限误差 0。相对上一阶段的 17.299 s，当前完整存储测量约缩短 19.8%，不能把该单样本百分比当作稳定通用加速比。

### 未参与 L1 选择的新输入

`The opposite of hot is`，输入 IDs `[671, 12236, 294, 6025, 344]`，5-token Prefill + 2 次 Decode，输出 ` cold. The`。

先用原始 CPU 路径独立生成参考，再使用完整专家存储和原有 L1 bootstrap 运行当前严格路径。全部 **624 个文件、1,182 个 tensor、25,143,792 个元素**逐位一致，最大有限误差 0。CPU 参考生成与离线存储构建重叠，故其 142.876 s 只作准确性运行记录，不用于加速比。

GPU 混合路径计时 11.888 s，Prefill 5.769 s，Decode 2.734/3.385 s。未为此输入创建 compact expert 集合或专用 L1。它验证了解除固定路由限制后的一个新案例，不能外推为长上下文、多会话、视觉或所有输入已经验收。

## 产物

- 原始 prompt 当前数据：`artifacts/dsv41-metal-dense-fullstore-20260913/`。
- 对照：`artifacts/dsv41-metal-dense-fullstore-parity.json`。
- 新输入 CPU 参考：`artifacts/dsv41-reference-heldout-20260913/`。
- 新输入当前数据：`artifacts/dsv41-metal-dense-heldout-20260913/`。
- 新输入对照：`artifacts/dsv41-metal-dense-heldout-parity.json`。
- 完整存储：`artifacts/dsv41-full-expert-store/`，含逐层 SHA-256、manifest 与构建日志。
- 构建与运行命令见 `experiments/dsv41_reference/README.md` 的 Strict inner FP8 GEMMs and complete expert storage 部分。

下一阶段重点是消除末端 CPU GEMM 的开销，同时保留明确的舍入验收规则；再把 router/attention 状态和缓存索引迁入 MLX，减少逐算子 CPU/GPU 往返。当前 L1/L0 分配保持不变，尚未引入 promotion 或扩大 L1 掩盖剩余计算开销。
