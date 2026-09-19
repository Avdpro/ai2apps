# GLM 5.3 Flash Q4 Cached-MoE 优化与验收记录

日期：2026-08-28
状态：阶段性完成；Natural、Direct Decode/Prefill、动态 L1、Hot16、会话与视觉路径已验收；Scope v2 与 MTP 仍为实验能力

## 1. 文档目的

本文汇总 GLM 5.3 Flash MLX 4-bit 在 oMLX/AI2Apps 中的 Cached-MoE 工作，包括：

- Q4 checkpoint 到计算就绪专家仓库的转换；
- 面向 Apple Silicon 统一内存的 C++/Metal Direct Loader；
- 动态 L1、固定 Hot16、逐 token 晋升与会话恢复；
- Decode 与 Prefill 的 SSD/计算重叠；
- Natural、Turbo Top5、Blast Top3 三档推理；
- 十类 Scope profile 的生成、离线覆盖率与在线 A/B 结论；
- 图片、多图、多轮会话的内存与正确性验证；
- MTP 草稿推理的当前状态；
- 最终性能、内存边界、回滚路径与后续工作。

本文中的“无损”指完整保留原始 Top-8 路由及其计算结果；Boost 会主动替换低权重 miss 专家，属于显式、可热切换的近似模式，默认关闭。

## 2. 模型与约束

### 2.1 Checkpoint

- Hugging Face：`Vontra/GLM-5.3-Flash-MLX-4bit-MTP`
- 固定 revision：`06d6c7530e8290e20fabdc37a825ce07bdfc490c`
- ModelScope 对应 revision：`760a9f63f4553ff1f725bddf63ca9f20577e4441`
- 量化：MLX affine Q4
- 稀疏 MoE 层：3～44，共 42 层
- 每层专家数：288
- 每 token 路由专家数：Top-8
- 可选 MTP：第 45 层

### 2.2 目标

1. 峰值统一内存不超过 64 GiB；
2. SSD 上的专家数据已经是 kernel-ready 格式，读取后不再解量化、转置或重排；
3. 命中路径保持 router indices 在设备侧；
4. Decode 时先计算 resident experts，同时加载 Tail/SSD miss；
5. Prefill 使用固定 bucket、双缓冲和 resident-first 重叠；
6. Natural 为默认精确模式，Boost 只能由调用者显式开启；
7. 保留旧 loader，作为 A/B、故障诊断和回滚路径；
8. 保留 GLM 原有 attention、router、VLM processor 与 fused MoE kernel。

## 3. Checkpoint 与专家仓库

### 3.1 原始布局的问题

原始 safetensors 中，每个专家由 9 段张量组成：

- `gate_proj`: weight、scales、biases；
- `up_proj`: weight、scales、biases；
- `down_proj`: weight、scales、biases。

直接从通用 safetensors 读取会引入索引解析、多个小范围读取、对象构造和形状准备，增加每个 miss 到可计算状态之间的固定成本。

### 3.2 计算就绪格式

转换器生成 `glm5-next-affine-q4-gate-up-fused-v2` 专家仓库：

- 按 layer、expert 固定大小排列；
- gate/up 在离线阶段按已经 pack 的 affine 行拼接；
- 不做反量化、不转置、不改变数值；
- 每条记录页对齐；
- 每个专家只需一次连续 `pread`/`preadv`；
- 读取目标直接是最终 MLX/Metal unified-memory slot。

每条专家记录包含六个最终数组：

1. fused `gate_up.weight`
2. fused `gate_up.scales`
3. fused `gate_up.biases`
4. `down.weight`
5. `down.scales`
6. `down.biases`

相关实现：

- `omlx/cache/glm5_expert_store.py`
- `omlx/patches/glm5_next_cache/dynamic_cache.py`

### 3.3 磁盘尺寸

| 项目 | 数值 |
|---|---:|
| 单专家记录 | 14,155,776 bytes，13.5 MiB |
| 单层 288 专家 | 4,076,867,584 bytes |
| 42 层专家仓库 | 159.46875 GiB |
| 42 层、每层 Top80 resident slots | 44.296875 GiB |
| 42 层、每层 Hot16 slots | 8.859375 GiB |

Top80 与 Hot16 是不同的逻辑分区，但都占用固定物理 slot；最终还要叠加 dense weights、KV/KDA、VLM workspace、scratch arena 和运行时对象，因此不能只用专家记录大小估算进程峰值。

## 4. Runtime 架构

### 4.1 Main/L1 与 Hot/L0

最终缓存被拆成两层：

- **Main/L1**：较长生命周期的动态专家集合，由 segmented LRU 管理；
- **Hot/L0**：固定形状的近期专家区，用于容纳最近 token、Tail miss 和即时复用；最终采用 Hot16；
- **Scratch**：Direct Decode/Prefill 的固定 arena，不参与长期身份管理。

文本默认物理预算为 96 slots/层：

- Main80 + Hot16；
- 启用 MTP 时，为额外状态预留 8 个 Main slots，有效 Main72 + Hot16；
- 多模态默认预留 16 个视觉 slots，使用 Main64 + Hot16，避免图片路径突破 64 GiB。

这意味着配置中的 `dynamic_slots=96` 是总 slot bank，不等价于 96 个 Main/L1 专家。

### 4.2 动态 L1

`Glm5DynamicCache` 使用固定容量、batch-pinned 的 segmented LRU：

- probation/protected 默认约 30%/70%；
- 本 token 正在使用的 slot 不会被替换；
- 先生成 replacement plan，物理写入完成后才 publish 新 tag；
- 避免异步 loader 尚未完成时暴露错误身份；
- miss expert 若已在 Hot/Tail 中，可直接晋升到 Main，无需再次读 SSD；
- 默认每层每 token 最多晋升 1 个专家，抑制短期路由抖动。

实现：

- `omlx/patches/glm5_next_cache/policy.py`
- `omlx/patches/glm5_next_cache/dynamic_cache.py`

### 4.3 Direct Decode Loader

Direct loader 不是 CPU buffer 到 GPU buffer 的二次复制。Apple Silicon 使用统一内存，native loader 把磁盘内容直接写入最终 MLX/Metal slot：

1. router 在设备侧得到 Top-8；
2. all-hit 时不把完整 route 拉回 host；
3. 只有 miss 边界需要 host 参与规划；
4. C++ `preadv_fused_experts` 直接填充六段最终数组；
5. tag 只在写入完成后更新；
6. fused SwitchGLU 立即消费这些 slot。

Decode 固定 scratch 为 8 slots，避免每 token 动态分配与重新准备形状。旧 Python/generic loader 仍保留，可通过开关做 A/B 或回滚。

### 4.4 Decode overlap

每层执行顺序为：

1. 识别 Main/Hot 命中与 Tail/SSD miss；
2. 立即提交 resident expert 计算；
3. 与此同时由 native loader 填充 miss slots；
4. miss ready 后补算其输出；
5. 按原始 router 权重合并层结果；
6. 对满足策略的 Hot expert 做最多一次 Main 晋升。

验收轨迹记录了 1,182 次 overlap call。若 verifier block 的专家并集超过 Hot16，则按 token 回退，保证正确性和内存边界。

### 4.5 Direct Prefill

Prefill 使用 32/96/208/全专家四档固定 bucket 和双缓冲：

- resident groups 先算并 `mx.async_eval`；
- SSD miss 同时进入下一 buffer；
- 减少临时 MLX array 创建；
- Prefill 完成后主动释放 workspace，再进入 Decode；
- route 分组仍保留原始 GLM kernel 与数学路径。

在 roadmap 验收 case 中，resident-first 相比 all-direct：

| 指标 | resident-first | all-direct | 变化 |
|---|---:|---:|---:|
| SSD/loader bytes | 291,481,583,616 | 339,120,000,000 | -14.0% |
| resident groups | 126 | 168 | -25.0% |

Wall time 容易受 SSD cache 与机器热状态影响，因此此项以真实读取字节、group 数和最终独立 TPS gate 共同判断。

## 5. Scope profile

### 5.1 十类 Scope

使用与 DeepSeek 相同的 DMoE 测试题集，通过显式数据路径生成了十类 profile：

1. business_finance
2. coding
3. data_ai
4. general
5. humanities_social
6. legal_policy
7. math_logic
8. medical_health
9. science_engineering
10. writing_creative

数据集 SHA-256：`8df151ccb7db57ad5e6d791ad30fcc4f1f85108d02e878a0ba1d59281e3a6fb3`
采样 route 数：211,680
layer steps：26,460
profile 生成耗时：836.58 秒
Scope L1 slots：80

### 5.2 离线覆盖率

| 策略 | route coverage | all-hit |
|---|---:|---:|
| Global Top80 | 76.41% | 26.22% |
| Scope Top80 | 76.44% | 25.03% |
| Scope Top80 + Hot8 | 78.54% | 27.29% |
| Scope Top80 + Hot10 | 78.85% | 27.44% |
| Scope Top80 + Hot12 | 79.61% | 28.13% |
| Scope Top80 + Hot16 | 81.66% | 33.20% |
| Scope Top80 + Hot24 | 83.64% | 39.19% |

Hot16 是覆盖率、固定内存和实际 TPS 之间较合适的平衡点；Hot24 继续提高覆盖率，但会压缩 Main 或突破目标内存。

### 5.3 在线 A/B 结论

静态 Scope 初始化没有成为默认策略：

| 路径 | 平均 Decode TPS | 相对纯动态 L1 |
|---|---:|---:|
| Dynamic L1 | 5.452 | baseline |
| Scope v2 static init | 5.341 | -2.04% |
| Scope hybrid | 5.553 | +1.86% |
| Dynamic + Hot16 | 5.981 | +9.70% |
| Dynamic + Hot16 + promote1 | 6.413 | +17.62% |

最终选择 **动态 L1 + Hot16 + 每层每 token 晋升 1 个专家**。十类 Scope profile 保留为：

- 新 session 的可选预热输入；
- 后续 Scope transition/prediction 研究数据；
- 离线容量与路由稳定性分析。

当前模型 Package 内携带的是安全的 `general` bootstrap profile，不应把完整十类 profile 描述为默认线上策略。

## 6. Boost 模式

### 6.1 行为

| 模式 | 保留原始专家 | 替换的低权重 miss | 正确性属性 |
|---|---:|---:|---|
| Natural | Top8 | 0 | 精确，默认 |
| Turbo | Top5 | 最多 3 | 近似，显式开启 |
| Blast | Top3 | 最多 5 | 近似，显式开启 |

Boost replacement selection 留在设备侧：

- 从 resident experts 中按 bias-corrected router score 选替代项；
- 排除原始 Top-8 中已经出现的 expert；
- 被保留的原始专家继续使用原始 routing weight；
- Prefill 和 Decode 可分别设置；
- 可按 request/session 热切换，已在运行中的请求从下一 token 生效；
- 默认始终为 Natural，不由 Runtime 自动降级质量。

实现：`omlx/patches/glm5_next_cache/boost.py`

### 6.2 正式长上下文 gate

统一 case：约 12K 字符、3,025 prompt tokens、Top80 + Hot16、promote1，三档峰值均为 62.645 GiB。

| 模式 | Prefill TPS | Decode TPS | 避免的 misses |
|---|---:|---:|---:|
| Natural Top8 | 95.112 | 5.087 | 0 |
| Turbo Top5 | 101.221 | 6.140 | 77,471 |
| Blast Top3 | 106.213 | 7.216 | 129,807 |

相对 Natural：

- Turbo Decode 提升约 20.7%；
- Blast Decode 提升约 41.8%；
- Prefill 也因读取减少分别提升约 6.4% 和 11.7%。

早期短 case 曾观察到更高或更低数值，但受热状态、page cache 与 prompt 组成影响明显；上表是 Runtime 合并使用的正式同配置 gate。

## 7. 缓存容量探索

动态 L1 基线演进如下。不同 case 的机器热状态并不完全相同，主要用于确认容量趋势，不应用来替代第 6.2 节的最终同条件 gate。

| 配置 | Active GiB | Peak GiB | Prefill TPS | Decode TPS | loaded experts | read time |
|---|---:|---:|---:|---:|---:|---:|
| L1 16 Direct | 16.528 | 22.613 | 87.608 | 2.896 | 12,718 | 13.429 s |
| L1 24 Direct | 20.958 | 27.043 | 71.331 | 3.426 | 11,178 | 11.570 s |
| L1 64 overlap | 43.211 | 49.309 | 66.725 | 4.333 | 7,393 | 7.766 s |
| L1 64 + prefill96 | 45.742 | 51.722 | 101.444 | 4.255 | 7,429 | 7.824 s |
| L1 80 + prefill144 | 55.867 | 61.847 | 71.439 | 4.832 | 6,527 | 6.931 s |

L1 80 的独立 Prefill 测试为 102.581 TPS、52.988 GiB。表中 71.439 TPS 是一次受 host/SSD 热状态影响的联合 run，保留它是为了避免只报告有利样本。

其它探索：

- Main68 + frozen Tail12：3.970 Decode TPS，未采用；
- native weighted sum：4.862 Decode TPS，约 +0.6%，差异接近噪声且改变浮点累加顺序，仅保留为 opt-in；
- no-sync/no-miss 诊断上界：31.913 Decode TPS，但不保持精确语义，不能作为产品配置；
- coding Scope 预热：5.075 Decode TPS，说明更好的跨 turn/Scope transition profile 仍有空间。

## 8. Session 与多轮文本

AI2Apps 系统 session ID 同时绑定：

- Boost 配置；
- Main/Hot 专家身份快照；
- KV/KDA cache 身份；
- 多模态 feature cache。

Main/Hot snapshot 使用 8-session LRU。恢复 session 时只搬运物理差集，不重建整个 slot bank；跨会话切换后 cache policy 仍继续根据新 token 热更新。

实现：

- `omlx/patches/glm5_next_cache/session_cache.py`
- `omlx/engine/glm5_dynamic.py`

因此多轮对话不会把 L1 固化为首轮 Scope。Scope 只可能影响初始化，后续仍由真实路由更新。

## 9. 视觉与多图多轮

### 9.1 Processor 正确性修复

初始 MLX loader 没有注册 `Glm5NextProcessor`，会退化为纯 tokenizer，从而静默丢弃图片。修复后：

- 1496×1106 手表图片生成 2,120 merged visual tokens；
- `pixel_values` 形状为 `(8480, 1176)`；
- `image_grid_thw` 为 `(1, 3)`；
- 图片内容真正进入 VLM 路径。

### 9.2 图片质量集

8 张图片覆盖桌面网页、App UI、支付账单、漫画/视频流与商品图片。Natural、Top80 + Hot16、promote1、视觉 cap 1600 的人工评分：

| 图片 | 分数 / 10 |
|---|---:|
| GitHub 页面 | 8.5 |
| ModelScope 上传页面 | 9.5 |
| Apple 配置页面 | 10.0 |
| Ming 手表 | 8.5 |
| 微信支付账单 | 10.0 |
| 漫画 App | 10.0 |
| Bilibili 首页 | 9.0 |
| Watchspace 文章 | 10.0 |
| **平均** | **9.44** |

同一 1600 cap 下，平均端到端吞吐约 4.25 TPS，平均用时 52.63 秒，最大峰值 61.68 GiB。2,120-token 手表 reasoning case 峰值 62.66 GiB。

### 9.3 多图多轮 feature cache

为每张图片按 SHA-256 缓存视觉 feature：

- 根据 `image_grid_thw` 拆分 flat patches；
- 只编码 cache miss 图片；
- 按消息原顺序重新组合 feature；
- 请求结束后释放空闲 VLM `BatchGenerator` 和异步 owner；
- GLM vision KV 默认 request-local；完整 session vision KV 仅可选开启，因为会增加约 8～10 GiB 瞬时内存且没有观测到有效收益。

正式三轮测试：

| Turn | 内容 | Prompt tokens | Feature cache | Peak GiB | Reclaimed GiB |
|---|---|---:|---|---:|---:|
| 1 | 微信支付图片问答 | 814 | miss + save | 52.173 | 51.970 |
| 2 | 纯文本追问银行卡尾号 | 898 | hit | 60.147 | 51.970 |
| 3 | 追加漫画图片并追问 | 1,753 | old hit + new save | 61.939 | 51.976 |

语义检查通过：模型能读出交易金额、银行卡尾号 8657、绿色标签，也能在第三轮区分新增漫画和之前的账单图。

早期视觉路径仍使用 Top80 + Hot16 时，第二/三轮峰值分别达到约 69.18/70.80 GiB。因此正式多模态配置预留 16 slots，使用 Main64 + Hot16；返回纯文本请求后可恢复 Main80 + Hot16。

详细报告：

- `benchmarks/results/glm5_vision_quality_20260828.md`
- `benchmarks/results/glm5_vision_multiturn_20260828.md`

## 10. MTP 状态

MTP 的 layer 45、target-hidden prefill、draft/verify、混合 KV/KDA rollback 和 Hot16 micro-decode 已接通，但没有成为默认能力。

关键结果：

| 配置 | Decode TPS | 结论 |
|---|---:|---|
| MTP block3，micro-decode 前 | 1.608 | 明显回退 |
| MTP block3，micro-decode 后 | 4.354 | 改善但不足 |
| MTP block2 | 5.038 | 比同 run Natural 5.209 低 3.3% |

block2 接受了 17 个 draft 中的 15 个，但 forced-reject 检查虽然 next token 相同，logits 最大绝对差达到 3.171875，未通过 exact-logit gate。因此当前结论是：

- MTP 代码保留为实验路径；
- 默认关闭；
- 不把 draft acceptance 当成端到端加速成立；
- 后续必须同时解决 verifier 成本、rollback 与 exact-logit parity。

## 11. 正确性与回归

已验证的关键约束：

- Natural 保留原始 Top-8；
- Direct store 转换不解量化、不改变 packed Q4 数值；
- loader publish 顺序不会暴露未写完的 slot；
- all-hit route 保持在 device；
- miss 发生时才进入必要同步边界；
- Boost 可按 Prefill/Decode 和 session 独立设置，默认关闭；
- 图片 processor、单图质量、多图多轮与 feature cache 均有实测；
- 超过 Hot16 union 时有正确的 per-token fallback；
- 旧 loader 保留作为 A/B 和回滚路径。

阶段性 roadmap 曾通过 171/171 项测试；Runtime 1.5.4 合并 gate 另执行了 29 项 selected tests，并对 GLM Boost/store/Scope/VLM/vision 路径执行了 155 项回归。两组数字来自不同测试集合，不应相加。

## 12. 推荐配置

### 12.1 默认文本

- Mode：Natural Top8
- Main/L1：80
- Hot/L0：16
- Promote：每层每 token 1
- Direct Decode：开启
- Direct Prefill：开启
- Scope static init：关闭，使用动态 L1/bootstrap general
- MTP：关闭
- 预期峰值：约 62～63 GiB，具体取决于上下文长度

### 12.2 默认视觉

- Mode：Natural Top8
- Total slots：96
- Vision reserve：16
- 有效 Main/L1：64
- Hot/L0：16
- Feature cache：开启
- Vision session KV：关闭
- 目标峰值：小于 64 GiB

### 12.3 显式加速

- Turbo：Top5，适合希望获得明显加速、同时保留更多原始 experts 的场景；
- Blast：Top3，适合优先吞吐的场景；
- 两者都应由具体调用者选择，不能成为 Runtime 的隐式默认值。

## 13. 主要文件

| 文件 | 职责 |
|---|---|
| `omlx/cache/glm5_expert_store.py` | Q4 compute-ready expert store 转换与读取 |
| `omlx/patches/glm5_next_cache/dynamic_cache.py` | Direct loader、Main/Hot/scratch、Decode/Prefill 路径 |
| `omlx/patches/glm5_next_cache/policy.py` | segmented LRU、batch pin、事务式 publish |
| `omlx/patches/glm5_next_cache/boost.py` | Natural/Turbo/Blast 与设备侧替代选择 |
| `omlx/patches/glm5_next_cache/session_cache.py` | session Main/Hot 快照与差量恢复 |
| `omlx/patches/glm5_next_cache/runtime.py` | GLM runtime patch、容量和视觉 reserve |
| `omlx/engine/glm5_dynamic.py` | session-aware VLM engine、Boost、KV/KDA、MTP |
| `packages/omlx-model-glm5-3-flash-4bit-mtp/service.yaml` | AI2Apps 模型 Package 配置 |

## 14. 复现与证据

机器可读结果：

- `benchmarks/glm5_moe_cache/results/2026-08-28-dynamic-l1.json`
- `benchmarks/glm5_moe_cache/results/2026-08-28-engine-boost-long.json`
- `benchmarks/glm5_moe_cache/results/2026-08-28-engine-boost-top5-top3-prefill.json`
- `benchmarks/glm5_moe_cache/results/2026-08-28-roadmap-1-6.json`
- `benchmarks/glm5_moe_cache/results/2026-08-28-scope-profile-v2-analysis-with-hot.json`
- `benchmarks/glm5_moe_cache/results/2026-08-28-scope-v2-live-ab.json`
- `artifacts/runtime-1.5.4-gates/glm5-vision-multiturn.json`
- `artifacts/glm5-3-flash-q4-expert-store/manifest.json`

相关发布与合并记录：

- `docs/ai2apps-mlx-runtime-1.5.4-direct-l1-glm-release.md`
- `docs/glm5-3-flash-4bit-mtp-0.1.0-release.md`
- `docs/dsv4f-direct-l1-runtime-merge-checkpoint-2026-08-28.md`

roadmap 结果记录的源码 commit：

```text
66736cca
```

运行 benchmark 时必须同时记录完整 commit、checkpoint revision、prompt、生成 token 数、冷热状态、内存峰值、SSD 读取量、cold TPS 和 steady TPS。旧结果没有全部拆分 cold/steady 的，不应事后补造，只按原始 JSON 报告。

## 15. 当前边界与后续方向

1. **Native route planner**：miss 边界仍有 host route extraction/sync；no-sync 诊断说明这是最大的剩余 Decode 上界，但必须先保持精确语义。
2. **Scope transition**：静态 Scope v2 在线无收益；应研究多轮中的 Scope 迁移和基于近期 route 的柔性预热，而不是锁死 profile。
3. **Prefill 并行度**：继续减少 group 调度与 SSD request 数，验证更大 batch/bucket 是否能在不提高峰值的前提下提升吞吐。
4. **MTP verifier**：只有 exact-logit、rollback 与端到端 TPS 同时通过，才考虑默认开放。
5. **长上下文矩阵**：补齐 4K/10K/更长上下文的 cold、warm、steady 分项，以及不同 SSD page-cache 状态。
6. **视觉内存复用**：继续缩短 VLM workspace 生命周期，但不得用跨请求隐式 vision KV 换取不可控峰值。
7. **浮点归并**：native weighted sum 只有约 0.6% 收益；除非能证明稳定收益并通过严格 parity，否则保持 opt-in。

## 16. 阶段性结论

GLM 5.3 的有效组合不是单纯增大 L1，而是：

```text
compute-ready Q4 expert store
  + unified-memory Direct Loader
  + dynamic Main80
  + fixed Hot16
  + promote1
  + resident-first Decode/Prefill overlap
  + request-local session/VLM lifetime control
```

在 64 GiB 峰值预算内，最终 Natural 长 case 达到 95.112 Prefill TPS、5.087 Decode TPS；显式 Turbo Top5 和 Blast Top3 分别达到 6.140 与 7.216 Decode TPS。视觉能力保持，多图多轮在 Main64 + Hot16 下完成正确性和内存验收。Scope 十类 profile 已生成，但静态在线初始化没有真实收益，因此未设为默认；MTP 也因端到端速度与 exact-logit gate 未通过而继续保持实验状态。
