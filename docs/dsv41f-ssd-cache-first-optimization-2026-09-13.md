# DS4.1F 第一轮 SSD 缓存优化

2026-09-13。基于已通过复跑的 CPU 参考，完成第一个有界存储优化版本。此轮没有修改官方模型、CPU 算子或 reference harness，没有接入 MLX GPU kernel；新增代码仅在 `experiments/dsv41_reference/`，不是已发布运行时变更。

## 实现

- `cached_store.py`：每层 8 个完整专家的 LRU bank。第一次访问一个专家时读完三组 weight/scale 六段，再发布缓存项；淘汰按完整专家进行。保留原始 FP4 字节，不改变专家调用、router 加权或归约顺序。
- 2 GiB 普通参数 admission-only cache。满后不再接纳超预算项，防止按层循环访问使全局 LRU 不断淘汰下一轮需要的权重。
- 8 MiB token embedding/Engram 原始行 LRU。先完整读取，再加入缓存；重复行保持原顺序。实际本短样本无 row hit。
- `run_cached.py`：向原始 reference harness 注入存储类。manifest 保留官方模型、CPU kernel、harness 的原有 SHA-256，并补充缓存代码 SHA-256、预算和计数。
- GPU 异步读写生命周期尚未实现。当前 CPU Tensor 引用保证淘汰后仍被计算持有的 tensor 不会失效，这不等于 Metal slot bank 的安全发布协议。

默认缓存 payload 上限约 7.61 GiB，包含 40×8 个专家约 5.60 GiB、2 GiB 普通权重和 8 MiB 行缓存。payload 不包括暂存读取、转换权重、Python 元数据、KV、激活或 OS 文件页缓存，不能当作进程内存上限。

## 精度和测试

5-token raw prompt `The capital of France is`，完整 40 层 Prefill + 3 次单 token Decode，greedy 输出仍为 ` Paris. The E`。

与原 CPU 基准比较：**832 个文件、1,576 个 tensor、30,722,252 个元素逐位一致，最大有限数值差 0**。包括逐层输入/输出、Attention/MoE、路由、Engram、全词表 logits、Top-10 和有效 KV 状态。未使用 Engram cache 尾部按参考流程规范化，处理记录与哈希保留在 manifest。

原 7 项数值/存储测试通过；新增 4 项缓存测试通过，覆盖：完整专家重复命中与淘汰后重载，行缓存重复/淘汰/越界，普通权重预算与禁用专家缓存，六段读取失败不发布残缺专家。

## 测量

固定相同 prompt、decode 长度、CPU 4 threads、数值算子和 trace 内容。以下无缓存值采用上轮独立复跑；不是同一时刻的严格 A/B，也没有清空 OS 页缓存。

| 项目 | 无缓存复跑 | 缓存版 |
|---|---:|---:|
| 总耗时，含 trace I/O | 148.414 s | 146.448 s |
| Prefill | 52.760 s | 56.203 s |
| 三次 Decode 合计 | 95.653 s | 90.245 s |
| 逻辑 pread | 57.979 GiB | 47.830 GiB |
| pread 次数 | 14,607 | 11,891 |
| 进程峰值 RSS | 7.122 GiB | 15.408 GiB |

逻辑读取减少 **17.51%**；一次测量的总耗时下降 **1.32%**，不足以声称稳定加速。初次原始基准为 168.822 s，后续同实现复跑已经降至 148.414 s，说明不能选择较慢的首轮来夸大缓存收益。

实际缓存 payload 峰值 7.603 GiB。完整专家载入 1,261 次、淘汰 941 次，行缓存命中 0。`expert_hits=7727` 是单个 weight/scale tensor 的命中数，包含首次专家载入后其余五段的访问，**不是 routed expert 命中率**。

本轮结论：存储缓存已通过精度门槛，能减少重复读取；在 CPU 短样本上，约 8.3 GiB 的额外 RSS 没有换来显著整体加速，不应把它作为最终性能配置。

## 下一阶段的实施方向

1. 将这些逐层输入/输出作为独立的 MLX 算子测试输入，先解决 FP8 激活量化、FP4 block scales、w2 前路由加权、FP32 归约的数值一致性，再替换整模型执行后端。
2. 把本次完整专家缓存协议映射到固定 Metal slot bank，加入计算完成后才能复用槽位的生命周期管理；CPU 引用计数不能替代该协议。
3. 分别计量每层/阶段 expert reuse 和实际 I/O 等待，决定 Main/Hot 分配以及 Prefill→Decode 交接。当前 8 槽位 LRU 是可验证原型，不是已调优选择。
4. CED bounded replay 保持独立质量分支，不加入本次 exact storage parity 结果。

## 产物与复现

数据目录：`artifacts/dsv41-cached8-20260913/`。

- 精度结果：`artifacts/dsv41-cached8-parity.json`。
- 测量摘要：`artifacts/dsv41-cached8-measurement.json`。
- 原始日志和完整 manifest：数据目录内 `run.log`、`manifest.json`。
- 命令与参数：`experiments/dsv41_reference/README.md` 的 First storage optimization 部分。

所有缓存关闭时仍可使用原始 `run_reference.py`。这次没有降低精度门槛，也没有修改已有 golden 的有效计算结果。

后续进展：Metal 专家计算与 GLM/Qwen 原生 SSD L0/L1 已接通并通过完整短序列精度对照，见 [Metal 检查点](dsv41f-metal-l0-l1-checkpoint-2026-09-13.md)。
