# Cache-MoE 的 Metal 同步优化研究

本轮为代码审查、官方资料研究与隔离 A/B。默认动态 L1 与冻结 v1 未修改。
尚未实现 MTLSharedEvent/Metal I/O 的模型集成，也没有 GPU 时间线证明完整
读取重叠。研究结论：具备实现条件，但需要同时改进资源生命周期与主机调度。

## 当前等待来源

| 位置 | 当前行为 | 含义 |
| --- | --- | --- |
| model.py:209 | 每层 `.item()` 读取 all-hit 布尔值 | 即使全命中也有一次主机决策边界 |
| model.py:212 | miss 时获取 IDs 和 LRU ages | CPU 必须知道读哪些专家 |
| metal_bank.py:31–32 | eval 消费者，然后 synchronize | 防止 CPU 覆写 GPU 尚在使用的专家内存 |
| run.py:50 | 每层输出 eval、日志、预算检查 | 额外一次阻塞边界，可能可以合并 |
| adaptive.py | 频次逐步 eval，每 16 步读取评分 | 动态 L1 的维护边界 |

准确地说，`mx.synchronize()` 默认等待默认设备的默认 stream，不是承诺等待
所有 GPU queues。当前主要计算在这一 stream，因而等待范围很宽。此前设计
将它简称“全局同步”，后续实现应使用这个准确语义。
[MLX synchronize 文档](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.synchronize.html)

`.item()` 的墙钟耗时包含前面尚未完成的 GPU 计算，不能全部当作可消除的
同步开销；必须用 CPU/GPU 时间线区分 GPU 有效工作和提交间隙。

## 最直接的 A/B

新增 `experiments/dsv41_analysis/probe_sync.py`，仅跳过每层输出回调。
Router 的 `.item()`、native loader 的全部覆写保护、动态 L1 均保留。
诊断关闭逐层日志和逐层 budget check，保留 20 ms footprint 采样、每步预算
检查及 MLX memory limit。因此不能把全部收益都归为硬件同步节省。

```sh
.venv/bin/python experiments/dsv41_analysis/probe_sync.py \
  --prompt-json artifacts/dsv41-benchmark2048-prompt.json --decode 128 \
  --output artifacts/dsv41-sync-no-layer-eval-20260913
.venv/bin/python experiments/dsv41_analysis/probe_sync.py --keep-layer-eval \
  --prompt-json artifacts/dsv41-benchmark2048-prompt.json --decode 128 \
  --output artifacts/dsv41-sync-keep-layer-eval-20260913
```

| 同入口测试 | Decode TPS | footprint 峰值 GB |
| --- | ---: | ---: |
| 保留层末 eval/回调 | 6.94 | 54.899 |
| 跳过层末 eval/回调 | 7.56 | 54.940 |

129 份 logits 逐值一致，生成 IDs 一致。本对照约 +9%；此前默认运行为
7.35 TPS，相比之下约 +3%。只做了一组，存在运行波动，不能声称稳定 +9%。
这是最小可行优化的正向证据，不是新的默认性能承诺。

## Metal 能解决什么

### 1. Shared Event 与按缓冲区退休

MTLSharedEvent 支持 CPU/GPU 交接与通知。可以令某个 L2 缓冲的 GPU 消费
完成后才让 I/O worker 获得写权限，读取完成后再发布 ready 信号。它减少
不相关任务之间的等待，并不缩短真实数据依赖。
[Apple CPU/GPU event 文档](https://developer.apple.com/documentation/metal/synchronizing-events-between-a-gpu-and-the-cpu)

建议每个独立缓冲维护 generation 与单调事件值，并严格遵守
FREE→READING→READY→IN_USE→RETIRED。不能共用一个不断升高的全局计数，
让完成顺序不同的任务误满足别的任务；不能把取消视为读取已经停止。
GPU 尚未用到未来层时不插 wait，直到真正消费目标缓冲才加入依赖。

MTLFence 主要处理 GPU pass 的资源依赖，不是 SSD 后台线程的通知替代品。
[Apple 资源同步文档](https://developer.apple.com/documentation/metal/resource-synchronization)

### 2. 原 GLM preadv 后台执行是第一优先

当前 native binding 已释放 GIL，读取代码自身支持工作线程。可保留这个经过
验证的高速 I/O 实现，使用独立预分配 L2 bank，从 Python 阻塞 `_load()` 路径
中分离“领取空闲 buffer→后台 preadv→完成发布”。不在读取线程运行 MLX 图。
禁止简单删除 synchronize 或让线程并发写现有 bank。

### 3. Metal I/O 作为第二个可比较的后端

Metal 3 提供独立 I/O command queue，可按文件 offset 加载到 MTLBuffer，
并通过 shared event 与 GPU 计算建立依赖。适合按专家记录预取，支持批量
提交；不要求先把整个文件加载到内存。
[Apple WWDC：Load resources faster with Metal 3](https://developer.apple.com/videos/play/wwdc2022/10104/)

但“原生 Metal I/O”不等于必然快于现有 preadv。需要比较同样记录、并发、
冷热文件缓存下的尾延迟和带宽，并检查 MLX allocator 的资源所有权。不能
宣称 GPU shader 能自己打开文件或无成本访问 SSD。

### 4. MLX 的接入点已经存在，但需要原生扩展

本机安装头文件提供：

- `mlx/event.h`：Event、signal、wait、is_signaled。
- `mlx/backend/metal/event.h`：底层为 MTL::SharedEvent。
- `mlx/backend/metal/device.h`：wait_event、signal_event、commit(completion)。

这些是 C++ 后端接口，不能假设可从普通 Python 或自定义 Metal kernel
直接调用。应通过与当前 MLX 版本匹配的自定义 primitive 接入 active encoder，
把依赖和资源注册进 MLX 图。自行在另一 queue 编码、却不告诉 MLX 资源使用
关系，会破坏正确性。接口/ABI 升级需重新验证。
[MLX 官方扩展指南](https://ml-explore.github.io/mlx/build/html/dev/extensions.html)

### 5. 逐层 Router 的主机分支是更深的问题

即使所有字节预取到位，当前代码仍每层 `.item()` 才能选择 Python 分支。
Shared Event 不能自动消除这个分支。后续需要把命中查表、分组和调度下沉到
原生执行层，减少 Python 往返。实际 miss 必须准确恢复，不能拿预测替代 Router。

不能在串行 compute queue 上先排一个等待未来 I/O 的任务、又把 I/O 所需的
路由计算排在它后面；这会制造队头阻塞甚至死锁。事件和预取缓冲只在实际
消费者处形成依赖，前面不相关的计算应继续提交。

## 推进顺序

1. 合并层末多余 eval/日志与预算检查，保留准确 trace 模式；本轮仅有隔离实验。
2. 建立 L2 双缓冲及明确的完成通知，复用 preadv，并验证字节/生命周期。
3. 用 Metal System Trace 区分 GPU 忙碌、主机阻塞和 I/O overlap，再判断收益。
   本机 xctrace 可用，但本轮尚未采集该时间线。
4. 原生化命中调度，减少逐层 `.item()` 往返。
5. 对照 Metal I/O，只有测到收益后才考虑替换默认读取后端。

预测器决定能提前多久知道需求，事件化 L2 决定能否把这段时间利用起来；
两者是互补条件，单独换同步 API 不会自动得到完全并行。

## 补充：分段乐观执行与回滚

用户指出旧实现存在跨 2～4 层后统一检测 miss 的机制。本轮只读核查发现，
精确匹配实现位于兄弟 DMoE 的 `dmoe/mlx_adapter.py:2319`
`_SegmentedQwenTextModel`，对应文档 `docs/transactional-packed-hit-v1.md`。
这是 Qwen 文本实现，不能将其性能数字标成 DS4 数据。当前仓库 DS4 patch
未找到相同分段循环；DMoE DS4 另有 `optimistic_slot_completion`，为单层先算
resident contribution 再补 miss，不把不完整输出送入后续层。

分段实现的关键步骤：冻结 segment 输入和 cache 字典中的数组；连跑 N 层，
GPU 记录路由与 miss；段末统一 eval candidate 与标记；全命中才提交。失败
则恢复 cache、加载缺失项后重跑，超过重试上限抛错。代码还存在段首 checkpoint
eval，因此不能把实际所有同步次数简单说成 40/N。

原型会收集段内全部 speculative misses 作为加载候选，但首次 miss 后的
hidden state 已被占位计算污染，后续路由不一定是真实路径；它依靠继续重试
直到全段验证通过保证输出。迁移时应优先处理首个可信 miss，或明确将后续
路由视为投机候选，不能将其记为真实训练标签或立即更新动态 L1。

DS4.1 必须回滚 h/mHC mix、窗口 KV、压缩 KV/index/pool 状态、shared 状态
别名及受影响元数据。Engram hash 可在 segment 之外每 token 只计算一次；
若实现重放完整 token，则也要恢复其历史。原生专家 bank 可保留已读权重，
但必须 pin in-flight 消费者并在安全边界更新映射，统计只能对接受的路径计数。

这条路线修正了“必须先原生化才能减少每层 .item()”的过强判断：分段回滚
也能摊薄检查成本，代价是 checkpoint 与重算。适合与预测 L2 联合实验，
先从 2 层开始，根据实测 segment 完整命中率选择 1/2/4 层。

专家命中率不是段完整命中率。仅作独立同概率示例，95% 专家命中、每层6专家
时，2 层全命中为 0.95^12≈54%，4 层为 0.95^24≈29%；真实相关性需按整段
轨迹测量。验收应同时记录 segment 接受率、重算层数、检查点成本和 TPS。
