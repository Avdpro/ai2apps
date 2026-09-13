# DS4.1F Metal 专家计算与原生 SSD L0/L1 检查点

2026-09-13。实验目录 `experiments/dsv41_reference/`；未修改生产运行时、GLM/Qwen C++ 源码或官方模型源文件。机器为 Apple M5 Max，128 GiB。HEAD 为 `11b5b9ac537e42b1029d1f0148bbbe6a33307f8e`；实验新增代码尚未提交，以运行 manifest 的代码 SHA-256 为精确版本。

## 已实现的执行路径

官方 CPU 模型保留 embedding、Engram、attention、router、共享专家、mHC 和输出头。40 层 routed experts 切换为 MLX/Metal：

1. 原始 BF16 输入在 GPU 按 group32 量化为 FP8，scale 使用官方 power-of-two 规则。
2. 自定义 Metal GEMM 直接读取原始 packed FP4 和 UE8M0 scale；按 group32 形成 FP32 部分和，再顺序累加，输出 BF16。
3. SwiGLU 在 GPU 完成 clamp、SiLU、up 相乘及 router 加权，**加权在 down projection 之前**。
4. down projection 同样走 Metal FP8 activation × FP4 weight。
5. routed expert 结果返回 CPU，按 expert ID 升序 FP32 累加，再加官方共享专家，保留参考顺序。

这是完整 40 层的 **CPU/Metal 混合参考执行**，不是完整 MLX 引擎。Router 当前仍在 CPU，尚未实现 device-only all-hit routing；Prefill 当前逐 token 处理 Top-6，也尚未使用 NAX 的大批量矩阵乘路径。

## L0 / L1 分配与生命周期

每层固定一个 14 槽位 bank，三组 weight/scale 对应六个 MLX uint8 数组：

- L1：8 个固定专家槽位，约 143.44 MiB/层。
- L0：6 个可覆盖槽位，约 107.58 MiB/层，足以容纳当前 Top-6 中所有 L1 miss。
- 共 40 层：L1 约 5.60 GiB，L0 约 4.20 GiB，原始专家 payload 合计约 9.81 GiB。

L1 IDs 按已有短 prompt Prefill trace 的频次选择，平频按 expert ID；属于**基于已知轨迹的静态 oracle fixture**，不代表经过 held-out 验证的通用 Top profile。L0 保留仍需使用的命中项，覆盖本轮不需要的槽位，读取完整成功后才发布新 tag。本版没有 L1 promotion、Scope 选择或读写 overlap。

覆盖槽位前先 `mx.eval` 所有已登记的懒执行消费者，再 `mx.synchronize`。仅 synchronize 无法保障尚未提交的 MLX 图已经消费旧权重。失败前先使待覆盖 tag 失效，禁止把部分读取的槽位误判为命中。专门的测试验证了“创建未 eval 的旧槽位消费者 → 加载另一个专家覆盖 → 旧结果仍正确”。

## SSD 必须走的原生路径

专家读取直接编译并调用仓库现有：

`omlx/custom_kernels/glm_moe_dsa/csrc/expert_loader.cpp::preadv_fused_experts`

这是 GLM/Qwen 共用的 C++ 多线程 `preadv` 路径，4 个 I/O workers，释放 Python GIL，六个 iovec 直接写入已经分配和 eval 的 MLX/Metal 统一内存槽位。DS4.1 把六段解释为 `w1.weight/scale, w2.weight/scale, w3.weight/scale`；加载器只检查字节布局，不执行 affine Q4 转换。

现有仓库 `_ext` 是 Python 3.11 构建，本实验 `.venv` 为 Python 3.13，无法直接导入。通过 `native/CMakeLists.txt` 在 `artifacts/dsv41-native-build/` 为当前 Python 编译同一份 C++ 源码，只增加隔离绑定；没有替换现有运行时扩展，也没有用 Python pread 冒充原生路径。ABI 和原始字节验证均通过。

普通参数和 Engram 仍随 CPU 参考走其原有读取路径；本阶段原生直写覆盖的是 routed experts，不能声称所有 SSD 读取已移至原生层。

## 精度问题与修复

初始 Metal SiLU 用 `gate * sigmoid(gate)`。第 0 层独立验证通过，但完整 Prefill 首次在第 6 层出现偏差，随后放大并改变路由。拆分检查发现 gate/up GEMM 逐位一致，差异源于 CPU 和 Metal SiLU 舍入，不能将其当作无关紧要的误差。

由于 gate GEMM 输出是 BF16，只存在 65,536 种位模式，改为一次性用参考 PyTorch 计算 FP32 SiLU 查找表，GPU 查表后执行原顺序乘法及 BF16 转换。表约 256 KiB，包含 gate 上限 clamp=10；**不是对激活再量化或降低精度**。运行时无 SiLU 的 CPU 往返。该表绑定当前 CPU 参考的 SiLU 行为，未来改变 PyTorch/参考算子版本需重新验证，不能宣称它已与 CUDA SiLU 一致。

修正后：完整 40 层 Prefill + 3 次 Decode 的 **832 个文件、1,576 个 tensor、30,722,252 个元素逐位一致**，包含 logits、Top-10、路由、各层输入输出、Engram 和有效 KV 状态。未使用 Engram cache 尾部按既有快照规范化流程处理。

## 首次完整测量

固定 5-token prompt `The capital of France is`，输出 ` Paris. The E`。数据包括 trace 保存，且 expert-major 文件刚生成，OS 文件页缓存可能为热态，不能视为物理 SSD 冷启动测试。

| 项目 | CPU 无缓存复跑 | Metal routed experts + L0/L1 |
|---|---:|---:|
| Prefill | 52.760 s | 6.147 s |
| 三次 Decode | 95.653 s | 12.341 s |
| 合计 | 148.414 s | 18.488 s |
| 进程峰值 RSS | 7.122 GiB | 15.945 GiB |

独立进程复跑耗时 **17.299 s**，同样 832 个文件全部逐位对齐 CPU golden；对应 Prefill 5.266 s，Decode 3.270/4.387/4.375 s。

本次总耗时约为 CPU 的 1/8.03；这是相同短样本的混合路径结果，不是通用模型吞吐。没有用这些数字声称达到全驻留 TPS 门槛。

首次运行原生专家读取 20,943,912,960 bytes，340 次加载调用，调用内部累计约 1.323 s；320 组 token-layer Top-6 的 GPU 调用累计约 1.222 s（含首次编译等开销）。CPU 普通参数/共享专家等另外读取 34,091,226,112 bytes。因此 native bytes 与 CPU manifest `read_bytes` 应相加，不能只选其中一个作总流量。

MLX 峰值分配 10,532,048,112 bytes（约 9.81 GiB）；它与 RSS 在统一内存环境有重叠，不能直接相加。单层热态六专家约毫秒级的实验只描述专家计算，不等于整模型 decode latency。

## 验证与产物

- CPU 原有 7 项、缓存 4 项测试通过。
- 新增 3 项 Metal 测试通过：FP8 量化边界/动态范围、BF16 正常数值范围的 SiLU 查表计算、原生槽位覆盖等待懒执行消费者及失败不发布。
- 第 0 层原生加载的 L1/L0 参数与原始 safetensors 抽取结果逐字节一致；第 6 层 SiLU 修正后独立验证通过。
- 完整数据：`artifacts/dsv41-metal-moe-silu-20260913/`。
- 完整精度结果：`artifacts/dsv41-metal-moe-silu-parity.json`。
- 独立进程复跑：`artifacts/dsv41-metal-moe-repeat-20260913/`，对应 parity JSON 在同级目录。
- 首个失败运行保留在 `artifacts/dsv41-metal-moe-full-20260913/`，属于失败诊断数据，不能用作 golden 或性能验收。

## 范围与下一步

当前 expert-major fixtures 只包含既有短基准实际使用的专家，共约 18 GiB，保留原始字节而非重新量化。运行器明确限制为固定基准 prompt；未覆盖新路由会失败，不回退慢路径或隐藏错误。因此目前仍是验证原型，不能用于任意聊天请求。

下一阶段应完成全专家 offset/record 寻址与通用存储准备，逐步把共享专家、dense 和 attention 移入 MLX；router 移入设备后实现无 host router IDs 的 all-hit lookup。之后才有意义调大 L1、采用 Hot promotion、异步预取/overlap，以及用 NAX 优化大批量 Prefill。CPU golden 和本阶段逐位一致数据继续作为精度检查点。

后续检查点：内部 FP8 GEMM 已迁入 Metal，完整 384 专家/层存储及新输入对照已完成，见 [FP8 Metal 与完整存储](dsv41f-metal-dense-full-store-2026-09-13.md)。
