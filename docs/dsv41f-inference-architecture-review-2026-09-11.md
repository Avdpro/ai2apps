# DS4.1F 推理架构选型 Review

日期：2026-09-11。审查本地当前工作树，HEAD 为 `11b5b9ac537e42b1029d1f0148bbbe6a33307f8e`。工作树包含其他未提交工作；本次仅做源码审查和报告，不改推理实现、不加载模型、不运行性能测试。下列历史性能来自仓库记录，不是本次复测。

2026-09-13 更新：用户已明确 DS4.1 不以不可测的 full-resident TPS 为准入门槛。官方本地源码的新审查见 `dsv41f-official-source-optimization-2026-09-13.md`；其中对权重施加位置、激活量化、专家累加顺序的结论优先于本文早期 PipeNetwork 对照。

## 结论

以 **GLM 的固定槽位专家执行器为底座，采用 Qwen Next 的数值一致性与 Prefill 策略，采用 Qwen PLE 的磁盘查表思路，独立实现 V4.1 模型及共享 KV 状态**。DS4F 适合提供 Direct-L1、压缩 KV 的持久化经验和验证方法，不宜整体复制其 Scope/Flesh 后端。

Qwen Next 本来就是 `Qwen4DynamicCache(Glm5DynamicCache)`；三者并非完全独立的缓存架构。新模型适配应保留官方 V4.1 router、attention、mHC 和 Engram 语义，只替换参数存储与加载边界。

## 各方案的适用部分

| 路径 | 当前实现 | 对 V4.1 的用途 |
|---|---|---|
| GLM Next | 固定 L1 + persistent Tail/Hot、SLRU、延后 promotion、计算命中项与读取 miss 重叠、分组 Prefill、会话槽位恢复 | 专家缓存执行器首选 |
| Qwen Next | 继承 GLM；保留原始 route reduction 顺序；canonical Prefill reuse；跨 chunk 保持 L1；PLE mmap | 精确模式策略和 Engram 存储参考 |
| DS4F | Scope L1、滚动 Hot、有限 Prefill miss bank、Direct-L1、Flesh 请求串行化、压缩 KV handler | 复用底层 I/O 和状态边界经验；不复用 V4 假设 |

## 关键审查发现

### 1. Qwen 的精确策略适合做默认值，但不能原样搬数学计算

`omlx/patches/qwen38_next_cache/runtime.py:39` 直接继承 GLM 执行器，并设置：

- `preserve_route_order=True`；
- `prefill_resident_first=False`；
- `prefill_canonical_reuse=True`；
- `prefill_retain_l1=True`。

这些设置避免因为专家属于不同缓存层而改变归约顺序或 QMM 分组。历史 Qwen 记录中 resident-first 实验只有 27/32 token 一致，canonical reuse + retained L1 为 32/32，另有 128-token 检查通过。不能把“同样 Top-K”当成数值结果必然一致。

但 PipeNetwork `moe.py` 在 FP32 计算专家权重乘法、求和和共享专家相加；GLM 通用执行器有按 `x.dtype`/`routed.dtype` 计算的路径。V4.1 适配必须显式保留自己的激活截断、累加 dtype、权重施加位置及共享专家相加顺序。只打开 `preserve_route_order` 不足以完成 parity。

Qwen 的第 129 token 才启用 promotion 是该模型的经验参数，不直接成为 V4.1 默认性能结论。应先做静态槽位基线，再单独比较 promotion。

### 2. DS4F 有明确的旧模型假设，不宜作为整体模板

`deepseek_v4/deepseek_v4_model.py` 的 miss lookup 使用长度 256；`scope_policy.py` 对前 3 层采用特殊处理，`scope_runtime.py` 包含 `range(3, 43)`。V4.1 是 384 routed experts、不同层结构且取消旧 hash routing。现有 Scope profile、专家 ID 映射和旧 router 不能继承。

保留 DS4F 的架构独立后端和完整状态快照经验，重新生成 V4.1 trace/profile。Scope 只是预热选项，不应成为首次正确运行的依赖。

### 3. 三套动态命中路径都不是完全无 CPU 同步

- DS4F `_scope_split_moe` 在 `mx.eval(miss_route_count_array)` 后调用 `.item()`；miss 后才返回需要的 expert IDs。
- GLM/Qwen decode 同样 eval miss count 并 `.item()`；主 L1 未命中后才读 route IDs。
- DS4F benchmark 的纯设备 all-hit 分支不能代表真实动态 fallback 路径。

因此可说主 L1 命中时不把完整 router indices 拷到 CPU，不能说没有同步。V4.1 先保持正确的同步边界，再统计其成本。原生写入复用槽位前的 Metal 完成等待不能直接删除。

### 4. Direct-L1 可复用原生机制，不能直接套任意权重布局

`custom_kernels/glm_moe_dsa/csrc/expert_loader.cpp:76` 校验六个目的 segment 的槽位字节总和等于 record_bytes，然后用 positional preadv 写入最终数组 backing。

- GLM/Qwen：fused gate/up + down，各带 affine weight/scales/biases。
- DS4F：gate weight/scales、down weight/scales、up weight/scales，由自己的 wrapper 传给同一 ABI。

V4.1 应先确认所选 checkpoint 的量化配置和每层布局，生成与实际内核完全匹配的 compute-ready expert records。原生 FP4/FP8 的解码与 MLX affine 重量化是两回事。缓存精确性比较使用同一份权重的简单 SSD 按需参考路径，结合真实单层驻留对照；量化质量另行比较官方源模型。全模型 full-resident 不是前提。

### 5. Engram 最接近 Qwen PLE，但现有 mmap 不等于完整的预取系统

`mlx_vlm_qwen4_exp_compat/vendor/mlx_vlm/models/qwen4_exp/language.py:936` 的 `_SafeTensorMMap` 映射 safetensors，只拷贝被访问的行；`DiskBackedShardedEmbedding:998` 支持 dense/affine 行读取，在调用时同步 indices、按 shard 分组并构造小型 MLX 数组。

当前代码没有显式的限额行缓存、行去重或异步预取；OS 文件页缓存仍会占用物理内存。它解决整表不作为 MLX 常驻权重的问题，不保证 RSS/page-cache 不增长。

V4.1 需要自己的 hash/token-normalization、两层表布局和 FP8/UE8M0 scale 解码。Qwen 的 shared weight_scale、128-way sharding、BF16 输出不能照搬。`virtual_ple.py` 是转换阶段接口，不能误作运行时 SSD loader。

推荐先实现正确的按行读取，随后加入去重、按页合并、限额热行缓存和 token 确定后的预取。Prefill 可提前知道整个输入 chunk 的行号；Decode 只能在当前输入 token 已知后确定该步行号，不能假设未来生成 token 已知。SSD Engram 和专家 miss 共享存储带宽，需要联合调度，而非无限增加 I/O 线程。

### 6. KV 必须是独立的 V4.1 状态协议

DS4F `cache_handlers.py` 将压缩池标记为不可任意 block-slice，支持完整状态恢复。这一原则可复用，但旧五元组布局不适用 V4.1。

V4.1 至少需要保存 owner compressed KV/index keys、各层 SWA ring、compressor partial group、token offset 和 Engram 历史；消费者应重建对 owner 的关联，避免保存多份共享数组。先提供完整边界快照和请求串行化，再考虑 prefix slicing、batching 和 MTP 回滚。

PipeNetwork `cache.py` 明确采用 FP4/FP8 fake quantization，数组 dtype 默认 FP32，容量按 max_seq_len 分配。不能以官方 packed FP4 KV 的 bytes/token 估算该运行时。真正 packed KV 应作为独立内核优化和验证工作。

## 内存预算

应按实际 tensor layout 计算，而不是按权重下载量设置机器门槛：

`峰值 ≈ 常驻非专家参数 + Σ层[(L1槽位+Hot槽位)×专家记录字节] + Prefill工作区 + Engram热行/暂存 + KV/压缩中间状态 + 激活/运行时开销`。

额外记录 mmap RSS、文件页缓存、系统内存压力；MLX peak 不能单独代表整机占用。Engram 全表磁盘容量不计入固定常驻预算，但其已触达页不能当作零成本。

V4.1 主干比 V4 大很多，同样槽位数也不代表同样内存。应按每层 record_bytes 和 miss 轨迹分配 L1，不直接移植 Top80/Top160/Top224 等设置。当前没有依据承诺 64/128 GiB 或某个 TPS。

## 推荐验证顺序

1. 独立 V4.1 文本后端，验证官方参考语义与 PipeNetwork 的已声明 reference adaptation；不依赖旧 Scope。
2. 固定量化 checkpoint，Engram resident/SSD 行读取对照，覆盖重复行、归一化、分块边界和多轮历史。
3. 同权重简单 SSD 按需路径对照缓存路径，核对路由、logits、生成 token；用真实单层驻留和独立算子参考补充正确性证据。性能验收采用固定内存预算下的 cold/warm、TTFT、steady TPS 及内存—速度曲线；不把 DS4F 的全驻留 85% 门槛套用到 DS4.1，不推算未知的全驻留 TPS。
4. 接入 GLM 固定槽位/Hot/Direct-L1，采用 Qwen canonical 顺序策略并保留 V4.1 FP32 数学语义。覆盖全命中、混合命中、全 miss、槽位回收和 I/O 失败。
5. 分别测试 Engram offload、专家 cache、两者组合；记录 cold/warm、TTFT、prefill/decode TPS、SSD 字节与请求数、同步时间、MLX active/peak、RSS。
6. 通过整状态保存恢复、跨 session 和长 chunk 检查后，再做预取/promotion/packed KV；视觉与 MTP 单独验收。

Boost 替换专家、REAP pruning 和关闭 Engram 都会改变计算或模型，不计入精确缓存收益。

## 历史证据与外部源码

- `docs/qwen38-next-cached-moe-checkpoint-2026-08-28.md`：同 prompt 的 full-resident 33.58 TPS/75.17 GiB，对比 Top224+Hot10 20.01 TPS/49.45 GiB；不同模型之间不可横比 TPS。
- `docs/ai2apps-mlx-runtime-1.5.4-direct-l1-glm-release.md`：DS4F 和 GLM 发布时的 Direct-L1/会话验证记录。
- [PipeNetwork model](https://github.com/PipeNetwork/deepseek-v41-mlx/blob/main/deepseek_v41_mlx/model.py)
- [PipeNetwork MoE](https://github.com/PipeNetwork/deepseek-v41-mlx/blob/main/deepseek_v41_mlx/moe.py)
- [PipeNetwork cache](https://github.com/PipeNetwork/deepseek-v41-mlx/blob/main/deepseek_v41_mlx/cache.py)
- [PipeNetwork Engram](https://github.com/PipeNetwork/deepseek-v41-mlx/blob/main/deepseek_v41_mlx/engram.py)

外部链接是本日查看的 main 页面，未固定 commit；实施前应 pin revision 并复核。
