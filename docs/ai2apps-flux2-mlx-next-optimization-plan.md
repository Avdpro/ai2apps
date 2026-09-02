# FLUX.2 Klein MLX 下一阶段优化计划

状态：已冻结，等待后续重新启动  
冻结版本：`ai2apps.model.flux2-klein-mlx` 0.1.2  
适用模型：FLUX.2 Klein 4B、FLUX.2 Klein 9B  
最后更新：2026-08-25

## 1. 冻结决定

FLUX.2 Klein MLX 在 0.1.2 停止继续优化，团队资源优先用于后续至少三组绘画模型的实现、MLX 适配和横向评测。

冻结版本保留以下正式能力：

- 4B、9B 文生图和最多四张参考图的编辑；
- BF16、Q8、Q4，其中全模型 Q8 为默认模式；
- 持久 compiled-denoiser callable；
- prompt embedding LRU；
- revision-keyed 原生 Q8/Q4 派生权重缓存；
- 编辑 KV cache；
- ModelScope 优先下载和完整 shard 校验。

实验性 Metal LayerNorm/AdaLN 融合代码可以保留，但默认关闭。混合精度配置目前只属于 benchmark candidate，不作为公开请求模式，也不进入 0.1.2 的兼容性承诺。

冻结开发包：

- 文件：`ai2apps.model.flux2-klein-mlx-0.1.2-development.ai2service`
- 文件 SHA-256：`c44e97d24f27d2790a140c117abe86252e559f01bf94ab39fa0ea3cd48fd7e2e`
- 包摘要：`sha256:68029cba7a8fca2a602aa8ea62055ede096caa6160df24e8265574c02e8974f4`

## 2. 当前性能基线

所有数据均为 4 个 denoising steps。1080p 使用符合模型约束的 `1920 x 1088`。

### Apple M5 Max 128 GB

| 模型与配置 | 分辨率 | 热生成 | Denoiser | 备注 |
| --- | ---: | ---: | ---: | --- |
| 4B，全 Q8 | 1024 x 1024 | 3.887 s | 3.479 s | 当前公开默认 |
| 4B，Transformer BF16、其余 Q8 | 1024 x 1024 | 3.469 s | 3.060 s | 快 10.8%，未产品化 |
| 4B，double blocks + TE/VAE Q8 | 1024 x 1024 | 3.577 s | 3.166 s | 快 8.0%，未产品化 |
| 4B，全 Q8 | 1920 x 1088 | 9.214 s | 8.334 s | 实测峰值 29.1 GiB，在线量化路径 |

1080p 高性能混合精度实测约 8.6-9.1 秒。由于连续运行出现热降频，当前不能把小幅差值作为稳定产品收益。

### DGX Spark GB10

| 模型与配置 | 分辨率 | 热生成 | Denoiser/备注 |
| --- | ---: | ---: | --- |
| 4B，MLX 原生缓存 Q8 | 1024 x 1024 | 8.358 s | 12.42 GiB peak |
| 4B，MLX 原生缓存 Q8 | 1920 x 1088 | 17.694 s | 15.970 s denoiser |
| 4B，CUDA Diffusers BF16 | 1920 x 1088 | 7.227 s | 79.8 s 冷加载，19.69 GiB peak |
| 9B，MLX 原生缓存 Q8 | 1024 x 1024 | 19.691 s | 18.895 s denoiser |
| 9B，MLX BF16 | 1024 x 1024 | 8.457 s | 7.636 s denoiser |
| 9B，CUDA Diffusers BF16 | 1024 x 1024 | 6.255 s | 34.74 GiB peak |

Spark 的 MLX Q8 性能瓶颈主要是 MLX CUDA 量化 Transformer GEMM。Spark 生产推理应走 CUDA Runtime；MLX CUDA 仅作为图一致性和性能对照，不作为主要部署路线。

## 3. 下一阶段目标

恢复优化时，目标必须是可测量的端到端收益，而不是孤立算子分数：

1. Apple 4B 1024 方图从 3.9 秒降低到 3.3-3.5 秒；
2. Apple 4B 1920 x 1088 从 9.2 秒降低到 7.5-8.2 秒；
3. 不降低默认 Q8 的可安装设备范围；
4. generation 与 edit 都必须覆盖，不能只优化文生图；
5. 固定 seed 的输出变化必须通过自动指标和人工接触表复核；
6. 新模式首次转换后必须支持原生派生权重快速重启。

合理的整体收益预期为 10-20%。若不改变分辨率、步数和模型权重，超过 25% 的收益不应作为项目承诺。

## 4. 优先级路线

### P0：等候上游 MLX 触发条件

默认不主动 fork MLX。满足以下任一条件后重新启动评估：

- MLX release notes 明确包含 quantized GEMM、SDPA、Metal graph fusion 或大图内存改进；
- 代表性 Q8 linear microbenchmark 提升至少 10%；
- 1024 或 1080p 的未经产品改动基准提升至少 7%；
- 新绘画模型的适配工作产出可复用的 attention、VAE 或 mixed-precision 基础设施。

升级时先跑无代码修改的完整基准，再决定是否迁移 Runtime。不要仅因版本更新而升级生产依赖。

### P1：产品化预量化混合精度

候选档位：

- `fast-q8`：Transformer BF16，text encoder 和 VAE Q8；
- `balanced-q8`：double blocks、text encoder 和 VAE Q8，其余 Transformer BF16；
- `q8`：全模型 Q8，继续作为低内存默认。

需要完成：

1. 将 precision profile 加入请求解析、pipeline cache key 和派生目录 key；
2. 在首次转换时按 component/path predicate 量化；
3. 保存 mixed checkpoint，并验证 mflux 能按各层已存储的 bits/group size 重建；
4. receipt 写入 profile、模型 revision、mflux/MLX 版本和量化规则版本；
5. 原子提交、并发锁、磁盘空间预估和失败回退沿用 0.1.2；
6. 为 4B、9B 分别声明最低/推荐统一内存，不能用同一估值；
7. generation、单参考编辑和多参考编辑均验证重启后原生加载。

预期收益：Apple 1024 约 5-12%；高分辨率约 3-10%。代价是增加约 4-8 GiB 常驻内存，最终数值以原生 mixed checkpoint 实测为准。

### P2：高分辨率 attention 路径

1080p 的像素面积约为 1024 方图的两倍，但 4B Q8 延迟从 3.9 秒增加到 9.2 秒，说明高分辨率下 attention、activation traffic 和 kernel scheduling 的占比显著上升。

分析顺序：

1. 对 1024、1536 x 864、1920 x 1088 分别做 Metal capture；
2. 分离 QKV projection、RoPE、SDPA、MLP、VAE decode 和同步开销；
3. 确认 MLX compiled graph 的实际 fusion boundary；
4. 测试 sequence bucketing、固定 shape compiled callable 和位置编码复用；
5. 只有在 SDPA 或 RoPE 占比足够高时，才考虑自定义 Metal kernel；
6. edit 必须分别测试 KV extract、cached denoise 和多参考长度增长。

预期收益：1080p 约 8-20%，1024 通常低于 8%。

### P3：VAE 和内存生命周期

候选项：

- prompt 编码结束后的 text encoder 生命周期管理；
- generation-only worker 的 text encoder 临时卸载策略；
- VAE decode shape cache；
- decode 前后精确释放临时张量；
- 1080p 的非破坏性 decode tiling；
- native mixed checkpoint 消除在线量化峰值。

预期速度收益通常只有 2-5%，但可能降低 3-8 GiB 峰值内存。优先以减少设备门槛和 OOM 风险衡量，而不是只看平均延迟。

### P4：自定义 Metal 内核的边界

0.1.2 已实现并验证 LayerNorm/AdaLN 与 gated residual/LayerNorm/AdaLN microkernel：单算子快 1.7-2.1 倍，数值误差可控；但真实 4B Q8 整图从 3.887 秒变为 3.955 秒，慢约 1.7%。原因是 FLUX denoiser 已由 `mx.compile` 进行更大范围优化，自定义 kernel 可能形成新的 graph boundary。

因此：

- 不默认启用现有 Metal fusion；
- 不重写完整 denoiser；
- 不重写 MLX 已提供的 GEMM 或 SDPA，除非 capture 证明单一热点占端到端至少 20%；
- 新 kernel 必须在完整 compiled pipeline 中获得至少 5% 稳定收益；
- 仅有 microbenchmark 提升不能进入产品。

### P5：可选的分辨率/超分策略

若产品允许非等价但感知质量接近的“快速 1080p”模式，可先生成较低原生分辨率，再使用本地超分模型输出 1920 x 1080/1088。

预期收益为 30-50%，但它改变生成任务和模型链路，必须作为单独模式：

- 明确显示原生生成尺寸和最终输出尺寸；
- 单独评估文字、细线、人物面部和重复纹理；
- 不得把超分结果与原生 1080p 基准混报；
- 需要把超分模型的下载、内存、许可证和延迟计入完整成本。

该路线不属于 FLUX Runtime 内核优化，优先级低于完成其他绘画模型。

## 5. 基准与质量协议

每个候选优化必须至少覆盖：

### 设备

- 一台当前主力 Apple Silicon，记录芯片、统一内存、系统版本和 MLX 版本；
- DGX Spark 仅做 MLX/CUDA 对照；
- 若目标包含低内存设备，增加 24/32 GB Apple Silicon 实机验证。

### 模型和模式

- 4B generation；
- 4B 单参考和四参考 edit；
- 9B generation；
- 9B edit；
- Q8、候选 mixed profile、BF16 control。

### 尺寸

- 1024 x 1024；
- 1536 x 864；
- 1920 x 1088；
- 至少一个竖图尺寸。

### 记录项

- 模型加载、首张、稳态中位数和 P90；
- denoiser、prompt encode、VAE decode 分段时间；
- active、cache、peak memory；
- 原始 checkpoint 与原生派生 checkpoint 的差异；
- compiled callable build 次数和 prompt cache 命中率；
- thermal state，长基准应交错 A/B，避免顺序造成热降频偏差。

### 质量门槛

- 固定 prompt、seed、steps、guidance 和尺寸；
- CLIP 或同等级 prompt alignment；
- LPIPS/SSIM 只用于同 seed 数值变化监控，不替代人工判断；
- 人物、产品文字、海报排版、建筑细节和复杂反射接触表；
- edit 增加参考一致性、主体保持和多参考冲突案例；
- 发现 black image、non-finite VAE 或明显结构退化时直接阻止发布。

## 6. 发布门槛

一个优化进入后续正式版本，必须同时满足：

1. 目标场景端到端中位数提升至少 7%，或峰值内存降低至少 15%；
2. 至少三轮交错 A/B 仍保持收益；
3. 4B、9B generation/edit 无功能回归；
4. 质量指标无显著下降，人工复核通过；
5. 派生权重可重启、可校验、可并发安全创建；
6. 默认模式不扩大最低硬件要求；
7. 可回滚到 0.1.2，并保留旧派生缓存隔离；
8. 包测试、Runtime 契约测试、安装/卸载和升级测试通过；
9. 更新 SBOM、source lock、benchmark receipt 和开发包摘要。

达不到门槛的结果只记录在 benchmark，不进入产品，也不通过多轮小优化累加后宣称未经整体 A/B 证明的收益。

## 7. 推荐恢复顺序

在其他三组绘画模型完成第一轮支持和基准后：

1. 汇总各模型共同热点，优先抽到 MLX Runtime 1.5.x/1.6.x 公共层；
2. 用最新 MLX 对 FLUX 0.1.2 做零改动复测；
3. 产品化 `balanced-q8` 的原生 mixed checkpoint；
4. 若内存允许，再产品化 `fast-q8`；
5. 对 1080p 做 Metal capture，决定是否开展 attention 专项；
6. 只有 capture 和 Amdahl 分析支持时才写新 Metal kernel；
7. 完成 4B/9B generation/edit 全矩阵后再发布新版本。

建议下一版本号为 0.2.0：新增公开 mixed-precision profile 属于用户可见执行策略变化，不应作为 0.1.2 的静默替换。

## 8. 暂不处理事项

- 不为了 Spark 的 MLX CUDA 表现 fork 整套 MLX；Spark 使用 CUDA Runtime；
- 不把 9B 的上游许可证作为技术阻断，许可证继续作为元数据展示；
- 不将 experimental Metal fusion 默认打开；
- 不以降低 steps、降低原生尺寸或改变 seed 作为 Runtime 性能优化；
- 不在完成其他绘画模型前继续消耗主线资源优化 FLUX。

