# DS4.1F Runtime / Package 升级准备

状态：Runtime 1.7.0、DS4.1 SSD checkpoint distribution 与
`ai2apps/model-deepseek-v41-flash 0.1.0` 均已发布。DS4.1 Package 已在全新匿名客户端通过
Repository/Publisher 签名、SHA-256、大小、本地归档字节和 envelope JSON 一致性核验；
Repository metadata v150。其余 SSD 模型迁移及三个兼容性修正版的收尾见
`docs/ai2apps-chat-ssd-model-packages-release-2026-09-17.md`。

## 已确定方案

采用原始 FP4/FP8 精度的 SSD-ready checkpoint。将专家按当前已验证的 expert-major 六段记录重排；视觉、Engram、普通权重保留原数值。避免安装端先下载原始专家、再产生第二份专家仓库。不得把 GLM affine-Q4 fused-v2 直接标成 DS4.1F 格式；当前 DS4.1F fused gate/up 实验未胜出，首版沿用已验证布局。

已检查本地 40 个 layer 文件和各自元数据：每层 384 专家，文件长度全部等于 record_bytes × 384。每记录 18,800,640 bytes，六段依次为 w1.weight/scale、w2.weight/scale、w3.weight/scale。专家总计 288,777,830,400 bytes（288.778 decimal GB）。此项是结构完整性检查，尚非全量发布 SHA 审计。

原始 safetensors header 统计：被替代的 0–39 层专家共 92,160 tensors，payload 同为 288,777,830,400 bytes；其余 3,925 tensors 共 221,508,192,600 bytes。因此保留其余所有 tensor 的重排版本 payload 约 510.286 GB，另加元数据。SSD-ready 本身不减少模型参数或下载权重体积；它避免额外约 288.778 GB 的安装端专家副本。MTP 等未启用 tensor 是否拆为可选分发另行界定，首版不能默默裁剪。

## Runtime 改造边界

当前 Runtime 源清单版本为 1.6.2；这不是本轮对公网最新版本的确认。候选版本应在核对 Registry/现有 submission 后分配，模型最低依赖必须指向实际含 DS4.1F 的新版，不能沿用 GLM 的 >=1.5.5。

1. 将 `experiments/dsv41_mlx` 的已验证核心迁入正式命名空间，移除实验 sys.path、artifacts 路径及 `_dsv41_loader` 临时构建路径。复用现有原生 preadv 装载机制，以打包 Runtime 的 CPython 3.11 / MLX ABI 编译并实测；不把临时 .so 塞进普通模型 Package。
2. 新增独立 DS4.1F engine，接入 `OmlxChatAdapter` 使用的 start/stop/chat/stream 接口及取消、采样、usage、EOS/stop handling；模型可单请求串行，不能声称已有批处理与任意 chunked Prefill。
3. 复用 `ai2apps-model-worker/v1`、Host 选择的 checkpoint 和现有路径授权，不需要创建新的 RPC 协议。视觉输入接入 Host 媒体资源，不能把实验脚本允许的任意本地路径当成产品输入契约。
4. 将当前从 checkpoint 动态导入的官方 chat encoding 纳入受审查、版本固定、带许可的 Runtime 代码；checkpoint 作为数据分发。保持官方 token/template/image 顺序。
5. 缓存准备层增加 DS4.1F 格式识别、原始 checkpoint provenance、逐文件摘要、尺寸/偏移/专家映射检查、原子激活及失败恢复。当前顶层 manifest 仅绑定原始 index hash，不能直接替代发布校验。重排普通权重时须重新建立 tensor index，并分别保留“原始来源 index 摘要”和“实际分发 index 摘要”。
6. 默认完整 Top6、动态 L1=40、L0=8、Prefill 双 scratch=64、Hot-direct、65 GB 进程预算；Burst 与 block 默认关闭，预测 L2/Scope/MTP 不声明支持。首版多轮可采用已验证的完整历史重放，增量 KV、追加图像与状态复用分别验收后启用。

当前代码搜索未找到正式 DS4.1F Runtime engine 或模型 Package；不能仅修改 Package manifest 就获得实验版能力。

## SSD-ready checkpoint 交付结构（设计，尚未生成）

- 完整的 tokenizer、配置、license、来源说明。
- 普通/视觉/Engram 及保留的其他原始 tensor 数据，重新索引但不重新量化。
- 40 层完整 expert-major records 与版本化 schema、每层摘要、段偏移、shape、expert-to-record 映射。
- 记录 source revision、原始 tensor/index 摘要、转换器版本和输出文件摘要。
- 不重复携带已经被 expert-major 替代的 0–39 层原专家 tensors。

与当前“原 checkpoint + 本地 expert store”执行布局相同，因此收益首先是部署、磁盘峰值和安装等待；不能把已有推理 TPS 再算成这次重排新增的加速。

## 模型 Package 和发布顺序

模型 Package 只携带 adapter、配置、许可/SBOM 与固定 checkpoint distribution 引用，不包含数百 GB 权重或原生扩展。暂不填写虚构 repo、revision、distribution ID 或发布版本。

1. 先构建 SSD-ready checkpoint 与最小读取适配；用原始 tensor bytes 对所有搬移段做校验，原始 checkpoint 与重排 checkpoint 跑相同文本/图像和逐步 logits 对照。
2. 上传 checkpoint 至固定 MS/HF 镜像，固定双方 immutable revisions，使用 `build_checkpoint_distribution.py` 按标准流程生成和发布 distribution，匿名回读签名 Index。不能将旧原始 checkpoint 的 distribution_id 复用于重排字节。
3. 完成新版 Runtime engine；本地 managed Worker 验证文本、图像、多轮、SSE/取消、stop/restart、路径授权、65 GB footprint；原有 GLM/Qwen/DS4 回归。通过标准 Runtime DMG 构建、Developer ID、公证/staple，再使用 `build_omlx_runtime_package.py` 封装签名。
4. 使用 `build_signed_registry_release.py` 构建模型 Package，安装真实候选做 managed-service smoke。正式发布先新版 Runtime、后依赖它的模型 Package，保存收据。

遵循 `docs/ai2apps-package-publication-runbook.md`。生产发布、管理员验证、Cookie 使用按届时实际发布上下文处理；本轮未读取 Cookie、未创建 submission、未改现有版本。正式代码迁移开始时同步登记 Desktop 下一版 Release 台账。


## 其他 MoE 的 SSD-ready 收益（源码核对）

用户确认顺序：checkpoint 构建/校验 → MS/HF 上传和 distribution → 新版 Runtime → 模型 Package。

- GLM-5.3 Flash：当前 service.yaml 与 model_installer.py 均只允许 keep_source；原始专家与 fused-v2 专家存储并存。可分发紧凑 backbone/vision/MTP 加完整 fused-v2 专家存储，消除重复专家副本。清单估算 source 170 GB、prepared 165 GB、keep peak 335 GB；这些是安装估算，不是本轮测得的最终体积。
- Qwen3.8 Flash Next：同样强制 keep_source，适合相同方式，保留 qwen4-exp-affine-q4-gate-up-fused-v1 布局。现有 distribution 文件总量 111,601,662,416 bytes；可节省量应按原始重复专家 payload 计算，不能把整个原 checkpoint 总量都算成净节省。当前支持 full/cached 两种模式，去掉原始专家后 full 模式需重建读取适配或明确限制为 cached，不能继续虚假声明兼容。
- DS4 Flash 原版和 2bit：当前已支持 keep_source/delete_after/stream_reclaim；SSD-ready 相比 keep_source 能省重复存储，相比已经回收原始权重的安装，稳态收益较小，主要减少转换时间、写入与峰值空间。清单 source/prepared/keep_peak 分别为 148/143/291 GB 和 90/90/180 GB，仅为清单估算。

共同前提：重写 backbone shard 和 index、保留普通/共享专家/视觉/MTP 等仍需 tensor、更新加载与安装 recipe。不能直接删除混合 safetensors shard。HF/MS snapshot 的 symlink/hardlink 和共享 blobs 不应重复计为物理空间，也不能在迁移中擅自清理被其他模型/版本使用的数据。首次新旧版本并存、下载 staging 和回滚保留仍可能产生额外磁盘峰值。

本节为调查和方案，不修改其他模型的 Package、已安装 checkpoint 或删除策略。

## 2026-09-17 Runtime 1.7.0 实施结果

Runtime 已从实验目录迁入正式 `omlx.patches.deepseek_v41` 命名空间，包含文本、视觉、
Engram、SSD 专家读取、Main40/Hot8 缓存和标准无损 Top6 路径。正式 Worker 使用
`DeepseekV41ChatAdapter`，多轮请求采用完整历史重放；图像通过受控 data URL 输入，默认
视觉上限 256 tokens。文本首 token 与冻结参考均为 671，完整 logits SHA-256 均为
`d7364c56754048399f32c12df0507e3041381bdb553bb2d84da1f96971fd7083`；carrots 图像
首 token 18863，完整 logits SHA-256 与保存的视觉基线均为
`0ae4c5da34c919ee2420c0655afcbccb0acad0b3315b15b02533d0a5e21cf919`。

新增统一 `omlx.ssd_checkpoint` 校验与外置 tensor reader。安装器会验证 schema、family、
layout、文件集合、大小、摘要及专家 manifest，然后原地激活 checkpoint，不再重建或复制
第二份专家仓库。Qwen Next Full/Cached、GLM fused-v2、DS4 原版/2bit、Qwen3.6 和
Ornith 视觉路径均已切换并使用真实 SSD checkpoint 完成短推理；八份机器收据位于
`artifacts/*-ssd-runtime-1.7-smoke/receipt.json` 和
`artifacts/dsv41-runtime-1.7-{smoke,vision-smoke}/receipt.json`。

Runtime Package 元数据已提升至 1.7.0，并声明 `ssd-checkpoint-v1`。Developer ID 签名的
DMG 位于 `artifacts/runtime-1.7.0/AI2Apps-oMLX-Runtime-1.7.0.dmg`。Apple submission
`19de5929-dbb1-486f-a471-8b3038ec8b8b` 已 Accepted；staple 后最终大小
375,944,358 bytes，SHA-256
`cf9a645e84c46711392b53d18855f86201fd32cca280dbd1f0c2d66b69748a32`。构建器新增压缩后
只读挂载与内层 bundle 深度签名门禁；Runtime 自带 CPython 3.11 已验证正式 DS4.1 engine、
SSD schema 及 `copy_expert_slots` 原生入口可导入，六段 GPU slot copy 数值正确。

外层签名 `.ai2service` 已构建并完成 Contract、Publisher 签名、内嵌 DMG 字节一致和全新
临时实例安装验收。Artifact 为 373,748,488 bytes，SHA-256
`b066700dcebec87012e93de01e6114db9f231b0a1c89642e97c50cd91a1ec3a7`。尚未创建
Registry submission 或更新生产 Runtime；Installation Cloud session 当前不可用，按 runbook
等待用户对 `ai2apps/runtime-omlx 1.7.0` 当前 App Dev Cookie 的精确读取授权。

固定 App-Shell 开发环境已通过规定脚本刷新到
`apps/ai2apps-acefox/.build/AI2Apps-app-dev.app`；bundle ID、`app-dev` instance、
Development/source-root、cloud Runtime、禁用更新 URL、`verify-release-app.sh` 与深度签名
均通过。实际窗口标题为 `AI2Apps-App-Dev: M5Max-App-Dev 127.0.0.1:53300`。
