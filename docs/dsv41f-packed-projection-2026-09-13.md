# DS4.1F 严格末端投影的内存布局优化

2026-09-13，实验基于 HEAD `11b5b9ac537e42b1029d1f0148bbbe6a33307f8e`，新增源码尚未提交，精确 SHA-256 记录在运行 manifest。仅修改实验目录和研究文档。

## 实现与精度边界

新增 `packed_projection.py` 和入口 `run_metal_packed.py`，在现有严格 CPU/Metal 混合路径上，优化全部 40 层 attention `wo_b` 和共享专家 `w2` 的 CPU GEMM。

原始 FP32 权重布局为 `[N,K]`，每次 group32 GEMM 从中抽取 `[N,32]`，行跨度为 K。新实现先转换成连续 `[K/32,N,32]`，使单组行跨度为 32。保留每组 32 项矩阵乘法、scale 乘法顺序、组间 FP32 顺序累加和末尾 BF16 转换。没有修改原始 FP8 字节或重新量化；每次调用重新排列权重，尚未持久缓存排列结果。

内部 FP8 GEMM 和 routed experts 延续 Metal；每层 L1=8、L0=6；专家 SSD 读取延续未经修改的 GLM/Qwen 原生 `preadv_fused_experts`、4 个 I/O workers 和直接写入 MLX 槽位。完整专家存储与 CPU golden 均未修改。

## 测量

Apple M5 Max，128 GiB，CPU 4 threads。计时包含 forward、权重读取及 trace 保存，不包含模型构建；OS 页缓存未清空，不能当作物理 SSD 冷启动、端到端 TTFT 或稳定服务 TPS。

原始输入 `The capital of France is`，5-token Prefill + 3 次 Decode，输出 ` Paris. The E`：

| 运行 | 合计秒 | Prefill 秒 | 三次 Decode 秒 |
|---|---:|---:|---|
| 上阶段严格路径 | 13.8813 | 4.5574 | 2.6185 / 3.3282 / 3.3769 |
| 新布局首次运行 | 11.6591 | 4.0274 | 2.5722 / 2.5249 / 2.5344 |
| 本轮顺序对照：原布局 | 13.8210 | 4.2879 | 2.5389 / 3.5118 / 3.4822 |
| 本轮顺序对照：新布局 | 11.8048 | 4.2110 | 2.5058 / 2.5355 / 2.5523 |

顺序对照计时段缩短约 14.6%。新布局两次峰值 RSS 约 15.73 / 15.72 GiB，对照约 15.64 GiB；这是进程 RSS，不是纯权重或 MLX 分配量。每次 320 个末端投影调用，新布局复跑的重排耗时 2.003 s，GEMM 循环 0.894 s；该细分不含函数中其他转换和输出处理。

新输入 `The opposite of hot is`，5-token Prefill + 2 次 Decode，输出 ` cold. The`：新布局 9.5440 s，Prefill 4.3454 s，Decode 2.5952 / 2.6031 s，RSS 约 16.30 GiB。上阶段记录为 11.8883 s，但没有为此输入新增成对性能对照。L1 bootstrap 沿用原输入选择，不为新输入重选。

## 验证与产物

- 新布局原输入首跑、复跑，以及原布局对照：每次 832 文件 / 1,576 张量 / 30,722,252 元素均与 CPU golden 逐位一致。
- 新布局新输入：624 文件 / 1,182 张量 / 25,143,792 元素逐位一致。
- 所有对照最大有限绝对误差为 0，包含保存的子层结果、路由、状态、层边界及 logits Top-10；只规范化未使用的 Engram 缓存尾部，并记录前后哈希。
- `test_packed_projection.py` 两项测试通过：不同 M/N/K、非均匀 scales、非整行块 N 的参考对照，以及拒绝非 group32；原 CPU reference 七项测试通过。
- 数据目录：`artifacts/dsv41-metal-packed-20260913/`、`artifacts/dsv41-metal-packed-repeat-20260913/`、`artifacts/dsv41-metal-packed-heldout-20260913/`、`artifacts/dsv41-metal-dense-layout-control-20260913/`。各自包含 `manifest.json`、`parity.json`、逐层 trace 和 `run.log`。

这仍是短上下文 CPU golden 验收，不是独立 CUDA 精度验证或全 MLX 推理引擎。CPU router/attention、CPU/GPU 往返、每次权重转换仍在。下一处明确开销是末端投影重复重排；可研究有界预排列缓存，但需要计入内存预算，当前尚未实现。
