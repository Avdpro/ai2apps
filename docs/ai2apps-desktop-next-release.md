# AI2Apps Desktop 下一版 Release 台账

状态：滚动维护中的唯一下一版入口

## Build 2252 已发布（2026-09-21）

- Build 2252 已从 clean、已推送 commit
  `9521a6d674babd03125ed0e310c926863dbd6cde` 构建；Developer ID、Apple 公证
  `3850a24c-4457-4516-b9d0-ff4cee2cc806`、Staple、Gatekeeper 和最终制品复验均通过。
- GitHub 正式 Release `v0.1.0-build2252` 与 ModelScope immutable revision
  `735eb1d4a1bfbc30677fc80308fc2bb9330a0429` 已发布；匿名完整回读的 DMG/metadata
  字节数和 SHA-256 均与本地一致。Cloud 先以 0 basis points 原子登记并完成严格双源预检、
  公网 GET/HEAD/ETag/304、Cloud 与数据库健康验收，随后将同一 `build2252-test` rollout
  提升至 `10000`。最终生产清单 SHA-256 为
  `894271943aa4977d78fae3a4c2f0d622382662905fd123b26a2e285df5002254`。
- 本版只纳入 `NXR-VERIFIED-OVERLAY-CHECKPOINT-READINESS-20260921`，不升级 oMLX Runtime
  或模型 Package。完整制品、测试、双源和生产发布回执见
  `docs/ai2apps-desktop-build-2252-release-receipt-2026-09-21.md`。剩余验收只包括目标 Mac 的
  2251→2252 自动发现、下载、安装、启动与更新后清理；不影响分发发布已完成的事实。

## Build 2251 已发布（2026-09-20）

- Build 2251 已从已推送源码 commit
  `12af6aa9bfd7bf853fbdbe752fbc8712e60bdbde` 构建，完成 Developer ID 签名、Apple
  公证与 Staple，并发布到 GitHub tag `v0.1.0-build2251` 和 ModelScope immutable
  revision `900bb17bee0d80949da98675dc369e9e28a1846c`。
- Cloud 先以 0 basis points 原子登记并完成公网 GET/HEAD/ETag/304 与双源完整预检，随后将
  同一 `build2251-test` rollout 提升至 `10000`。最终生产清单 SHA-256 为
  `3e3cecaa8a2aaf4f58e6c7a2ac5de4331ff28b026ad2f155f0b8ecb937e1a5dd`。
- 完整不可变回执见 `docs/ai2apps-desktop-build-2251-release-receipt-2026-09-20.md`。剩余验收只包括
  目标 Mac 的 2249→2251 自动发现、下载、安装、启动与更新后清理；不影响分发发布已完成的事实。

- 发布前生产基线：`0.1.0 (2249)`；正式版本：`0.1.0 (2251)`，`arm64`、`cloud` Runtime profile、
  `com.ai2apps.desktop`、instance `default`、`SANDBOX_MODE=0`。Build 2250 保持内部候选，
  不提升、不覆盖。
- 纳入本版的 Desktop/Local 用户能力：
  `NXR-DISCOVER-LEGACY-INSTALL-20260920`、`NXR-ACPF-ACTION-BREATHE-20260920`、
  `NXR-ACPF-SUCCESS-CONFIRMATION-20260920`、`NXR-DISCOVER-DOWNLOAD-TELEMETRY-20260919`、
  `NXR-PACKAGE-PARALLEL-DOWNLOAD-20260919`、`NXR-RESTART-AI2APPS-LABEL-20260919`、
  `NXR-DEEPSEEK-V4-SSD-AUTO-TIER-20260919`、`NXR-ADAPTIVE-DOWNLOAD-20260919`、
  `NXR-DOWNLOAD-PROGRESS-20260919`、`NXR-GALLERY-PAN-BOUNDS`、
  `NXR-IMAGINE-GALLERY-VIEWER`、`NXR-SHARED-CHECKPOINT-CACHE`、
  图片模型公共 Checkpoint 布局验证、Imagine Studio 配置后本地模型发现、
  ACPF 公共弹窗国际化、`NXR-052` Gallery 菜单、`NXR-051`、`NXR-050`、`NXR-048`、
  `NXR-047`、`NXR-043`、`NXR-042`、`NXR-041`、`NXR-038`、`NXR-034`、`NXR-035`、
  `NXR-036`、Studio/Mini-App `NXR-037`、`NXR-001` 至 `NXR-010`、`NXR-014` 至
  `NXR-029` 中所有标为 `ready` 的项目、`NXR-031`、`NXR-032`、`NXR-033`、Official
  Cloud Connector `NXR-037`、Launcher `NXR-039`、Voice Studio `NXR-040`、`NXR-045`、
  Video Studio `NXR-046`、Studio 列表 `NXR-052`、`NXR-ZIMAGE-BASE`、
  `NXR-IMAGE-CAPABILITY-SPLIT`、`NXR-SHARED-CHECKPOINT-REUSE` 与
  `NXR-ORNITH-FULL-SSD`。其中已经由独立 Runtime/Package 交付的部分不在 Desktop DMG
  重复内嵌大型推理 Runtime 或 checkpoint；Desktop 只交付 Host、目录、安装与 UI 合同。
- 纳入与已发布 Package/Runtime 对齐所必需的客户端合同：
  `NXR-MODEL-REASONING-CONTRACT-20260919`、`NXR-MODEL-PACKAGE-STREAM-CODEC-20260920`、
  `NXR-QWEN36-TIERED-PRESPLIT-20260920`、`NXR-FLUX2-KLEIN-9B`、
  `NXR-CHAT-SSD-CHECKPOINTS-20260914` 与 `NXR-PACKAGE-CHAT-METRICS-20260918` 的已发布、
  已回归或已实机验收部分。2026-09-20 用户已确认 DeepSeek V4 `auto`、Chat 性能指标、
  Runtime/Package 重启恢复、完整自适应下载和 ACPF/Discover 成功流程；未据此宣称所有模型、
  Rush 按压或所有大型 checkpoint 均完成逐一实机验收。
- 明确延期且不作为本版 Release note 的项目：`NXR-DEV-TEST-REBUILD-20260920` 与
  `NXR-PUBLISH-LIVE-SESSION-20260919`（开发/发布工具）；Ideogram JSON 提示词后续 Package；
  Z-Image 未完成的 UI 重试；`NXR-049` 视觉复核；Cloud Work complexity `NXR-046` 的完整
  Work 端到端；aria-label `NXR-044` 的 Accessibility Inspector；测试实例 `NXR-040` 的剩余
  P0 队列；`NXR-011`、`NXR-012`、`NXR-013` 的未验收阶段；`NXR-030` 的 Package 重建；
  所有 DSV4.1 L1/L2、miss/resume、ICB、性能实验及未切入生产默认的研究路径。延期代码若作为
  dormant development/experimental source 存在，不得在生产配置、目录或 Release note 中启用或
  宣称已交付。
- `NXR-RELEASE-ALL-20260911` 由本次 Build 2251 正式门禁取代；`NXR-INTERNAL-2250` 保留为
  历史内部证据。Build 2251 必须从 clean、已推送 commit 重建，重新跑全量 Python、Swift、
  JS/静态门禁，比较 2249 最终 DMG 与候选 staging 内容，并完成签名、公证、双源、Cloud 与
  2249→2251 实机升级验收后才能标记发布完成。
- 2026-09-20 正式源码门禁通过：Python 完整回归 10,050 passed / 67 skipped /
  74 deselected / 0 failed；AI2Apps Test System 80 passed / 1 skipped；Node 前端专项
  4/4；Swift 壳层 77/77。这些是候选源码门禁，不代替后续 App/DMG
  签名、公证、双源回读、Cloud 清单和 2249→2251 实机升级验收。
- 发布前门禁发现并修复 `NXR-FLUX2-KLEIN-9B` 的真实客户端缺口：Imagine
  Studio 现在为 FLUX.2 Klein 9B 的图片生成和编辑都提供明确 ACPF 安装方案，
  固定 Runtime `>=1.7.8,<2.0.0`、Package `>=0.1.0,<1.0.0`、Checkpoint `/9b`、
  48 GiB 最低设备门槛及 FLUX 非商业许可提示；中英文 ACPF 文案同步补齐。

### NXR-VERIFIED-OVERLAY-CHECKPOINT-READINESS-20260921：增量 Checkpoint 激活

- 状态：`ready`（107 项相关回归及 App-Dev OpenVDN DMD 8-step Q4 实机重试通过）。
- 修复已完整安装的 Registry 增量/overlay checkpoint 被通用独立模型布局探针误判为不完整的问题。
  OpenVDN 的 5.09 GB checkpoint 已通过签名分发清单校验，但权重位于
  `stage-dmd-step-250/` 等子目录，根目录按设计没有独立模型所需的 `config.json` 和
  safetensors，因此旧逻辑向 Worker 输出空路径并在 ACPF 95% 报
  `The model provider did not become ready after activation`。
- 同一缺陷覆盖 H3 的四个增量变体：LightX2V 4-step、LightX2V 8-step、OpenVDN
  DMD 8-step 和 OpenVDN Stage-B 50-step；本次通用修复一次覆盖四者。FL2VA Q4/Q8 与
  Ref2VA Q4/Q8 是完整 checkpoint，继续走既有独立模型布局校验，不受原缺陷影响。
- 模型感知校验现在接受与 Package 声明 `distribution_id` 精确一致的不可变 Registry
  snapshot，并校验分发格式、manifest digest、完整文件集合、只读常规文件及安装时记录的
  device/inode/size/mtime；任意文件变更、额外文件、符号链接或分发 ID 不匹配都会拒绝。
  普通 Transformer、Diffusers、ONNX 和 SSD Cached-MoE 的既有布局门禁不变。
- App-Dev Local 已通过 Helper 原位重启加载修复；对原失败会话点击 Retry 后直接复用共享
  checkpoint cache，四步立即完成，Worker 配置获得非空 OpenVDN 路径，Video Studio 随后
  识别 `(Local) AI2Apps-MLX · OpenVDN H3 DMD 8-step Q4` 并报告生成环境已就绪。Python
  源码热挂载验证无需重建 App。校验发生在 Desktop Local/Host 的 Service Supervisor，模型
  Package 与 `ai2apps/runtime-omlx` 均无需升版；正式交付需纳入下一版 Desktop App。使用当前
  仓库热挂载的 App-Dev/Dev 只需重启 Local，嵌入固定快照的 Test 和生产实例则需重建或升级
  Desktop App。
- 2026-09-21 已通过标准 `build-test-app.sh` 重建固定 Test App 并启动验收：Bundle ID
  `com.ai2apps.desktop.test`、instance `test`、cloud Runtime、生产更新地址、非 Development
  快照、`verify-release-app.sh` 和深度签名均通过。发布前门禁为 Swift 77/77、相关 Python
  107/107、`git diff --check` 通过；拟纳入 Desktop 0.1.0 Build 2252。

### NXR-VIDEO-TASK-INVOCATION-IDENTITY-20260921：视频后台任务身份分层

- 状态：`ready`（21 项 Video Task、Video Studio 与 schema 定向回归通过；App-Dev 原失败
  OpenVDN DMD 8-step Q4 任务实机 Retry 已越过身份恢复并进入 `generate`）。
- 修复 Video Studio 经 `/v1/videos/generations` 创建的持久任务把任务隔离键
  `ai2apps-user:<UUID>` 直接交给 Cloud 身份仓库的问题；身份仓库只接受 URL-safe 用户 ID，
  因此前一实现会在 Worker 调度前报
  `cloud_user_id must contain 1 to 200 URL-safe identity characters`。
- schema 71 为 `video_generation_tasks` 增加独立 `invocation_actor_id`：登录用户任务用真实用户
  UUID 恢复调度身份，API Key 任务继续以 `local-api:<hash>` 隔离列表、取消和幂等范围，同时
  以 `local` 进入本机后台调度。迁移保留已有任务并把历史 `ai2apps-user:<UUID>` 归属原位规范
  化，Retry 继续继承原始调用身份。
- `VideoTaskManager` 同时兼容已发布 Desktop 内嵌的旧 oMLX 路由与新路由：创建、读取、列表、
  取消、重试和 Join 都在持久层边界统一旧前缀，避免要求开发实例先重建 App 才能恢复任务。
  新 `omlx/server.py` 会直接传递分离后的任务归属与调用身份。App-Dev 只重启了自身 Local，
  schema 实机从 70 升到 71，原任务在刷新后仍可见；点击 Retry 后状态从 `starting` 进入
  `generate`，旧身份错误未复现。此修复不改模型 Package、Checkpoint 或
  `ai2apps/runtime-omlx` Worker Package；Test 与生产需由下一版 Desktop App 带入。

### NXR-DEV-TEST-REBUILD-20260920：开发与测试实例同步

- 状态：`ready`。按用户要求通过标准 `build-dev-app.sh` 与 `build-test-app.sh` 重建固定 Dev/Test App，旧 App 已分别归档；未改动实例数据。
- Dev 保留 `com.ai2apps.desktop.dev` / `dev` 与当前仓库 Development source root；Test 保留 `com.ai2apps.desktop.test` / `test`、cloud Runtime、非 Development 独立快照。Test 内 Registry 源码与当前兼容修复逐字节一致。
- Dev 严格签名验证、Test 标准 release App 验证通过；两实例已启动，本机 bootstrap 均返回 HTTP 200。仅本地开发/测试重建，未发布生产制品。

### NXR-DISCOVER-LEGACY-INSTALL-20260920：旧模型 Package 安装计划兼容

- 状态：`ready`（104 项 Registry/Discover 回归通过，App-Dev Local 已重启加载；未执行实际模型下载）。
- 修复目录装饰器把 modelInstall/modelProfile 解析依赖于 discovery 分类成功的问题。三类元数据现在独立解析，保留各自签名声明及旧版本映射边界；Flux 4B 0.1.4、Flux 9B 0.1.0、Ideogram、Qwen Image、Z-Image 等无需重新发布 Package 即可进入已有 ACPF 安装流程。
- 覆盖 7 类模型的计划/会话 API、全部旧版安装映射、未知 Package 与超版本拒绝。签名、Checkpoint 校验和许可确认流程不变。Python 改动仅需 Local 重启，无需重建 App。

### NXR-ACPF-ACTION-BREATHE-20260920：主操作按钮呼吸提示

- 状态：`ready`（CSS 与静态检查完成，待用户视觉反馈）。
- 共享 ACPF 的可见且可用主按钮增加 2.4 秒柔和阴影呼吸，覆盖继续、确认下载/许可、重启、重试和安装成功后的完成按钮。隐藏/禁用按钮不播放；悬停和键盘聚焦时保持稳定高亮，焦点轮廓保留；系统减少动态效果时使用静态光晕。只改变阴影，不改变按钮位置或文字对比度。
- 更新所有直接引用共享 CSS 的入口资源版本；纯样式修改，刷新页面生效，不需要 Local 重启或 App 重建，不改变安装/授权行为。相关 diff whitespace 检查通过。

### NXR-ACPF-SUCCESS-CONFIRMATION-20260920：安装成功后确认关闭

- 状态：`ready`（前端实现、自动化测试和 App-Dev 实机安装完成页验收均通过）。
- ACPF 到达 ready 后停止轮询，保留对话框并显示“安装成功”、可开始使用说明、100% 进度与“完成”按钮。点击完成才 resolve configured result/恢复调用方后续动作，保留原 completion policy 与 acknowledge-return 语义；ready 状态忽略过时的取消/重试点击。刷新恢复的未确认 ready session 同样展示成功确认；已就绪能力 probe 的 already_ready 快路径保持不弹安装框。
- 共享逻辑覆盖 Chat、Discover、Studio 等 ACPF 入口；新增三条文案覆盖全部 9 个语言目录，并统一更新 7 个入口的共享脚本版本以避免旧缓存。
- 验证：48 项 ACPF/本地化回归通过；Node 控制流测试覆盖下载变为成功、刷新恢复成功、未确认不关闭、不提前恢复动作、点击后正常返回且停止轮询。纯前端改动，刷新对应页面生效，无需重启 Local 或重建 App；未操作当前安装。
- 2026-09-20 用户完成 App-Dev 实机验收：Chat ACPF 的 DeepSeek V4 安装四步均进入 Completed，成功页保持可见直至点击 Done；Discover 的 FLUX.2 Klein 4B 安装成功页同样正确显示三步 Completed、100% 进度和 Done。验收中发现的问题已修正，Runtime 已升级。

### NXR-DISCOVER-DOWNLOAD-TELEMETRY-20260919：Discover Package/Checkpoint 下载统计

- 状态：`ready`（代码、自动化验证及 Local 重启后的 App-Dev 实机界面验收通过）。
- 已确认 Discover Package 使用 Registry 四块并行及两次同源连胜优选策略，Checkpoint 委托共享 ACPF 自适应下载链路。截图处于权限审核，下载已结束；此前页面只在下载阶段基于轮询估算速度，后续阶段清空显示。
- 新增共享后端 DownloadProgress：Package 和 Checkpoint 基于收到字节提供最近 5 秒速度、剩余下载 ETA、文件及总字节；续传基线不计入速度，重试回退重置采样，Checkpoint 跨文件使用总计。Installer task 和 ACPF 传递统计，Discover 下载时明确显示速度与 ETA，校验/授权阶段保留最近传输尺寸及最近速度并移除 ETA；ACPF 同步保留最近传输摘要。无后端新字段时保留旧页面采样兼容，过期实时统计归零，避免继续展示陈旧速度。
- 验证：129 项 Registry/Checkpoint/Acquisition/ACPF/本地化回归通过；新增统计与 Installer 取消共 3 项通过；Node 速度格式行为、Discover 实际 install 方法从下载到审核显示、模型委托 ACPF 行为测试通过；新增后端统计后的 ACPF 定向复测通过。
- 修改 Python 下载器/Installer/Orchestrator、共享 JS、Discover JS/template、中英文文案及测试。Discover 静态资源版本已更新。当前安装授权流程不自动批准或重启；完成当前安装后重启 Local 并刷新 Discover 生效。未修改 Cloud 或发布制品。
- 2026-09-20 用户完成 App-Dev 实机验收：下载面板正确显示当前文件 `experts/layer-000.moe`、当前文件百分比与字节数、总下载百分比与字节数、实时速度和 ETA；Discover 安装完成页及 Package 状态同步正常。

### NXR-PACKAGE-PARALLEL-DOWNLOAD-20260919：Runtime/Package 并行分块

- 后续选源规则：按分块顺序统计校验成功的竞争胜者，同源连续胜出两块后，后续预取只请求该源，保留最多四块并行；已发出的竞争请求正常收尾。选定源传输失败/超时/坏哈希导致请求耗尽时，清空优选及连胜记录并恢复多源竞争；使用选源轮次隔离旧在途结果，防止故障前结果重新锁定失效源。新增连续胜出、交替胜出不锁定、选定源失败后重新竞争并锁定备用源测试，Registry/ACPF 共 80 项通过。2026-09-20 已完成 App-Dev 下载、重启及状态恢复实机验收。

- 状态：`ready`（实现、77 项定向回归、完整 Runtime 实网对比及 App-Dev 重启状态恢复实机验收通过）。
- Registry Package 下载由逐块串行改为最多 4 个不同块同时下载；保留每块多源竞争与 SHA-256 校验，并按顺序 fsync 落盘和持久化连续已校验前缀，兼容原有续传文件。预取窗口按 32 MiB 预算缩减并发（单个更大的合法块仍可下载）；进度汇总在途块且不重复累计竞争源流量。
- 失败/取消清理所有预取请求，取消期间等待已开始的后台落盘及状态写入结束，防止旧写入与后续续传冲突。保留最终完整制品 SHA-256 校验和安装签名流程。
- 实网完整 Runtime 1.7.5（373,254,507 bytes）对比：串行 120.31 秒 / 2.96 MiB/s，四块并行 82.75 秒 / 4.30 MiB/s，两次完整 SHA-256 均与已发布制品一致；临时下载文件已清理。当时模型下载同时运行，结果仅代表此次共享带宽条件，不能承诺固定提速倍数。
- Registry 与 ACPF 定向回归 77 项通过，diff whitespace 检查通过。涉及 `ai2apps/packages/registry.py`、`tests/test_ai2apps_registry_v1.py`；新增四块实际重叠、乱序完成仍有序写入、进度边界、失败清理及取消中落盘持久化测试。App-Dev 已有进行中的模型下载，因此本轮不重启 Local；下载结束后的下一次 Local 重启加载此修改，无需重建 App。不修改 Cloud、不发布、不自动开始模型下载。
- 2026-09-20 用户确认 Runtime/Package 并行下载及 AI2Apps 重启后的安装状态恢复均通过；Runtime 已升级至已发布的 1.7.8。

### NXR-MODEL-REASONING-CONTRACT-20260919：强制思考模型协议化（in_progress）

- 新增签名的 `ai2apps.reasoning/v1` 模型契约；对话模型 Package 可声明
  `required / optional / none`，并由 Host 校验后公开到模型目录。Runtime 不再忽略
  `chat_template_kwargs`；`required` 会覆盖客户端 Thinking Off，从生成首 token 起把
  `think_tags` 分流为 `reasoning_content` 与 `content`，同时兼容模型省略 `<think>`、只返回
  `</think>` 边界的输出。非流式响应使用同一分离规则。
- Runtime 候选升至 1.7.5；全部现役 oMLX 对话模型 Package 同步完成显式契约：DeepSeek
  V4 Flash 0.3.4、Ornith 0.1.4、DeepSeek V4 Flash 2-bit 0.3.5、DeepSeek V4.1 Flash
  0.1.1、GLM-5.3 Flash 0.1.5、Qwen3.6 0.3.4、Qwen3.8 27B 0.3.3、Qwen3.8 Flash
  Next 0.1.4。DeepSeek V4 两个量化版本、Ornith 与 GLM 均声明
  `mode: required`，携带自己的 Jinja chat template，把 assistant generation prompt 从旧的
  `<｜Assistant｜></think>` 修为 `<｜Assistant｜><think>\n`；客户端即使残留 Off 设置也不能
  关闭强制推理；Ornith 与 GLM 沿用 checkpoint 中已经正确开启 `<think>` 的模板。DeepSeek
  V4.1 与三个 Qwen Package 声明 `mode: optional, default_enabled: true`。V4.1 专用引擎不再
  硬编码 `thinking_mode="chat"`，而是映射签名契约和请求的 `enable_thinking`。Checkpoint 与
  权重均不变。
- 开发规范要求新建或升级的 LLM/VLM Package 必须声明真实思考策略；App/Mini-Entry 不得按
  名称或偶然标签猜测，`required` 应禁用 Off，`none` 应隐藏 Thinking。发布测试必须覆盖
  Prompt、流式/非流式分流、缺失开标签恢复和多轮历史。
- 共享 Runtime 1.7.5 已完成 Developer ID 签名、Apple 公证、staple、Gatekeeper 与 Publisher
  签名，并先于八个依赖模型 Package 发布；九个制品的公网匿名回读均确认 exact bytes 与
  envelope 完全一致，Registry metadata version 176。隔离安装最终 Runtime 与 DeepSeek V4
  0.3.4 后 Worker 达到 running，依赖锁精确指向已发布 1.7.5 digest。生产 Cloud 暂不接受
  可选 `modelInstall` 外层投影，最终模型制品使用标准兼容开关省略该投影，Package 源码与签名
  `service.yaml` 保持真实声明，客户端 fallback 严格限于本次版本。完整回执见
  `docs/ai2apps-mlx-runtime-1.7.5-reasoning-contract-release.md`。App-Dev/Test 交互式多模型推理属于
  后续客户端部署验收，不改变本次已发布 Registry 制品。
- 发布后 App-Dev 实机发现 GLM 0.1.4 的 Cache-MoE recipe 漏掉强制的
  `engine.scope_pack`，ACPF 在 checkpoint 下载前 45% 报
  `Preparation engine.scope_pack must be Package-relative`。0.1.5 已补入绑定现有 profile
  SHA-256、模型 ID 与固定 revision 的 Package-owned scope pack；91 项定向回归通过，最终
  Chat ACPF profile 下限同步提高到 `>=0.1.5,<1.0.0`，Retry 会升级已安装的坏版 0.1.4；
  最终签名制品 SHA-256 为
  `dfc5761347bd1e7fc8a41a57a723460656c63694696821326a24ce64f9b1fdbd`。隔离安装精确 Runtime
  1.7.5 + GLM 0.1.5 后 Worker 达到 running，依赖锁正确。0.1.5 已使用精确版本授权通过标准
  live Shell BiDi 发布路径完成生产发布，submission
  `bee627d6-0aa4-423c-881c-33dbf8689fa7`，Registry metadata 177；匿名回读的制品字节与
  Envelope 均完全一致。固定 App-Dev Local 已单独重启并加载最新 Chat，安装向导可见 GLM，
  Profile 明确要求 `>=0.1.5,<1.0.0`；为避免未经请求下载约 181 GB checkpoint，验收停在确认前。
  详见 `docs/ai2apps-glm5-3-scope-pack-hotfix-0.1.5.md`。
- DeepSeek V4.1 实机随后暴露独立的流式解码缺陷：专用引擎使用
  `skip_special_tokens=True` 同时删除 `<think>`/`</think>` 边界，并把未完成 UTF-8 的临时
  U+FFFD 当成稳定前缀；下一个 token 修正前缀时又重放整段文本，导致正确的
  `reasoning_content` 同时重复进入 `content`。现已保留思考边界、显式排除 EOS、延迟 U+FFFD
  并强制 append-only delta；11 项 Runtime/Worker 回归通过。固定 App-Dev 已按规定脚本重建，
  仅重启 `app-dev` Local 后真实请求 `请只回答：你好` 的 UI 正文仅为 `你好`，持久化记录也
  确认推理与正文严格分离。此修复不追溯修改已发布 Runtime 1.7.5；Runtime 1.7.6 已从
  1.7.5 冻结发布源仅叠加该 decoder 文件，排除工作区无关原生二进制变化。Apple 公证
  `06b63e09-2d23-47c5-91b2-f6fbf7ea79a4` Accepted，staple/Gatekeeper 通过；生产 submission
  `8a9f69d0-4512-4e3b-bdbb-ad9c0cce2f98` 已发布，Registry metadata 178，匿名回读 artifact
  与 Envelope 完全一致。隔离安装 Runtime 1.7.6 + DeepSeek V4.1 0.1.1 后 Worker running，
  依赖锁精确指向发布摘要；无需修改 checkpoint 或模型 Package。大型 Runtime 暂沿用 1.7.5
  的 Cloud 单源，后续需在单独授权下补齐 GitHub/ModelScope 固定源与 Cloud 激活。详见
  `docs/ai2apps-deepseek-v41-thinking-stream-fix-2026-09-19.md` 与
  `docs/ai2apps-mlx-runtime-1.7.6-deepseek-v41-stream-release.md`。

### NXR-MODEL-PACKAGE-STREAM-CODEC-20260920：模型输出策略下沉到纯 Python Package（published）

- Runtime 与模型 Package 的边界已固化：Model Worker Package 只允许签名 Python 策略和数据
  资产；MLX/oMLX、tokenizer 原生实现、Metal kernel 与执行器继续由 Runtime 提供。Contract v1
  构建/验包及旧 Service Archive 验包都会拒绝 `.so/.dylib/.metallib/.node` 等原生载荷和
  Model Worker 的 `native_artifacts` 声明，错误码
  `model_worker_native_payload_forbidden`。
- Runtime 新增版本化 `ai2apps.model-stream-codec/v1` 及默认
  `PrefixTextStreamCodec`。`OmlxChatAdapter.create_stream_codec()` 默认返回 `None`，因此已发布
  Package 继续使用 Runtime 当前 decoder；以后新建或升级的 Package 可仅用纯 Python 覆盖
  token 前缀解码和 append-only delta，不需要复制或升级 Runtime 原生代码。DeepSeek V4.1 专用
  引擎已接入该 hook；当前模型 Package 全部不升版。
- Runtime 候选元数据升至 1.7.7，并新增 capability `model-stream-codec-v1`；模型 Package 手册已
  写入强制边界、API 示例、兼容策略及测试矩阵。69 项定向回归、Ruff 与 diff whitespace
  检查通过；未修改的 DeepSeek V4.1
  0.1.1 经标准构建器原样构建成功。标准 Runtime 构建器已产出 361,684,836-byte 的 ad-hoc
  1.7.7 开发制品，SHA-256 为
  `4a4d0d76c03246ca4bb1d7bd84d9aaa7bc452a0d711aa0d0942b9c833a909df8`，并由旧 Service
  Archive inspector 重新验包通过。
- 固定 `AI2Apps-app-dev.app` 已按标准脚本重建并保留 `app-dev` 数据；旧 App 归档为
  `AI2Apps-app-dev-20260920-000836.app`。深度严格签名验证、bundle/instance 身份、Bundle 内
  codec/hook 文件均通过；实时原生标题为
  `AI2Apps-App-Dev: App-Dev 127.0.0.1:51268`，Local 健康检查返回 `healthy`。
- Runtime 1.7.7 已完成 Developer ID 冻结；Apple 公证
  `b15b7da5-0eec-4afb-aad6-6279e131220d` Accepted，staple/Gatekeeper 通过。生产 artifact
  SHA-256 为 `f1b8d19e6befcb9c604bf975fd6dbdd3bb055db8a78fa83c17ef3e498dfc9408`，
  Cloud Submission `9b85c590-199c-4ec4-80e7-f87d10fc4392` 已发布，Registry metadata 179；
  匿名回读 artifact bytes 与 Envelope JSON 完全一致。当前模型 Package 与 checkpoint 均未升级。
  候选与生产回执分别见 `docs/ai2apps-mlx-runtime-1.7.7-model-stream-codec-candidate.md`、
  `docs/ai2apps-mlx-runtime-1.7.7-model-stream-codec-release.md`。

### NXR-QWEN36-TIERED-PRESPLIT-20260920：Qwen3.6 Tiered 预拆分专家 bank（published）

- Qwen3.6 SSD reader 会把 Top120 + Tail24 直接写入 `switch_mlp` 与
  `tail_switch_mlp`；文本模型 sanitizer 此前仍只接受 256-row 全量 bank 或 144-row 临时合并
  bank，因此把合法的 120-row 主 bank 误报为 checkpoint 损坏。VLM sanitizer 已有正确的预拆分
  兼容逻辑。
- Runtime 文本路径现与 VLM 对齐：当主 bank 数量等于 resident experts、tail bank 已存在且数量
  匹配时直接接受；全量 256 与旧 144-row 合并格式继续兼容。新增真实 Top120 + Tail24 回归。
- 34 项 Qwen3.6 定向测试通过；Cache-MoE Worker、Inference Runtime Package 与 Runtime builder
  的 24 项相关回归通过。另一个既存 DeepSeek 2-bit adapter 测试独立运行仍失败，与本差异无关。
- 已发布 Runtime 1.7.7 不可变，本修复归入 1.7.8 开发候选；Qwen3.6 0.3.4 模型 Package 与
  checkpoint 不需要升级。标准 Package Manager 已把 1.7.8 开发候选安装到 App-Dev，启动时
  原子激活新 Runtime 并把 Qwen3.6 等兼容模型锁迁移到候选 digest；实际 Qwen3.6 Worker 已确认
  从 1.7.8 路径运行，真实 Chat 请求返回 `40` 且 Prefill/Token Gen 指标非零，旧专家数量错误未复现。
- Runtime 1.7.8 已完成 Developer ID 签名、Apple 公证（Submission
  `54b2c19c-45d8-4648-a550-270a1b815feb`）、staple、Gatekeeper、Publisher 签名与 Cloud
  发布；Cloud Submission `319cad86-d84d-4992-a16a-8a0bb53dee77`，Repository metadata
  version 180。匿名回读确认 artifact bytes 与 envelope JSON 完全一致。正式回执见
  `docs/ai2apps-mlx-runtime-1.7.8-qwen36-tiered-presplit-release.md`。
- 同一生产制品已原样上传到 GitHub 固定 tag `package-runtime-omlx-v1.7.8` 和 ModelScope 固定
  revision `9a6411755593810876673cd594e085c169048f26`；两端元数据、匿名完整下载 SHA-256 与
  首/中/尾/单字节 Range 均通过，GitHub 为标准 206，ModelScope 为严格 `200 + Content-Range`。
  Cloud 进一步完成每个外部源的完整文件、45 个 8 MiB piece 与 48 次 Range 校验并激活：
  ModelScope `src_9a0c8006-02a1-4072-89b7-ac7dd2ba130b`，GitHub
  `src_7d273abf-119c-44df-afe9-5af509c82e69`。最终 Cloud + ModelScope + GitHub 三源均为
  active，Repository metadata version 182，Snapshot digest
  `ab0756465380540977ee446ad9cdb7aae7fb3ecdb1e7b2030572d0cacffe78d8`；匿名回读再次确认
  artifact bytes 与 Publisher envelope 精确一致。
- 2026-09-20 发布前综合复验发现两项 Installer 测试仍固定旧的 Qwen3.6 普通 Hugging Face
  仓库与 revision；产品代码和签名 Package 已正确使用 SSD 合同
  `Avdpro/Qwen3.6-35B-A3B-4bit-SSD@c6b2081c394f6c1270b243eb77292e70769af341`。
  仅将测试夹具和断言更新到现行合同后，下载/Checkpoint/Registry/Installer/Provisioning/
  Model Manager/Chat Adapter 合计 196 项全部通过；ACPF 成功确认、Discover 下载统计和传输
  进度 3 项 Node 测试全部通过。未修改产品运行行为或已发布 Package。

### NXR-RESTART-AI2APPS-LABEL-20260919：安装完成后的重启文案（ready）

- ACPF 安装向导、Discover 安装完成、Package 卡片待激活状态及 Chat 模型激活提示不再显示
  内部组件名 `Restart Local / 重启 Local` 或 `Restart local service / 重启本地服务`，统一改为
  用户可理解的 `Restart AI2Apps / 重启 AI2Apps`，
  避免被理解为重启整台电脑。英文、简繁中文、西班牙语、法语、日语、韩语、葡萄牙语和
  俄语资源已同步；Discover 内建 fallback 同步更新。
- 仅修改直接加载的 JavaScript 与本地化资源，刷新 Shell 页面即可生效，无需重建 App。

### NXR-DEEPSEEK-V4-SSD-AUTO-TIER-20260919：SSD Checkpoint 自动内存档位修复

- 状态：`ready`（Runtime 已完成 Apple 公证、Cloud 发布和 GitHub/ModelScope 三源激活；App-Dev 安装后的 `auto` 真实推理与 Chat 性能指标实机验收通过）。
- App-Dev 的 DeepSeek V4 Flash SSD checkpoint 使用新布局标识
  `ai2apps-ssd-checkpoint`；Runtime 自动档位估算只识别旧
  `ai2apps-backbone-expert-store`，因此把约 12.2 GiB 骨干误当完整模型，看到 Lean
  约 32.7 GiB 后错误判定三档均无效。修正后按骨干加 43 层外置专家计算完整模型约
  156 GiB；128 GiB 设备在保留 20% 系统/KV 空间后自动选择 Optimal Top60，估计驻留
  约 53.6 GiB。
- 受限 App 进程不能启动 `sysctl` 时，物理内存探测新增 POSIX page-count 回退，避免无
  MLX 的控制面误降为 8 GiB。旧布局、新 SSD 布局和 Full 外置专家注入均保留。
- 新增档位估算、128 GiB sysconf 回退和 SSD Full 注入回归；当前 66 项定向测试通过，
  真实已安装 checkpoint 的离线复算得到 Lean/Compact/Optimal 全部可用且推荐 Optimal。
  App-Dev 临时显式固定相同的 Optimal Top60 后，真实 Chat 冷启动请求成功返回 `40`，旧
  的无可用内存档位错误未再出现；首次请求约 51.7 秒，Prefill 约 3.0 tok/s、Decode
  约 5.1 tok/s。1.7.4 安装后需恢复 `auto` 再做最终真实验收。
  Runtime 1.7.4 已从正式 1.7.3 冻结源码只叠加上述三个 Runtime 文件构建；内部 DMG
  376,767,222 bytes，SHA-256
  `581ad359a7c107decc7f3ba6deb20d922c086ec3e02cf1118f8bcef5e579a7ed`，Developer ID
  签名与 DMG 完整性通过。Apple submission
  `19430ca1-eaed-494c-87e9-8f0ada32c06c` 已 Accepted；stapled DMG、Stapler、Gatekeeper
  通过。正式 Package 374,581,509 bytes，SHA-256
  `20efe8fb3c97c6bef997918028940da253090a76029b8cbc2b78ffc7ddb4bd4c`；Cloud submission
  `3aca5beb-2c5e-4c33-9345-ec27173c212d` published，Repository metadata 163。
- GitHub 与 ModelScope 公开制品已匿名完整下载，大小/SHA-256 与签名本地制品一致；抽样
  Range 字节一致，GitHub 为标准206，ModelScope为受限兼容的200+Content-Range。GitHub
  Source `src_e89f926a-f465-41ea-82ac-ada4743c5cf9` 已通过48-piece/full SHA/Range门并激活，
  Repository metadata 166、Snapshot
  `fee0a791efbec7b47831538620debd9b32b31f7962e9b516d13aa593c1d59988`。ModelScope 嵌套
  路径登记触发 Cloud INTERNAL_ERROR，未落库；改用既有正式 Runtime 已验证的根路径形状，
  ModelScope 复用同一 blob 产生不可变 revision
  `dc48b9b4c2e44135ad887986a5e60a827ae31fe6`。Source
  `src_5a8dc563-7939-4fd2-865c-897254024c31` 通过48-piece/full SHA及严格
  `http-200-content-range` 门并激活；最终 Repository metadata 167、三源 Snapshot
  `a02cd12584a4f02fe2b8fa5d507584c8034359df9a0dd00c31501d07eaed586a`。匿名 Registry
  回读确认签名、Envelope、本地制品字节完全一致，Cloud/GitHub/ModelScope 均 active。
- 横向审计确认同一布局误判会影响共用 DeepSeek V4 profile 的 4-bit/2-bit Package，
  1.7.4 已同时覆盖；DS V4.1、Qwen3.6、Ornith 不走该判断。GLM 与 Qwen Next 的后续
  Package 0.1.3 已完成真正的自动档位选择：128 GiB 保持 Balanced Top96/Top160，较低内存
  分别降到 Lean Top80/Top128，Qwen Performance 保持显式；低于 Lean 加标准系统/KV 预留
  时拒绝。发布门槛同步为 GLM 72 GiB、Qwen 64 GiB，均依赖 Runtime >=1.7.4。
  GLM submission `44e3091a-638c-459b-851e-10ef9f2b3764`、Qwen submission
  `ac46844c-34dc-4598-84f1-22bb37c6eab3` 均 published，Repository metadata 最终为165；
  SSD checkpoint distribution 未改。两套 Package/Contract/Discover 80项与发布/Runtime
  builder 32项通过，128 GiB 实机 resolver 均选择 Balanced，归档无权重或原生载荷。
- 2026-09-20 用户在 128 GiB App-Dev 环境完成最终实机验收：DeepSeek V4 Flash 在 `SCOPE auto` 下正常回复，界面显示 Prefill 0.55 tok/s、Token Gen 7.6 tok/s、Thinking 13.1 秒、Duration 46.1 秒及 SSD Pressure 指标。该证据关闭 `auto` 与 Chat 指标验收；不据此额外宣称 Rush 按压控制已验收。

### NXR-ADAPTIVE-DOWNLOAD-20260919：模型下载按吞吐量分源

- 状态：`ready`（实现、回归、真实分块下载对比及 App-Dev 完整模型下载验收通过）。
- Checkpoint 调度取消 piece index 轮流分源；先采样、再按已校验块的传输吞吐量 EMA 和在途请求数排序，异常或坏哈希源降级 30 秒但保留兜底。默认并发 4 → 8，允许显式 1–32；连接池至少 16、keep-alive 60 秒。探测并发有界、单探测超时 15 秒；下载用固定数量 worker，失败/取消等待所有 worker 清理。逐块哈希、落盘确认、跨文件组合回退与断点续传校验保留。
- Checkpoint/Acquisition/Registry/ACPF/本地化共 122 项测试通过。定向测试覆盖较低探测延迟但实际较慢的源、快速坏哈希源降级、取消后无残留请求，以及原有断点续传/范围响应/许可验证；真实 A/B 各取同一签名清单前 32 块（256 MiB），旧四并发轮流分源 29.59 MiB/s，新八并发自适应 29.27 MiB/s，均 32 块完整校验通过。本次网络未复现此前慢 ModelScope，不能声称实测固定倍数提速。数据仅在临时目录，未启动完整下载、未导入候选权重。
- 文件：`ai2apps/checkpoint_distribution.py`、`ai2apps/checkpoint_acquisition.py`、`tests/test_checkpoint_distribution.py`。已通过专属 Helper 重启 App-Dev Local，新 PID/boot ID 验证通过，bootstrap HTTP 200；已下载块保留。无需重建 App；未发布。
- 2026-09-20 用户完成完整模型下载、安装和启动验证；下载过程中自适应多源进度持续更新，完成后模型服务成功进入可用状态。

### NXR-DOWNLOAD-PROGRESS-20260919：ACPF/Discover 下载速度、ETA 与块内进度

- 状态：`ready`（实现、定向测试及 App-Dev 实际下载验收通过）。
- ACPF 与 Discover Package 安装显示最近 5 秒收到字节的平均速度、下载 ETA；续传/任务切换/重试回退重置采样，停滞时速度降至零，ETA 无估计时显示破折号。模型 HTTP Range 每次读取上报块内进度，按并发 piece 汇总并分离收到/已校验字节，失败重试清除临时计数；完整哈希校验不变。
- Package/模型逐块哈希与落盘移出 asyncio 主线程；界面轮询 500ms，进度过渡 500ms，减少块边界跳动。ETA 仅估算剩余下载，不包含安装/启动时间。
- 验证：Checkpoint、Registry、ACPF 与本地化定向回归 110 项全部通过，Node 前端采样行为测试通过，相关 diff whitespace 检查通过；新增块完成前进度与校验后计数、坏源重试不重复累计验证。后续补齐 DeepSeek V4.1 Flash 名称及说明的中英文翻译键，修复 Profile 新增文案未同步字典导致的本地化回归失败；不改 Profile 内容。
- 涉及 `ai2apps/checkpoint_distribution.py`、`ai2apps/packages/registry.py`、ACPF/Discover JS/CSS/template 与定向测试。App-Dev 需重启 Local 并刷新页面，无需为此重建 App；未发布或操作正在运行的下载。
- 2026-09-20 用户实机确认 ACPF 下载中的当前文件、块内百分比、当前/总字节、总进度、速度和 ETA 正确显示，并完成到安装成功状态。

### NXR-PUBLISH-LIVE-SESSION-20260919：发布工具在线读取授权会话

- `in_progress`：标准 Package 发布工具新增显式 `--browser-live`，复用已认证 Shell BiDi broker，核对 Local installation/instance、精确 Profile 和 scoped Cookie；不读 SQLite、不隐式回退、不输出协议/凭据、不结束共享浏览器会话。离线 SQLite 保留为互斥显式选项。更新发布规范，取消将退出 Shell/App 作为常规前置步骤。
- 15 项发布工具测试通过，覆盖 Cookie 名称/域/路径、歧义拒绝、编码校验、错误脱敏、隔离 Profile 和过滤 BiDi 命令；Dev Local 启动后保持 Shell 运行，`--browser-live --publishers-only` 和 `--list-only` 均真实成功，原 Publisher/key active。未读取 SQLite、未退出浏览器。在线工具验收完成；Runtime 1.7.3 与 App-Dev/Test 更新仍在进行。

### NXR-PACKAGE-CHAT-METRICS-20260918：Package Chat TPS 与 Rush 控制

- 2026-09-19：用户授权发布 Runtime 1.7.3、Apple 公证，并更新固定 App-Dev/Test，保留实例数据。1.7.3 manifest/SBOM 已同步；与正式 1.7.2 比对，源代码增量仅共享 Chat Adapter、Worker control endpoint 与 Host boost 路由。109 项回归通过。Dev Installation 会话缺发布权限，精确授权的 Dev Cookie 标准读取暂因数据库锁失败；未提交/发布、未替换实例。
- 候选已由正式 1.7.2 Runtime 源码快照叠加本次 3 文件构建，Developer ID/内外签名通过；Apple 已上传，submission `6212d14b-20c5-4460-933d-6c39f3ca77b5`。恢复记录见 `docs/ai2apps-mlx-runtime-1.7.3-chat-metrics-release.md`；尚无 Cloud submission。
- 后续：Apple Accepted/staple/Gatekeeper 通过，原 Publisher 签名包发布为 1.7.3，Cloud submission `99416633-5c2f-477a-9c8d-f4b986ace281`、metadata 162；匿名完整下载与本地 SHA/envelope 精确匹配。隔离 Qwen3.8 原包安装、依赖锁和 Worker 启动通过。App-Dev/Test 固定脚本重建、旧 App 归档和完整签名校验完成，未重置数据。App-Dev Discover 安装完成，显示 Local/Cloud 1.7.3 并执行 Restart Local。Test 新 App 已启动，等待用户登录后升级 Runtime。多源分发和真实 Chat/Rush 性能验收待完成；当前 Cloud-only，不宣称全流程验收完成。

- 状态：`in_progress`（代码与定向回归完成，待固定 App-Dev 重建后实机验证）。
- 修复：Package 模型目录从可信 checkpoint preparation recipe 声明 Cached-MoE 能力；Host Engine Boost 路由转发到已运行 Worker 的认证 control endpoint，不经过生成队列、不启动新引擎，实际引擎不支持控制/模型不匹配时拒绝。共享 OmlxChatAdapter 输出流式最终 usage 与原生速度；旧引擎缺原生 TPS 时附 Worker 观测估算及来源字段，Chat 缺统计显示“—”。
- 文件：`ai2apps/model_providers.py`、`ai2apps/model_worker/{omlx_chat,server}.py`、`omlx/server.py`、`ai2apps/web/templates/chat.html`、`tests/test_ai2apps_omlx_chat_adapter.py`。
- 分发：未修改模型 Package/权重。Qwen3.8 27B 继承共享 OmlxChatAdapter，统计修复由共享运行代码获得，不需单独修改模型包；其普通 VLM 引擎不因此获得 Rush。现有已运行 Worker 必须重启，App-Dev 因内嵌 omlx 路由变化需固定脚本重建。正式分发须把共享 Local/Worker 源码纳入相应 Desktop/Runtime 制品；未构建、未发布，不宣称旧安装已生效。
- 验证：共享 Chat Adapter、Model Provider、Worker、Chat UI 93 项通过；覆盖最终 usage 原生 TPS、已加载引擎控制/错模型拒绝、控制端点认证与无效参数/不支持引擎拒绝。相关文件 diff whitespace 检查通过。尚未实机验证长回复 Rush 按下恢复与速度数值。

### NXR-GALLERY-PAN-BOUNDS：图片查看器按实际溢出拖拽（ready）

2026-09-14 后续修正：用户实测发现图片缩小偏下且拖动留白不对称。查看区域改为绝对填充 stage，固定 minmax 网格并让图片以 object-fit:contain 填充明确尺寸，避免图片固有高度撑大网格；上下留白统一。允许所有 Zoom 下拖动，四边提供对称 48px 过拽余量，缩小到可容纳时对应轴重新居中；取消拖动 transform 动画以避免延迟。行为测试新增 25% 和正反方向边界对称验证；待实机视觉复核。

2026-09-14：Gallery/Imagine 共用图片查看器移除缩放百分比拖拽门槛，按图片实际渲染尺寸、Zoom 和可视区域计算可拖动轴及边界；缩放后校正位移，完整显示的轴保持居中。图片常态光标为 grab，拖动时为 grabbing。行为测试覆盖 75%、100%、125%、150%、200% 裁切拖动、边界限制及完整显示不拖动。纯前端修改，刷新页面生效，无需重建 App；待实机视觉验收。

### NXR-IMAGINE-GALLERY-VIEWER：输出图复用 Gallery 查看器（ready）

2026-09-14：Gallery 对话框提取为 `_gallery_preview_dialog.html`，Gallery 和 Imagine 共用模板及 Gallery 缩放/平移/下载逻辑。Imagine 输出图支持点击、Enter/空格打开只读查看，不要求先 Add to Gallery，不创建资产；隐藏重命名，限制同源 http(s) 内容，Esc 关闭并恢复滚动与焦点。只读 viewer 不初始化 Gallery 列表/API。`node tests/gallery_result_viewer.test.cjs` 与 JS 语法检查通过；待 App-Dev 页面刷新实机确认。纯前端改动无需重建 App。未修改模型 Package。

### NXR-FLUX2-KLEIN-9B：独立 9B 模型 Package（in_progress）

2026-09-15（发布完成）：9B 0.1.0 submission `747cac69-b127-4efe-b5cc-30fda6216899` published，Registry 138；权重 distribution published / Index 68 签名回读通过。正式 Package 37,886 bytes，SHA-256 `2ce8e4cdde2a0d15053c4e80d749144627d7b2d3429309cc7a490243c465b6b0`，匿名完整下载一致。41 tests passed，精确签名包独立 managed install + Runtime 1.6.2 Worker running。用户本轮明确延后真实媒体处理，不声称新出图验收。发布回执 `docs/ai2apps-flux2-klein-9b-0.1.0-release.md`。Package 发布任务完成；客户端有界安装映射仍需随未来 Desktop 候选验收，故本 ledger item 保持 in_progress。4B 未变。

2026-09-15（继续）：当前 Dev Cookie 发布查询成功，原 Publisher key 非秘密元数据指纹与 Cloud 匹配。补齐 conditional redistribution 的结构化许可/下载确认字段；标准构建器完成签名分发：21 files、34,722,772,164 bytes、4140 pieces，digest `sha256:6e9cfa02ae3a5f710f61479e2476e1653da1552ef957abe2ed076ce8393ac08d`。验证模式为 HF 完整本地字节对 MS 固定元数据，不声称双端完整下载。3 项 Package 测试通过。正在标准提交/审核，尚未声称 Package 发布完成；snapshot 移至 `/private/tmp/92196c8e11f7b6cf2b7493e037d8c5345c559216`。

2026-09-15：完整 HF snapshot 已下载，逐文件 SHA-256 与固定 MS revision 的 21 个文件全部匹配，共 34,722,772,164 字节（不是仅 LFS 元数据对比）。新增 9B 0.1.0 有界安装映射，保留 4B；新增独立身份、adapter 拒绝 4B、许可哈希/双源固定版本三项测试，3 passed（退出时沙箱 Metal 探测警告，不声称真实推理）。Installation 发布查询返回 active user session required；已打开固定 Dev App 的 Account→Security 管理员验证页面等待用户操作。尚未签名/发布，仍需原签名上下文、标准 distribution 构建/发布、managed smoke 和 Package 发布。

最新进展：用户接受上游许可后，官方 Hub 固定 revision 配置下载成功，GatedRepoError 阻塞解除。完整权重下载进行中，路径 `/private/tmp/ai2apps-flux2-klein-9b-source`。ModelScope 固定 revision `429fffab3014811a56c21359f408a155e0bda9e1`，标准分发模块确认 21 个必需文件均有最终 SHA-256，总计 34,722,772,164 字节。已补许可证全文及哈希、NOTICE、SBOM、source lock、pyproject 和分发构建规格；仍未签名或发布，未把元数据检查当作完整字节验证。最终构建时须使用以 HF revision 命名的 snapshot 目录。

2026-09-14：用户要求将 9B 作为独立于 4B 的模型发布，并保留现有 ACPF/Discover 许可展示确认。新增 `packages/ai2apps-model-flux2-klein-9b-mlx` 候选 0.1.0，Package/Service/model ID 独立；复用现有推理模块，adapter 仅接受 9B。4B 未修改。模型权重使用 FLUX Non-Commercial License，不能继承适配器代码的 Apache-2.0。ID/上游身份/JSON/YAML 和四个 Python 模块语法检查通过，未声称推理通过。

固定上游 revision `92196c8e11f7b6cf2b7493e037d8c5345c559216`；官方 Hub 客户端下载配置返回 `GatedRepoError`，当前账号访问不足。没有读取/输出 Cookie、没有签名或发布，没有填写占位 distribution ID。待获得上游权重访问后完成固定双源字节核验、完整许可证/SBOM/source lock、签名分发、客户端安装映射、真实 managed install 和 Package 发布。候选 README 明确标注不可发布状态。

当前生产基线：AI2Apps `0.1.0` Build `2249`

生产清单：`https://coder.ai2apps.com/updates/stable.json`

基线回执：`docs/ai2apps-desktop-build-2249-release-receipt-2026-09-03.md`

候选 Build：尚未分配；构建时必须严格大于 `2249`

## 1. 用途

本文件只记录“当前生产 Release 之后，已经完成或正在进行、需要评估是否进入下一版
Desktop App 的工作”。它不是长期 Roadmap，也不代替 Git、测试报告或最终 Build 回执。

AI2Apps 经常从混合工作区构建，`git diff` 无法可靠回答某项工作是否已经进入上一版。
因此每项可能改变 Desktop 用户收到的 App、内嵌 Local、Helper、Shell、AceFox、更新器、
Runtime profile、安装行为或发布流程的工作，都必须在完成该项工作的同一轮登记到这里。

登记是默认自动动作，不需要用户另行说“加入台账”。执行开发工作的 Agent 必须在结束当轮
工作前创建或更新相应条目；即使功能尚未完成或被外部条件阻塞，也应分别以
`in_progress` 或 `blocked` 记录。只有未产生任何可发行改动的纯调查、讨论和诊断可以不登记。

## 2. 状态定义

| 状态 | 含义 |
| --- | --- |
| `in_progress` | 实现或验证尚未完成，不能进入 Release |
| `blocked` | 实现已基本完成，但存在明确的外部依赖或验收阻塞 |
| `ready` | 代码、测试、迁移和发布说明齐全，可以进入候选构建 |
| `deferred` | 已明确决定不进入下一版，必须写明原因和目标版本 |
| `included` | 已进入某个完成验收的 Build，并已复制到该 Build 回执 |

`included` 只能在最终公证 DMG、Cloud 发布和目标 Mac 端到端升级完成后填写，不能因为
源码合并、App 构建成功或上传完成就提前标记。

## 3. 下一版候选工作

### NXR-SHARED-CHECKPOINT-CACHE：同机实例共享已验证 Checkpoint（ready）

- 2026-09-18：按用户要求将 Registry Checkpoint 的权重数据迁移为同一存储容器内的
  机器级内容寻址缓存；Dev、App-Dev、Test 和生产实例仍保留独立账号、Package 状态、
  HF Home、可写模型准备目录及 Worker 视图，但由 Supervisor 注入同一个
  `AI2APPS_CHECKPOINT_CACHE_ROOT`。下载按 distribution identity 使用跨进程非阻塞文件锁，
  获锁后重新检查完整只读 snapshot；并发安装相同 checkpoint 时只允许一个实例访问
  HF/ModelScope，其他实例直接命中共享结果。已有实例私有 `checkpoint-cache-v1` 作为一次性
  验证导入源，可无网络迁移到共享池。
- 实例“重置数据”继续删除该实例的 Support/Cache 根和 Worker 视图，但共享 Checkpoint 根位于
  `Library/Caches/AI2Apps/shared/checkpoint-cache-v1`，由路径边界显式保护；App-Dev/Test 重置
  对话框同步说明共享 Checkpoint 保留。升级前的实例私有缓存会在重置前原子移动到共享保留区；
  未重置的各实例旧缓存和保留区均作为全机验证导入源，另一实例已有同一 distribution 时不走网络。
- 2026-09-18 验收：Python Checkpoint/Provisioning/Shell 定向回归 200 项通过，Ruff 通过；Swift
  Contracts/Supervisor/Helper 全套 77 项通过。新增真实独立 Python 进程 `flock` 排他测试，并以
  两个 Acquisition Service 并发验证网络请求量等于单实例基线、结果为一次下载加一次 cache hit。
  固定 `AI2Apps-dev.app`、`AI2Apps-app-dev.app`、`AI2Apps-test.app` 均由规定脚本重建并通过签名/
  Release App 校验；Dev 与 App-Dev 已以新 Helper 和新 Local 重启。共享根已建立；存量缓存的
  后续整理与删除结果见下一条。
- 2026-09-18 本机存量整理完成：17 份实例 manifest 合并为 11 个唯一 distribution，
  242,531,923,853 逻辑字节全部完成共享端 size/SHA-256 复验；共享池最终有 11 个 manifest、
  11 个 snapshot，`du` 约 203GiB。复验 0 错误后删除 app-dev/dev/test/main 与三个历史
  dev-acpf 实例的 7 个私有 `checkpoint-cache-v1` 根，最终扫描无残留。迁移工具的成功删除与
  失败全保留测试 2 项通过，Ruff 通过；删除后 Punctuation distribution 强制断网 acquisition
  返回 `cache_hit=true`、`source_bytes={}`。完整回执见
  `docs/ai2apps-shared-checkpoint-consolidation-2026-09-18.md`。

### NXR-CHAT-SSD-CHECKPOINTS-20260914：对话模型自有 checkpoint 与 Runtime（in_progress）

- 2026-09-18（App-Dev 首次安装修正）：ACPF 使用正式 Package model ID 请求 Checkpoint，
  而 Cache-MoE Host 配方曾错误地以内部 `install_id` 作为主键，导致 DS4.1 安装在 55% 处报
  `unsupported AI2Apps model`。Host 现以正式 model ID 绑定分发清单，内部 `install_id` 仅用于
  Scope Pack 兼容校验，并保留 `service_key` 供完成后重启 Worker。SSD-ready 路径同时延后旧式
  expert-store 转换模块导入；签名 SSD Checkpoint 的下载和激活不再要求 Cloud 控制面的 Python
  环境安装 `mlx_lm`。89 项模型配方、Checkpoint 激活和 Provisioning 回归通过，Ruff 定向检查
  通过；新增 DS4.1 无 MLX Host 导入回归。App-Dev Local 已重启并实机重试，界面从两次失败
  进入 `Downloading model checkpoint`，HF 固定 revision 已实际返回 206，当前下载写入机器级
  共享 Checkpoint 缓存；总量约 475.27 GB，本机可用空间约 1.5 TiB。

- 2026-09-17（ModelScope严格Range客户端完成）：Cloud OpenAPI 1.50.0发布后，Local/Desktop
  Package与Checkpoint下载器共用严格单区间验证；仅可信ModelScope固定revision接受
  `200 + Content-Range`，精确校验offset/total/length/identity/body，普通200整文件拒绝且有界
  中止，piece/full SHA门不变。75项定向回归及Ruff/compile通过；真实Runtime 1.7.0 MS单源从
  piece 2恢复，45 pieces、373,748,488字节和完整SHA
  `b066700dcebec87012e93de01e6114db9f231b0a1c89642e97c50cd91a1ec3a7`通过；DS4.1 MS
  `experts/layer-0.bin`真实probe与4KiB字节对照通过。Installer扩展回归22通过、2个旧Qwen源断言
  失败，与本改动无关。该代码属于Desktop/Local控制面，已发布Runtime 1.7.0无需重建。MS正式
  Source已登记，Cloud v1.50.0完整验证通过；48次严格
  `http-200-content-range`、完整摘要和45-piece清单均匹配。Dev/App-Dev已加载当前源码，固定
  Test App已重建并通过包内源码等值、嵌入式导入与deep/strict签名验证。Cloud 随后部署策略
  修正；同一管理员step-up激活成功，Source revision 8、Repository metadata 154，匿名固定公钥
  验签确认Cloud/GitHub/ModelScope三源已公开。报告：
  `docs/modelscope-range-client-compatibility-2026-09-17.md`。
  - 后续审计确认该拒绝不是既有 Package 合同：普通 Package/Source 一直允许已完成 step-up 的
    系统管理员自审并写专用审计事件。Cloud 1.50.0 新增的
    `assertCompatibleSourceApprover` 仅对非 standard Range receipt 强制不同账号，来源是本项目
    需求文档误写的双人审批要求。已发布更正需求，要求恢复既有管理员 step-up 语义且保持全部
    Range/piece/完整SHA门禁：
    `docs/ai2apps-cloud-modelscope-range-activation-policy-correction-v1.md`。
  - Cloud生产镜像`ai2apps-cloud:range-policy-20260918`部署后，使用原Source、passed
    validation、digest、ETag和幂等键重试激活成功；Snapshot digest
    `49d0748f75606adf61397106ebcf197316a5d2c1530d9d41a0ac0d7fede515c2`。

- 2026-09-17（七模型发布及兼容性修正完成）：七套 SSD distribution、Runtime 1.7.0 与
  七个模型 Package 已按依赖顺序 published；最终 Repository metadata v153。
  匿名验收确认 DS4 4bit/2bit、Qwen3.6、DS4.1 的公开归档、Repository/Publisher 签名、
  SHA-256、大小、本地字节和 envelope 全部一致。GLM/Qwen Next/Ornith 0.1.1 被发现将
  AI2Apps Contract 最低版本误升到0.1.1，当前0.1.0客户端会拒绝安装；已修正为兼容
  `>=0.1.0 <2.0.0` 并使用原Publisher发布0.1.2。三份修正版均无权重/原生载荷，44项
  专项/Contract/Discover检查通过；全新匿名客户端逐个验证双签名、SHA/大小、本地归档
  字节和envelope一致。0.1.1保留为不可变历史但不可作为可安装交付，0.1.2均为最新版本。
  回执：`docs/ai2apps-chat-ssd-model-packages-release-2026-09-17.md`。

- 2026-09-17/18（Runtime 1.7.0 ModelScope 严格兼容与三源发布完成）：
  `ai2apps/runtime-omlx 1.7.0` submission
  `5553a51b-7cf2-48be-8d66-7e5466be7293` 已发布，Repository metadata 142；GitHub
  同字节制品经 Cloud 全量 SHA-256、Range 和 45-piece 验证后激活，Snapshot 143。
  ModelScope 同字节制品位于不可变 revision
  `18751703b53671cb2db926f9f8ed508a70df15b0`。Local/Desktop 已加入受限的严格
  `200 + Content-Range` 支持，Cloud OpenAPI 1.50.0 已部署对应
  `package-single-range-v2` 门禁。Source
  `src_3125a4d0-27d8-4cfc-a9f2-43b0ec8ad3a2` 经 validation
  `val_9f67323e-596d-46ef-92bb-13ca61e2b53b` 完成全量 SHA-256、大小和 45-piece 校验；
  receipt 记录 48 次 `http-200-content-range`。策略修正后 Source 已 active、revision 8；签名
  Repository Snapshot 154 已匿名确认公开 Cloud/GitHub/ModelScope 三源。发布脚本已增加现有
  Source 恢复验证动作，5 tests passed。Dev/App-Dev/Test 开发客户端均具备兼容能力，无需
  Desktop Release。

- 2026-09-17（Runtime 1.7.0 本地候选完成，外部发布待授权）：七套 SSD checkpoint 已在
  HF Avdpro / MS ai2apps 完成全文件双源验收。Runtime 已增加统一 schema/摘要/范围校验、
  无重复专家库直接激活、正式 DS4.1 文本/视觉 engine，并适配 Qwen Next Full/Cached、
  GLM、DS4 4bit/2bit、Qwen3.6 与 Ornith；八条真实 checkpoint smoke 通过。DS4.1 文本
  和视觉完整 logits SHA-256 与冻结参考一致。Runtime Package 元数据升至 1.7.0；Developer
  ID 签名 DMG 已通过 Apple submission `19de5929-dbb1-486f-a471-8b3038ec8b8b`，stapled
  SHA-256 为 `cf9a645e84c46711392b53d18855f86201fd32cca280dbd1f0c2d66b69748a32`。
  外层正式 Package 已签名并在全新临时实例安装通过，SHA-256 为
  `b066700dcebec87012e93de01e6114db9f231b0a1c89642e97c50cd91a1ec3a7`。Installation
  Cloud session 当前无 active user session；等待 1.7.0 精确 Cookie 读取授权后提交 Registry，
  再继续模型 Package。详见 `docs/ai2apps-mlx-runtime-1.7.0-ssd-checkpoint-signed-build.md` 和
  `artifacts/runtime-1.7.0/build-receipt.json`。

- L2持续训练目标已启动（in_progress）：以全40层真实miss为分母，主要48/次级64个专家总预取预算，目标新会话独立验收≥70%覆盖；先执行缺失加权、缓存/前轮路由输入、rank128/256/512验证集消融，已有测试集不参与调参。尚未达标或集成发布。计划 `docs/dsv41f-l2-continuous-training-plan-2026-09-16.md`。
  - 第一轮最高48预算31.74%；新增rank512无缓存对照32.15%，目标未达成。v3上一token逐层FFN状态pilot精确通过，90序列/16512行补采与分阶段训练运行中，另排队40条/5120行训练扩充。24条新主题会话仅预留，未用于选择。状态预测头可继承已有全局头，数值迁移差9.54e-7；实验尚无真实异步L2或TPS验收。
  - 后续rank1024无缓存验证集48/64预算覆盖33.26%/38.27%；状态小样本微调未超过同会话迁移基线，已将epoch0纳入模型选择以避免负收益。大批采集/训练继续运行，70%目标保持未完成。
  - 滚动提前1层复用官方Router并训练修正，同cohort顺序cap64覆盖51.64%，因果储备策略53.48%，尚无deadline/TPS验收。pre-attention单会话探针均值修正65.95%，仅128行且异步通知机制未验证；正在扩充40会话。大模型采集顺序调度，未同时加载双模型，未修改活动Runtime/Package。目标未达成。
  - 扩大pre-attention验证至1024行后cap64覆盖64.90%；仿射与分数校准未超过各自均值基线。已排队previous-attention因果特征pilot，含精确forward核验；仍为实验脚本/冻结采集快照，未改活动Runtime或Package，独立最终验收未开展。
  - 因果置信度与未来预算储备在2048行验证将cap64离线覆盖提高到71.50%（误读388.93MB/token），cap48为62.05%。仅验证集、同层attention前预测，SSD deadline/异步通知及独立验收均未证明，不标记目标完成，不改生产默认。
  - 完整40会话复核cap64离线覆盖71.35%、误读389.97MB/token。新增隔离Metal完成回调mailbox原型，65packet正确、通知早于synthetic GPU tail结束；尚未实测模型通知开销与SSD READY，不接入活动Runtime。
  - v5 previous-attention两会话精确核验完成，单会话Top6离线68.27%，扩展40会话已排队。真实模型异步通知窗口与输出一致性A/B正在隔离实验中执行；主推理、Runtime和Package均未切换。
  - 真实模型640对异步通知核验通过全部logits/缓存/SSD字节一致，稳态TPS差约0.5%；预测到真实route送达中位仅0.619ms，尚未证明SSD及时完成。提前1层预算策略覆盖提升到57.06%，仍未达目标；v5扩充采集已启动。
  - 提前一层逐特征ridge/逐层低秩模型完成小cohort对照，未超过共享模型57.06%；已启动54序列相同cohort共享/逐层模型训练与预算评估。仅实验训练代码，生产默认不变。
  - 扩大54序列训练完成，共享/逐层提前一层模型均约55.1%（验证cohort已扩大）；新增当前路由条件分支热启动精确，单独训练未超过基线，保留epoch0。v5完成后自动做预算评估，独立holdout仍未打开。
  - 有界跨token L2回放完成，256槽仅保留未消费预测时乐观覆盖60.55%；448槽诊断最高63.66%、有效载荷8.42GB、SSD总读取增加约30%。无deadline/实际footprint证明，未接入默认推理，70%目标仍未达到。
  - 新排序训练未超过基线；训练/验证覆盖67.81%/55.06%，已排队完整补采扩充后的预测器训练，最终holdout仍未使用。小批SSD延迟诊断排在v5采集后，所有改变保持实验隔离。
  - v5完整评估与训练层混合将同层离线覆盖提高到72.83%，但SSD小批实测单专家约1.42ms，超过0.62ms通知窗口，及时READY目标仍未证明；不作为默认方案。原v3采集已恢复，继续更早预测训练。
  - 驻留专家近似预测+精确重算的隔离探针通过logits/缓存/SSD字节一致。短块2/4在单16-token提示离线覆盖79.0%/74.2%，但未接预取且TPS降至3.88/4.13，不能部署或视为达标。原采集已恢复。
  - 真实短块预取已接原native SSD读取与备用槽零拷贝交换，16步精确logits/路由/逻辑缓存一致、峰值60.9GB。普通/严格F_NOCACHE Block4及时覆盖69.15%/68.36%，严格短测约5.65TPS。尚有40/token额外异步通知、未独立验收、未达70%，保持实验隔离。 下一轮显式实验开关对齐预测专家累加顺序并比较短块尾部策略；仅排队，未改默认Runtime。 后续20会话×128token真实预取成对验证已排队，严格65GB/精确输出检查，最终holdout保留。 增加隔离packed回读实验以替代额外通知；尚待模型验证，不作为默认。

- L2 rank128首次训练/独立测试完成（实验未发布）：3292288参数，10轮按验证loss选第9轮；测试集后35层总预算32/48个预取，分别覆盖10.68/13.47个真实miss/token，精度33.36%/28.05%，优于简单基线但误读量仍大。单头FP32隔离预测中位数0.228ms，不代表真实L2延迟/TPS；未接入Runtime。报告 `docs/dsv41f-l2-r128-training-2026-09-16.md`。

- L2 v2采集完成复核：116序列/20992有效行（训练12032、验证4480、测试4480），全量文件哈希与checkpoint一致，family与完全相同输入均无跨split重叠，峰值58.682GB。首版训练数据就绪，尚未训练或集成发布；真实多轮与模板分布限制仍保留。回执 `artifacts/dsv41-l2-v2-20260916/collection-audit.json`。

- 2026-09-16（in_progress，实验未发布）：启动预测 L2 v2 采样；独立冻结 legacy 无损前向，采全40层分数/Top6、上一轮归一化 hidden、当前 token embedding 及 L0/L1 驻留状态，在 token 完成边界导出。首批116序列，最多20992行，family隔离；短/长输入256行 pilot 的 token/logits/SSD字节/晋升/fence对照通过，峰值57.443GB，批量采集已启动。尚未训练或接入 Runtime，正常缓存7 TPS回归仍待执行。详见 `docs/dsv41f-l2-collection-v2-2026-09-16.md`。

- 2026-09-16（进度澄清，正常缓存回归待执行）：全 miss 的无损 Top6 3.190/3.214 TPS 使用32输入/32 Decode并逐层强制缓存失效；历史7.045/7.168 TPS使用2048输入/128 Decode、正常缓存，且在最新 window 准入修改之前测得。两者不可直接比较；最新代码的历史正常缓存 legacy/auto 配对回归尚未完成，不将全 miss 验收扩大为正常负载无退化结论。下一步固定历史 prompt、L0=8/L1=40、eviction_dual、Prefill64 验证正确性和完整 TPS。进度及边界已记录至 `docs/dsv41f-allmiss-cost-floor-2026-09-16.md`；本次仅文档更新，未发布。

- 2026-09-16（completed，实验未发布）：window 准入与首次miss退出已验证；32步全miss：Top2旧4.419–4.549、新4.701–4.782 TPS，Top4旧3.834/新4.013，自然Top6旧3.190/新3.214；全部logits/SSD/fence一致，新版1280次miss、零跨层构图，峰值约55.2GB。已入窗再突变全miss的总吞吐4.580，首窗口仍有一次推测成本，不能宣称逐token严格零额外成本。`DSV41_WINDOW_FORCE=1`保留固定窗口诊断。详见 `docs/dsv41f-allmiss-cost-floor-2026-09-16.md`。默认packet未改，未发布。

- 2026-09-16（completed，实验未发布）：零miss隔离测试确认连续路径缺少充分流水提交：同token逐层94.73ms、整40层84.83ms、逐层异步75.05ms，等效吞吐+26.2%；guarded40仍159.51ms。已加入可选 `DSV41_ASYNC_WINDOW=1`，真实Top2/window4/2048+128配对合并8.062→8.793 TPS（+9.1%），logits/SSD/晋升/fence全一致，Top2/4逐步状态通过，峰值约57.3GB。诊断数不等同端到端L2 TPS，默认packet未变。详见 `docs/dsv41f-allhit-pipeline-isolation-2026-09-16.md`。同时纠正统计说明：runner每token结算计数，仍在Decode计时内。

- 2026-09-16（completed，实验未发布）：Burst 跨层优化完成：按层保存/提交状态、Gate 发布停止屏障、首次 Gate 前原生调度、miss 后重组，以及可选 `--inference-mode window` 原生推测窗口。2048/128 正式 Top2 ABBA 合并 8.805→9.307 TPS（约+5.7%，旧版波动较大）；Top4 window2 8.077→7.568，无收益。全部 logits/SSD/晋升/fence 一致，15组逐步状态对照通过，峰值约57.3 GB。guarded 真正 GPU 停止仍慢，auto 保持 packet。新增 ABI 防止后端/bridge 混用；详见 `docs/dsv41f-burst-window-optimization-2026-09-16.md`。未变更 Runtime/Package 发布默认。

- 2026-09-16：历史 2048/128 锚点复核完成：无损 legacy/auto 为 7.045/7.168 TPS；历史 baseline/Prefill0 Top2 参数下为 8.912/8.884 TPS，logits/SSD/晋升/fence 同配置全一致。历史完整 10.107 尚未复现，约八成以上额外时间位于前16步；不能以尾段10.3代替完整值。自动 guarded 未证明净收益，已撤掉自动触发，auto 保持原生 packet，显式 guarded 与恢复诊断保留。详见 `docs/dsv41f-tps-anchor-recheck-2026-09-16.md`。未发布。
- 2026-09-16：新 packet 兼容性扩展验收完成：图像/历史消息、trace/route capture、Static/其它 L1 策略及形状、Burst 尾部/Prefill、实验 dispatch 默认选择新 packet，不再自动回退 legacy；原数学前向及维护逻辑保留。11 组/22 次运行、105 份 logits、605 份诊断张量及路由一致，SSD/晋升/fence 一致，峰值≤58.21 GB。跨层 guarded 仍有独立范围限制，未发布 Runtime/Package。报告：`docs/dsv41f-packet-compatibility-2026-09-16.md`。
- 2026-09-16：DS4.1F 独立纯文本入口默认切换到新 auto executor；旧路径保留 --inference-mode legacy，未验收的图像/诊断/实验参数组合明确回退旧路径，manifest 记录选择。入口切换验收通过：默认 auto 与显式 legacy 在默认 Prefill 配置下 8 步 Decode/9 份 logits 逐字节一致，SSD/缓存/晋升/fence 一致；4 项 CPU 入口选择与参数转发测试通过。正式 Runtime/Worker 尚未集成，未发布。
- 2026-09-16：miss/resume 退化路径优化验收完成：auto 在频繁 miss 时使用单次 packet＋原生 dispatch，首次跨层 miss 后当前 token 立即转入原生 tail。正常两轮均值 3.969→4.032 TPS；每层真实 miss 两轮 2.196→2.248 TPS，SSD 请求与 bank fence 一致，无新增同步。1,580 个状态张量切换对照一致，Natural/Burst Top2/4 logits 对照通过。实验入口默认 auto/block4，产品 Runtime 默认不变，未发布。报告：`docs/dsv41f-miss-resume-native-packet-2026-09-16.md`。
- 2026-09-16：DS4.1F GPU miss/resume 隔离实验完成：真实 Metal ICB 跳过与实际 miss 层恢复，支持无损及 Burst Top2/4。8 组共 520 份 logits 与原引擎逐字节一致，SSD 请求量/晋升/fence 保持一致，40 层边界通过。但 Decode 明显负收益（无损 4.002→2.803 TPS，最佳新窗口），默认仍为旧路径；不纳入 Runtime 发布，独立后端仅供后续研究。报告：`docs/dsv41f-gpu-miss-resume-implementation-2026-09-16.md`。 补充消融：旧流程仅开启受保护后端即降至 2.758 TPS（65 份 logits 一致），已定位整套执行包装具有主要退化，尚待分项优化。

- 2026-09-15：用户确认实验引擎默认采用每层Main40/Hot8＋eviction_dual零复制晋升，已更新run.py和AdaptiveModel默认及README；旧策略可用`--l1-policy baseline`显式选择，固定层扩容仍关闭。L0容量8/12/16共8次测试logits一致、峰值≤63.352GB，长Decode TPS基本持平，故保留Hot8。Prefill64仍需显式参数。此项为后续Runtime集成候选，未发布Runtime/Package；不显式指定策略/槽数的默认入口3步Decode验证通过：Main40/Hot8、eviction_dual零复制，4份logits与已验证参考精确一致；证据`artifacts/dsv41-default-l1-20260915/verification.json`。

- 2026-09-15：完整新旧L1主对照完成（本轮未改Runtime）：旧baseline16步＋Hot复用 vs 新双频次＋淘汰晋升＋零复制，Main40/Hot8固定，2例×AB/BA共8个新进程，全部logits一致，旧基线身份校验通过。128步4.664→4.716 TPS（+1.12%）、2083输入/512步4.787→4.844（+1.18%），四个配对方向均正但样本小，不宣称普遍/显著加速；读回和栅栏均下降，峰值≤57.354GB。该结果是整套策略净收益，不能用此前零复制局部对照4.03%/2.43%替代。详见 `docs/dsv41f-l1-end-to-end-comparison-2026-09-15.md`；默认和发布状态不变。

- 2026-09-15：DS4.1F 零复制槽位晋升已实现：L0/L1 改为逻辑角色，GPU 按物理槽索引读取；miss 覆盖旧 L1 槽，晋升原地保留权重，无 memcpy/GPU copy。修正 Natural/Burst 命中分类，复用现有读回及单一栅栏。8次128/512步配对 logits、逻辑晋升/命中/读取/同步计数一致；复制23.802/97.989GB→0，TPS4.510→4.692、4.888→5.007（+4.03%/+2.43%），峰值≤57.336GB。eviction_dual内部默认启用，--promotion-copy保留同策略对照，总体baseline默认未改。Burst Top2/Block1、Top4/Block4各32步copy/swap配对的logits、缓存、读取、同步及回滚统计全部一致；随机160次bank操作及旧native/LRU安全回归通过。详见 `docs/dsv41f-zero-copy-promotion-2026-09-15.md`。未发布。

- 2026-09-15：DS4.1F eviction_dual 已实现：仅 L0 淘汰时筛选；Natural/Burst 复用 miss 元数据读回和单一写入栅栏，零维护专用 GPU→CPU 边界。8次短/长配对 logits 完全一致，逐对读回/栅栏总次数均不增加；长读回55152→36967、栅栏17938→16567，少请求56.045GB，TPS4.859→4.823（无加速结论）。峰值≤57.351GB；仅opt-in，baseline默认不变。Burst Top2/Block1、Top4/Block4各32步回归通过；6项bank/native安全测试及2项策略回放/精度范围测试通过。详见 `docs/dsv41f-l1-eviction-promotion-2026-09-15.md`。未发布。

- 2026-09-15：L1 双频次及保护区/试用区策略已接入实验引擎 Natural/Burst，复用 Hot→Main 内存复制；保留 baseline 默认。独立回放晋升决策校验通过；12次128/512步配对所有 logits/输出一致，峰值≤57.343GB。长 Decode TPS：baseline 5.000、双频次4.858、试用区4.907；少读32.958/44.990GB，但未加速，新策略仅 opt-in。Burst双频次Top2/Block1及试用区Top4/Block4各32步通过，提交路由计数准确、晋升复用正常。详见 `docs/dsv41f-l1-runtime-policies-2026-09-15.md`。尚未发布 Runtime。

- 2026-09-15：DS4.1F Hot→Main晋升复用完成并默认启用，Natural/Burst共用；原生统一内存memcpy，缺失专家仍走原preadv，保留lazy consumer与GPU同步栅栏。4项复制/旧native测试＋原LRU测试通过；128步逐层诊断460次Hot晋升零SSD读取；自然路径8次128/512配对及Burst Top2/Block1、Top4/Block4回归均输出一致。128/512步分别少读9.006/34.706GB，峰值≤57.339GB；小样本TPS−0.30%/−2.23%，不宣称加速。旧native缺复制入口明确拒绝、不回退SSD；`--promotion-reread`仅诊断对照。详见`docs/dsv41f-hot-promotion-reuse-2026-09-15.md`。仅实验引擎与其native扩展，未发布Runtime。

- 2026-09-15：DS4.1F只增不减L1实验完成：40槽底座，8个训练边际收益较高层增至48，总1664槽；独立growth-v1 schema保留旧1600槽校验。5项CPU测试、5用例20次AB/BA通过，4116份logits摘要与本轮/上轮基线一致。Decode4.726→4.722TPS（−0.10%），命中70.904→71.464%，峰值57.337→58.553GB；native读取仅−0.65%，整体无明显收益，保持Main40默认，仅opt-in。详见`docs/dsv41f-l1-growth-results-2026-09-15.md`，未纳入Runtime发布。

- 2026-09-15：DS4.1F逐层L1形状研究完成：300条采样、60次真实容量校准、4096/512完整logits与持续会话检查通过；checkpoint绑定的opt-in向量、采集/因果回放已实现。用户将性能验收从240次缩减为5例×4次，全部输出一致，Decode4.471→4.434 TPS（−0.82%，重复运行有明显波动），性能组峰值57.352GB；验证回放读取仅−0.399%。保留Main40默认，不自动纳入发布，不宣称通过完整统计门槛。详见`docs/dsv41f-l1-shape-results-2026-09-15.md`；研究完成，正式Runtime集成仍未验收。

- 2026-09-15：新增默认未接入的direct-index Metal attention微基准原型，验证能否省掉KV gather；并开始逐层cache miss/I/O归因。微基准直接索引原型慢1.5–2.3倍，未接入Model。Main40/48容量A/B：128步各两轮129 logits一致；512步一对513 logits一致，Decode8.25→8.79 TPS、末128步8.71→9.29、命中88.83→92.50%，footprint57.28→63.22GB，仍保留Main40通用默认。详见`docs/dsv41f-indexed-attention-cache-ab-2026-09-15.md`。仅实验，不属于已启用Runtime优化。

- DS4.1F attention/indexer专项开始：抽取index评分/TopK、稀疏KV gather/SDPA边界用于Prefill与Decode分项诊断，默认运算不变；分组64/128/256六次2048/128完整模型A/B全部logits、tokens、cache计数一致，256分组Prefill仅+1.3%、Decode不变，保留64默认；非整除query合成边界最大差4.8e-7，7/8项逐位一致、全部有限。新增双阶段profile定位Indexer约0.063秒而稀疏attention约3.62秒（同步诊断非吞吐）。详见`docs/dsv41f-attention-profile-ab-2026-09-14.md`，未发布。

- DS4.1F Decode调度实验：新增legacy/shared/unsorted三路径，共享gate/up输入量化与三投影索引计划；暂保留legacy默认，待2048/128完整logits和吞吐A/B选择。仅实验代码，未发布Runtime。

- DS4.1F性能入口：逐层eval/日志改为默认关闭，新增`--layer-progress`诊断开关，`--trace`仍保留逐层求值；Router/专家覆写安全等待与每步预算检查不变。当前仅实验runner，2048/128按on/off/off/on四次A/B通过：全部129份logits、tokens、cache/promotion记录一致，Decode平均6.96→7.20 TPS（+3.43%），Prefill+1.88%，footprint峰值57.292GB；详见`docs/dsv41f-layer-progress-switch-2026-09-14.md`。尚未视为Runtime发布验收。

- 最新：GLM SSD候选114,160张量全字节验证完成，99文件/181.75GB；HF Avdpro与MS ai2apps双源上传已同时启动。Runtime新布局验收、固定远端版本和签名distribution仍待完成；没有删除GLM原始checkpoint或旧专家库。以下构建中/上传中条目为历史进度。

- 首批Qwen/DS4.1F双源文件集合、大小、SHA256已全部匹配（73/172文件），LFS属性差异已统一，HF/MS均固定不可变commit。分发spec已准备但尚未签名/发布；具体commit及摘要见迁移文档和dual-source-verification收据。

- DS4.1F 当前 MLX/CPU参考/分析入口已迁移至 SSD checkpoint；CPU Store 支持外置专家，重新导出工具禁止覆盖输入专家目录。使用 macOS sandbox 禁止访问原 checkpoint/旧expert-store进行文本、图像及多轮回放精度回归；9场景/28个完整logits输出全部逐位一致，CPU参考24张量SHA256一致，峰值58.22GB；结果写入 `artifacts/dsv41-ssd-only-regression-20260914`，详见 `docs/dsv41f-ssd-only-engine-validation-2026-09-14.md`。原生扩展仍需保留，正式 Runtime/Package 集成未完成。

- 用户接受沿用既有账号 HF Avdpro / MS ai2apps；四个首批仓库已创建，DS4.1F/Qwen Next 双源上传进行中，尚未完成远端摘要验收或发布。Qwen 模型卡已修正并在 MS 页面确认 Qwen Community License 1.0。

- 首批 DS4.1F/Qwen Next SSD-ready 候选已生成并完成全 tensor payload 校验；DS4.1F 文本/图像各4步完整 logits 与原布局逐位一致，相关8项测试通过。新增 external tensor 读取模块及实验加载适配；Qwen Full/Cached 外置张量加载钩子已接入，10项导出及加载测试通过，Qwen 原/新布局 × Full/Cached 已通过33+4 tokens短推理输出对照，使用既有 Runtime CPython3.11与极速SSD扩展；managed Worker、安装准备与多轮验收仍待完成。GLM fused-v2 专家存储已构建，SSD导出正在逐tensor验证；第45层MTP保留在backbone，两个导出测试通过。其余模型仍未验收。

- 用户授权升级 Runtime 和全部对话模型 Package，采用自有 checkpoint；MoE 使用无重复原专家的 SSD-ready 布局，非 MoE 保持原精度镜像。Qwen Next 必须继续支持 Full/Cached。
- 执行顺序：checkpoint 构建与字节/推理校验 → MS/HF 固定 revision 与签名 distribution → 新版 Runtime → 模型 Package；不得提前填写虚构 distribution ID。
- 已开始构建工具与迁移清单及断点续传工作；尚未升级现有 Package 版本或发布 Runtime。现有发布与安装数据不删除。
- DS4.1F 需正式 engine/Worker/视觉集成，现有 GLM/Qwen/DS4 需加载与准备层适配、原生 ABI 及真实 Package 回归。完成前不可纳入 Release。
- 依据：`docs/dsv41f-runtime-package-preparation-2026-09-13.md`；本轮进度：`docs/chat-checkpoint-migration-2026-09-14.md`。


### NXR-RELEASE-ALL-20260911：全量现有改动发布验收（in_progress）

- 用户最新收敛验收重点：本轮主要交付四个Image模型Package更新；真实音视频处理、Suite草稿恢复等后续验证延期，不作为本轮Image发布的新前置任务。保留Suite五项挂载通过证据，不将延期项标成已验证。继续保留直接影响Image安装的Desktop兼容前置（editing-only验证与四个新版本安装映射），不得因范围收敛跳过它。

- Suite 0.1.1实装挂载回归完成：Test2254 / port64004 下五个表单均正常显示，Host能力探测正常；Run `20260911T110555Z-28490` 为 SCOPED_PASS（5 passed / 0 failed / 0 blocked），测试账号已释放。关闭空白挂载故障，不等于真实媒体推理、草稿刷新恢复或完整Desktop发布通过；仍未生产发布。

- Suite 0.1.1最终候选已用原 key 标准签名，SHA `be5790b9d42191113a8a316fea2356d8dd58d34b85e37d7d68ebb4d8941439b0`，30,877字节；相关18项回归通过。Test 2254产品内验签一致，审计review/medium，Run `20260911T110555Z-28490` 等待用户在安装界面批准新版本。尚未确认安装、mount或真实推理，不算已发布。

- 用户明确授权将修复套件升级为0.1.1，沿用原 Publisher/key 做 Test 验收。已同步 Package、App、5个组件及 SBOM 版本，保留0.1.0历史制品；本次仍不是生产发布授权。

- 用户批准后的实际安装返回 `Same version already has another digest`，r2 未安装。旧0.1.0与新字节触发正常不可变版本保护；未关闭校验、删记录、重置实例或擅自改版本。Run `20260911T105258Z-27711` 五项按安装前置阻塞记录，等待明确将 Suite 测试升级范围扩展至0.1.1；没有生产发布。

- 沙箱适配续验收：相关150项回归通过（4.11秒）；Test 2254 标准构建/严格签名通过且内嵌代码摘要与源码相同。原 key 已签独立 r2 Test 候选，SHA `fe8f14e7acfac66ac9a150a4e35ff166dc7b78f9c05b5e29e9aa3cd6ec8811c1`。Run `20260911T105258Z-27711` 在真实 Discover 检查验签成功，正常审计 review/medium，停在用户安装批准；5项实际 mount 尚未执行，不标 ready，不发布生产。

- 用户已批准生产沙箱适配：新增验签资源内嵌交付、绑定当前 frame/mount 的 MessageChannel 媒体通道和 Host 隔离草稿存储，保留 opaque-origin/connect-src none。每次操作重新走现有 Broker 的 actor/mount/声明校验，不开放任意 URL；导航撤销通道。新增动态 JS 通道安全测试与资源路径/注入/体积回归；首轮相关35项及新增通道测试通过。Test 2254 标准重建中，实装验收未完成，不可据单测发布。

- 最新实装结果：用户确认安装后，Test 2253 能发现 Suite 全部5个 Mini-App，但5个实际挂载界面均空白。Run `20260911T101930Z-8823` 已结束：0 passed / 5 failed / 0 blocked，测试账号已释放。套件直接 fetch/localStorage 与生产 opaque-origin、connect-src none 沙箱不兼容；当前 Studio 消息集成只有 resize，缺少对应执行通道。初始空白的资源加载原因仍需浏览器证据确认；不得放宽 CSP 掩盖问题。需另行实施 mount-bound Host 通道、受验证资源交付和隔离草稿存储后重新签名/实装验收，尚未生产发布。详细证据见全量验收回执最新章节。

- Test-only 导入续验收：40项测试通过；最终 Test 2253 标准构建/签名校验通过，包内模块与源码 SHA 一致。实际 Discover 检查候选验签成功，正常审计返回 review/medium（Test 未配置本地 AI auditor）。Run `20260911T101930Z-8823` 已显示安装审批按钮，等待用户在产品 UI 明确批准；尚未安装、未报5项 mount 通过、未发布生产。

- 用户明确允许补齐 Test-only 候选导入入口：新增 `ai2apps/packages/test_candidates.py`、受现有 system-manage 授权保护的 API 与 Discover Test 面板。要求 Helper/test 身份及固定 Test 数据目录；从受信任 Registry snapshot 绑定 Publisher/key/namespace，原样验签后执行本地审计，按摘要明确批准安装；不写 Registry 发布/安装状态，记录 Test candidate 来源。首批 10 项隔离、验签、摘要确认与无安装副作用测试通过；Test 重建和真实 Suite 安装/5项 UI 复验仍待完成，不算已发布。

- 最新续验收：授权跨实例公开元数据查询后，在 binding-fix-v2 找到原 Suite key；标准构建器已生成独立 Test 候选，SHA-256 `96d361461b6edc8002364026b4a1474dacc0888e91ac816e2f0f96fa74a4b7c6`，29,742 字节，原公钥离线验签通过。当前 Dev Profile Cookie 经标准脚本认证成功，两个原 Publisher key 在 Cloud 均 active。没有新 submission 或生产发布。Test 本地入口仅支持旧内嵌签名格式，Contract v1 未发布候选缺少受支持的导入入口；不能伪造 Registry 已发布状态绕过。详见全量验收回执续记。

- 用户补充授权后已只读核对 dev：原 key 指纹无匹配，Package signing 元数据记录数为 0。旧 Suite 签名包有9个载荷与源码不同，不能替代当前验收。仍需定位原 key 的记录ID/namespace；未换 key、未新签名或发布，详见验收续记。

- Suite 续验收授权已收到：仅签名重建 0.1.0 并安装 Test，不读 Cookie、不发布生产。原签名 key `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc` 的公开记录不在当前 App-Dev 元数据中；读取 dev 原发布上下文元数据被权限检查拒绝，未绕过，待明确只读授权。独立的 Suite/Host/broker/workflow 33 项测试通过；未新签名或安装。详情见全量验收回执的授权续记。

- 本轮最终：合并回归 **2104 passed、6 deselected（476.44 秒）**；P0 **66 passed、0 failed、10 blocked**，测试账号已释放。5 个开发中主 App 与5 个缺少独立 Media Voice Suite 的 Mini-App 保持真实 blocked；尚待用户确认该套件 0.1.0 的 Test-only 签名安装授权。JUnit 已归档至 `.build/releases/acceptance-20260911T0816/`（完整路径见验收回执）。没有发布 Package 或正式 Desktop，没有提交/推送源码。

- 后续证据集中记录在 `docs/ai2apps-full-release-acceptance-2026-09-11.md`。扩展回归 681 passed；Package 契约 31 passed；合并回归 2103 passed，唯一失败为多步 Agent 用例 3 秒等待不足，保留全部断言的实测完成时间 3.379 秒，现仅该测试改为 10 秒上限且复验通过。最终合并重跑与 UI 队列仍在进行，尚未签发生产候选。新增测试诊断改动位于 `tests/test_ai2apps_agents.py`。

- 解锁后续验收：用户确认已解锁，CUA 精确连接 `com.ai2apps.desktop.test.shell`，登录表单可访问；标准 Harness 新 Run `20260911T081651Z-64291` 已恢复测试账号登录并执行 P0 UI 队列。旧 Run 的 blocked 结果保留，不覆盖为通过。
- 扩展 Runtime 回归发现 25 项旧契约断言失败（648 passed、6 deselected）：API-Key 网页登录/设置已经退役、统计信息不再暴露密钥、模型显示名规范更新、Shell 增加 Desktop 版本上下文、Chat 设置结构调整。测试现改为断言退役入口 410 且无 Session/设置副作用；模型与参数验证测试显式注入测试身份，不改变产品认证。涉及 `tests/test_audio_api.py`、`test_admin_api_key.py`、`test_admin_auth.py`、`test_admin_i18n_chat.py`、`test_server.py`、`test_server_main.py`。复验进行中，未据此推进生产发布。

- 用户在 Build 2250 内部候选后明确要求继续到完成发布，并选择将全部现有改动纳入本次发布验收。此授权覆盖现有源码的全量验收范围，不把未验收项自动改为 ready，也不授权绕过 Cloud 发布边界。
- 正式候选必须由提交并推送的干净源码重建；2250 保持不可变内部证据，不直接提升为生产版。测试数据、缓存和 `:memory:.ses` 不作为源码提交或产品载荷。
- 预检发现 packaged AceFox 未包含已实现的 PromptParent 品牌补丁；已用原 AceFox 工程的 `mach build faster` 与 `mach package` 刷新，包内已出现精确 Shell origin 和 useTitle 分支；未使用 Development overlay。
- 修复 Desktop builder 未携带根许可证说明的问题：App 的 `Contents/Resources/Licenses/` 现在保存 LICENSE、LICENSE-POLICY、NOTICE、TRADEMARKS 和 BSL 文本，标准 verifier 缺任一项即拒绝。没有修改许可证条款。
- 测试账号 Broker 标准 doctor 显示 configured/authorized；随后标准 Harness 尝试测试登录，未读取用户 Cookie、未重置 Test 数据。固定 Test App Build 2251 已通过标准构建与 verifier，旧 Test App 已归档。
- 全量回归 1466 passed、1 failed、4 deselected（434 秒）；失败是能力说明新增文案遗漏翻译。已补齐五组中英文 ACPF 键，相关翻译与许可证测试复验 3 passed。测试系统自身 81 passed。
- P0 Run `20260911T071647Z-57326`：46 passed、0 failed、30 blocked。UI 项被原生登录 fields-unavailable 阻塞；随后精确 Test Shell 的 CUA 检查确认 Mac 锁屏且自动解锁失败，需要用户手动解锁。不得以非交互检查代替 UI 通过。
- 本轮新增源码：`ai2apps/web/i18n/{en,zh}.json`、Desktop builder/verifier、`tests/test_desktop_release_licenses.py`。翻译修复发生在 Test 2251 打包后，最终候选仍需重建。真实 UI、推理、升级和 Cloud 发布仍未完成，四个模型 Package 尚未发布。
- 回退：保留 2250 内部制品与当前生产 2249；新候选未发布前不改变 stable。正式回退继续使用 Cloud 审计流程，不推送更低 Build。
- 验收更新：固定 Test App Build 2251 已构建并通过 verifier；全量回归 1466 passed、1 failed、4 deselected。失败为五组 ACPF 翻译键遗漏，已修复，相关翻译与许可证复验 3 passed。翻译修复晚于 Test 打包，正式候选必须重建。
- P0 Run `20260911T071647Z-57326` 为 46 passed、0 failed、30 blocked；标准测试登录 fields-unavailable，随后 CUA 精确检查 Test Shell 确认 Mac 锁屏且自动解锁失败。需要用户手动解锁，UI 不得算作通过。未重置 Test 数据，未读取用户 Cookie，四个模型 Package 与正式 Desktop 均尚未发布。

### Imagine Studio Ideogram JSON 提示词适配（2026-09-11）

- 状态：`in_progress`，未发布新 Package。
- 已撤掉公共平台的 `/ideogram-caption` 接口、聊天模型扩写模块与 Imagine Studio
  的模型专用 prompt 分支及对应临时测试。标准图片调用继续传原始 composed prompt；
  Ideogram 私有 JSON 适配应由 Package 承担，不引入公共平台聊天模型依赖。
- 使用已安装 Runtime 1.6.2、现有 Q4 缓存，1024×1024、seed=0、官方 Turbo 12
  参数实测：中文和英文最小 JSON 均为灰色拒绝画面，详细英文 JSON 成功熊猫吃竹子。
  三份输入均通过官方 CaptionVerifier，不能把格式通过等同于实际出图成功，
  也不能从上述对照认定额外 AI 扩写必需。补充对照：中英文固定模板均失败；
  完整中文 JSON 成功熊猫吃竹子；中文固定模板改用官方20步参数仍失败。
  共7次真实文生图，7份输入均通过官方格式校验。Package 更新门槛未通过，未改包或发布。
- 当前测试是直接调用 Package pipeline 的 GPU 测试，不等同于签名 Package 的沙箱安装验收。
- 源码变更：`ai2apps/api/imagine_studio.py`、`ai2apps/web/static/js/imagine_studio.js`、
  删除 `ai2apps/images/ideogram.py`，撤回 `tests/test_ai2apps_imagine_studio.py` 临时扩写测试。
- 测试证据：`ai2apps/docs/ideogram-json-probe-2026-09-11/README.md`，同目录保存
  7组 JSON、图片、报告、校验结果及测试脚本；未执行图生图或签名安装验收。
- 回归14/14通过，指定文件 diff 检查通过；经固定 app-dev Helper 重启 Local 生效，
  CUA 确认固定 Shell 在端口53496正常启动。
- 官方参考：https://github.com/ideogram-oss/ideogram4/blob/main/docs/prompting.md


### 图片模型公共 Checkpoint 布局验证（2026-09-11）

- 状态：`ready`（本次安装就绪误判修复；不代表所有模型推理验收）。
- 实机确认 Ideogram 四个嵌套权重已完成下载，但通用根 config/权重检查将其拒绝，
  Worker 配置 path=null，最终 ACPF 95% 报统一就绪超时。此前 Z-Image/FLUX 特例未覆盖它。
- 将适配器布局检查集中到 `ai2apps/checkpoints.py`，Ideogram 要求全部四份非空源权重，
  配置由 Package 提供；Qwen Image 的 mflux Runtime scheduler 与 Z-Image/FLUX 一致处理。
- 影响文件：`ai2apps/checkpoints.py`、`ai2apps/packages/supervisor.py`、
  `tests/test_checkpoint_runtime_components.py`。保留未知后端、缺分片和缺任意 Ideogram 组件的拒绝检查。
- 验证：布局、ACPF、Imagine 模型目录回归 55/55 通过。经固定 app-dev Helper 重启 Local，
  Ideogram Worker path 从 null 恢复，原失败会话经 UI Retry 达到 `ready / 100%`、error=null，
  安装弹窗自动退出，无需重下权重。Qwen 尚未实机推理；未把服务就绪等同于真实出图。
- 测试命令（仓库根）：`.venv/bin/python -m pytest tests/test_checkpoint_runtime_components.py
  tests/test_ai2apps_provisioning.py tests/test_imagine_model_catalog.py -q`。沙箱退出时有 Metal
  无设备的 atexit 提示，测试 exit=0；GPU 推理没有包含在这些回归中。


### FLUX.2 Klein ACPF 就绪判定补齐（2026-09-11）

- 状态：`in_progress`。FLUX Worker 已启动，但完整的签名分发没有 scheduler 目录，
  此前仅覆盖 Z-Image 的 Runtime 调度器判断导致 FLUX checkpoint path 为 null。
- 将豁免限定到 `flux2-klein/mflux-mlx-optimized` 精确组合；权重分片及其他组件仍需完整。
- 为两种后端参数化回归：可接受 Runtime scheduler，不接受未知后端或缺少权重。
- 用户截图已验证此前 Z-Image 本地图像编辑成功；本项单独验证 FLUX。
- 验证：两种后端回归 2/2 通过，diff 检查通过。已重启准确的 app-dev Local，
  实际 FLUX Worker 配置的 checkpoint path 从 null 恢复为现有分发目录，服务再次 ready；
  无需重新下载。ACPF UI 重试及真实 FLUX 出图尚待验收。

### Imagine Studio 配置后本地模型发现（2026-09-11）

- 状态：`ready`。
- 原因：前端读取 OpenAI `/v1/models`，却用该响应未提供的 `source_type` 等管理目录
  字段筛选，导致 ACPF 返回 ready 后本地图片模型仍不可见。
- 新增登录保护的 `/v1/platform/imagine-studio/models`，共用 ACPF 的 Package resolver，
  明确返回 checkpoint_ready、图片操作与几何能力，且不暴露 Worker 地址、凭据或本地路径。
  配置完成时直接刷新模型目录并传播请求错误，避免被无关的历史刷新覆盖。
- 文件：`ai2apps/api/imagine_studio.py`、`ai2apps/web/static/js/imagine_studio.js`、
  `tests/test_imagine_model_catalog.py`、`tests/test_ai2apps_imagine_studio.py`。
- 验证：模型目录权限、未下载/内部模型过滤、几何能力与现有 Imagine Studio 回归测试。

### ACPF 公共弹窗国际化（2026-09-11）

- 状态：`ready`。
- ACPF 接入现有 `window._t` 语言字典，补齐简体中文与英文；其他语言使用现有英文回退。
  覆盖公共状态、按钮、选择计数、下载进度、许可确认提示，以及全部内置 Profile 的中文
  标题、说明、档位标签与步骤文案。动态设备推荐理由也支持旧 Session 中已保存的文案。
  许可原文与第三方错误原文不作自动翻译。
- 文件：`ai2apps/web/static/js/capability_provisioning.js`、`ai2apps/web/i18n/en.json`、
  `ai2apps/web/i18n/zh.json`、`tests/test_acpf_localization.py`。
- 验证：全部内置 Profile 翻译覆盖、实际 JS 翻译函数中英文计数与旧计划理由测试 2/2
  通过；Node 语法检查及 diff 检查通过。Locale 字典启动时缓存，需要重启 Local。

### Z-Image MLX Checkpoint 就绪判定修复（2026-09-11）

- 状态：`in_progress`（代码与回归通过，待 UI 配置重试验收）。
- 原因：签名分发已完整落盘，但通用 Diffusers 检查要求 `scheduler/`；mflux Z-Image
  使用 Runtime 内建调度器，分发不包含该目录，导致 Worker Checkpoint 路径为 null，
  ACPF 在 95% 等待 60 秒后超时。
- 修复：仅针对 `family=z-image` 且 `implementation=mflux-mlx-metal-optimized`
  的 Worker 允许 Runtime 提供 scheduler；其他组件与索引分片检查保持生效。
- 文件：`ai2apps/checkpoints.py`、`ai2apps/packages/supervisor.py`、
  `tests/test_checkpoint_runtime_components.py`。
- 验证：相关测试 3/3 通过；真实 app-dev 已下载快照经修复后解析得到有效路径，
  无需重新下载。改动在 ai2apps 热挂载范围，仅需重启 Local。

### NXR-052：Gallery 图片列表右键菜单

- Mini-Entry 按钮调整（2026-09-11）：保留 Studio 素材栏外层“打开 Gallery App”入口，
  内层页头原打开按钮改为刷新当前目录，保留当前目录、搜索和类型筛选；加载或操作中禁用重复点击。
  导入按钮改用加号；导入和刷新均提供可见的 Hover Tip，键盘聚焦也显示提示，沿用中英文文案
  与无障碍名称。导入改为可聚焦按钮，点击调用隐藏文件选择器。
- 状态：`ready`
- 类型：Gallery Shell-App、Gallery Mini-Entry、资产集合操作。
- 用户可见变化：Gallery 完整页面与所有 Studio/AceFox Sidebar 使用的 Gallery Mini-Entry
  共用同一套图片右键菜单，提供打开、下载、重命名、删除、复制、粘贴和移动。移动会在菜单内
  展开可写目标集合；普通删除移入废纸篓，废纸篓中的删除保持永久删除确认。
- 交互与边界：复制/粘贴使用同源 Gallery 内部剪贴板，只保存受当前账户权限再次校验的 Asset ID，
  不读取或覆盖系统剪贴板，也不暴露宿主文件路径；粘贴把资产加入当前实体集合。Recent 与 Trash
  等虚拟/只读集合会禁用不成立的粘贴或移动操作。图片列表空白区也可打开菜单，使空集合能够接收
  已复制图片；鼠标右键和键盘 Context Menu / Shift+F10 均可打开。
- 需要进入 App 的文件：`ai2apps/web/static/js/gallery.js`、`ai2apps/web/static/css/gallery.css`、
  `ai2apps/web/templates/system_apps/gallery.html`、`ai2apps/web/templates/system_apps/gallery_mini.html`、
  `ai2apps/web/templates/system_apps/_gallery_asset_context_menu.html`、`ai2apps/web/i18n/en.json`、
  `ai2apps/web/i18n/zh.json`、`tests/test_ai2apps_gallery.py`。
- 当前验证（2026-09-11）：Gallery 专项回归 `8/8` 通过，JavaScript、英文/中文 JSON 与
  `git diff --check` 通过。固定 App-Dev 的 Local 通过认证 Helper 通道重启至端口 `57152`；实机
  确认完整 Gallery 与 Video Studio 内 Gallery Mini-Entry 均显示七项菜单，窄栏菜单没有溢出。
  复制动作成功写入内部剪贴板，切换到空 Public 集合后右键空白区仅启用粘贴；未对用户现有资产
  执行粘贴、移动、重命名或删除。
- Release notes 建议：Gallery 图片现在可在完整页面和 Studio 素材栏中通过右键快速打开、下载、
  重命名、删除、复制、粘贴或移动到其他集合。
- 纳入 Build：待定。

### NXR-051：AI Browser 九语言界面本地化

- 状态：`ready`
- 用户可见变化：Profile 管理页接入系统统一语言设置，覆盖简体中文、繁体中文、英语、日语、韩语、西班牙语、法语、巴西葡萄牙语和俄语。标题、说明、按钮、创建/删除弹窗、占位符、无障碍标签和操作结果共 40 项文案完整翻译；用户自定义名称保持原文。
- 错误提示补齐名称校验、登录失效/无权限、配置文件不存在、默认配置文件保护、服务不可用、超时、网络失败及无效请求；将后端已知错误与 HTTP 状态映射为本地化说明，未知错误保留 HTTP 状态而不直接显示未翻译的技术诊断。参数替换按字面插入名称，避免特殊字符或花括号被再次解释。页面标签标题也使用当前语言。
- 文件：`ai2apps/web/templates/system_apps/ai_browser.html`、`ai2apps/web/static/js/ai_browser.js`、`ai2apps/web/i18n/*.json`。
- 验证（2026-09-10）：JavaScript 语法及 diff 空白检查通过；九种语言各 32 个键完整性、Jinja 模板渲染、Node 模拟创建/启动/切换窗口/删除/HTTP 错误/默认 Profile 保护及特殊名称插值均通过；Browser Profile 专项回归 5 项通过。固定 App-Dev 路径的 Computer Use 连接超时，未完成实机视觉验收。模板和脚本刷新 Shell 生效；语言字典由 Local 缓存，现有进程可能需要从 Helper 菜单重启 App-Dev Local 后再刷新，不能仅凭静态刷新认定新翻译已载入。无需重建 App。
- Release notes 建议：AI Browser 现支持跟随系统语言显示完整的 Profile 管理界面。
- 纳入 Build：待定。

- 补充验证（2026-09-10）：9 种语言各 40 个键完整性检查通过；Node 执行级检查覆盖错误映射、结构化 422、网络错误、空白/超长名称阻止提交；英文和中文页面标签标题渲染通过。用户确认范围为 AI Browser 全部界面。

### NXR-050：Imagine Studio 模型选择器对齐 ACPF 安装入口

- FLUX 编辑保真修正（2026-09-11）：Imagine Studio 对本地 FLUX.2 Klein 编辑请求显式传递 use_kv_cache=false，覆盖 Image Edit、换风格、参考图和合影等共享请求路径；文生图、Cloud、其他本地模型不变。固定红杯原图/seed=0/4 步/Q8 对照：开缓存 9.2 秒明显改杯型，关缓存 12.8 秒基本保留原图几何与高光。静态 JS 刷新生效，不修改已签名 Package；增加 4B/9B 与非目标模型请求隔离回归。

- Z-Image 参数（2026-09-11）：开放本地 Z-Image 采样步数与重绘强度并保存到 Draft/Run；重绘百分比转换为 mflux 起始比例（默认 75% 重绘 → strength 0.25，8 步时执行 6 步），文生图仍默认 8 步；显示 Img2Img 能力说明，本地新 Run 使用本地标题。仅修改客户端，不修改已安装模型 Package。

- 输出栏滚动（2026-09-11）：标题统一为单行大号 Output；有结果时预览图片先随栏滚动、到顶部后 sticky 覆盖后续内容，保持 contain 完整显示，并限制预览高度不超过栏内可视高度。仅影响 Imagine Studio。

- 输出栏刷新按钮（2026-09-10）：新增中英文 Hover/键盘焦点提示，解释仅同步任务与结果、不重新生成或扣费；图标放大到 20px，按钮外框尺寸不变。

- 完成态修正（2026-09-10）：Gallery 按钮禁用绑定显式返回 boolean，避免缺少 adding/galleryAssetId 时 undefined 被绑定为 disabled；等待光标仅用于实际导入中。Run 进度条仅在 queued/running 显示。静态页面刷新生效，App-Dev 实测蓝杯 Artifact 成功加入 Gallery、侧栏出现缩略图、成功态进度条隐藏；新增缺省/空值/导入中/已导入禁用状态回归。

- 绘图目录补齐（2026-09-10）：新增 Ideogram 4 MLX Q4、Qwen Image 2512 和 Qwen Image Edit 2511，连同 Z-Image、FLUX 共五个独立 Checkpoint 选择项。Qwen 使用组件配置按各自文生图/编辑能力验证；保留内存兼容性、安装状态与许可证确认。专用 Actor Replacement 不支持通用绘图输入，不列入此能力。文件：`ai2apps/provisioning/profiles/imagine-studio.yaml`；需要重启 App-Dev Local 载入目录。相关回归 56 项通过，并新增与全部 `packages/*/service.yaml` 的通用 Image 模型清单对照检查（Imagine 专项 11 项再次通过）；新版五项列表尚未实机验收。
- 状态：`ready`
- 用户可见变化：Imagine Studio 的共享模型下拉菜单末项新增本地化“安装更多模型”，覆盖文生图、
  图片编辑、更换图片风格、参考图创作和合影等内置 AI Mini-App；纯本机且不使用模型的“调整图片”
  保持无模型选择器。入口在已有 Cloud/本地模型以及没有可用模型时均保留；无模型时先显示不可选的
  “暂无可用模型”占位，确保末项安装动作仍可被主动选择并触发。
- ACPF 行为：动作值 `__install_more__` 不作为模型 ID；选中后立即恢复原模型显示，再用
  `image.generation` Capability 和 `{ installMore: true }` 打开共享 ACPF 全量可信配置选择界面；
  “安装更多”模式强制使用多选，可在一次流程中选择多个兼容模型，不受能力档位默认单选模式影响。
  复用 ACPF 已安装项禁用、兼容性原因、确认、许可证、下载、恢复和完成回调；取消或失败不修改
  当前模型，安装完成刷新可用目录并保留仍有效的用户选择。
- 通知条修正（2026-09-10）：Imagine Studio 顶部通知条按工作区左右各留 18px，并在宽屏与
  工作区内容边缘对齐；取消反馈使用中性色并在 4 秒后消失，成功提示 4.5 秒、一般错误 8 秒后
  自动消失，同时保留手动关闭。新操作开始时会取消旧计时器，避免旧通知误清除后续提示。
- 文件：`ai2apps/web/templates/system_apps/imagine_studio.html`、
  `ai2apps/web/static/js/imagine_studio.js`、`ai2apps/web/static/css/imagine_studio.css`、
  `ai2apps/web/static/js/capability_provisioning.js`、
  `tests/test_ai2apps_imagine_studio.py`、`tests/test_ai2apps_provisioning.py`。
- 当前验证（2026-09-10）：Imagine Studio 与 ACPF 专项回归 `56/56` 通过，新增 Node 执行级测试确认
  动作项恢复原选择、以 `installMore=true` 唤起 ACPF，且不触发草稿保存；普通模型切换仍更新模型并
  保存草稿。两个 JavaScript 文件语法、Ruff 和 `git diff --check` 通过。固定 `AI2Apps-App-Dev`
  在端口 `52750` 热加载源码后实机确认：菜单动作恢复 `(Cloud) OpenAI · GPT Image 2`，ACPF 显示
  “选择要安装的模型”及 Z-Image/FLUX 多选项；取消后未下载、未安装，原模型仍保持选中。纯静态
  HTML/JavaScript 变更无需重建 App 或重启 Local。通知修正后重新挂载同一 App，实机确认取消提示
  左右留白、使用中性色，并在约 4 秒后自动从可访问性树和画面中消失。
- Release notes 建议：在 Imagine Studio 模型菜单中直接安装更多本地图像模型。
- 纳入 Build：待定。

### NXR-049：App Launcher 紧凑卡片与介绍悬停提示

- 状态：`in_progress`（实现与回归完成，待 App-Dev 实机视觉验收）
- 用户可见变化：卡片展示图标、名称及 Experimental 实验标记，移除冗余 Open 按钮、分类及实例状态正文；介绍复用 Dock 深色圆角 Hover-Tip，支持悬停与键盘聚焦，长文本自动换行，底部空间不足时向上显示。保留 Dock 固定操作和多窗口切换、新建入口。
- 卡片最小高度由 142px 降至 112px，名称间距缩小；搜索仍匹配介绍与分类。
- 用户反馈修正（2026-09-10）：恢复图标旁的 Experimental 实验标记及原有黄色样式；JavaScript 语法和 diff 空白检查通过。
- 布局修正（2026-09-10）：修复实验标记横排样式被误限定到 development 卡片的问题，所有卡片的图标行统一使用 flex 与底对齐，Experimental 位于图标右侧；恢复 development 图标灰色背景选择器的正确作用范围。选择器检查与 diff 空白检查通过。
- 文件：`ai2apps/web/static/js/shell.js`、`ai2apps/web/static/css/shell.css`。
- 验证（2026-09-10）：`node --check ai2apps/web/static/js/shell.js`、`git diff --check` 通过；仓库根目录执行 `.venv/bin/python -m pytest tests/test_ai2apps_shell.py -q`，114 项通过。退出时环境报告无 Metal device，不影响测试结果。Computer Use 连接固定 App-Dev/Shell 路径持续超时，未完成刷新及实机视觉验收；纯静态改动无需重建 App。
- Release notes 建议：精简 App Launcher 卡片，将应用介绍改为悬停提示。
- 纳入 Build：待定。

### NXR-048：Discover 模型安装兼容 Cloud catalog 详情结构

- 状态：`ready`
- Discover 内存口径跟进（2026-09-10）：卡片改读独立 `runtimeMemoryBytes`，
  既有 Package 依据 service.yaml 的 Lean/Compact 档位兜底；GLM 显示约 55 GiB。
  `minimumMemoryBytes` 保留安装整机门槛并与 Chat Profile 对齐（GLM 64 GiB）；
  缺少运行数据时显示“—”，不挪用整机门槛。签名 Profile 兼容可选运行内存字段。
  Discover + Registry 52 项测试通过，JS 语法检查通过；尚未重启 App-Dev 页面验收。
- 模型资源数据跟进（2026-09-10）：按不可变 Checkpoint 发布收据修正六项 Chat
  模型下载尺寸，并依据 Cached-MoE / VLM 实测修正内存估计；Qwen3.6 使用安装验收
  的约 19 GiB 与 Top120 内存记录。详情来源提示注明档位、峰值和系统门槛为估计；
  UI 二进制单位改为 GiB/MiB。证据和未核实项见
  `docs/discover-chat-model-profile-evidence-2026-09-10.md`。无需 Cloud 变更或重发旧 Package。
  验证：Discover + Registry 51 项通过，Discover JS 语法检查通过；尚未重启当前
  App-Dev 做页面验收。测试退出时出现 sandbox 无 Metal 设备的清理告警，测试退出码为 0。
- 重启续跑跟进（2026-09-10）：Discover 模型安装 ACPF 会话现在持久记录
  `returnTo`，Shell 在 Local 重启后自动返回 Discover；修复前已创建、没有该字段的会话也会
  依据受限的 App/Capability 身份兼容恢复。ACPF 遇到尚未安装的 restart-required Runtime
  依赖时，会在用户已确认的可信安装范围内先安装该依赖，再进入等待重启；重启后继续模型
  Package，不再循环提示安装 Runtime。等待重启说明改为蓝色信息提示，只有实际失败显示红色。
- 安装状态跟进（2026-09-10）：已安装接口现在把签名 `modelInstall` 声明与本机可用的
  Package Model/Checkpoint 状态关联，返回 `modelReady` 和已就绪配置 ID；Discover 卡片与
  详情只有在尚无可用 Checkpoint 或存在新版本时显示“安装模型”，当前版本已有可用配置时
  显示“已安装”。这保留了“只装 Package、稍后下载模型”的既有流程。
- 模型分类跟进（2026-09-10）：Text 是可重叠的能力分类；除原生 Text 模型外，声明
  `multimodal-conversation` 的多模态模型也会列入 Text，同时继续保留在 Multimodal。
  Local 的分页后端与 Discover 前端使用相同规则，不把仅图像生成等非对话模型误列为 Text。
- 用户可见变化：从 Discover 安装既有模型 Package 时，不再因按钮闪回并提示
  “The catalog release version is unavailable”而中止；Local 能从当前 Cloud catalog 详情的
  `package.latestVersion` 和 `package.displayName` 解析发行身份并进入 ACPF 安装流程。
- 根因与兼容边界：Cloud catalog 详情使用嵌套 `package` 摘要，Local 安装接口此前仅识别
  顶层字段、`latestRelease` 或签名 manifest。现在分类、模型评分、ACPF 安装计划和安装接口
  统一兼容嵌套摘要；既有官方 Package 继续使用受版本上限约束的内部映射，未来 Package
  仍必须在签名 manifest 中声明模型元数据，不要求逐个重发旧 Package。
- 文件：`ai2apps/packages/discovery.py`、`ai2apps/api/packages.py`、
  `ai2apps/provisioning/orchestrator.py`、`ai2apps/web/static/js/capability_provisioning.js`、
  `ai2apps/web/static/js/discover.js`、`ai2apps/web/static/js/shell.js`、
  `ai2apps/web/templates/system_apps/discover.html`、
  `tests/test_ai2apps_registry_v1.py`、`tests/test_ai2apps_provisioning.py`、
  `tests/test_ai2apps_shell.py`。
- 当前验证（2026-09-10）：使用与生产 Cloud 返回一致的 `package + releases` catalog 详情
  新增回归，模型安装计划与 ACPF 会话创建均通过；Registry 与 Discover 分类联合回归
  47 项通过；重启续跑跟进与 Provisioning、Shell、Registry、Discover 分类联合回归共
  206 项通过。固定 App-Dev 实机验收已确认：首次重启后自动返回 Discover 并下载、安装
  `ai2apps/runtime-omlx 1.6.2`；第二次重启仍自动返回 Discover，Runtime 显示为
  `Local 1.6.2`，模型 Service Package 完成并进入 Checkpoint 下载阶段，未再出现原依赖
  循环。为避免验证额外消耗约 17 GB 下载，确认进入 Checkpoint 阶段后主动取消测试会话。
  安装状态跟进后的联合回归共 207 项通过；在用户已完成 Checkpoint 的当前 App-Dev 实机上，
  Qwen3.8 卡片同时显示 `Local 0.3.2` / `Cloud 0.3.2`，操作按钮已变为禁用的“Installed”。
  模型分类跟进的 Discover/Registry 50 项范围回归通过；固定 App-Dev 实机的 Text 分类已
  同时显示 Qwen3.8 Flash Next、Ornith、GLM-5.3、Qwen3 VL、Qwen3.5 与已安装 Qwen3.8
  等带 `MULTIMODAL` 标记的对话模型。
- Release notes 建议：修复部分模型 Package 在 Discover 中点击安装后立即复原的问题。
- 纳入 Build：待定。

### NXR-047：Shell App 原生对话框品牌标题

- 状态：`ready`
- 用户可见变化：Shell 内页面的 `alert`、`confirm`、`prompt` 标题统一为 `AI2Apps`，不再显示页面 URL；保留原生阻塞、按钮和返回值语义。
- 实现：AceFox `browser/actors/PromptParent.sys.mjs` 依据父 Chrome 文档精确匹配 `chrome://browser/content/ai2apps/shell.xhtml`，设置原生 `title` / `useTitle`。普通浏览器、认证及 beforeunload 提示保持原逻辑。
- Development 构建：`apps/ai2apps-acefox/scripts/build-release-app.sh` 在现有仅 Development 的 Shell overlay 中同步匹配源码树的 `actors/PromptParent.sys.mjs`；生产必须使用包含该源代码修改的 AceFox 正式快照。
- 验证（2026-09-10）：15 项标题与边界检查通过，覆盖带实例 query/hash 的 Shell 地址；JavaScript / zsh 语法、diff 检查通过。通过固定入口重建 App-Dev，`verify-release-app.sh` 与 `codesign --verify --deep --strict` 通过；包内 PromptParent 与源码逐字一致，Development、app-dev、cloud、源码根合同正确。实机窗口标题为 `AI2Apps-App-Dev: M5Max-128G 127.0.0.1:58113`；Chat 的原生删除确认框窗口及标题正文实际显示 `AI2Apps`，未确认删除。alert / prompt 共用分支已检查，未分别触发实机输入场景。
- 纳入 Build：待定。

### NXR-046：Cloud 管理 Work complexity API Default

- 首次发送保留手选模型（2026-09-18）：空白 Chat 首发原先调用 startNewChat 后无条件采用系统默认，导致本地手选被覆盖。新增 initialModel 参数，仅首次发送创建会话时传入发送前的模型；显式 New Chat 仍遵循中等复杂度/API Default。会话、发送 sourceModel 和右侧显示保持一致；新增实际执行 startNewChat/sendMessage 的回归，模拟异步目录刷新覆盖并验证恢复手选，覆盖显式新建与已有会话。
- Mini-App 安装入口对齐（2026-09-10）：浏览器 Chat Mini-Entry 与 Studio Chat 共用模型安装菜单控制器，末项提供“安装更多模型”，动作立即恢复当前值、不写入手动偏好，进入 ACPF installMore 模式；安装完成刷新目录。Chat Mini 模板补载共享 ACPF 资源；Studio 无独立 mount 时通过标准 Shell launch 获取 Chat AppInstance，后端仍执行 actor/AppInstance 授权校验。未执行真实安装。
- 对话模型安装入口（2026-09-10）：Chat 对话模型下拉菜单末项新增“安装更多模型”，恢复当前模型后进入 ACPF installMore 模式，复用 text.chat.local 配置与确认流程。模型选择器统一规范写入 `docs/ai2apps-app-development-guide.md`，适用于 App/Mini-Entry/Mini-App，明确菜单内部末项、可用性、已安装禁选、取消保留选择与异步刷新验收。
- 切回 App 刷新修复（2026-09-10）：Chat 在局部变量完整组装包含 API Default 的目录后仅发布一次，避免异步间隙删除选中项；等待 Alpine 选项渲染后显式同步原生 select 值，防止 currentModel 未变而右侧误显首项 Claude。Browser/Studio Mini-Entry 原本已同步重建选项并赋值，本次额外保留异步加载期间最新的有效手动选择。
- 刷新修复验证：Chat UI、Browser Mini-Entry、Studio Mini-App Chat 共 43 项回归通过；App-Dev 原有对话刷新、最小化再恢复窗口后，顶部与右侧均保持 DeepSeek V4 Flash (API Default)，Knowledge 保持 Off。Mini-Entry 完成代码与回归检查，未新增真实推理请求。
- Mini-Entry 跟进（2026-09-10）：Browser Chat Sidebar 与 Studio Mini-App Chat 统一使用共享默认选择函数；已有手动选择优先，否则读取 `work_standard`，空值继承 Cloud API Default。兼容旧模型目录的 provider ID，同时保留独立 `cloud/ai2apps/` Points 路由；不把继承值写入手动偏好，无有效默认时不再自动选择首项。文件：`ai2apps/web/static/js/{chat_mini,mini_app_chat}.js`、`tests/test_ai2apps_chat_mini.py`。
- 状态：`in_progress`（Cloud 已部署，客户端定向回归通过；待桌面 UI 与实际 Work 端到端验收）。
- Chat 默认目录修复与实机复验（2026-09-10）：运行诊断确认策略 ID 为 `cloud/ai2apps/deepseek/deepseek-v4-flash`，旧目录仅返回 `cloud/deepseek/deepseek-v4-flash`，可用性检查因此拒绝默认选择。Chat 在目录存在对应模型时注册独立 API Default 项，复用能力元数据但保留专用 `cloud/ai2apps/` Points 路由及原有显式 provider 路由；不硬编码 DeepSeek、不将默认路由降级为 BYOK。临时诊断 UI 已移除。App-Dev 刷新与 New Chat 均实际选中 `DeepSeek V4 Flash (API Default)`，输入框启用，Knowledge 为 Off。Chat UI 与 Cloud defaults 共 44 项测试通过，新增目录兼容、路由保留、能力继承、去重及缺失目录测试；未发送真实推理请求，完整 Work 验收仍待完成。
- App-Dev 登录后 UI 验收（2026-09-10）：三档 Work 均实际显示 `Use API default — (Cloud) DeepSeek V4 Flash`，专用能力槽位保持 `Not assigned`，中档下拉目录包含 DeepSeek V4 Flash。Chat 的 Use Knowledge 实际为 Off；但首次打开与点击 New Chat 均未正确选中默认模型，顶部模型按钮缺失、输入框禁用，右侧原生下拉显示首项 Claude Sonnet 4.6，故 Chat 默认继承验收失败。未发送推理请求、未改用户模型配置；需定位并修复后复验，不得将单元测试通过视为本项 UI 通过。
- App-Dev 首启复验（2026-09-10）：经用户明确授权，停止精确 `app-dev` 进程，将其 support/cache 私有目录移入 `/Users/avdpropang/Library/Application Support/AI2Apps/app-dev-reset-backup-20260910-0019/` 后启动固定 App，其他实例及公共模型缓存未动。全新未登录实例成功生成 Cloud 默认策略缓存，未生成显式 `default-models.json`；Shell 显示 Core 用户登录页，后续 Chat/Model UI 验收等待用户重新登录。旧数据保留可恢复备份，未永久删除。
- 用户可见变化：未手选的三个复杂度档位动态继承 Cloud 默认 AI，界面显示继承模型；
  初始 Cloud 选择要求为 `deepseek/deepseek-v4-flash`，客户端不硬编码该模型。
- 实现：启动最多等待 3 秒拉取，每 5 分钟刷新；origin 隔离的原子缓存最长有效 24 小时；
  显式模型选择始终优先，空值恢复继承，专用能力槽位不变。Cloud 显式路由不被 BYOK 拦截。
- 文件：`ai2apps/cloud_defaults.py`、`ai2apps/model_manager.py`、`ai2apps/platform_runtime.py`、
  `ai2apps/cloud_gateway.py`、`ai2apps/api/cloud.py`、`ai2apps/web/static/js/dashboard.js`、
  `ai2apps/web/templates/dashboard/_models.html`、`tests/test_ai2apps_cloud_defaults.py`。
- Cloud 交接：`docs/ai2apps-cloud-api-default-model-requirements.md`；未修改或部署 Cloud。
- Cloud 回执（2026-09-10）：Cloud 项目已部署 OpenAPI 1.47.0；交接文档为 `/Users/avdpropang/sdk/ai2apps-cloud/docs/ai-defaults-client-handoff-v1.md`，生产回执为同目录 `ai-defaults-production-deployment-2026-09-10.md`。客户端侧匿名实测生产 `GET /v1/ai/defaults` 返回 HTTP 200、`Cache-Control: no-store`、revision `1` 和 `deepseek/deepseek-v4-flash`，Cloud 部署阻塞解除。未修改 Cloud 配置、凭据或数据。
- 验证（2026-09-09）：默认策略、Model Manager、Cloud Gateway、Local API 与存储/生命周期
  定向回归 79 项通过；补充 Local 策略读取接口合同测试后策略测试 10/10 通过
  （累计 80 个不同测试）。Dashboard JavaScript 语法和定向 diff 检查通过。
  尚未重启 App-Dev 或验证真实 Cloud 推理；Cloud 部署前无法完成端到端验收。
- Release notes 建议：任务复杂度默认模型可随云端配置更新，用户手动选择保持不变。
- Chat 跟进（2026-09-10）：Chat 初次选择和新建对话默认使用 Model App 的 `work_standard`；未设置时使用同一 Cloud 策略的 API Default，不再读取 health 默认模型。已有对话/手动选中的有效模型不被后台刷新覆盖；新建对话重新读取配置。默认策略缺失或目标不可用时不随意选列表首项，等待用户明确选择。
- Chat 文件与验证：`ai2apps/web/templates/chat.html`、`tests/test_chat_ui_overhaul.py`；33 项定向回归通过，覆盖中等复杂度优先、API Default 继承、空策略、别名、保留手选及不可用模型。Test 包尚未包含本次 Chat 默认选择与默认关闭 Knowledge 的改动。
- 客户端复验（2026-09-10）：在仓库根目录执行 `.venv/bin/python -m pytest tests/test_ai2apps_cloud_defaults.py tests/test_ai2apps_model_manager.py tests/test_ai2apps_cloud_gateway.py tests/test_chat_ui_overhaul.py -q`，84 项通过。覆盖默认继承且不写入显式选择、清空恢复继承、专用槽位、重启缓存、origin 隔离、24 小时过期、null 停用、404/非法响应/网络故障保留有效缓存、Points 路由不受同厂商 BYOK 拦截与 Chat 默认选择。首次从 `ai2apps/` 子目录执行因 `secrets` 遮蔽标准库导致收集失败，改为仓库根目录后通过；退出时有沙箱 Metal atexit 警告，不影响测试结果。尚未完成全新未登录桌面 UI、真实周期刷新及实际 Work 推理矩阵；不将 Cloud 自身推理回执视为 Desktop 验收。
- 纳入 Build：待定。

### NXR-044：App / Mini-App 控件补齐 aria-label

- 状态：`in_progress`
- 类型：System App / Mini-Entry HTML 可访问名称、Package Mini-App 动态按钮。
- 实现边界：按用户要求仅添加静态或 Alpine 绑定的 `aria-label`，动态角色按钮仅增加
  `setAttribute('aria-label', ...)`；原有元素、文字、样式、事件和业务逻辑保持不变。
- 覆盖：Chat Mini 消息输入；Voice 项目/片段字段、试听及弹窗按钮；Video 清除帧、
  工具栏与 Composer 按钮；Imagine 调整工具栏及预设名称；Gallery Mini 搜索/集合/上传入口；
  media-voice Package 角色删除按钮。已有合格名称的 Shell 主控件保持不变。
- 需要进入 App 的文件：`ai2apps/web/templates/system_apps/{chat_mini,readaloud,video_studio,imagine_studio,gallery_mini}.html`。
- Package 文件：`packages/ai2apps-media-voice-studio-suite/web/mini-app.js`；未来 Package 候选需要
  包含该修改，本轮不构建或发布 Package。
- 当前验证（2026-09-09）：共添加 52 处 aria-label；与修改前快照比对，去除新增属性后
  5 个模板逐字一致，Package JavaScript 仅新增一条属性设置。5 个 Jinja 模板、57 个
  Alpine aria-label 表达式和 Package JavaScript 语法检查通过；控件无重复 aria-label，
  新复用的翻译 key 均存在于中英文词典，定向 `git diff --check` 通过。
  未做实机可访问树验收，状态保留 `in_progress`。
- 剩余边界：只添加属性不能解决 Gallery 上传入口的键盘焦点问题；依用户限制未改动其
  hidden、tabindex、元素类型或事件。新增 Composer 播放和裁剪名称使用英文，完整本地化待后续处理。
- Release notes 建议：补充 App 与 Mini-App 的控件可访问名称，改善语义 UI 测试定位。
- 纳入 Build：待定。

### NXR-043：Discover Shell-App 卫星天线图标

- 状态：`ready`
- 类型：Desktop Shell、系统 App 导航图标。
- 用户可见变化：Discover 在 Shell Dock、App Launcher 与 AppUI 页面标题区不再使用容易与
  浏览器混淆的罗盘，统一改为用户最终选定的 Lucide `satellite-dish` 单色卫星天线图标。
- 实现边界：直接复用客户端已打包 Lucide `0.453.0` 的内置图标，不携带 Discover 专属 SVG
  注册或第二条渲染路径；按 Shell 的 `22px` 桌面、`20px` 移动显示与激活态反白规则渲染。
- 需要进入 App 的文件：`ai2apps/apps/system.py`、`ai2apps/web/templates/system_apps/discover.html`、
  `ai2apps/web/static/js/shell.js`、`ai2apps/web/static/js/ai2apps_icons.js`、
  `ai2apps/web/templates/base.html`、`tests/test_ai2apps_shell.py`。
- 当前验证（2026-09-09）：Shell 定向回归 `114/114` 通过；相关 JavaScript 语法与
  `git diff --check` 通过。早期自定义火箭候选暴露了切换 App 时无条件重建整个 Dock 的问题；
  普通 App/Home 切换现只原位更新 `is-current`，保留全部 SVG DOM，仅目录、Pin、排序或 Badge
  变化才重建 Dock。最终卫星天线改为内置 Lucide 后，不再依赖自定义图标注册与兜底轮询。
  固定 App-Dev 已通过 Settings 的标准重启入口从端口 `51358` 恢复到 `57179`；实机截图确认
  Dock 激活态和 Discover AppUI 页头均显示卫星天线。验收临时打开的 Settings 实例已关闭，
  Dock 恢复到操作前状态。
- Release notes 建议：Discover 使用新的卫星天线图标，在 Shell Dock 中更容易与浏览器区分。
- 纳入 Build：待定。

### NXR-042：全 App 统一模型显示身份

- 状态：`ready`
- 类型：Local API、Chat、Models、Coder、Knowledge、Mobile/Mini Chat 与 Studio
  模型选择器。
- 用户可见变化：所有模型显示名统一为
  `(Source) Provider · Model`，Source 仅使用 `Cloud`、`Local`、`BYOK`；比如
  `(Cloud) OpenAI · ChatGPT 5.6 Luna`、`(BYOK) OpenAI · ChatGPT 5.6 Terra`和
  `(Local) AI2Apps-MLX · Qwen 3.8 27B NVFP4`。
- 合同与兼容边界：模型路由 ID、默认选择和已保存配置均不变；Local API 新增
  结构化 `identity` 并保留 `id` 作为唯一调用键。AI2Apps Cloud 服务不需改动，
  现有 Model/Runtime Package 不需重发；Local 根据现有 Cloud provider 字段与
  Package `runtime.provider` 生成展示身份。
- 需要进入 App 的主要文件：`ai2apps/model_identity.py`、
  `ai2apps/model_providers.py`、`ai2apps/api/cloud.py`、`ai2apps/api/readaloud.py`、
  `ai2apps/api/video_studio.py`、`omlx/api/openai_models.py`、`omlx/server.py`、
  `omlx/admin/routes.py`及相关 Web 模型选择器。
- 当前验证（2026-09-08）：新增 Model Identity 契约回归 `7/7`；Model Provider、
  Chat UI、Imagine Studio、Video Studio、Read Aloud 与 Mini-App Chat 联合回归
  `94/94` 通过；Cloud Client 与 Desktop Shell 联合回归 `154/154` 通过。其他
  涉及完整 oMLX Engine 导入的组合测试在当前无 Metal 的命令执行环境中会被
  MLX 主动终止。三实例目标已纠正为 `main`、`app-dev`、`test`：普通
  `AI2Apps-dev.app` 不属于本次更新范围，误启动的 Dev 已停止；固定 App-Dev 与 Test
  已通过各自标准构建入口刷新并启动。App-Dev 运行于端口 `50951`，实机 Chat 模型选择器
  显示 `(BYOK) OpenAI · ChatGPT 5.6 Luna`；Test 运行于端口 `50829`，保持未绑定账户的
  登录初始状态。两者主 App 与内嵌 Shell 的图标一致，托盘角标资源分别保持 App-Dev
  单橙点与 Test 双紫菱形，严格深度签名检查和 App 图标回归 `4/4` 通过。
- Release notes 建议：Chat 和各 Studio 现在使用一致的模型名称，可直接识别
  Cloud、本地与本地密钥来源，以及实际推理服务商。
- 纳入 Build：待定。

### NXR-041：新设备默认名称使用芯片型号与统一内存

- 状态：`ready`
- 类型：Cloud 设备注册、Desktop Shell 启动信息。
- 用户可见变化：新 Installation 绑定 Core 账户时，设备名不再采用浏览器兼容字段
  `navigator.platform` 所返回的误导性 `MacIntel`；Local 从 macOS 读取 Apple Silicon 芯片型号和
  统一内存，并生成紧凑名称，例如 `Apple M5 Max`、128 GiB 对应 `M5Max-128G`。
- 兼容边界：已经注册或由用户重命名的 Cloud 设备继续使用已保存名称；硬件型号无法识别时回退
  到系统主机名，登录页请求失败时保留可编辑的 `Mac` 占位值。登录页通过既有本机
  `/v1/platform/client/bootstrap` 合同取得默认值，不新增 Cloud API 或浏览器硬件指纹接口。
- 需要进入 App 的文件：`ai2apps/api/client.py`、`ai2apps/web/static/js/login.js`、
  `tests/test_ai2apps_client_bootstrap.py`。
- 当前验证（2026-09-08）：Client Bootstrap 定向回归 `9/9` 通过，覆盖
  `M5Max-128G` 格式、未知硬件主机名回退和已注册设备名优先级；JavaScript 语法、Ruff 与
  `git diff --check` 通过。沙箱不允许读取宿主 `sysctl`，真实 App 中的实机值留待候选构建验收。
- Release notes 建议：新设备现在默认使用芯片型号和统一内存命名，更容易在设备列表中识别。
- 纳入 Build：待定。

### NXR-040：固定的 AI2Apps-test 发布态测试实例

- 状态：`in_progress`
- 类型：macOS Desktop 构建、Helper、实例数据生命周期。
- 用户可见结果：新增固定 `AI2Apps-test.app`，使用与正式版相同的 cloud Runtime、签名和
  Release App 校验链，但采用独立 `com.ai2apps.desktop.test` Bundle ID 和 `test` instance ID，
  因而不会读写正式版、`dev` 或 `app-dev` 的 User Data。旧测试 App 在替换前归档。
- 测试版专属能力：只有带签名 `AI2AppsAllowInstanceDataReset` 开关的 Helper 显示“重置数据…”；
  用户二次确认后停止 Local、关闭测试 Shell 和 Agent，删除 test 实例的 Application Support 与
  Caches 根目录并退出。公共 `~/.cache/huggingface/hub` 明确不属于删除目标。
- 自动化 fresh-install：Test Helper 的认证 loopback 控制通道新增 `instance.reset`，但仅在签名
  reset capability、固定 `com.ai2apps.desktop.test`、instance `test`、Harness actor 和显式
  `confirm_instance_id=test` 全部匹配时接受。CLI 的 `--fresh-install` 通过该操作复用菜单对应的
  `InstanceDataReset`，不在 Harness 中直接递归删除目录；失败时选定测试范围统一 BLOCKED。
- 托盘身份：Test 的四种 Helper 状态图标统一叠加左上角和右上角两个紫色菱形；保留原状态
  图案，同时与正式版无角标和 App-Dev 左上角单个橙色圆点明确区分。
- App 图标与 App-Dev：Test 主 App 与内嵌 Shell 的全尺寸 `.icns` 将球体上半部改为浅蓝色；
  App-Dev 对应区域改为淡紫色。构建期从原图各原生尺寸着色，保留渐变、黑色 Logo、边框和
  下半球。App-Dev 同时获得与 Test 相同的实例级“重置数据…”能力，只清理 `app-dev` 私有根。
- 安全边界：重置目标由 `InstancePaths` 生成并再次校验为两个互不嵌套的实例私有根；删除前
  拒绝目标及关键父目录中的符号链接。正式版和通用 `dev` 实例没有该菜单能力。
- 构建防回退：专用图标已从包装脚本参数提升为共享 Release 构建合同。任何入口只要使用
  Test 或 App-Dev 的保留身份字段，就必须使用完整固定身份；共享构建器自动强制对应色彩与
  托盘角标，并在签名前校验主 App/内嵌 Shell 图标一致及四种 Helper 状态角标完整。标准
  production、`main` 和通用 `dev` 构建反向禁止携带这些专用图标。签名后的主 App、Shell
  与 Helper 还会写入一致的 `AI2AppsIconContract`，通用 Release verifier 会再次按实例身份
  独立检查该合同和实际角标，避免其他构建入口绕过包装脚本。
- 需要进入 App 的文件：
  - `apps/ai2apps-acefox/scripts/build-test-app.sh`
  - `apps/ai2apps-acefox/scripts/build-app-dev-environment.sh`
  - `apps/ai2apps-acefox/scripts/build-release-app.sh`
  - `apps/ai2apps-acefox/scripts/tint_app_icon.py`
  - `apps/ai2apps-acefox/Sources/AI2AppsContracts/InstanceDataReset.swift`
  - `apps/ai2apps-acefox/Sources/AI2AppsHelper/main.swift`
  - `apps/ai2apps-acefox/Sources/AI2AppsHelper/HelperControlServer.swift`
  - `ai2apps/helper_control.py`
  - `ai2apps-test-system/src/ai2apps_test/accounts.py`
  - `ai2apps-test-system/src/ai2apps_test/cli.py`
  - `ai2apps-test-system/src/ai2apps_test/runner.py`
  - `apps/ai2apps-acefox/Tests/AI2AppsContractsTests/ContractsTests.swift`
  - `tests/test_ai2apps_shell.py`
  - `tests/test_ai2apps_app_icon.py`
  - `ai2apps-test-system/docs/test-app.md`
  - `docs/ai2apps-app-dev-environment.md`
- 当前验证（2026-09-08）：Swift Package 全量 `74/74`、Desktop Shell `111/111` 通过，新增
  用例确认私有 Support/Cache 会被删除、公共 HF cache 保留，并拒绝符号链接父目录；Shell 脚本
  语法与 `git diff --check` 通过。标准测试版构建入口已生成 689 MiB 固定
  `AI2Apps-test.app`，内部与最终路径两轮 `verify-release-app.sh` 及严格深度 codesign 均通过。
  签名元数据确认 Bundle ID `com.ai2apps.desktop.test`、instance `test`、Runtime profile `cloud`、
  无 Development 标记，且 Helper 的 reset capability 为 `true`。实机启动后 Helper、Local 与 Shell
  均发布 `test` 身份，Local 在自动端口 `58778` 达到 `ready`；Computer Use 可确认测试 Shell
  独立运行，但本轮辅助功能层读取托盘菜单超时，未执行具有永久删除效果的实际菜单确认操作。
  同日新增 Test 专属托盘身份后，Desktop Shell 回归仍为 `111/111`；四份最终 Helper SVG 均通过
  XML 校验并同时包含左右两个紫色菱形角标，固定 App 再次通过两轮 Release 校验和严格深度
  codesign。最后一个单角标制品已归档为 `.build/archive/AI2Apps-test-20260908-014259.app`。
  2026-09-08 后续图标预览与成品像素抽样确认 Test 浅蓝、App-Dev 淡紫均只改变上半球并保留
  原渐变。Test 与 App-Dev 已分别用标准固定入口重建，旧制品归档为
  `.build/archive/AI2Apps-test-20260908-020057.app` 和
  `.build/archive/AI2Apps-app-dev-20260908-020238.app`；两者严格深度 codesign 均通过，主 App
  与内嵌 Shell 图标着色一致，Helper 的签名 reset capability 均为 `true`。图标与 Shell 联合回归
  `116/116`、Ruff 和 `git diff --check` 通过。Computer Use 按精确固定路径启动两者后，Test 在
  端口 `65486`、App-Dev 在端口 `65341` 达到 `ready`，Helper、Local、Shell descriptor 分别发布
  正确的 `test` / `app-dev` 身份。为避免破坏长期实例数据，没有在验收中确认执行最终删除按钮；
  删除行为由 Swift 隔离、HF cache 保留及符号链接拒绝测试覆盖。
  2026-09-08 实机首次执行 App-Dev 重置暴露了只读制品目录兼容问题：已验证的 Runtime Package
  与模型 distribution 使用 `0555` 目录权限，Foundation 递归删除在这些目录停止，并以未本地化的
  `ContractError error 1` 弹窗结束。重置器现在先在两个实例私有根内逐层恢复目录所有者的
  `rwx` 权限，再执行删除；内部符号链接只作为链接删除且不会跟随，公共 HF cache 仍不在目标中。
  重置时 Shell/Agent 改为强制退出，避免已经确认重置后再次出现 AceFox 的 Quit 对话框；
  `ContractError` 同时提供可读错误描述。包含真实 `0555` 目录树、内部/父级符号链接及公共 cache
  保留的 Swift 全量回归 `76/76` 通过，Shell 回归 `112/112` 与 `git diff --check` 通过。共享修复已
  通过两个标准入口进入新的固定 App，原 Test 与 App-Dev 分别归档为
  `.build/archive/AI2Apps-test-20260908-022304.app`、
  `.build/archive/AI2Apps-app-dev-20260908-022429.app`；两个新包再次通过双层 Release verifier、
  严格深度签名检查并保留 reset capability。修复后的 App-Dev 按固定路径启动，在端口 `51853`
  达到 `ready`，三个 descriptor 均确认 `app-dev` 身份。
  2026-09-09 新增 `--fresh-install` 与受限 Helper reset 控制操作；Swift 全量回归 `76/76`、
  Helper 控制回归 `13/13`、Harness 全量回归 `41/41` 通过；顶层
  `./bin/ai2apps-test --fresh-install` 已验证会转换为 fresh-install 选择流程。固定 Test App 已通过标准
  `build-test-app.sh` 重建，双层 Release verifier 与严格深度签名校验通过；包内 Helper 已确认包含
  `instance.reset`、Harness actor 和显式确认字段。真实删除验收会清除 `test` 实例数据，留待用户
  明确启动 fresh-install 测试时执行。
- Release notes 建议：不适用；这是发布前测试环境，不进入正式用户 App。
- 纳入 Build：测试工具本身需随仓库保留；测试专属 Bundle 标记不进入正式 Build。

### NXR-038：重复启动同一实例时激活现有窗口

- 状态：`ready`
- 类型：macOS Desktop Launcher、实例生命周期
- 用户可见问题：同一个 AI2Apps 实例已经运行时，再次从 Finder 启动该 App 会继续尝试为同一
  Profile 创建 AceFox 进程，最终显示 Firefox“一次只能打开一个副本”的错误对话框，而不是回到
  已打开的 AI2Apps 窗口。
- 修复：Launcher 在启动 Helper 后、创建新 AceFox 进程前读取该实例的 Shell run descriptor；仅当
  PID、instance ID、Shell/Main bundle identity 和实时可执行文件身份全部通过校验时，直接激活该
  Shell 的全部窗口并成功退出 Launcher。身份不匹配或进程不存在时仍执行正常启动；更新后的 App
  handoff 明确绕过复用路径，继续完成新版本健康启动。
- 需要进入 App 的文件：
  - `apps/ai2apps-acefox/Sources/AI2AppsLauncher/main.swift`
  - `docs/ai2apps-desktop-next-release.md`
- 当前验证：Swift Package 全量回归 `72/72` 通过，`git diff --check` 和固定开发 App 的
  `codesign --verify --deep --strict` 通过。已由标准 `build-dev-app.sh` 重建固定
  `AI2Apps-dev.app`，旧版归档为 `AI2Apps-dev-20260907-232822.app`。实机首次启动 Shell PID
  为 `71397`、Local 端口为 `63049`；随后在 Finder 再次打开同一 App，原窗口被置于前台，
  Shell descriptor 的 PID 与发布时间均未变化，且未出现 Firefox 重复实例对话框。固定
  `AI2Apps-app-dev.app` 也已通过专用 `build-app-dev-environment.sh` 重建，旧版归档为
  `AI2Apps-app-dev-20260907-233506.app`；实机确认 `app-dev` 以 cloud Runtime 在端口 `63813`
  就绪，窗口标题为 `AI2Apps-App-Dev: M5Max128G · App-Dev 127.0.0.1:63813`，通用 `dev`
  实例仍独立运行在端口 `63049`。
- 纳入 Build：待定。

### NXR-034：源码挂载 Mini-App 的可执行开发 Sandbox

- 状态：`ready`
- 类型：App-Shell 开发基础设施、Package Mini-App 本地调试
- 用户可见问题：Development source mount 可以发现并挂载 Package Mini-App，但严格
  opaque-origin CSP 使受认证的外部 CSS/JavaScript 无法加载，页面只显示 Studio 的标题条；
  `connect-src 'none'` 同时阻止页面调用 mount-scoped Host Capability Broker。
- 修复：仅当 Entry 来源为 `development` 且 Runtime 显式设置
  `AI2APPS_ALLOW_DEVELOPMENT_RUNTIME=1` 时，sandbox 增加 `allow-same-origin`，并把
  `connect-src` 限制为当前 Local origin。已安装 Package、生产 Bundle 和未显式启用的
  Runtime 继续使用原 opaque-origin、`connect-src 'none'` 策略。
- 发行边界：该策略只用于源码态热开发；Package 发布前仍需实现并通过严格 sandbox 下的
  生产 Mini-App bridge/broker 验收，不得把开发例外带入正式制品。
- 需要进入 App 的文件：
  - `omlx/admin/routes.py`
  - `ai2apps/extensions/manager.py`
  - `tests/test_ai2apps_shell.py`
  - `tests/test_ai2apps_development_packages.py`
  - `docs/ai2apps-studio-mini-app-package-contract-v1.md`
  - `docs/ai2apps-app-development-guide.md`
- 当前验证：Development Package、Shell、Studio Capability Broker 和 Extensions 联合测试
  `146/146` 通过；关键 Ruff 规则和 `git diff --check` 通过。固定
  `AI2Apps-app-dev.app` 已通过标准脚本重建及签名验证，旧版本已归档；真实 App-Dev
  Studio 中五条 Media Voice Studio Suite Mini-App 均已显示完整交互内容，转写页面也已
  成功调用 mount-scoped Broker 并准确提示尚未配置模型，而不是停留在只有标题的空页面。
  独立的通用 `dev` 实例未被终止或改写。
- 纳入 Build：待定。

### NXR-035：Read Aloud Package Mini-App 草稿路由隔离

- 状态：`ready`
- 类型：App-Shell、Read Aloud、Package Mini-App 兼容性
- 用户可见问题：Read Aloud 打开 Package Mini-App 后，折叠或展开左右工作区会把 Package
  Mini-App ID 发送给仅接受内置定义的 Read Aloud draft API，右上角因此显示
  `Read Aloud Mini-App was not found`。
- 修复：宿主的延迟保存、直接保存和加载草稿都跳过 Package Mini-App；Package 页面继续通过
  自身状态和 mount-scoped Broker 管理任务数据，内置 Mini-App 的既有草稿机制保持不变。
  Read Aloud 脚本资源版本同时更新，避免 App-Dev 刷新后继续命中旧缓存。
- 需要进入 App 的文件：
  - `ai2apps/web/static/js/readaloud.js`
  - `ai2apps/web/templates/system_apps/readaloud.html`
  - `tests/test_ai2apps_studio_mini_app_client.py`
- 当前验证：Read Aloud 与 Studio Mini-App Client 回归 `9/9` 通过，JavaScript 语法和
  `git diff --check` 通过。固定 `AI2Apps-App-Dev` 刷新后，Audio Speaker Voice Replacement
  保持完整显示；连续切换输出面板不再出现 draft 404 或右上角红色错误。
- 纳入 Build：待定。

### NXR-036：Studio Package Mini-App 依赖状态采用真实 Capability Probe

- 状态：`ready`
- 类型：App-Shell、Read Aloud、Video Studio、Package Mini-App 能力发现
- 用户可见问题：Read Aloud 和 Video Studio 过去把 Package Mini-App 成功挂载直接解释为
  `Dependencies ready`，即使 Mini-App 的 mount-scoped Capability Probe 已明确报告模型未安装，
  宿主底部徽标仍会与页面内提示矛盾。
- 修复：共享 Studio Mini-App Client 新增 mount-bound capability probe；Read Aloud 和 Video
  Studio 按已声明能力的 `implemented`/`ready` 聚合结果显示依赖状态。未探测、探测失败或任一
  声明能力未就绪时均 fail closed 为 `Setup required`，成功挂载不再等同于依赖就绪。
- 需要进入 App 的文件：
  - `ai2apps/web/static/js/studio_mini_apps.js`
  - `ai2apps/web/static/js/readaloud.js`
  - `ai2apps/web/static/js/video_studio.js`
  - `ai2apps/web/templates/system_apps/readaloud.html`
  - `ai2apps/web/templates/system_apps/video_studio.html`
  - `ai2apps/web/templates/system_apps/imagine_studio.html`
  - `tests/test_ai2apps_studio_mini_app_client.py`
- 当前验证：Read Aloud、Video Studio、Studio Mini-App Client 与 Capability Broker 联合回归
  `27/27` 通过；三个 JavaScript 文件语法检查和 `git diff --check` 通过。固定
  `AI2Apps-App-Dev` 强制刷新并重新挂载 Audio Speaker Voice Replacement 后，页面内继续提示
  Detailed Transcription、MLX Demucs 和 MLX Seed-VC v2 尚未齐备，底部徽标同步显示
  `Setup required`，不再显示 `Dependencies ready`。
- 纳入 Build：待定。

### NXR-037：Studio/Mini-App 通用 ACPF Setup 按钮

- 状态：`ready`
- 类型：App-Shell、ACPF、Studio Package Mini-App 开发合同
- 用户可见结果：Read Aloud、Video Studio 与 Imagine Studio 的依赖徽标已统一为按钮；Package Mini-App 的
  `Setup required` 点击后直接进入 ACPF Profile 选择，不再要求用户离开 Studio 手工寻找模型。
  内置 Mini-App 同样沿用各 Studio 既有 ACPF 配置流程。
- 通用机制：共享 Studio Mini-App Client 从签名/校验后的 Mini-App requirements 读取主
  Capability，并以当前可信 Studio AppInstance 调用 ACPF。Package 只能声明语义能力，具体
  Runtime、Service Package、Checkpoint、版本和验证目标由 Host 内置 Profile 决定。Profile
  Registry 新增一个受信任 Profile 服务多个 Studio App ID 的兼容能力。
- 重启恢复修复（2026-09-07）：共享 Client 现在持久化最小化的 Mini-App 恢复上下文，并按
  `actionId=setup-mini-app` 区分 Package 配置与 Studio 内置模型配置。Runtime/Local 重启后，
  Read Aloud、Video Studio、Imagine Studio 会优先恢复原 ACPF Session、重新挂载发起配置的
  Mini-App，然后继续 Provider/Checkpoint 安装和 Readiness Probe；旧 Session 仍可按语义
  Capability 反推出来源 Mini-App。
- 真实旧 Session 修复（2026-09-07）：App-Dev Session
  `prv_fb601554b22f48dc82e47006aab6595d` 显示 Runtime 重启后的实际阻塞并非 Session 丢失，
  而是已发布的 `ai2apps/model-demucs-mlx 0.1.0` 在读取客户端版本上限绑定的 legacy
  `modelInstall` 之前被新制品校验提前拒绝；同时服务端 Session 列表没有返回带 return intent
  的 retryable failed Session。合同现仅对客户端内置白名单及其固定最高版本保留兼容，新的
  模型 Release 仍强制签名 `modelInstall`；服务端现在允许原 AppInstance 重新发现可重试失败。
  修复后精确重启 `app-dev` Local，刷新即恢复原“配置指定角色换声”面板；点击重试后三个模型
  Package 均通过校验并 finalizing，流程继续到 55% Sortformer Checkpoint 的 NVIDIA 许可确认页。
- Media Voice Profile：详细转写提供 Compact/Quality；音轨分离配置 MLX Demucs；音频和视频
  角色换声一次规划 oMLX Runtime、Detailed Transcription、MLX Demucs、MLX Seed-VC v2 及
  所需 Checkpoint/Service 验证；视频字幕配置详细转写，翻译作为可选 Capability 不阻断基础
  字幕工作流。探测失败继续 fail closed。
- ACPF 进度可读性与全量状态刷新（2026-09-07）：相同阶段、相同标题的组件合并为一行，
  例如 `下载所需模型 ×5`、`安装模型 Package ×3`，具体 Package/模型可按需展开；每组明确显示
  `已完成`、`进行中`、`失败` 或 `待处理`。运行对话框改为固定标题、固定底部总进度和操作按钮，
  只有中间步骤区域滚动。平台新增经过 Studio AppInstance 授权的批量 Capability Catalog Probe，
  Read Aloud、Video Studio、Imagine Studio 在目录加载、ACPF 恢复及安装完成后一次重算所有已安装
  Package Mini-App 的 readiness，不再只更新当前挂载项；旧 mount-bound Probe 与旧 Package 发现、
  安装机制保持兼容。
- 需要进入 App 的文件：
  - `ai2apps/provisioning/profiles.py`
  - `ai2apps/provisioning/profiles/studio-media-voice.yaml`
  - `ai2apps/api/studio_mini_apps.py`
  - `ai2apps/studio/capability_broker.py`
  - `ai2apps/web/static/js/capability_provisioning.js`
  - `ai2apps/web/static/js/studio_mini_apps.js`
  - `ai2apps/web/static/js/readaloud.js`
  - `ai2apps/web/static/js/video_studio.js`
  - `ai2apps/web/static/js/imagine_studio.js`
  - `ai2apps/web/static/css/capability_provisioning.css`
  - `ai2apps/web/static/css/readaloud.css`
  - `ai2apps/web/static/css/video_studio.css`
  - `ai2apps/web/templates/system_apps/readaloud.html`
  - `ai2apps/web/templates/system_apps/video_studio.html`
  - `ai2apps/web/templates/system_apps/imagine_studio.html`
  - `packages/ai2apps-media-voice-studio-suite/app.yaml`
  - `tests/test_ai2apps_provisioning.py`
  - `tests/test_ai2apps_studio_capability_broker.py`
  - `tests/test_ai2apps_studio_mini_app_client.py`
- 当前验证：Package Discovery、Provisioning、Capability Broker、Studio Client、Read Aloud、Video Studio、Imagine Studio、Media
  Voice Package 与 Development Package 联合回归 `123/123` 通过；关键 Ruff、五个 JavaScript
  文件语法和 `git diff --check` 通过。固定 App-Dev Local 已单独重启至端口 `62551`，普通
  `dev` 实例未改动。Read Aloud 重新加载带 cache-buster 的共享 Client 后，Detailed
  Transcription、Voice and Background Separation、Audio/Video Speaker Voice Replacement
  四项 Package Mini-App 在左侧列表同时显示完成标记；逐项切换确认底部均为
  `Dependencies ready`，说明一次 Catalog Probe 已更新整列状态。ACPF 的聚合函数、四态标记、
  固定头尾与仅中部滚动结构已有自动回归覆盖；当前真实音频依赖已全部就绪，因此未为视觉验证
  人为卸载 Package 或 Checkpoint。
- 纳入 Build：待定。

### NXR-001：Package 多源竞速、分片校验与断点续传

- 状态：`ready`
- 类型：客户端功能、下载可靠性、ACPF/Discover 共用基础设施
- 用户可见结果：Package/Runtime 安装可读取签名 Snapshot 中任意数量的
  `artifact.sources`，按 piece 并发竞速，坏源或停滞源不会阻塞其他源；支持校验后断点
  续传，并保留旧单源完整下载兼容。
- 需要进入 App 的文件：
  - `ai2apps/packages/registry.py`
  - `ai2apps/api/packages.py`
  - `ai2apps/provisioning/orchestrator.py`
- 发行测试：
  - `tests/test_ai2apps_registry_v1.py`
  - `tests/test_ai2apps_provisioning.py`
- 已完成验证：相关 pytest `63/63` 通过；Ruff 通过；生产 Cloud 单源 Range fixture
  piece hash 匹配；旧单源 fallback 测试通过。
- Cloud 依赖进展（2026-09-03）：ModelScope `HEAD` 缺少 `Content-Length` 的严格
  `GET bytes=0-0` 回退已经部署生产；Cloud 使用生产校验器完成 457,410,846 字节制品、
  全量 SHA-256、piece manifest 与 Range 预检，265/265 测试通过。此项只解除服务端
  校验兼容阻塞，不代表外部 Source 已进入匿名 Snapshot。
- Source 发布进展（2026-09-03）：GitHub Source 已由 step-up admin 正式激活；公共
  Repository Snapshot v101 已匿名确认发布 Cloud + GitHub。ModelScope 正式复验的新
  validation 已完整通过；Cloud 状态转换热修上线后，该 Source 已由 step-up admin 正式
  激活。公共 Snapshot v102 的签名和 pin 验证通过，匿名清单已包含 Cloud、ModelScope、
  GitHub 三源；三个源的首个 8 MiB Range 均返回 `206`，大小和 piece SHA-256 完全一致。
- 客户端生产实测（2026-09-03）：使用当前客户端实现从公共 Snapshot v102 下载
  `ai2apps/runtime-omlx 1.5.7`，55 个分片全部完成，Cloud 与 GitHub 均实际成为过竞速
  胜出源；最终文件大小为 457,410,846 字节，完整 SHA-256 为
  `b7f5e0bddcf285908ddd75465c02bdd35a9f6aa90690c739054a75295ea4bd49`，与签名清单一致。
  ModelScope 本次因速度未胜出，但其独立 Range 206 和分片摘要验证已经通过。
- 后续 UI 复验发现客户端为每个 Range 请求发送了并非源站真实 ETag 的合成
  `If-Range: "sha256-…"`。ModelScope CDN 因条件不匹配按 HTTP 规范退回完整 `200`，
  因而在客户端竞速中被淘汰；GitHub 返回 `206` 掩盖了该问题。客户端已移除合成
  `If-Range`，继续以不可变 Source URL、精确 `Content-Range`、分片 SHA-256 和最终
  完整 SHA-256 为校验边界。
- 全新隔离 Dev App UI 验收（2026-09-03）：从零安装 `ai2apps/runtime-omlx 1.5.7`；
  ModelScope CDN 实际返回 `206 Partial Content`，并实际成为部分 piece 的竞速胜出源；
  Runtime 完成后自动进入重启、Package、Checkpoint、验证和启动流程，最终
  Provisioning Session 为 `ready / 100%`，Qwen3.8 27B NVFP4 已在 Chat 中连续完成两次
  本地推理。
- 客户端专项测试（2026-09-03）：Registry 与 Provisioning 共 63 项测试通过，覆盖多源
  竞速、超过并发数的候选源、停滞源淘汰、坏源回退、已验证分片断点恢复和旧单源兼容。
- 客户端全量回归（2026-09-03）：已将 App Catalog、Checkpoint 进度回调、Chat/Fusion
  UI、FLUX.2 4B 发布范围、Local Session 认证、Knowledge Service、Runtime 1.5.7 与
  Browser Agent 无 Dock 行为的旧测试断言同步到当前合同；AI2Apps Python `1146/1146`
  与 Swift `69/69` 通过。
- Build 2249 对照：直接检查 Build 2249 已公证 DMG 内嵌
  `AI2AppsLocal/app/ai2apps`，上述三项客户端实现未包含在 2249 中。
- 源码可复现性（2026-09-03）：`ai2apps/provisioning/orchestrator.py` 与
  `tests/test_ai2apps_provisioning.py` 已随本轮 development checkpoint 纳入版本控制，不再
  依赖 dirty-tree 隐式打包。
- 发行验证：全新隔离 Dev App 的 UI 安装与本地模型推理验收已完成。
- Release notes 建议：Package 与 Runtime 下载现支持多源竞速、逐分片完整性校验和断点
  续传；单个镜像不可用时可自动由其他镜像继续。
- 纳入 Build：待定。

### NXR-002：ACPF 安全复用用户已有 Hugging Face Checkpoint

- 状态：`ready`
- 类型：客户端功能、模型安装、磁盘与网络复用
- 用户可见结果：ACPF 在实例私有缓存未命中时，会只读检查当前 macOS 用户的标准
  Hugging Face Hub 缓存；若存在 Package 固定的 repo/revision，则仍按 Cloud 签名的
  Checkpoint Distribution 清单逐文件校验大小与 SHA-256，校验通过后纳入 AI2Apps 的
  私有安全缓存，不再重复下载模型权重。
- 安全边界：`HF_HOME`、Token、Worker 缓存及可变状态继续保持实例隔离；外部 Hub
  仅作为候选输入，不能绕过许可确认、签名清单、固定 revision 或完整哈希校验。
- 需要进入 App 的文件：
  - `apps/ai2apps-acefox/Sources/AI2AppsContracts/InstanceIdentity.swift`
  - `apps/ai2apps-acefox/Sources/AI2AppsSupervisorCore/LaunchPlan.swift`
  - `ai2apps/packages/supervisor.py`
  - `ai2apps/model_installer.py`
- 发行测试：
  - `apps/ai2apps-acefox/Tests/AI2AppsSupervisorCoreTests/SupervisorCoreTests.swift`
  - `tests/test_ai2apps_installer.py`
  - 全新隔离 Dev App 从 ACPF 安装 Qwen3.8 27B NVFP4；Runtime/Package 从零安装，
    Checkpoint 必须命中现有全局 HF cache 并完成校验导入，不得产生 21.83 GB 网络下载。
- 当前验证（2026-09-03）：重新构建的全新隔离 Dev App 从零完成 Runtime 与 Package
  安装；Checkpoint 阶段识别标准 Hugging Face Hub 缓存中的固定
  `unsloth/Qwen3.8-27B-NVFP4@16b6615a…`，仅访问 Cloud 签名 Distribution 清单，未产生
  21.83 GB 模型文件网络请求；逐文件校验及私有缓存导入完成，Provisioning Session 为
  `ready / 100%`，Chat 中本地模型连续两次返回 `OK`。
- 纳入 Build：待定。

### NXR-003：Local 重启后去重 ACPF 进度对话框

- 状态：`ready`
- 类型：客户端 UI、ACPF 状态恢复
- 用户可见问题：ACPF 安装 Runtime 后按提示重启 Local，恢复中的同一 Provisioning
  Session 会短暂显示两份内容相同的进度对话框；任务完成后两份都会消失，不影响安装
  或模型启动，但会造成重复反馈。
- 复现结果（2026-09-03）：全新隔离 Dev App 安装 Qwen3.8 27B NVFP4 时稳定复现一次。
- 根因与修复（2026-09-03）：Chat 的 Alpine `x-data` 对象包含自动执行的 `init()`，
  模板又通过 `x-init="init()"` 显式执行一次，导致重连后两次调用 ACPF `resume()`；已移除
  Chat 的重复显式初始化，并在 ACPF 公共库中增加跨调用的 Session-ID runner 注册表，
  重复 `resume/ensure` 共享同一 Promise、poller 和 overlay，终态后自动释放。
- 自动化验证：JavaScript 语法检查通过；Provisioning 与 Shell 合同测试 `142/142`
  通过；`git diff --check` 通过。
- UI 验收（2026-09-03）：使用 clean2 隔离实例将已备份 Session 临时恢复为待处理状态，
  通过认证 Helper 控制通道真实重启 Local，端口从 `60296` 切换至 `60581`；重启前后
  同一 Session 均只显示一个对话框。验收后已精确恢复该 Session 的原始 `ready / 100%`
  状态，未改动 Runtime、Package、Checkpoint 或全局 Hugging Face 缓存。
- 纳入 Build：待定。

### NXR-004：托盘 Helper 复用并激活对应 AI2Apps 实例

- 状态：`ready`
- 类型：客户端可靠性、Helper、实例生命周期
- 用户可见问题：从托盘选择“打开 AI2Apps”时，如果正在运行的开发版 App 在重新打包后
  被移动到归档路径，Helper 的严格路径校验会把同一实例误判为不存在，并尝试再启动一个
  AI2Apps App 实例。
- 修复方向：继续以 `run/shell.json` 的实例 ID 和 PID 为首选定位；严格路径校验未通过时，
  仅允许同一 Shell bundle ID、同一主 App bundle ID、同一 `AI2AppsInstanceID` 且实时
  可执行文件与其实际 Bundle 一致的存活进程作为激活回退。找不到可信对应进程时才启动
  新实例。
- 需要进入 App 的文件：
  - `apps/ai2apps-acefox/Sources/AI2AppsHelper/main.swift`
  - `apps/ai2apps-acefox/Sources/AI2AppsSupervisorCore/ShellProcessIdentityValidator.swift`
- 发行测试：
  - `apps/ai2apps-acefox/Tests/AI2AppsSupervisorCoreTests/ShellProcessIdentityValidatorTests.swift`
  - 对已被开发构建脚本移动到 `.build/archive/` 的运行实例执行托盘“打开 AI2Apps”，确认
    只激活原 PID，不产生第二个 Shell 进程。
- 当前验证（2026-09-03）：Swift `71/71` 通过；真实开发实例 PID `54855` 的
  `proc_pidpath` 已处于 `.build/archive/AI2Apps-dev-20260903-120936.app`，而
  `run/shell.json` 仍指向稳定的 `.build/AI2Apps-dev.app`，严格路径校验按预期失败；新回退
  校验确认该进程的 Shell bundle ID、主 App bundle ID、`AI2AppsInstanceID=dev` 与实际
  Bundle 可执行文件全部一致。修复后的 Helper 已从稳定开发 App 启动，当前 dev 实例仍仅有
  一个 Shell 进程。
- Release notes 建议：托盘“打开 AI2Apps”现在会可靠激活当前 Helper 对应的已有窗口，
  仅在该实例确实未运行时才启动新窗口。
- 纳入 Build：待定。

### NXR-005：账户密码最小长度统一为 8 位

- 状态：`ready`
- 类型：客户端兼容性、账户安全策略、Cloud 合同对齐
- 用户可见结果：注册、登录、密码重置以及管理员、设备和组织操作中的密码再认证统一接受
  8–128 个 UTF-8 字节的密码；7 字节密码仍会被拒绝。客户端与 Cloud 对中文、emoji 等
  非 ASCII 密码使用相同计数方式。
- 安全边界：不改变密码哈希、密钥存储、验证码、速率限制、权限检查或 step-up 有效期。
- 需要进入 App 的文件：
  - `ai2apps/password_policy.py`
  - `ai2apps/api/auth.py`
  - `ai2apps/api/cloud.py`
  - `ai2apps/api/packages.py`
  - `ai2apps/api/upstreams.py`
  - `ai2apps/web/templates/login.html`
  - `ai2apps/web/templates/system_apps/account.html`
  - `ai2apps/web/templates/system_apps/discover.html`
  - `ai2apps/web/static/js/discover.js`
  - `ai2apps/web/i18n/en.json`
  - `ai2apps/web/i18n/zh.json`
- Cloud 生产依赖（2026-09-03）：以实际生产 `1.39.0` 为基线完成同步发布，OpenAPI
  升至 `1.40.0`；主线提交 `f2032b1b19add0aa4d8dd0d219c86a3df436e6f1`，生产端口
  `3246`，容器 healthy、零重启。Node 24 干净容器全量测试 `273/273`，Trivy
  High/Critical 为 0，无数据库迁移，生产仍为 47 个迁移；7/8 字节边界、登录、管理员
  二次验证、owner reauth、公开合同与权限边界验收通过。旧容器和数据库/Nginx 备份已
  保留为回滚点。完整回执：
  `/Users/avdpropang/sdk/ai2apps-cloud/docs/account-password-policy-production-deployment-2026-09-03.md`。
- 发行测试：`tests/test_ai2apps_password_policy.py`，以及 Account、Local Auth、Cloud API、
  Package 和 Upstream 相关回归测试。
- 客户端验证（2026-09-03）：密码策略边界测试 `16/16`，包含 13 个请求模型的 OpenAPI
  长度合同、8 字节注册/登录成功、7 字节拒绝和非 ASCII UTF-8 边界；Account、Local Auth、Upstream、Package、
  Shell 相关回归合计 `169/169` 通过。Ruff、JavaScript 语法与 `git diff --check` 通过。
  首轮沙箱内 Package 回归有 8 项因禁止绑定临时回环端口失败，在允许本机 loopback bind
  后独立重跑 `30/30` 通过；旧管理员测试收集时的 MLX Metal 初始化 abort 属于无 GPU
  沙箱限制，不是本项断言失败。
- 纳入 Build：待定。

### NXR-006：固定且隔离的 App-Shell App 开发环境

- 状态：`ready`
- 类型：开发构建基础设施；不改变生产 App 的默认构建参数或运行行为。
- 开发结果：新增固定的 `AI2Apps-App-Dev` 环境，使用
  `.build/AI2Apps-app-dev.app`、Bundle ID `com.ai2apps.desktop.appdev` 和实例
  `app-dev`；它可与通用 `AI2Apps-dev.app`/`dev` 实例同时运行。
- 隔离边界：App Dev 构建内嵌 `cloud` Runtime、`omlx` 与依赖快照，不引用仓库
  `.venv`；受信任的 `ai2apps` 源码从当前工作树热挂载，日常 HTML/CSS/JavaScript 修改刷新
  页面即可生效，Python App/API 修改只需重启 Local。`omlx` 与依赖始终锁定到 Bundle，且
  Local 启动计划会剥离继承环境中的源码路径，只接受 Development Helper 从签名 Bundle
  合同显式注入。数据库、配置、日志、Cookie、浏览器 Profile、端口和缓存继续按实例隔离；
  不注册 Login Item，不读取生产更新清单。
- 托盘辨识：`app-dev` Helper 的普通、工作中、可更新和更新就绪图标均在标准图标左上角
  增加橙色圆点；生产 App 与通用 `AI2Apps-dev.app` 保持原图标。2026-09-03 重建后确认 Bundle
  内四个 SVG 均只包含一个开发圆点、XML 有效，严格签名验证通过；新 App 冷启动后 Helper、
  Shell 和 Local 已就绪，Local 端口为 `63716`。
- Shell 辨识：固定构建把主 App、AceFox Shell 及其所有本地化 Bundle 名称统一设置为
  `AI2Apps-App-Dev`；若上游 Shell `Info.plist` 不含 `CFBundleDisplayName`，构建时会显式补建，
  使 macOS 左上角应用名称不再回退为 `AI2Apps`。2026-09-03 最终 Bundle 已确认主 App 与
  Shell 的 `CFBundleName`/`CFBundleDisplayName` 以及本地化名称全部一致，严格签名验证通过；
  冷启动后 Helper、Shell、Local 均正常就绪，Local 端口为 `64163`。
- Shell 标题快照修复：定位到 packaged AceFox 的 `browser/omni.ja` 落后于通用 Dev App
  使用的当前 `shell.mjs`，旧快照没有 Local-aware 标题函数。App Dev 构建现在只在
  Development 模式下把匹配 AceFox 工作树中的当前 Shell 资源覆盖进 staged
  `browser/omni.ja`，并将标题前缀设置为 `AI2Apps-App-Dev`；生产构建默认不启用覆盖。最终
  Bundle 解包确认包含 Local-aware 标题函数及目标前缀，严格签名验证通过；真实 UI 冷启动
  验收的窗口标题为 `AI2Apps-App-Dev: MacIntel · AI2Apps 127.0.0.1:65050`，macOS 应用菜单名
  同时为 `AI2Apps-App-Dev`。
- 需要进入 App 的文件：
  - `apps/ai2apps-acefox/scripts/build-release-app.sh`
  - `apps/ai2apps-acefox/scripts/build-app-dev-environment.sh`
  - `apps/ai2apps-acefox/scripts/runtime-entrypoint.sh`
  - `apps/ai2apps-acefox/Sources/AI2AppsHelper/main.swift`
  - `apps/ai2apps-acefox/Sources/AI2AppsSupervisorCore/LaunchPlan.swift`
  - `apps/ai2apps-acefox/Sources/AI2AppsSupervisorCore/LocalProcessSupervisor.swift`
  - `apps/ai2apps-acefox/Tests/AI2AppsSupervisorCoreTests/SupervisorCoreTests.swift`
  - `apps/ai2apps-acefox/README.md`
  - `docs/ai2apps-app-dev-environment.md`
- 验证（2026-09-03）：Shell 脚本语法和 `git diff --check` 通过；最终构建通过
  `verify-release-app.sh` 和 `codesign --verify --deep --strict`。最终 Bundle 确认显示名为
  `AI2Apps-App-Dev`、Bundle ID 为 `com.ai2apps.desktop.appdev`、实例为 `app-dev`、
  Development 标记为 true、Runtime profile 为 `cloud`，且不存在生产 Update Manifest
  URL。最终 Bundle 冷启动后 `app-dev` Helper/Local/Shell 分别使用独立 PID，Local 就绪于
  自动端口 `63219`，运行描述指向固定 App 路径。
- 热挂载验证：Swift 全量 `72/72` 通过，新增测试确认未授权继承环境不能注入开发源码目录；
  使用内嵌 Python 验证 `ai2apps.__file__` 指向当前仓库、`omlx.__file__` 指向 App Bundle。
  Jinja 模板目录与静态资源目录均解析到当前仓库，且模板环境 `auto_reload=true`。
  在 Bundle 构建完成后向仓库新增静态探针，运行中的 Local 立即返回探针内容；删除后同一
  URL 立即返回 `404`，证明静态资源无需重建或重启即可刷新生效。
- 纳入 Build：不适用；这是本地开发环境入口，生产构建保持原默认值。

### NXR-007：Chat 显式控制 Knowledge 上下文

- 状态：`ready`
- 界面精简（2026-09-10）：删除 Chat 左侧对话列表底部重复的 Settings 按钮及空页脚，保留右侧 Settings 入口；新增单一设置入口回归断言。
- 推理署名（2026-09-10）：左下角新增低对比度说明，最终文案为“AI2Apps local inference built on oMLX”／“AI2Apps 本地推理，基于 oMLX 构建”，替换 powered by 以明确基础与扩展开发关系；明确限于本地推理以免误指 Cloud Provider。覆盖全部 9 种语言，保留右侧唯一 Settings 入口。
- 类型：客户端 UI、Chat 上下文控制、Knowledge Mini-Entry
- 用户可见结果：Chat 右侧选项栏的 Thinking 区块新增“使用 Knowledge”开关；关闭后，
  当前 Chat 的普通模型回复和 Agent Run 均跳过 Knowledge 检索。右侧展开箭头可直接打开
  Knowledge 侧边栏，并优先复用当前对话中已经存在的 Knowledge Mini-Entry。Thinking 与
  Use Knowledge 标题下的辅助说明暂时隐藏，以保持右侧设置栏紧凑。Chat 顶部的 App
  Mini-Entry 选择器只展示实际声明了 Mini-Entry 的 App，不再列出无法嵌入对话的 App。
- 状态边界：开关按 Chat 保存并同步到后端 Session metadata；新建及旧版未记录该字段的
  Chat 默认关闭（2026-09-10 调整），已保存的显式开关状态保持不变，分支 Chat 继承来源 Chat 的选择。开关只控制是否检索，不会
  删除或改写用户已经选择的知识桶。
- 需要进入 App 的文件：
  - `ai2apps/web/templates/chat.html`
  - `ai2apps/web/i18n/*.json`
  - `tests/test_chat_ui_overhaul.py`
- 验证（2026-09-03）：Chat UI、Shell、Knowledge、附件和工具调用相关测试共 208 项中
  207 项通过；唯一失败是既有 `chat.model_tab` 静态断言，与本项改动无关。专项的
  Knowledge 开关、全语言文案和右侧栏回归测试通过；补充验证空白新 Chat 尚未生成
  Session 时也可直接挂载 Knowledge Mini-Entry。固定 `AI2Apps-app-dev.app` 已刷新并在
  实机窗口确认开关可切换、右箭头可打开 Knowledge 侧边栏；`git diff --check` 通过。
- Release notes 建议：Chat 现在可以按对话显式开启或关闭 Knowledge，并可从 Thinking
  设置一键打开 Knowledge 侧边栏管理参与回答的知识桶。
- 纳入 Build：待定。

### NXR-008：Base App 恢复 Runtime-backed Audio API

- 状态：`ready`
- 类型：客户端回归修复、Audio Package Gateway、Chat TTS
- 用户可见问题：使用 `cloud` Runtime profile 的 inference-free Base App 安装并准备好
  TTS Runtime、模型 Package 和 Checkpoint 后，Chat 的“朗读”仍返回裸
  `404 Not Found`。
- 根因（2026-09-04）：`omlx.server` 为避免启动时导入 MLX，在 `cloud` profile 下跳过了
  整个 `audio_routes`；这同时误删了本应由 Base App 保留并代理到独立 Runtime Worker 的
  `/v1/audio/*` Package Provider Gateway。请求未进入已 ready 的 TTS Worker。
- 相关问题：Chat 会保留或自动选择 `checkpoint_ready=false` 的音频模型。本次实际准备的是
  Qwen3-TTS CustomVoice 8-bit，但界面选择了尚未准备的 Base 5-bit。
- 修复方向：将旧进程内音频引擎的 MLX/PCM import 保持为按需加载，在 Base App 中始终注册
  OpenAI-compatible Audio Router；Chat 自动选择模型时优先使用已经准备好的 checkpoint。
- 需要进入 App 的文件：
  - `omlx/server.py`
  - `omlx/api/audio_routes.py`
  - `ai2apps/web/templates/chat.html`
  - `tests/test_cloud_runtime_profile.py`
  - `tests/test_ai2apps_audio_packages.py`
- Cloud 边界：Base App 对未匹配到已安装 Package 的旧进程内音频模型明确返回 `503`，
  不再尝试导入 MLX；Runtime-backed Package 请求仍在此判断前正常路由。
- 自动化验证（2026-09-04）：Cloud profile 无 MLX import、Audio Router 注册、未知模型
  边界与 Chat 就绪模型选择合同共 `14/14` 通过；TTS、STT、STS 与 Voice 完整 Audio 回归
  `154/154` 通过（另有 6 项按测试配置 deselected）；`git diff --check` 通过。
- 实机验证（2026-09-04）：固定 `AI2Apps-app-dev.app` 完成重建与严格 Bundle 验证，Local
  就绪于端口 `61817`。Chat 自动选择已准备的 `Qwen3 TTS 1.7B CustomVoice 8-bit`，朗读
  正常开始并结束；Base App 向端口 `61844` 的 TTS Runtime Worker 连续两次发送
  `/v1/audio/speech`，均返回 `200 OK`。未知非 Package 模型探针返回预期 `503`。
- Voice 配置显示与偏好修复（2026-09-04）：原生 `<select>` 不再保留通过 `x-show` 隐藏的
  “Not supported”占位选项，动态创建的 TTS、角色与 Emotion 选项显式同步当前值；支持
  Emotion 的模型会显示真实选择。角色、速度和 Emotion 现在按 TTS 模型记住上次选择，
  没有历史偏好时分别使用首个可用角色、速度 `1` 与自然的 `neutral`。固定 app-dev 热加载
  实机确认 CustomVoice 显示名不再错位，Emotion 从错误的 “Not supported”恢复为
  `neutral`，选择 `happy` 后刷新仍为 `happy`。偏好同时写入实例专属浏览器 Profile 的
  loopback Cookie，在 Local 端口变化后仍可恢复；不同实例的 Profile 继续保持隔离。
- ASR 转写修复（2026-09-04）：Qwen3-ASR Runtime 1.5.7 在请求未指定 `max_tokens` 时仍向
  后端显式传入 `None`，覆盖模型自带的 `8192` 默认值并触发 `NoneType` 与整数比较错误。
  修正后的 Runtime Adapter 会省略未设置的可选参数，STT Engine 也会防御性过滤 `None`；
  Base App Gateway 对已安装的 Qwen3-ASR 1.5.7 临时补入其原生默认值，因此用户无需等待
  新 Runtime Package 发布即可恢复识别。Adapter 与 Package Gateway 专项测试 `25/25`
  通过，`git diff --check` 通过。首次只重启 Local 后实机仍复现，进一步确认 app-dev 只热挂载
  `ai2apps`，`omlx` 固定来自 Bundle，因而 Base Gateway 修复并未加载；随后已重建并严格
  签名验证固定 `AI2Apps-app-dev.app`，确认三处修复均已嵌入，切换到新 Bundle 的 Helper
  PID `10642` 后再次通过认证控制通道重启 Local。新 Local PID `10895`、端口 `53492`、
  状态 `ready`。完整旧进程内 STT 测试在当前无 Metal 设备的沙箱中无法运行，没有将该
  环境限制误记为产品失败。
- 开发 Build（2026-09-04）：通用 `AI2Apps-dev.app` 与固定 `AI2Apps-app-dev.app` 均已按
  各自规定脚本完成包含跨端口 Voice 偏好持久化修复的最终重建，签名验证后替换稳定路径，
  旧 Bundle 已归档；重启后 `dev` 与 `app-dev` 分别在独立 Local 端口 `65132`、`65117`
  ready。
- Release notes 建议：修复安装本地语音模型后 Chat 朗读仍显示 `Not Found` 的问题。
- 纳入 Build：`AI2Apps-dev.app`、`AI2Apps-app-dev.app`。

### NXR-009：Chat 右侧栏状态持久化

- 状态：`ready`
- 类型：客户端 UI 回归修复、Chat 工作区偏好。
- 用户可见问题：用户打开或关闭 Chat 右侧设置栏后刷新页面，界面会重新使用窗口宽度
  推导的默认状态，丢失用户刚才的选择。
- 修复（2026-09-04）：Chat 初始化时优先恢复当前浏览器 Profile 保存的右侧栏展开状态，
  每次切换后立即更新；没有历史状态时才继续使用原有的响应式默认值。偏好同时写入
  `localStorage` 和同 Profile 的 loopback Cookie，因此页面刷新以及 Local 端口变化后均可
  恢复；Terminal 内嵌 Chat 仍强制隐藏侧栏，且不会覆盖普通 Chat 的偏好。
- 需要进入 App 的文件：
  - `ai2apps/web/templates/chat.html`
  - `tests/test_chat_ui_overhaul.py`
- 验证（2026-09-04）：Chat UI 与 Shell 专项回归 `134/134` 通过，覆盖保存、恢复、
  跨端口 Cookie 与 Terminal 隔离；固定 `AI2Apps-app-dev.app` 实机先后确认“关闭后刷新仍
  关闭”和“打开后刷新仍展开”，`git diff --check` 通过。
- Release notes 建议：Chat 会记住右侧设置栏的展开或关闭状态。
- 纳入 Build：待定。

### NXR-010：Discover 模型一级分类与能力子分类

- 状态：`ready`
- 类型：客户端功能、Discover UI、Package 构建合同、Cloud Registry 查询合同。
- 用户可见结果：Discover 将模型从普通 Service 中独立出来，并提供文本、语音、多模态、
  图像、视频和向量子分类；语音分类继续按“全部语音 / TTS 语音合成 / ASR 语音识别”筛选，
  模型卡片直接显示 TTS 或 ASR 任务标签，并显示模型大小、最低内存、速度、能力及评分来源。
  模型安装会先选择具体模型配置，再通过持久化 ACPF Session 安装依赖与 Provider Package、
  下载 Checkpoint、处理许可确认并验证服务；“仅安装 Package”保留为详情页高级入口。
- 旧包兼容：客户端内置按 Package ID 和最高旧版本约束的对照表，当前已发布模型无需重建或
  重新发布；同一 Package 的下一版本以及新的模型 Package 必须在签名 `ai2apps.json` 声明
  `discovery.kind/categories/tasks`、完整 `modelProfile` 和 ACPF 安装索引 `modelInstall`。旧资料
  明确标为估算，新版本不会继承旧模型的大小、评分或安装索引。
- 需要进入 App 的文件：
  - `ai2apps/packages/discovery.py`
  - `ai2apps/packages/contract_v1.py`
  - `ai2apps/packages/registry.py`
  - `ai2apps/api/packages.py`
  - `ai2apps/provisioning/orchestrator.py`
  - `ai2apps/web/static/js/capability_provisioning.js`
  - `ai2apps/web/static/js/discover.js`
  - `ai2apps/web/templates/system_apps/discover.html`
  - `ai2apps/web/i18n/en.json`
  - `ai2apps/web/i18n/zh.json`
- Cloud 依赖：`docs/cloud-discover-model-categories-requirements.md` 与
  `docs/ai2apps-cloud-package-discovery-schema-requirements.md`；客户端在 Cloud 支持服务端
  过滤前提供最多 100 个 Service 结果的兼容过滤，完整分页验收后方可改为 `ready`。
- 文档与测试：`docs/model-worker-package-manual.md`、
  `tests/test_ai2apps_discover_categories.py`。
- 当前验证：Package 合同、旧版本映射完整性、下一版本强制声明、非模型 Service 防冒充、
  目录模型/普通 Service 分离、Audio Package、Model Provider 及 Registry 回归 `82/82`
  通过；Ruff、JavaScript 语法、i18n JSON 和 `git diff --check` 通过。固定 App Dev 完整
  重启后 Local 端口从 `59995` 更新为 `60762`，实机确认 Discover 出现“模型”一级分类及
  全部模型、文本、语音、多模态、绘图、视频、嵌入二级分类；“语音”筛选只展示对应模型，
  模型卡片正确显示 `MODEL` 与 `SPEECH` 标识。仅重启旧 Helper 管理的 Local 会继续使用
  Bundle 内快照；完整退出并重开固定 `AI2Apps-app-dev.app` 后源码热挂载正常生效。随后在
  Local 端口 `61759` 实机确认语音任务栏及卡片 TTS/ASR 标签；选择 TTS 后仅保留 Fish
  Audio、CosyVoice、Qwen TTS、VibeVoice 等语音合成模型。模型资料合同进一步覆盖现有
  28 个模型的版本受限估算映射、正整数大小/内存、1–5 评分和基准来源；专项测试 `11/11`
  通过，相关回归 `86/86` 通过。Local 端口 `64151` 实机确认模型卡片以两列紧凑指标显示
  大小、内存、速度、能力，并把旧表数据明确标记为“估算”；普通 Service 卡片不显示指标。
  Discover 模型安装改造后的 Package 合同、Registry API、ACPF 编排、Audio Package 与 Model
  Provider 联合回归 `123/123` 通过，Ruff、JavaScript 语法及 `git diff --check` 通过；固定 App
  Dev 完整重开后 Local 端口为 `57310`，原生窗口标题、`app-dev` 隔离身份和模型安装 API 路由
  均已核验，模型卡片按钮显示为 `Install model`。实机没有触发真实 Package 或 Checkpoint 下载。
- Release notes 建议：Discover 新增独立模型目录，可按文本、语音、多模态、图像、视频和
  向量能力快速筛选，并可直接比较大小、内存、速度和能力；现有模型无需重新安装。
- 纳入 Build：待定。

### NXR-011：Video Studio Phase 1.1 Shell 与 Run 工作区

- 状态：`in_progress`
- 类型：客户端 UI、Video Studio、任务恢复与重试。
- 用户可见结果：Video Studio 统一使用 Mini-App 术语；文生、图生和参考素材入口在切换时
  保留各自草稿；左右栏可折叠并在窄窗口中作为抽屉打开；生成结果栏显示当前 Run、执行
  步骤、模型 revision 和历史记录，失败、取消或过期的 Run 可从服务端冻结输入安全重试。
- 状态边界：Run 与历史继续以服务端持久任务为事实来源；`localStorage` 只保存当前
  Mini-App、左栏模式、折叠状态和所选 Run 等 Shell 展示偏好，不保存 Prompt 或媒体正文。
- 需要进入 App 的文件：
  - `ai2apps/api/video_studio.py`
  - `ai2apps/video/tasks.py`
  - `ai2apps/web/templates/system_apps/video_studio.html`
  - `ai2apps/web/static/js/video_studio.js`
  - `ai2apps/web/static/css/video_studio.css`
  - `ai2apps/web/i18n/en.json`
  - `ai2apps/web/i18n/zh.json`
  - `docs/ai2apps-studio-app-ui-design-standard-v1.md`
- 发行测试：
  - `tests/test_ai2apps_video_studio.py`
  - `tests/test_ai2apps_video_tasks.py`
- 当前验证（2026-09-04）：JavaScript 语法、中英文 i18n JSON、Ruff 和 `git diff --check`
  通过；按当前正式 schema v69 隔离并行迁移改动后，Video Studio Shell、API 与任务回归
  `17/17` 通过，包含冻结文字与图片输入 Retry。固定 App Dev 的 UI 控制接口连续超时，
  Chrome 与内置浏览器访问当前 Local 均停在登录页，因此登录后桌面与窄屏视觉验收仍待完成。
- Release notes 建议：Video Studio 现在会分别保留三个内置 Mini-App 的创作草稿，支持
  可折叠与窄屏工作区，并提供更完整的 Run 详情、历史和安全重试。
- 纳入 Build：待定。

### NXR-012：AceFox 本地文件原生路径

- 状态：`in_progress`
- 类型：AceFox 平台能力、本地文件、内存效率与安全边界。
- 用户可见结果：用户从 Finder 拖入文件或通过系统文件选择器打开文件时，AI2Apps Local
  页面可从同一个磁盘后备 `File` 对象读取真实路径；视频等大文件可以把路径交给本地服务
  流式处理，无需先调用 `FileReader` 或 `arrayBuffer()` 将完整内容放入 JavaScript 内存。
- 安全边界：保留 Firefox 原有 `mozFullPath` 的 `ChromeOnly` 限制；新增的
  `mozAI2AppsFullPath` 只允许当前已由 Helper 验证并启动的精确
  `http://127.0.0.1:<port>` Local origin 读取。Shell 在重连前和退出时撤销 origin，普通网页、
  其他 loopback 端口和无效配置均得到 `SecurityError`；纯内存 `File` 返回空路径。
- 需要进入 App 的 AceFox 文件：
  - `dom/webidl/File.webidl`
  - `dom/file/File.h`
  - `dom/file/File.cpp`
  - `modules/libpref/init/StaticPrefList.yaml`
  - `modules/libpref/moz.build`
  - `browser/components/ai2apps/content/shell.mjs`
- 发行测试：
  - `dom/file/tests/test_ai2apps_native_path.html`
  - 使用 Finder 拖拽与系统文件选择器分别选择一个大视频，确认两条入口得到相同真实路径，
    且 App 处理期间 JavaScript 堆不随视频大小线性增长。
- 当前验证（2026-09-04）：Firefox 启用测试的完整 `mach build` 与 release
  `mach build binaries` 成功；新增 headless Mochitest 的磁盘路径、内存文件和跨 origin 拒绝
  `4/4` 通过，其中分别覆盖拖拽列表与文件输入列表。开发 App 实机拖拽/文件选择及大视频
  内存曲线验收尚待完成。通用 `AI2Apps-dev.app` 与固定 `AI2Apps-app-dev.app` 已基于重新打包的
  AceFox 快照完成重建、临时签名与严格 Bundle 验证；重启后两个 Local 分别健康运行于
  `51851`、`51861`，原生窗口标题分别绑定 `dev` 与 `app-dev` 环境。
- Release notes 建议：AI2Apps 现在可直接引用通过拖拽或文件选择器打开的本地大文件，降低
  视频、音频等素材进入本地工作流时的内存占用。
- 纳入 Build：待定。

### NXR-013：Read Aloud Studio v1 对齐

- 状态：`in_progress`
- 类型：客户端 UI、Read Aloud、Studio Run/Artifact、Gallery 资源交付与任务恢复。
- 用户可见结果：Read Aloud 左栏统一使用 Mini-App 术语并加载五个版本化内置描述符；
  右栏升级为可恢复的 Run Workspace，展示状态、总进度、Step、音频 Artifact 和历史，
  支持取消、失败重试、原生下载和保存到 Gallery；单句试听与整项目渲染使用同一持久任务链。
- 状态与安全边界：创作表单按 AppInstance 和 Mini-App 保存服务端草稿；Run、Step 和
  Artifact 以服务端数据库为事实来源；Gallery 音频经用户、Installation、AppInstance 和
  consumer 绑定的短期 Resource Handle 交付，不暴露宿主文件路径。`localStorage` 仅保存
  当前 Mini-App 这一展示偏好。
- 响应式与可访问性：桌面三栏支持独立折叠；中等宽度降级为两栏；Mobile 提供
  Mini-Apps / Create / Output 分层导航；补充键盘素材选择、焦点样式、进度语义和图标按钮标签。
- 需要进入 App 的文件：
  - `ai2apps/api/readaloud.py`
  - `ai2apps/readaloud/tasks.py`
  - `ai2apps/studio/repository.py`
  - `ai2apps/gallery/repository.py`
  - `ai2apps/api/gallery.py`
  - `ai2apps/storage/migrations.py`
  - `ai2apps/platform_runtime.py`
  - `ai2apps/web/templates/system_apps/readaloud.html`
  - `ai2apps/web/static/js/readaloud.js`
  - `ai2apps/web/static/js/gallery.js`
  - `ai2apps/web/static/css/readaloud.css`
  - `ai2apps/web/i18n/en.json`
  - `ai2apps/web/i18n/zh.json`
- 发行测试：`tests/test_ai2apps_readaloud.py`、`tests/test_ai2apps_readaloud_tasks.py`、
  `tests/test_ai2apps_gallery.py`、`tests/test_ai2apps_platform_storage.py`。
- 当前验证（2026-09-04）：Read Aloud、渲染任务和 Gallery 专项回归 `18/18` 通过，平台
  schema/迁移关键用例 `5/5` 通过；Python 编译、Ruff、JavaScript 语法、中英文 JSON 和
  `git diff --check` 通过。平台存储联合回归在进入与本改动无关的 MLX 服务生命周期用例时
  因当前沙箱无 Metal 设备中止。固定 `AI2Apps-app-dev.app` 的 Local 已通过受认证 Helper
  控制通道重启，最终端口 `64314` 返回平台健康 `ok`、数据库与目标 schema 均为 v70；
  实例数据库确认五张 Studio/Gallery 表及 Read Aloud 的 Mini-App/placement/model revision
  列均已落地，OpenAPI 已公开 Read Aloud `mini-apps`、`drafts` 和 `runs` 路由。
- Release notes 建议：Read Aloud 现在以 Mini-App 组织创作入口，语音生成会保存为可恢复、
  可下载、可加入 Gallery 的 Run 和 Artifact，并改进窄屏与键盘操作体验。
- 纳入 Build：待定。

### NXR-014：Imagine Studio Mini-App 与持久 Run 工作区对齐

- 状态：`ready`
- 类型：客户端 UI、Imagine Studio、Studio Run/Artifact、Gallery Resource Handle、草稿恢复。
- 用户可见结果：Imagine Studio 的三个现有创作入口升级为版本化内置 Mini-App；Studio Shell
  明确分离左侧 Mini-App/素材发现区、中间受信任 Adapter 创作面和右侧 Run 工作区。右栏统一展示
  Run、Step、Artifact、进度、错误、取消、重试、原生下载和加入 Gallery，旧生成历史会投影到新的
  Run/Artifact 模型中，避免升级后丢失结果。
- 状态与安全边界：创作草稿按用户、AppInstance 与 Mini-App 持久保存；Run、Step、Artifact 以
  平台数据库为事实来源；Gallery 拖放仅传递 Asset Reference，由服务端签发绑定 consumer App 与
  AppInstance 的短期 Resource Handle，再触发标准 `gallery.asset.drop`，不向 Mini-App 暴露宿主路径。
- 响应式与发现体验：左右栏可独立折叠；窄屏提供 Mini-Apps / Create / Output 分层导航；Mini-App
  发现区支持搜索、状态与版本展示、收藏和最近使用，并补充键盘焦点样式。
- 需要进入 App 的文件：
  - `ai2apps/api/imagine_studio.py`
  - `ai2apps/api/gallery.py`
  - `ai2apps/gallery/repository.py`
  - `ai2apps/studio/repository.py`
  - `ai2apps/storage/migrations.py`
  - `ai2apps/config.py`
  - `ai2apps/apps/system.py`
  - `ai2apps/web/templates/system_apps/imagine_studio.html`
  - `ai2apps/web/static/images/imagine-studio/styles/*.webp`
  - `ai2apps/web/static/js/imagine_adjust.js`
  - `ai2apps/web/static/js/imagine_style_catalog.js`
  - `ai2apps/web/static/js/imagine_studio.js`
  - `ai2apps/web/static/css/imagine_studio.css`
- 发行测试：`tests/test_ai2apps_imagine_studio.py`、`tests/test_ai2apps_gallery.py`、
  `tests/test_ai2apps_platform_storage.py`。
- 当前验证（2026-09-04）：Imagine Studio、Gallery 与 schema/迁移专项回归 `17/17` 通过；Python
  编译、JavaScript 语法与 `git diff --check` 通过。固定 `AI2Apps-app-dev.app` 的 Helper、Local 与
  Shell 已按 `app-dev` 身份重启，Local 确认 schema v70，新 Shell 连接端口 `49372`；实机验收确认
  新版 Mini-App 发现区和 Render workspace 已加载，旧 `CURRENT PIPELINE` 界面不再出现。测试退出时
  nanobind 报告当前沙箱没有 Metal 设备，但 pytest 结果为成功，且该提示与本项非模型 UI/存储改动无关。
- 后续修正（2026-09-04）：Cloud 模型目录 ID 在进入 Imagine Studio 时统一规范为
  `cloud/ai2apps/<provider>/<model>` Gateway ID，修复裸 `openai/gpt-image-2` 被误判为未启用本地
  Provider、导致图片生成返回 `404 Image model is not enabled` 的问题；Imagine Studio 与 Cloud
  Gateway 回归 `18/18` 通过，并在 App-Dev 中重新挂载确认 Cloud 图片模型恢复为可生成状态。
- 鉴权修正（2026-09-04）：Imagine Studio 按模型来源拆分请求路径；Cloud 模型改走
  `/v1/platform/cloud/ai/images/*`，由平台注入当前 Principal 对应的 Cloud Device 身份，本地 Package
  模型继续使用 `/v1/images/*`。修复低层兼容端点丢失用户身份后返回
  `401 AUTHENTICATION_REQUIRED` 的问题；相关回归 `18/18` 通过，并在端口 `51861` 的 App-Dev
  中重新挂载确认鉴权错误横幅消失、Generate 恢复可用。
- 草稿兼容修正（2026-09-04）：加载旧草稿时将裸 Cloud 模型 ID 迁移到规范 Gateway ID，避免
  无匹配 `<option>` 时浏览器错误回退到目录第一项。实机确认先前的旧 GPT Image 2 草稿曾因此
  被切换到 Google Gemini 3.1 Flash Image；该 Google Provider 当前由 Cloud 返回 502，本地不
  篡改其服务状态，当前 App-Dev 草稿恢复选择 GPT Image 2。
- 长任务可靠性修正（2026-09-04）：实机日志确认 GPT Image 2 Cloud 请求已返回 `200` 且 Cloud
  Request 状态为 `completed`，但原同步浏览器请求在大体积 Data URL 返回前断开，界面仅显示
  `NetworkError`，成功图片也未进入历史。Cloud 图片生成现由 Local 后台执行持久 Run：提交接口
  立即返回 `202`，服务端持有 Cloud 请求、校验并落盘图片、创建 Artifact 后更新 Run 终态；前端
  只轮询短请求，并会在页面重新挂载后继续监控进行中的 Run。Cloud Device 身份头与幂等键均由
  服务端传递；本地 Package 模型仍使用原本的前端直连流程。Imagine Studio 与 Cloud Gateway
  回归 `18/18` 通过，Ruff、Python 编译和 JavaScript 语法检查通过。固定 App-Dev 的 Helper、
  Local 与 Shell 已按 `app-dev` 身份重启，Local 在端口 `55538` 以 schema v70 就绪；实时 OpenAPI
  已公开后台执行路由，Imagine Studio 已重新挂载。扩展联合回归在前 `45` 项通过后，仍于既有
  MLX 服务生命周期用例因当前沙箱无 Metal 设备退出。
- Google Provider 外部阻塞（2026-09-04）：后台 Run 上线后，GPT Image 2 使用相同提示词、
  `1536x1024 / auto / png` 参数成功并持久化 Artifact；Google Gemini 3.1 Flash Image 随后由
  Cloud 明确返回 `502 AI_PROVIDER_ERROR`，证明不是 Desktop 断线、鉴权或落盘问题。Cloud 修复、
  模型目录能力与生产验收要求已记录在
  `docs/cloud-google-gemini-image-provider-repair-requirements.md`；在 Cloud 完成修复前不建议继续
  让用户付费重试该 Google 模型。
- Google Provider 对接完成（2026-09-04）：Cloud 已以 OpenAPI `1.41.0`、数据库迁移 48 部署
  Google 正式 `generationConfig.imageConfig` 合同。Desktop 不再按模型名硬编码尺寸能力，改从
  顶层 `imageOptions` 渲染固定画幅、质量和输出格式；Google 的非方形尺寸继续以
  `1536x1024 / 1024x1536` 作为 3:2、2:3 请求别名，并在 UI 明示实际像素由模型返回决定。
  后台 Run 以响应的 `image.size`、`image.format` 和 Data URL MIME 保存实际尺寸与 JPEG 文件，
  同时在 Artifact 元数据保留请求尺寸/格式。专项回归 `18/18` 通过；固定 App-Dev 在端口
  `61299`、schema v70 就绪，实机目录确认 Google 仅有 Auto 质量以及 Auto、1:1、3:2、2:3
  尺寸选项。尚待用户授权一次生产付费生成，验证 Run、Artifact 落盘与刷新恢复。
- Google 尺寸文案修正（2026-09-04）：按产品要求，Google 尺寸下拉不再显示 Cloud 协议层的
  `1536x1024 / 1024x1536` 兼容别名，而显示当前生产真实输出 `1264x848 / 848x1264`；选项
  内部值仍使用 Cloud 接口要求的 3:2、2:3 兼容别名，避免提交不受支持的像素值。方形继续显示
  `1024x1024`，旁注明确这些是 Google 当前的 1K 输出尺寸。
- Image 核心风格选择（2026-09-04）：将原高级设置中的 5 项纯文字下拉升级为跨 Mini-App 的
  Image 核心能力，默认保持“无风格”；文生图、图片编辑与参考图创作共用同一个选择和状态，
  切换 Mini-App 时不再被各自草稿覆盖。对话框按写实、艺术绘画、现代视觉、游戏/动漫四类展示
  51 种风格及对应示例图，并在应用后把所选风格提示词追加到所有生成或编辑请求。素材复用自既有风格库，
  修正了重复微距、Modern 拼写以及巴洛克/哥特中文错位，补入 8 位像素风格；51 张 256px PNG
  转为随 App 发布的 WebP，体积由约 9.7 MB 降至约 1 MB。旧草稿的简版风格 ID 会自动映射，
  选择状态保存为 Imagine Studio 级偏好，同时继续写入 Run 和 Mini-App 草稿以支持追溯与旧数据迁移；
  对话框支持取消、Escape、遮罩关闭、键盘焦点与窄屏双列布局。
  Imagine Studio、Cloud Gateway 与图片 API 专项回归 `20/20`、两份 JavaScript 语法和
  `git diff --check` 通过；固定 App-Dev 端口 `61299` 实机确认 51 张缩略图加载、分类切换、
  风格选择和应用后主界面回显正常，并确认在 Image Edit 选择 `Realism` 后切换到 Reference
  Creation 仍显示同一风格，验收未触发图片生成。
- 调整图片 Mini-App（2026-09-04）：新增版本化内置 `ai2apps.imagine.adjust-image`，在本机使用
  Canvas 对单张图片进行非 AI、非破坏性参数调整。支持原始比例及 1:1、4:3、3:4、16:9、9:16
  中心裁剪，左右旋转、水平/垂直翻转，以及曝光、鲜明度、高光、阴影、对比度、亮度、饱和度、
  自然饱和度、黑点、颜色平衡、色温、色调、锐度、清晰度、噪点消除和晕影；支持实时预览、
  撤销、重做和复原。预览限制长边以保证交互流畅，完成时按裁剪后的原始分辨率重新渲染无损 PNG，
  并保存为标准 Run/Artifact，可继续下载或加入 Gallery；整个调整过程不调用 Cloud 或本地 AI 模型。
  Imagine Studio、Cloud Gateway 与图片 API 联合回归 `21/21`，两份 JavaScript 语法、
  Python 编译和 `git diff --check` 通过；通过标准 App-Dev builder 刷新固定开发 App，
  旧 App 已归档为 `AI2Apps-app-dev-20260904-222136.app`。端口 `55270`（重载后 `56956`）实机确认
  Mini-App 数由 6 增至 7，调整工作区、全部 16 项参数、裁剪比例与旋转/翻转入口正常。
  实际导入 3456×2234 和 512×512 图片验收时，发现 AceFox 不支持通过
  `fetch(data:)` 将 Canvas Data URL 转回 Blob，已改为纯本地 Base64 解码；复测完成旋转、
  512×512 PNG 导出、Run 成功状态和 Artifact 落盘，重载并重新打开
  Imagine Studio 后仍可恢复该 Run、预览和 Artifact。
  后续修正 Gallery 新图导入的调整状态边界：用户拖入或更换图片时重置旋转、
  翻转、裁剪和色彩参数，只有恢复同一草稿的 Gallery 素材时才恢复已保存的调整。
  大图保存链路进一步改为直接从 Canvas 异步生成二进制 PNG Blob，再切成 192 KiB 小块经
  专用 JSON 结果接口顺序上传，绕开 AceFox 中会中断 Canvas Blob/multipart 请求的路径；
  同时避免先生成大体积 Data URL、再 Base64 解码成文件所造成的额外内存峰值。服务端限制
  单块与整图大小、隔离 App Instance/Actor/Installation，并清理十分钟未完成上传；Cloud 图片
  结果仍保留 Data URL 与原 multipart 接口的兼容路径。Imagine Studio 专项回归 `9/9`、
  JavaScript/Python 语法和 `git diff --check` 通过；标准 App-Dev builder 已刷新固定开发 App，
  旧 App 归档为 `AI2Apps-app-dev-20260905-001852.app`。端口 `51468` 实机以 1264×848、
  饱和度 100、自然饱和度 57 的草稿复测，Run 成功、Artifact `image/png` 落盘且下载链接可用。
- 调整方案与批处理（2026-09-05）：调整图片工作区新增 `Lock adjustment`，开启后更换或拖入
  新图会沿用当前裁剪、变换和 16 项调色参数；选择已保存方案也会自动保持参数。支持命名保存、
  更新、选择以及在管理对话框中改名/删除本机持久化方案。`Done and save` 同行新增批量处理，
  可从多个本地文件、一个本地目录或当前 Gallery 集合取图，并选择覆盖原图/原 Gallery 资产，
  或另存到用户选择的本地目录/当前 Gallery 集合；本地目录与文件路径只来自 AceFox 对当前认证
  Local origin 暴露的用户选择结果。批量渲染复用单图调整引擎，保留输入格式，目录另存保留相对
  层级；本地写入使用同目录临时文件、fsync 与原子替换，Gallery 覆盖保留原 Asset ID 和 Collection
  关系，覆盖前有不可撤销确认。调整方案、锁定和当前选择同时进入用户/AppInstance/Mini-App 范围
  的持久草稿，避免 App-Dev Local 端口变化时因 origin 更换而丢失。Imagine Studio 专项回归
  `9/9`、Ruff、Python/JavaScript 语法与 `git diff --check` 通过；标准 builder 两次刷新固定开发 App，
  最终旧 App 归档为 `AI2Apps-app-dev-20260905-005151.app`。端口 `56219` 实机保存“跨端口持久方案”
  并启用锁定，Local 重启到 `56441` 后方案选择、名称和 Lock 状态均恢复；方案管理和批量处理对话框
  的三个来源、覆盖/另存以及目录选择入口均完成实机 UI 验收。批量本地另存、覆盖与 Gallery 原位
  替换由 API 自动化覆盖，测试使用临时文件，不改动用户原图或 Gallery 资产。最终图片签名、MIME
  与扩展名校验加固加载后，固定 App-Dev 再次重启至端口 `56747` 并保持正常连接。
- 模型裁剪预设（2026-09-05）：调整图片的 Crop 下拉补充当前 OpenAI 与 Google 图片模型尺寸。
  方形显示共享的 `1024×1024`，OpenAI 横竖图显示 `1536×1024 / 1024×1536`，Google 横竖图
  使用生产实际返回的 `1264×848 / 848×1264`。裁剪引擎按各尺寸的精确宽高比执行中心裁剪，
  Google 不以近似 `3:2 / 2:3` 代替实际比例；输出仍保留裁剪后源图分辨率，不做无意放大。
- 更换图片风格 Mini-App（2026-09-05）：新增内置 `ai2apps.imagine.style-transfer`，接收一张原图、
  一个必选的 Image 核心风格和可选补充说明，通过标准图片编辑 API 生成风格转换结果。工作流提示词
  明确保留主体身份、姿态、构图、几何与关键内容，只重绘材质、光线、色彩和纹理；输入图比例继续
  匹配模型支持的最近输出尺寸。该 Mini-App 将具备图片编辑能力的 OpenAI 模型排在首位，新草稿
  默认选择 OpenAI；用户手动选择并保存过其他模型时尊重其草稿，不强制覆盖。未选择目标风格时
  禁止提交，补充说明允许为空；Run、Artifact、重试、下载及加入 Gallery 复用现有持久工作区。
  Imagine Studio 专项回归 `9/9`、Ruff、JavaScript 语法与 `git diff --check` 通过。因运行中的旧
  App-Dev Development Bundle 未提供源码热挂载，按标准 builder 刷新固定开发 App，旧 App 归档为
  `AI2Apps-app-dev-20260905-011632.app`；清理构建前遗留 Local 后，新固定 App 在端口 `60070`
  启动。实机确认 Mini-App 数由 7 增至 8，入口、单图必选、目标风格必选、可选补充说明、
  OpenAI GPT Image 2 默认选择及禁用提交状态均正常；验收未上传图片或触发付费生成。
- 合影 Mini-App（2026-09-05）：新增内置 `ai2apps.imagine.group-photo`，在 Cloud 单次最多四张图片
  的现有合同内提供 3 个人物 Slot 和 1 个可选背景图 Slot，并支持用背景文字替代背景图。生成区增加
  独立的背景描述、气氛、姿势与互动字段，以及复用 Image 核心风格选择器的可选视觉风格；至少需要
  两张人物图，且背景图/背景描述必须有一项。合成提示词明确输入角色顺序、每个人只出现一次、保持
  人物身份与面部特征、禁止合并/复制/遗漏/新增人物，并要求统一光线、比例、透视、阴影、视线和
  人体结构。该 Mini-App 与更换风格一样优先排列 OpenAI 图片编辑模型，新草稿默认选择 OpenAI，
  手动保存过的模型仍由草稿恢复。人物、背景及结构化描述会随 Mini-App 草稿和 Run 输入持久化，
  Gallery 背景素材使用稀疏 Slot 保存，刷新后不会被错误恢复为人物图。Imagine Studio 专项回归
  `9/9`、Ruff、JavaScript 语法与 `git diff --check` 通过；标准 builder 刷新固定开发 App，旧 App
  归档为 `AI2Apps-app-dev-20260905-055523.app`。新固定 App 在端口 `64136` 启动，实机确认 Mini-App
  总数增至 9、四个语义化 Slot、三项结构化输入、OpenAI GPT Image 2 默认选择和提交禁用状态正常；
  验收未选择用户图片或触发 Cloud 付费生成。
- Gallery Mini-Entry 恢复修正（2026-09-04）：实机确认 Gallery API 与 Mini-Entry 页面正常，
  失败来自外层 Shell 强制刷新前遗留的旧 mount token，导致 Imagine Studio 的 Host Bridge 请求
  30 秒无响应；强制刷新后标准 Mini-Entry mount 成功并创建 `app_mounts` 记录。Imagine Studio
  现在会在恢复到 Assets 视图时主动挂载 Gallery，并在 Host Bridge 无响应或宿主不支持挂载时降级
  到同源第一方 Gallery Mini-Entry，避免显示永久失败卡片；用户手动重试会先清理旧 URL 与 mount ID。
  Imagine Studio 与 Gallery 联合回归 `15/15`、JavaScript 语法、Ruff 和 `git diff --check` 均通过；
  端口 `61299` 实机强制刷新后保持 Assets 视图，并自动恢复 Gallery Mini-Entry，无需再次切换 Tab。
- Studio 横向修正（2026-09-04）：检查所有 Gallery Mini-Entry 消费方后，确认 Video Studio 与
  Read Aloud 仍有相同的 Host Bridge 超时失败路径；两者现与 Imagine Studio 一致，在恢复到
  Assets 视图时主动挂载，在 Host 无响应或不支持挂载时降级到同源第一方 Gallery Mini-Entry，
  并在 Retry 前清理旧 URL 与 mount ID。仓库内三个 Studio 的 Gallery 挂载恢复策略现已统一。
  三个 Studio 专项回归 `20/20`、三份 JavaScript 语法检查、Ruff 与 `git diff --check` 通过；
  端口 `61299` 实机确认 Read Aloud 与 Video Studio 均可挂载 Gallery，Video Studio 在保持
  Assets 视图强制刷新后也会自动恢复 Mini-Entry。
- AceFox Sidebar Gallery 修正（2026-09-04）：实机确认 AceFox Sidebar 直接加载的 Gallery
  Mini-Entry 正常显示并绑定当前 `bidi_context`，不经过 Web Shell `mountMiniEntry`，因此不会复现
  Studio 的 Host Bridge 超时；但其“打开完整 Gallery”和素材预览错误依赖不存在的 Web Shell
  bridge，前者点击无反应、后者会显示不支持预览。Gallery 现会在 Browser Sidebar 环境使用同源
  新标签页打开完整 Gallery 或指定素材预览，同时保留 Desktop Shell 原有 bridge 行为。AceFox
  实机切换回 Gallery 重新加载脚本后，“打开完整 Gallery”已成功新建标签页并加载完整页面；Gallery、
  Imagine Studio、Read Aloud 与 Video Studio 联合回归 `28/28` 通过，JavaScript 语法、Ruff 与
  `git diff --check` 通过。
  Sidebar 当前仍未创建平台 `app_mounts`，后续需按浏览器控制架构将其升级为 mount-bound Gateway
  session；本次没有放宽 BiDi、Profile、Context 或身份校验。
- Gallery Shell-App 图标更新（2026-09-09）：以最终选定的 B3 概念替换原
  `gallery-horizontal-end` 图标，使用等高横向三图叠层、左侧前景图、放大太阳和较细的太阳/山形
  内部线条。自定义图标通过共享 Lucide 注册表接入，Shell Dock、App Launcher、Gallery 完整页面
  与 Mini-Entry 使用同一 `gallery-stacked-horizontal` 标识，不改变其它系统 App 图标。Gallery 与
  Shell 合同回归 `121/121` 通过，JavaScript 语法、Ruff 与 `git diff --check` 通过；固定 App-Dev
  的 Local 已通过受认证 Helper 控制通道从端口 `57781` 重启至 `50476`，实机确认 Shell Dock
  已渲染 B3 图标且 Gallery 可正常打开。后续用户截图证明首次验收误把空图标容器识别为图形：
  Lucide 内置注册表实际被冻结，旧缓存中的首版注册脚本未能注册 B3，因而呈现为空色块。图标现由
  独立 `window.ai2appsIcons` 注册表和共享渲染器处理，并提升静态脚本版本参数以强制淘汰旧缓存；
  修复完成前不得沿用首次实机验收结论。最终在端口 `51358` 的固定 App-Dev 中强制刷新复验，确认
  Shell Dock 的普通态/选中态以及 Gallery 完整页面页头均实际显示 B3 的三张横向叠图、太阳与山形
  线稿，不再是空色块；修复后 Gallery 与 Shell 合同回归 `122/122` 通过。
- Release notes 建议：Imagine Studio 现在以 Mini-App 组织图像创作，并将每次生成保存为可恢复、
  可重试、可下载及可加入 Gallery 的标准 Run 和 Artifact；同时改进素材边界、发现能力和窄屏体验。
- 纳入 Build：待定。

### NXR-015：oMLX Runtime 1.6.0 Detailed Transcription 能力合同

- 状态：`ready`
- 类型：Runtime Package、高级语音转写基础设施。
- 用户可见结果：oMLX Runtime 新增独立的
  `audio-detailed-transcription-v1` capability，为字幕、会议转写的 Qwen3 ASR、
  forced alignment、VAD 和说话人分离流水线提供 Runtime 版本边界。
  该能力不加入 Chat STT 选型，原有 `audio-stt` 合同保持不变。
- 版本与依赖：Runtime 从 `1.5.7` 升至 `1.6.0`；MLX Detailed
  Transcription 候选 Package 的 Runtime 下限同步收紧为 `>=1.6.0,<2.0.0`。
- 体积精简：Runtime 只内嵌 `ai2apps/model_worker` 而不再复制整个 Host
  源码树；移除 Python tests/cache、xgrammar 仅供链接的静态库，以及归 Host
  所有的 ModelScope、Selenium 和 MCP 客户端。MLX、MLX-LM/VLM、MLX Audio、
  sherpa-onnx、通用 ONNX Runtime、PyAV 和 xgrammar 运行时动态库全部保留。
- 发布边界：Host 的 dedicated model type/route 已随 Runtime 候选完成；三个新
  checkpoint distribution 仍为后续门禁。Runtime 1.6.0 已生成 Developer ID
  签名、Apple 公证及 Publisher 签名候选，但当前工作树非 clean，本轮未提交
  Registry，不将本地签名候选冒充已发布 Runtime。
- 需要进入 Runtime/Package 的文件：
  - `packages/ai2apps-runtime-omlx/service.yaml`
  - `packages/ai2apps-runtime-omlx/ai2apps.json`
  - `packages/ai2apps-runtime-omlx/META/runtime-manifest.json`
  - `packages/ai2apps-runtime-omlx/META/sbom.spdx.json`
  - `experiments/mlx_whisperx/package_candidate/service.yaml`
  - `experiments/mlx_whisperx/package_candidate/ai2apps.json`
- 验证（2026-09-04）：Runtime/Package/Model Worker 合同与 MLX Detailed
  Transcription 候选测试 `109/109` 通过，`git diff --check` 通过。标准
  Runtime 构建器已生成精简后的
  `ai2apps-runtime-omlx-1.6.0-development.ai2service`，大小 `361,983,771`
  字节，完整 SHA-256 为
  `fed092398e6e5c502a8ed4bccb74b696b4d187504163e774687e11aa9bd429b0`，
  Package digest 为
  `sha256:64b0a6522caedf21fe5eeede73ee66ca40d61b87bf69335abd64abf523071c11`。
  相比精简前同版本开发件的 `436,977,802` 字节，减少 `75,581,675`
  字节（`17.3%`）。
  归档反向解析确认 service/descriptor/SBOM 版本一致为 `1.6.0`、新 capability
  存在、DMG 固定路径正确；实际挂载 DMG 后的 Bundle 与外层 DMG 均通过
  `codesign --verify --deep --strict`，Bundle Info.plist 版本为 `1.6.0`，并确认已内嵌
  Qwen3-ASR `max_tokens=None` 修复和独立
  `/v1/audio/transcriptions/detailed` Worker 路由。从签名 Bundle 内实际导入
  MLX、MLX-LM/VLM、MLX Audio、STT/TTS Engine、sherpa-onnx、ONNX Runtime、
  PyAV 和 xgrammar 全部通过，并确认 Host-only 模块不存在。
  同日正式候选 DMG 已完成 Developer ID 签名与 Apple 公证，submission
  `938e8163-7319-4bd9-b5ce-abfdeba34216` 为 `Accepted`，staple 与 Gatekeeper
  验收通过；最终 DMG 大小 `384,756,624` 字节，SHA-256 为
  `1ae8c38aab38c98f68c6d7eb9c2167bebcb6ecaedce94a812a48808547bc5505`。
  公证件内 Python 为 `3.11.10`，全盘无 cp313/Python 3.13 路径，四个 oMLX
  自定义扩展均为 cp311 且 ABI probe/Direct-L1 symbol 通过。外层正式候选
  `ai2apps-runtime-omlx-1.6.0-production.ai2service` 已由现有正式 Publisher key
  签名，大小 `382,501,589` 字节，SHA-256 为
  `ce4f946b4f3a9f90f5e68e07d1d8a965e4ba1634a89fe895dfd6ca2a9c03a9a5`；离线
  envelope 验证和包内 DMG 等值校验通过。完整收据见
  `docs/ai2apps-mlx-runtime-1.6.0-detailed-transcription-signed-build.md`。
  Runtime 随后以 submission `cb038b5f-2cac-4bda-93ad-f90eaa42f5d3` 完成审核和
  Registry 发布；GitHub 与 ModelScope 相同字节镜像均通过 Cloud 的完整 SHA、Range
  和 46-piece 校验并激活。最终签名 Repository Snapshot v107 同时包含 Cloud、
  ModelScope、GitHub 三源；匿名真实客户端完成多源竞速下载，ModelScope 与 Cloud
  均实际赢得分片，组装后的完整摘要和 Publisher 签名验证通过。发布回执见
  `docs/ai2apps-mlx-runtime-1.6.0-detailed-transcription-release.md`。
- Release notes 建议：oMLX Runtime 新增独立的高级语音转写能力基础，
  用于字幕和会议转写，不影响 Chat 现有语音输入。
- 纳入 Build：待定。

### NXR-016：MLX WhisperX Detailed Transcription Package

- 状态：`ready`
- 类型：Model Package、Host 模型合同。
- 用户可见结果：新增独立字幕/会议转写模型类型，组合 Qwen3-ASR、Qwen3
  ForcedAligner、MeetingEnergyVAD 与 Sortformer，输出逐词/逐字时间戳、匿名说话人、
  语速及明确的高级能力 provenance；不会出现在 Chat STT 选项中。
- Package：正式源码位于 `packages/omlx-model-detailed-transcription/`，Package ID
  `ai2apps/model-detailed-transcription-mlx`；0.1.1 已发布，当前沙箱兼容修正版为
  `0.1.2`，依赖已发布的
  `ai2apps/runtime-omlx >=1.6.0,<2.0.0`，不内嵌任何 checkpoint。
- Checkpoint：0.6B/1.7B ASR、ForcedAligner、Sortformer 均使用匹配本 Package model
  identity 的 distribution，并已完成 HF/ModelScope 字节一致的 Publisher 签名构建、
  Cloud 发布与匿名回读。Sortformer 使用 NVIDIA Open Model License 的条件式下载同意与署名合同。
- Host：新增 `audio_detailed_transcription` 模型类型、默认 endpoint 与音频能力验证；
  ForcedAligner/Sortformer 以隐藏的 `audio_processing` 内部模型声明，避免暴露为用户可选
  Chat 模型。Cloud 当前仍拒绝新的签名 Discover 字段，因此 0.1.2 使用版本上限明确的
  Desktop legacy mapping；Cloud 升级需求已记录在
  `docs/cloud-discover-model-categories-requirements.md`。
- 验证：流水线、Package 合同、Model Worker 路由、现有音频 Package、Discover mapping
  与发布脚本的 0.1.2 联合回归 `136/136` 通过；无权重 Contract v1 测试构建通过。首次生产提交
  `7e1b05e1-6c8c-4e8f-b613-57054e978af6` 已验签和批准，但发布门禁正确拒绝 compact
  模型复用另一个 model identity 的 0.6B distribution；该不可变提交不能发布，需为
  detailed-transcription compact identity 新建同权重 distribution 后替换提交；该新增
  distribution 已发布并通过公共索引 v46 匿名验证。0.1.1 随后以 submission
  `ce41c54f-7672-4d64-a4ef-495377e2932d` 发布，公共 Registry 与完整 artifact 下载摘要
  验证通过；真实 Runtime/Package 安装成功，但首次推理确认 Package 对上传路径调用
  `Path.resolve()` 会在 macOS 沙箱中因 `/tmp` → `/private/tmp` 返回 500。0.1.2 已移除
  canonicalization、补充 multipart 布尔字符串解析，并让 smoke 显式关闭 diarization，
  随后使用正确的注册 Publisher 私钥完成 0.1.2 签名；正式发布 submission 为
  `ab93f656-e5e9-4360-bdc5-a11d2ccce717`，Repository Snapshot 为 v109。匿名目录确认
  latest=0.1.2、installable=true、无 blocker，完整下载 SHA/大小与本地发布件一致，
  envelope 逐 JSON 相同。直接使用公共下载 artifact 再次完成 Runtime 1.6.0 中英文
  managed-service 推理：英文 9/9 对齐且文本完整正确；中文 18/19 对齐，ASR 遗漏参考
  文本中的“我”一字。完整回执见
  `docs/ai2apps-mlx-whisperx-detailed-transcription-0.1.2-release.md`。
- 纳入 Build：待定。

### NXR-017：跨 Distribution 复用相同 Checkpoint 文件

- 状态：`ready`
- 类型：Desktop/Local Checkpoint 安装与缓存基础设施。
- 用户可见结果：不同 Package 或模型 identity 的 checkpoint distribution 只要声明了
  相同文件 SHA-256，AI2Apps 会从共享内容寻址 blob 缓存复用已验证文件；全部命中时不再
  请求 Hugging Face/ModelScope，部分命中时只下载缺失文件或跨文件 piece 的必要片段。
- 安全边界：每次 acquisition 仍先完成签名 manifest、许可证同意和 distribution identity
  校验；复用前重新校验 blob 类型、大小与完整 SHA-256。新 distribution 仍生成独立、只读的
  metadata/snapshot 视图，文件内容通过硬链接共享，不合并或绕过 Registry identity。
- 需要进入 App 的文件：
  - `ai2apps/checkpoint_acquisition.py`
  - `ai2apps/checkpoint_distribution.py`
- 自动化验证：Checkpoint acquisition/distribution、Registry、发布策略、安装器与共享缓存
  联合回归 `91/91` 通过；Ruff 与 `git diff --check` 通过。新增用例覆盖跨 distribution
  全量命中零网络，以及部分文件命中时只请求缺失文件。
- 真实验证（2026-09-04）：在全新隔离缓存中先导入普通 Qwen3-ASR 0.6B distribution
  `dist_ai2apps_qwen3_asr_0_6b_4bit_313d8501_v1`，随后请求 Detailed Transcription 的
  `dist_ai2apps_detailed_transcription_qwen3_asr_0_6b_4bit_313d8501_v1`；第二次 acquisition
  返回 `cache_hit=true`、`source_bytes={}`、checkpoint 源请求 `0`，9 个文件共
  `712,778,752` 字节全部复用，两个只读 snapshot 的文件 inode 完全一致。
- 发行边界：这是 AI2Apps Desktop/Local 代码变更；不需要升级 oMLX Runtime、模型 Package
  或重新发布既有 checkpoint distribution。
- Release notes 建议：已安装模型的相同 checkpoint 文件现在可以跨 Package 安全复用，
  减少重复网络下载和磁盘占用。
- 纳入 Build：待定。

## 4. 发布流程工作

### NXR-021：纯 MLX Seed-VC v2 零样本音色转换

- 状态：`ready`（Runtime 1.6.2、模型 Package 与 HF/MS 双源 checkpoint 均已发布并匿名验收）
- 类型：oMLX Runtime 音频 API、Model Package、Apple Silicon 零样本音色转换。
- 用户可见结果：`POST /v1/audio/process` 新增请求作用域 `reference` 音频以及
  `mode/diffusion_steps/guidance_intelligibility/guidance_similarity/length_adjust` 控制；
  Seed-VC v2 的 timbre 与 AR voice 两条路径均已用纯 MLX 跑通，不需要预训练用户音色。
- 安全边界：Torch 仅用于可信离线权重转换；Model Worker 只读取 Host 分配的 safetensors，
  参考音频只属于当前请求，不能注入 checkpoint 路径，也不会自动持久化为 Voice Profile。
- 需要进入 App/Runtime 的文件：`ai2apps/model_worker/audio_capabilities.py`、
  `omlx/api/audio_routes.py`。
- Model Package：`packages/omlx-model-seed-vc-v2/`；实验与验证：
  `experiments/mlx_seed_vc/`、`docs/ai2apps-mlx-audio-model-package-development-plan.md`。
- 当前验证：HuBERT、ASTRAL、AR、双 CFG CFM DiT、CAMPPlus、BigVGAN 均完成官方权重
  数值对照；Qwen3-ASR 恢复完整中英文原句。M5 Max 上 10 步英文/中文 RTF 分别为
  `0.1607`/`0.1476`，峰值 MLX 内存约 `4.54`/`5.23 GB`；签名 Runtime 1.6.0 自带
  Python 3.11 的 Package-layout 冒烟 RTF `0.3484`、峰值 `3.345 GB`，确认无需新增底层
  Python/MLX 依赖。Runtime 1.6.1 已加入 request-scoped reference multipart、双 CFG 参数
  路由和显式 `audio-reference-input-v1` 能力声明；Package/能力声明/API 联合回归
  `50/50` 通过。同一 11.04 秒 Ryan→Serena 任务的听感与 RMVPE 复核确认，Seed-VC v2
  音色相似度优于当前 RVC 候选，但逐帧相对基频变化的 MAD 为 `14.98 cents`（10 步）和
  `14.42 cents`（30 步），高于 RVC 70/80 轮的 `8.22/9.00 cents`；关闭 cosine sway
  后仍为 `14.54 cents`。固定上游提交与原始 checkpoint 的官方 Torch/CPU 同任务 30 步
  对照为 `15.49 cents`，MLX 并未放大中位基频抖动；Torch 的 90 分位逐帧误差较低
  （`58.82` 对 `73.60 cents`），仍需扩大样本验证少数突变帧。该任务 Torch RTF
  `2.0588`，MLX RTF `0.1878`，MLX 约快 11 倍。因此当前颤音主要是无显式 F0 条件的
  checkpoint/生成路径边界，不是简单增加扩散步数、关闭 sway 或 MLX 数值精度可以消除，
  后续应评估显式 F0 稳定化方案。
- 发布结果（2026-09-05）：`ai2apps/model-seed-vc-v2-mlx 0.1.0` 已正式发布，artifact
  SHA-256 为 `070db748df6e4aa395120a2a5f3391eb2476e44f8f7e959af14246474af513d2`；完整
  checkpoint distribution `dist_ai2apps_mlx_seed_vc_v2_2122cee1_v1` 已固定到 HF
  `2122cee1…` 与 MS `f1c5ab39…`，16 个文件、267 个分片、`2,236,581,603` 字节。
  匿名客户端验证 checkpoint index v51、Repository snapshot v117、Publisher 签名、artifact
  SHA-256 及本地/公开 envelope 完全一致；全新隔离 Platform base 中与 Runtime 1.6.2 一同
  安装后服务为 `active`。完整回执：
  `docs/ai2apps-mlx-seed-vc-v2-0.1.0-release.md`。
- Package 收敛（2026-09-05）：已生成可复现的最终复合 checkpoint 上传布局，15 个文件共
  `2,236,581,275` 字节，布局清单 SHA-256 为
  `cefd682aa86b79fe7388eb2b825d94d82a037b1a3f9fdef1ae82b1b76e572c4a`；模型卡、GPL-3.0
  许可证、第三方 NOTICE、SPDX SBOM 与 source lock 已加入 Package 源。Worker 默认档由
  10 步改为已完成 Torch/MLX 对照的 30 步，保留 10 步 fast 与 30 步 AR voice 档，并增加
  guidance/length-adjust 范围校验。最终目录的 30 步 multipart Worker 冒烟已在 Metal 上通过。
  同时修复了异步 Worker 在线程池缺少 MLX CPU/GPU stream 的真实崩溃：模型现在线程内加载，
  并使用 thread-local 双设备 stream。最终发布增加根 `config.json` 以满足通用 Host checkpoint
  完整性检查；Package 绑定上述已发布不可变双源 distribution，不内嵌权重。
- Release notes 建议：新增在 Apple Silicon 上离线运行的 Seed-VC v2 零样本音色转换，支持
  请求内参考音频、快速 timbre 与 AR voice 两种模式及独立语义/音色引导。
- 纳入 Build：待定。

### NXR-022：oMLX Runtime 1.6.2 原生音色训练协议

- 状态：`ready`（Runtime 1.6.2 已完成签名、公证、发布和三源匿名验收）
- 类型：oMLX Runtime、Model Worker 协议、Apple Silicon 本地音色训练。
- 用户可见结果：Host 新增 `POST /v1/audio/voices/train`，Runtime Worker 新增有界、可取消的
  `audio_voice_training` operation，并通过 `audio-voice-training-v1` 显式声明支持；模型
  Package 可以在安装前要求该协议，不会把 1.6.1 的推理 Runtime 误判成可训练环境。
- 安全边界：训练输入为一个受大小限制的 multipart ZIP；具体模型 Adapter 继续负责成员类型、
  数量和解压大小校验。Worker 不接受任意 checkpoint 路径，进度、取消和结果均沿用既有协议。
- 数值合同：RVC 默认训练精度统一为 FP16，使用 FP32 Adam 主权重和动量；BF16/FP32 保留为
  显式选项。
- 需要进入 Runtime/Package 的文件：`omlx/api/audio_routes.py`、
  `ai2apps/model_worker/server.py`、`packages/ai2apps-runtime-omlx/`，以及 RVC Package 的训练
  Adapter 与 CLI 默认值。
- 当前验证：Runtime/Model Worker/Provider/资源与构建器联合回归 `71/71` 通过；Metal 环境下
  audio route/STT 回归 `37/37` 通过（4 项按选择器排除）。
- 发布结果：Runtime 1.6.2 已完成 Developer ID 签名、Apple 公证、Publisher 签名和 Registry
  发布；GitHub/ModelScope 双外部源均通过完整 SHA-256、Range 和 45-piece Cloud 预检并激活。
  匿名生产下载器验证 Snapshot v115、完整 Package 和 Publisher 签名通过。发布回执：
  `docs/ai2apps-mlx-runtime-1.6.2-voice-training-release.md`。完整 RVC 与 Seed-VC v2 Package
  已于同日完成发布和匿名验收。
- 纳入 Build：待定。

### NXR-020：MLX-RVC 音色转换与通用参数转发

- 状态：`ready`（Runtime 1.6.2、完整训练/推理 Package 与 HF/MS 双源 checkpoint 均已发布）
- 类型：oMLX Runtime 音频 API、Model Package、Apple Silicon 本地音色转换。
- 用户可见结果：`POST /v1/audio/process` 可向签名音频处理 Package 转发
  `task/profile/semitones/retrieval_rate/protect/speaker_id/seed`；MLX-RVC 已跑通
  ContentVec、RMVPE、检索、特征保护、Flow 与 NSF 解码器的纯 MLX 音频到音频路径。
- 安全边界：生产推理不加载 pickle、Torch、torchaudio 或 FAISS；旧 `.pth`/`.index` 只在
  可信离线构建环境转换为带哈希的 safetensors。Worker 只读 Host 分配的固定 checkpoint，
  请求不能注入本地模型路径。
- 需要进入 Runtime 的文件：`omlx/api/audio_routes.py`。
- 实验与设计文件：`experiments/mlx_rvc/`、
  `docs/ai2apps-mlx-audio-model-package-development-plan.md`。
- 当前验证：官方模型逐模块数值对照通过；最终 RVC v2/48 kHz checkpoint 与 3399×768
  检索库已完成安全转换并跑通中英文。M5 Max 128 GiB 上 60 秒分块 RTF `0.0357`、MLX
  峰值约 6.20 GB，相比整段约 18.42 GB 降低约 66.3%。Package、Sandbox 与听感/说话人
  相似度验收尚未完成。新增 Qwen3-TTS CustomVoice `serena` 合成测试音色：48 条中文、
  24 条英文，共 370.8 秒；在固定 RVC 上游修订上使用 MPS 完成 v2/48 kHz/RMVPE 100 轮
  训练并构建 12954×768 检索库。独立 `ryan` 合成源经纯 MLX 转换的 11.04 秒冒烟 RTF
  `0.0990`，输出 11.02 秒、无非有限值或削波；Qwen3-ASR 回听保持整句结构，仅有两处
  近义词替换。该资产明确标注为 synthetic test voice，尚未发布 checkpoint 或 Package。
  现已新增 Package-owned 原生 MLX 训练链：原始 WAV 的 ContentVec/RMVPE/频谱缓存、Posterior
  Encoder、正向 Flow、NSF Generator、RVC v2 九路判别器、BF16 优化、进度/取消以及直接输出
  safetensors Voice Bundle。370.8 秒 Serena 数据完成 100 轮、1800 次 G/D 更新耗时
  `667.57s`，约为 Torch/MPS 的三分之一；全网络训练未通过 ASR 内容门禁，已明确拒绝作为
  交付候选。默认 `safe` 模式冻结 `enc_p` 与 Flow，10 轮/180 步耗时 `58.02s`，独立中文
  回听保留完整句式，仅有两处近音替换。检索改用矩阵式精确 L2 后，36936 向量推理峰值从
  64.9 GB 降至 5.85 GB，RTF 从 `0.205` 降至 `0.0448`。新增
  `audio_voice_training` Worker operation 和 `/v1/audio/voices/train` 路由；因此训练功能需要
  下一版 Runtime 协议，1.6.1 仍只提供推理。
  最终标准档采用 30 轮 safe adaptation：540 次 G/D 更新耗时 `184.70s`，独立 Qwen3-ASR
  回听仅有“语义→语音”一处近音替换；保留全部 36936 个检索向量时推理 RTF `0.0436`、
  峰值 5.85 GB。听感复核发现该候选较 Torch 对照低约 10.4 dB，并有更明显颤音，因此已撤销
  质量候选资格。根因修复现已补回固定上游的 48 Hz 高通、3.7 秒重叠切片、混合峰值归一化和
  `128-bin log-mel L1 × 45` 重建损失；旧实现使用未归一化原始音频及非等价多分辨率频谱损失。
  直接全 FP16 训练首轮产生 NaN；改为 FP16 前后向、FP32 Adam 主权重/动量并增加非有限值
  快速失败后，10 轮/360 步稳定完成，耗时 `136.24s`。同句输出 RMS 从 `-31.19 dBFS`
  恢复到 `-24.00 dBFS`，峰值 `-5.79 dBFS` 与 Torch 的 `-5.78 dBFS` 基本一致，纯 MLX
  推理 RTF `0.0428`。随后完成确定性 30 轮/1080 步训练，用时 `418.38s`；同句输出 RMS
  `-22.95 dBFS`、峰值 `-5.70 dBFS`、RTF `0.0418`，音高误差帧差 MAD 为 `8.43 cents`
  （旧 MLX 为 `12.34`，Torch 对照为 `9.12`）。10/20/30 轮试听均已保留；该修复候选仍需
  用户听感和内容回听验收。训练器现已增加滚动完整断点：保存 G/D、FP32 主权重、两个 Adam
  状态、epoch/step 与固定配置；单片段 1→2 轮恢复与连续 2 轮的 353 个导出张量逐项完全一致。
  可恢复 60 轮轨迹完成 2160 步，用时 `858.65s`，并保留 30/40/50/60 轮试听；60 轮同句
  RMS `-23.17 dBFS`、峰值 `-2.53 dBFS`、音高误差帧差 MAD `8.40 cents`。后续 100 轮可从
  60 轮状态仅续训 40 轮。尚待 Package 清单、沙箱端到端与签名发布。
  已实际从 60 轮完整状态恢复并续训到 100 轮/3600 步，新增 40 轮用时 `577.47s`，与前段
  合计 `1436.12s`。100 轮同句 RMS `-24.27 dBFS`、峰值 `-7.93 dBFS`、RTF `0.0417`；
  音高误差帧差 MAD 从 60 轮 `8.40`、70 轮 `8.22` 上升至 100 轮 `10.56 cents`，因此不按
  epoch 自动认定最终最优，保留 60/70/80/90/100 供听感、ASR 内容和说话人相似度联合选型。
- Release notes 建议：本地音频处理 API 新增模型无关的音色转换控制参数，为 MLX-RVC 与
  后续 MLX-Seed-VC Package 提供统一入口。
- Package 收敛（2026-09-05）：首版推理 Package 选定用户听感更自然的 native MLX e70
  Serena 合成测试音色，并把 voice、ContentVec、RMVPE 合并为一个原子 checkpoint；最终
  上传布局 14 个文件共 `974,917,451` 字节，布局清单 SHA-256 为
  `fab82f57d0fa9378774aa29e5153c38205a517818fe5bafcd711ef90e93b510d`。模型卡明确 synthetic
  voice 边界，MIT 许可证、NOTICE、SPDX SBOM、source lock 和可复现 staging 脚本已加入。
  最终目录的 `audio_process` Worker 冒烟已在 Metal 上通过，并与 Seed-VC 一同修复线程池
  MLX stream 崩溃。最终原子 checkpoint 又加入 MLX 训练 G/D 初始化、根配置及通用 Host
  safetensors 标记，共 19 个文件、169 个分片、`1,410,906,582` 字节；双源 distribution
  `dist_ai2apps_mlx_rvc_serena_e70_training_738acad9_v1` 固定到 HF `738acad9…` 与 MS
  `643998a0…`。`ai2apps/model-rvc-mlx 0.1.0` 已正式发布，artifact SHA-256 为
  `fd000d66f963ba40034ac6330ac83ea9d639b3814843b001050de52c8813e3ed`；匿名 checkpoint
  index v51 与 Repository snapshot v117 验证通过，全新隔离 Platform base 中精确发布 digest
  与 Runtime 1.6.2 一同安装后为 `active`。完整回执：
  `docs/ai2apps-mlx-rvc-0.1.0-release.md`。
- 纳入 Build：待定。

### NXR-023：模型 Package discovery 的 Cloud v1 兼容桥接

- 状态：`ready`（0.1.0 兼容桥接已验证；Cloud schema 升级需求已落盘）
- 类型：Desktop/Local Package 发现兼容、Cloud 合同对齐。
- 背景：本地 Package Contract v1 已要求新模型 Package 签名携带顶层 `discovery` 与
  `modelProfile`，但生产 Cloud 当前 schema 将这两个字段判为 additional properties。首次 RVC
  提交在创建 submission 前被拒绝，因此未产生重复或悬挂发布。
- 兼容处理：RVC 与 Seed-VC v2 的 `0.1.0` 使用现有的显式、版本上限 legacy map，分别声明
  `voice-conversion/voice-training` 与 `voice-conversion/voice-cloning`；下一版本不会自动沿用。
  `tests/test_ai2apps_discover_categories.py` 与音频/Package/Checkpoint 联合回归共 `89/89`
  通过，两个 Cloud v1 兼容 artifact 随后成功发布并完成匿名验证。
- Cloud 边界：未从本仓库修改 Cloud 代码。所需 schema、存储、公开投影和验收用例已写入
  `docs/ai2apps-cloud-package-discovery-schema-requirements.md`，交由 Cloud 项目升级；升级后新版本
  应恢复由签名 manifest 直接携带元数据。
- 需要进入 App 的文件：`ai2apps/packages/discovery.py`。
- 纳入 Build：待定。

### NXR-019：通用音轨分离能力声明合同

- 状态：`ready`
- 类型：Model Package 合同、音频能力发现、未来 Video/Meeting Pipeline 基础设施。
- 用户可见结果：音频处理模型可以用签名 `audio_capabilities` 声明原生 stem 和稳定输出
  profile；调用方能够区分模型原生四声部、pipeline 派生的对白/背景双轨和未来更强模型的
  原生对白、音乐、音效、环境声输出，不再根据模型名称推测能力。
- 安全与兼容边界：继续使用 `audio_processing`/`audio_process`，不新增 Runtime operation；
  未声明 profile 默认拒绝。fallback 必须显式声明默认 profile，派生输出必须携带
  `derivation`，不能把 vocals 静默冒充原生 dialogue。
- 需要进入 App 的文件：
  - `ai2apps/model_worker/audio_capabilities.py`
  - `ai2apps/checkpoints.py`
  - `docs/model-worker-package-manual.md`
- 实验及设计文件：
  - `experiments/mlx_demucs/capabilities.py`
  - `experiments/mlx_demucs/pipeline.py`
  - `docs/ai2apps-mlx-audio-model-package-development-plan.md`
- 当前验证：能力声明、Model Provider 与 MLX-Demucs 实验联合测试 `50/50` 通过；Ruff、
  compileall 与 `git diff --check` 通过。中文夹具通过 `music_4stem` profile 实际生成四个
  等长 44.1 kHz 立体声 WAV，并返回 native/direct provenance。正式 Package 收敛过程中
  发现公开 `mlx-community/demucs-mlx` 使用 `htdemucs.safetensors` 与
  `htdemucs_config.json` 配对，而 Host 过去只承认根 `config.json/config.yaml`。完整性检查
  已增加严格的同 basename `*_config.json` 配对规则，任意不匹配配置仍 fail closed；对应
  回归和真实 checkpoint 验收已纳入发布门禁。`ai2apps/model-demucs-mlx` 0.1.0 及
  `dist_ai2apps_mlx_demucs_htdemucs_d4519e24_v1` 已正式发布；干净实例使用 Runtime 1.6.2
  和公开双源 distribution 完成 Managed Service Sandbox 推理，9 秒输入返回 HTTP 200
  及包含双轨 WAV/JSON 的 ZIP。Package 匿名回读通过 Repository snapshot v120。
- Release notes 建议：音频处理模型现在可以声明可发现、可校验的音轨分离拓扑，并明确
  区分模型原生输出与流水线派生输出。
- 纳入 Build：待定。

### NXR-018：Video Studio「提取音轨」Mini-App

- 状态：`ready`
- 类型：客户端功能、Video Studio、Mini-App、Gallery Resource Handle、Studio Run/Artifact。
- 用户可见结果：Video Studio 新增版本化内置 Mini-App `ai2apps.video.extract-audio 1.0.0`；
  用户可以从 Gallery 选择/拖入视频或直接导入本地视频，在设备上提取第一条音轨，获得可播放、
  下载及保存回 Gallery 的独立 WAV 文件。该流程不要求安装视频或语音模型，也不调用 Cloud。
- 执行与安全边界：Finder 拖入或系统文件选择器提供 `mozAI2AppsFullPath` 时，页面仅把已选择
  文件的路径交给同源 Local 服务，后端验证绝对路径、普通非空文件与 `video/*` 类型后由 PyAV
  直接流式读取，不再先把大视频装入 JavaScript Blob 或复制到 Gallery；没有原生路径的浏览器
  环境继续回退到 Gallery 导入。Gallery 输入仍使用绑定用户、Installation、AppInstance 和
  consumer App 的短期 Resource Handle。PyAV 将音轨本地解码为 48 kHz、16-bit、立体声 PCM
  WAV；结果写入 durable Workspace Artifact，Run、草稿和 Artifact 元数据均不持久化源绝对路径。
- 恢复与导出：Mini-App 输入草稿按 AppInstance 持久保存；Run 历史、进度、错误及 Artifact 由
  平台数据库恢复；失败/取消 Run 可重试，结果支持播放器、原生下载和 Gallery Artifact 导入。
- 需要进入 App 的文件：
  - `ai2apps/api/video_studio.py`
  - `ai2apps/video/audio_extraction.py`
  - `ai2apps/video/tasks.py`
  - `ai2apps/web/templates/system_apps/video_studio.html`
  - `ai2apps/web/static/js/video_studio.js`
  - `ai2apps/web/static/js/gallery.js`
  - `ai2apps/web/static/css/video_studio.css`
  - `ai2apps/web/i18n/en.json`
  - `ai2apps/web/i18n/zh.json`
- 发行测试：`tests/test_ai2apps_video_studio.py`、`tests/test_ai2apps_video_tasks.py`、
  `tests/test_ai2apps_gallery.py`。
- 当前验证（2026-09-04）：Video Studio、视频任务与 Gallery 联合回归 `26/26` 通过；Ruff、
  JavaScript 语法、中英文 Video Studio i18n `203` 键一致性和 `git diff --check` 通过。使用
  H.264 + AAC 的真实 MP4 冒烟输入成功生成 RIFF PCM、48 kHz、16-bit、立体声 WAV；固定
  `AI2Apps-app-dev.app` 重新启动 Development Source 环境后，最终 Local 端口 `58158` 健康、schema
  v70，OpenAPI 已公开 Mini-App、草稿、Run、取消和音轨执行路由；实机三栏 UI 显示四个已安装
  Mini-App，「Extract Audio」中栏输入、就绪状态和右侧 Audio Run 工作区布局均正常。
- 原生路径增量验证（2026-09-05）：联合回归仍为 `26/26` 通过；新增用例确认绝对本地路径可
  直接完成 WAV Artifact、相对路径被拒绝，且源绝对路径不进入 Run 或 Artifact 元数据；Ruff、
  JavaScript 语法与 `git diff --check` 通过。同步修正 Workspace Artifact 写入：Studio Run ID
  不再错误写入只引用 Agent Run 的 Workspace `artifacts.run_id` 外键，Studio 与结果的关联仍由
  `studio_artifacts` 保持。
- Release notes 建议：Video Studio 现在可以在本地从视频提取独立音轨，并将结果播放、下载或
  保存到 Gallery，无需配置生成模型。
- 纳入 Build：待定。

### NXR-024：Video Studio 多轨 Video Composer Mini-App

- 状态：`ready`
- 类型：客户端功能、Video Studio、Mini-App、本地媒体编辑、聊天控制。
- 用户可见结果：Video Studio 新增 `ai2apps.video.composer 0.2.0`；支持图片/视频/音频多轨、
  轨内多片段、片段移动与左右裁切、9 px 边界/播放头磁吸、分割、速度与音量调整、淡入淡出、
  轨道静音/锁定、画面叠层顺序、预览区直接移动/缩放图层、透明度、横竖画布、快速预览、
  撤销/重做、键盘快捷键、持久草稿、后台 Run、取消、MP4 下载及保存到 Gallery。
- 聊天编辑：可使用已安装对话模型把自然语言规划成最多 20 个白名单操作；发送给模型的上下文
  只包含画布、轨道、片段 ID 与编辑参数，不包含本地路径。模型结果在浏览器端执行严格字段、
  数值范围、目标 ID 与淡化时长校验，任一操作失败则整批回滚；无模型时支持常见的速度、音量、
  淡入淡出、分割、删除和画中画确定性指令。
- 执行与安全边界：原生文件选择/拖入优先使用实际本地路径，由同源 Local 立即登记成绑定
  actor、Installation 与 AppInstance 的不透明 Source ID；路径和文件指纹只保存在权限为 0600
  的私有后端记录中，草稿、Run、Artifact 和聊天上下文均不出现路径。普通浏览器回退为 Gallery
  导入与 Resource Handle。渲染完全使用 App Runtime 内嵌 PyAV、NumPy 与 Pillow，生成 H.264 +
  AAC MP4，不依赖系统或 Homebrew `ffmpeg` 可执行文件；音频按片段窗口解码，避免把长源文件
  整段载入内存。
- 需要进入 App 的文件：
  - `ai2apps/video/composer.py`
  - `ai2apps/api/video_studio.py`
  - `ai2apps/web/templates/system_apps/video_studio.html`
  - `ai2apps/web/static/js/video_studio.js`
  - `ai2apps/web/static/css/video_composer.css`
  - `ai2apps/web/i18n/en.json`
  - `ai2apps/web/i18n/zh.json`
- 发行测试：`tests/test_ai2apps_video_composer.py`，并与 Video Studio、Video Tasks、Gallery
  回归联合运行。
- 当前验证（2026-09-05）：H.264 + AAC 真实媒体源完成双视频轨叠层、速度、透明度、音视频
  淡化与混音渲染，输出同时包含可解码视频和音频流；Source ID 跨 AppInstance 不可读取，公共
  响应和 Run/Artifact 不泄露路径。Composer、Video Studio、Video Tasks 与 Gallery 联合测试
  `29/29` 通过；覆盖 Composer、Video Studio、Video Tasks、Runtime Video、Shell 与聊天路径的
  扩展回归 `150/150` 通过；Ruff、JavaScript 语法和 `git diff --check` 通过。固定
  `AI2Apps-app-dev.app` 已按标准流程重建并通过 release verification 与严格 codesign 校验；实机
  使用原生文件选择器导入 H.264 + AAC MP4，草稿可在 Local 重启后恢复，最终在端口 `51127`
  完成带视频和音频的 1 秒 MP4 Workspace/Studio Artifact，播放器加载至 100%，Run 显示
  `Completed`，并提供 `Download MP4` 与 `Add to Gallery`。实机同时发现并修正了 Studio Run ID
  误写 Workspace Agent Run 外键的问题，新增回归断言防止复发。
- 预览交互修复（2026-09-05）：拖动期间不再深拷贝项目并继续修改失效的 Clip 引用，而是持续
  更新当前项目中的同一 Clip，仅在指针结束时保存一次；位置拖动允许画面部分移出画布且始终
  保留 16 px 可见区域，因而全画布大小的 Clip 也能移动。补充 `pointercancel` 清理、禁用触摸
  默认手势，并把右下角缩放柄扩大至 18 px。Composer、Video Studio 与 Shell 联合回归
  `113/113` 通过；App Dev 端口 `52667` 实机拖动后坐标由 `(0,0)` 更新为 `(297,171)`，缩放后
  尺寸由 `640×479` 更新为 `478×358`，位置和大小均连续生效。
- 连续拖拽二次修复（2026-09-05）：确认响应式字段本身在首次移动后会使 Alpine 的
  `x-for` 预览层重构并取消当前 pointer stream。位置与缩放现在采用两阶段提交：手势期间仅更新
  稳定 DOM 图层的百分比样式并保持 Pointer Capture，松开或取消时才一次性写回 X/Y/W/H、刷新
  响应式项目并保存草稿，因此下方 Inspector 数值不会在拖动中触发页面重构。
- Composer 素材与时间线交互增强（2026-09-05）：图片可从文件或 Gallery 导入视频轨道，默认
  时长 1 秒并可从两端继续调整；预览图层双击恢复素材原始像素尺寸。工具栏和轨道表头提供明确的
  新增 Video/Audio Track 入口，Gallery 与本地文件可直接投放到指定轨道和时间点。时间刻度文本
  不再接收 Pointer Event 或被选中，刻度空白区支持按住横向拖动播放头。Clip 整体移动和左右裁切
  均以同轨片段边缘、播放头或零点为候选执行 12 px 磁吸，Snap 开关可即时禁用；磁吸时显示高亮
  反馈。时间线移动、裁切以及预览位置/大小调整全部采用手势期间 DOM 更新、结束时响应式提交，
  避免 Inspector 更新打断 pointer stream。图片真实渲染和 Composer/Video Studio/Gallery 联合
  回归 `18/18` 通过，Ruff、JavaScript 语法和目标文件 `git diff --check` 通过。固定 App Dev 已按
  标准流程重建并运行于端口 `59941`：实机确认新增 Video Track 后出现 `Video 3`；刻度拖动把
  播放头从 `0.02s` 连续更新到 `3.64s`；时间线 Clip 单次拖动从 `0.02s` 更新到 `1.82s`；预览
  图层单次拖动令 X/Y 从 `137/121` 更新到 `283/238`，双击后 W/H 从 `640×479` 恢复为素材原始
  `32×32`。自动化驱动器未能跨 Gallery iframe 生成可用的原生 HTML5 DataTransfer，因此指定
  轨道 Gallery 拖放以模板/脚本集成断言覆盖，图片登记、1 秒默认时长与 1.5 秒可调时长则由真实
  Pillow/PyAV 渲染测试覆盖。
- 跨轨移动（2026-09-05）：时间线 Clip 拖动升级为横纵二维手势；纵向经过同类型且未锁定的轨道
  时，目标轨即时高亮，Clip 以稳定 DOM `translateY` 跟随，横向时间磁吸改为使用目标轨的片段
  边界。松手后一次性提交 `start` 与 `trackId`；视频不能误入音频轨、音频不能误入视频轨，锁定轨
  也不会成为目标。Composer 与 Video Studio 回归 `10/10` 通过，JavaScript 语法、Ruff 和目标
  文件 diff 检查通过。固定 App Dev 刷新后实机把首个 Clip 从 `Video 1` 纵向拖到 `Video 2`，
  Inspector 的 Track 同步显示 `Video 2` 且 Start 磁吸为 `0`；随后使用 Undo 恢复测试前草稿。
- 时间线编排约束、群组与颜色（2026-09-05）：同轨 Clip 在前端所有入口和后端 Project 校验层
  均禁止时间重叠；向左移动遇到前一片段即停止，向右移动或延长时波纹推动后续冲突片段，首尾
  相连的连续片段会链式跟随，缩短时也会向左收拢。拖入已有时间位置、Inspector 数值编辑与聊天
  编辑同样执行约束。支持 Shift 连选相邻片段、Command/Ctrl 增减选择、组成/取消 Group；群组
  保持成员相对时间并作为整体在同轨或跨轨移动。Clip 支持颜色选择，新素材按区分度较高的调色板
  轮换默认色，群组在时间线上有连接标识。新增 Project 重叠拒绝、Group/颜色序列化与 UI 集成
  覆盖；Composer、Video Studio、Video Tasks、Gallery 联合回归 `31/31` 通过，时间线算法独立
  验证覆盖左移碰撞、右移波纹、相连链与群组整体移动；Ruff、JavaScript 语法和目标文件 diff
  检查通过。固定 App Dev 因验收时 Mac 锁屏未能完成本轮 GUI 复验，源码由开发环境热挂载，待
  下次解锁后刷新即可使用。
- Composer Chat 面板临时隐藏（2026-09-06）：当前内嵌 Chat 区域不再参与布局，Clip Inspector
  改为占满底部宽度；聊天计划与编辑逻辑暂时保留，供后续迁移为独立 Chat MiniEntry 时复用。
  首次实机验收仍出现 Chat，确认并非浏览器缓存，而是固定 App Dev 的旧包仍在提供过期的内嵌
  WebUI，未实际命中当前源码热挂载。已通过 `build-app-dev-environment.sh` 标准入口重建固定
  `AI2Apps-app-dev.app` 并重启；新 Local 端口 `52717` 返回当前 Composer 脚本，实机界面已出现
  Group/Ungroup 与颜色功能且不再包含 Chat 控件。重建通过 release verification，运行后的固定
  App bundle identity、`app-dev` instance、Development/source-root/cloud Runtime 合同及严格
  codesign 校验均通过。
- Clip Inspector 可读性修复（2026-09-06）：经两轮 App-Dev 实机视觉复核，最终将标题、字段
  标签和输入值分别从原有 10/7/9 px 调整为 16/11/13 px，输入控件增高到 36 px，桌面布局从
  每行四项降到三项；同步提高文字、边框和禁用状态的对比度并增加蓝色键盘焦点轮廓。标题栏
  操作按钮使用单行居中的弹性布局，在空间不足时整组换行，避免 Group/Ungroup/Split 文本越出
  按钮边界。
- Composer 帧网格时间基准（2026-09-06）：Clip Inspector 的 Start/Duration 固定显示三位小数，
  并分别显示起始帧号和持续帧数。项目 FPS（默认 30）成为时间线结构编辑的最小单位；本地或
  Gallery 素材插入、拖放、Clip/Group 移动、左右裁切、播放头定位、分割、Inspector 输入、磁吸、
  ripple 推动及旧草稿恢复均统一量化到帧边界。后端在 Project 校验入口再次按 FPS 归帧，确保
  聊天编辑或其它客户端提交的亚帧小数不会进入渲染时间线。
- Composer Clip 关键帧（2026-09-06）：视频/图片 Clip 可在当前播放头所在帧添加多个关键帧，
  每帧保存 X/Y、宽高和透明度；目标关键帧可选择硬过渡、线性过渡或柔性缓入缓出。Inspector
  提供帧列表、选择、属性编辑和删除，时间线 Clip 显示菱形关键帧标记；预览区拖动、缩放及双击
  恢复素材尺寸会编辑当前选中的关键帧。关键帧使用 Clip 相对整数帧持久化，后端校验唯一性和
  Clip 范围，PyAV 导出使用与前端相同的插值语义；裁切会重映射或移除受影响关键帧，分割会将
  关键帧分配到左右片段并保持分割点的画面状态。已通过固定 App-Dev 环境重建与实机 UI 验证：
  Clip 可在播放头添加 F0 关键帧，Inspector 可编辑属性、删除关键帧，并可在硬过渡、线性和柔性
  三种模式间切换；重启后的 App-Dev Local 运行于 `127.0.0.1:54667`。
  - 固定端点关键帧（2026-09-06）：每个视频/图片 Clip 会自动拥有 `start` 与 `end` 两个端点关键帧，
    分别锁定在首帧与最后一个有效帧；界面以锁形图标区分且禁用删除，起始关键帧无前序画面，
    因此固定为硬过渡。调整 Clip 长度时结束关键帧自动随尾帧移动，裁切与分割会为结果片段重建
    正确的端点状态；后端保存校验也会补齐并归位端点，旧草稿可直接迁移。
  - 预览变换语义（2026-09-06）：播放头正好命中关键帧时，预览层以橙色边框和「关键帧」标记
    提示局部编辑，移动、缩放及双击恢复尺寸只写入当前关键帧；播放头位于两帧之间时，改用青色
    边框和「整个片段」标记，平移会给 Clip 基础位置及全部显式关键帧位置施加相同偏移，缩放会按
    宽高比例更新 Clip 与全部显式关键帧尺寸。关键帧的 X/Y、宽高、透明度允许留空，留空字段在
    预览和 PyAV 导出中均继承上一个关键帧的已解析值，Inspector 以占位值提示当前继承结果。
  - 淡化职责收敛（2026-09-06）：关键帧透明度成为视频画面淡入淡出的唯一机制，PyAV 导出不再
    把 Clip 的 Fade 参数额外乘入画面透明度，避免与关键帧动画叠加产生非预期结果。原 Fade 参数
    仍保留用于音轨包络与快速预览音量，Inspector 和中英文提示统一改名为「音频淡入/淡出」，且
    仅对含音频素材显示；聊天规划提示也明确这两个字段只影响音频。
  - 播放头磁吸与端点保护（2026-09-06）：在时间刻度或预览进度条拖动播放头时，会按同一 12 px
    阈值吸附到任意 Clip 的起点和终点，并以蓝色播放头反馈命中状态；关闭 Snap 后立即恢复逐帧
    移动。新增 `Cmd/Ctrl+N` 快捷键快速开关磁吸，工具栏提示同步标明快捷键。首尾关键帧的删除
    保护扩展到端点标记及首尾帧位置双重判断；选中关键帧时按 Delete/Backspace 只尝试删除当前
    关键帧，不再误删 Clip，端点帧保持锁定。后端仍会在收到缺失端点的数据时自动补回固定首尾帧。
    在轨道上单击 Clip 时，如果播放头位于片段范围之外，会比较与片段起点、终点的距离并跳转到
    更近的一端；播放头已在片段内时保持当前位置，实际拖动 Clip 时也不会触发这次跳转。
  - 关键帧位置与多选拖动（2026-09-06）：关键帧 Inspector 增加整数帧位置输入，普通关键帧可在
    Clip 内部帧之间移动，拒绝占用已有关键帧的帧位，并同步移动播放头；固定首尾关键帧的帧位置
    输入保持禁用。轨道多选后，拖动已选 Clip 会保留当前选择，并把与它在同轨排列中前后相邻的
    已选 Clip 组成临时移动块；无需素材边界恰好逐帧贴合，块内相对间隔保持不变。被动跟随的已选
    Clip 计入移动块尾边界，继续按现有 ripple 规则推动后方未选 Clip，从而维持同轨不重叠约束。
  - 轨道工具栏整理（2026-09-06）：移除预览上方重复的添加视频/音频轨按钮，只保留轨道区入口；
    Undo/Redo 以及每条轨道的静音、锁定、删除按钮提供不会被时间线裁切的浮层 Hover Tip 和无障碍
    标签。删除含 Clip 的轨道前显示可撤销确认，空轨道仍可直接删除。新增轨道时若当前选中了 Clip，
    会插入到该 Clip 所在轨道之后并重新编号轨道层级；没有选中 Clip 时仍追加到末尾。
    - Hover Tip 定位修复（2026-09-06）：提示层改为传送到页面顶层，脱离 Composer 的裁切上下文；
      水平方向使用真实指针位置并补偿 App Shell Mini-App 挂载偏移，垂直方向保持在控件上方 6 px，
      同时在窗口左右各保留 88 px 安全边界。固定 App Dev 重建后，新 Local 端口 `55529` 实机确认
      Undo 提示框与按钮中心对齐；Composer 专项测试 `10/10`、JavaScript 语法及 diff 检查通过。
  - 视频轨输出语义（2026-09-06）：视频轨的首个控制由音量图标改为眼睛图标，Hover Tip 明确为
    「隐藏/显示视频轨道」；音频轨继续使用扬声器图标和「静音/取消静音」。隐藏视频轨只关闭画面
    合成，素材自身的音频仍参与快速预览和 PyAV 导出混音；静音音频轨则继续完全排除其声音。
  - Clip 蒙版图（2026-09-06）：视频/图片 Clip 可从 Inspector 导入或从已登记图片素材中选择独立
    蒙版，草稿和渲染请求仅保存受作用域保护的不透明 `maskSourceId`。蒙版在快速预览和 PyAV 导出
    中始终拉伸至 Clip 当前画面尺寸；带 Alpha 的图片仅以 Alpha 通道决定可见度，没有 Alpha 的
    图片转换为亮度蒙版，黑色完全透明、白色完全不透明、中间灰度形成半透明。蒙版与原素材 Alpha
    及关键帧透明度相乘，API 在导出前验证蒙版 Source 存在且确实为图片。
  - 项目文件、素材替换与变速 ripple（2026-09-06）：Composer 工具栏新增打开、保存、另存为，
    使用 `.ai2video` JSON 项目文件；文件仅包含时间线结构和 AppInstance 作用域内的不透明 Source
    ID，不记录媒体真实路径。Local 以 4 MiB、严格 schema、绝对路径和素材作用域校验为边界，并
    通过同目录临时文件原子替换保存；自动草稿保留最近项目文件路径，`Cmd/Ctrl+S` 与
    `Cmd/Ctrl+Shift+S` 分别执行保存和另存为。Clip Inspector 可在同类已登记媒体源之间替换素材，
    保留布局、蒙版和关键帧，新源较短时复用右边界 ripple 收缩。视频/音频 Clip 的 Speed 编辑以
    保持源片段范围不变为语义，自动按 `旧时长 × 旧速度 ÷ 新速度` 对齐帧网格重算 Duration；变慢
    推后重叠/相接的同轨后续 Clip，变快向左收拢相接链，聊天变速指令使用相同路径。Composer 专项
    测试 `10/10` 通过，Ruff、JavaScript 语法、英文/中文 JSON 与 `git diff --check` 通过；固定
    `AI2Apps-app-dev.app` 已按标准流程重建，并彻底重启 Helper、Local 与 Shell。新 Local 运行于
    `127.0.0.1:59781`，实机确认 Open/Save/Save as 均正确本地化、旧的预览区加轨按钮已移除，选择
    Clip 后可见 Media source、Speed 与帧对齐 Duration 控件。
- Release notes 建议：Video Studio 现在可以在本地完成多轨视频剪辑、音轨拼接、图层合成与
  MP4 导出，并可通过聊天指令安全地批量调整时间线。
- 纳入 Build：待定。

### NXR-025：禁止 Local 修改已签名内嵌 Python Runtime

- 状态：`ready`
- 类型：Desktop Helper、Runtime 完整性、签名稳定性。
- 内容：`LocalLaunchPlan` 现在强制设置 `PYTHONDONTWRITEBYTECODE=1` 与
  `PYTHONNOUSERSITE=1`，并忽略父进程对这两个值的覆盖。Local 启动后不再向已签名的内嵌
  `site-packages` 写入 `__pycache__/*.pyc`，也不会加载用户 site-packages。
- 原因：Video Composer 实机验收发现，内嵌 Python 首次启动生成 `sitecustomize.pyc` 会改变
  Helper 的 sealed resources，使启动前通过的 `codesign --verify --deep --strict` 在启动后失败。
- 验证：Supervisor Core `72/72` 单元测试通过并覆盖两个强制环境变量；固定 App Dev 重建后，
  启动前与启动后均通过 `codesign --verify --deep --strict`，新 Helper/Local 在端口 `52667`
  健康运行，内嵌 site-packages 未再生成 `sitecustomize*.pyc`。
- 需要进入 App 的文件：
  - `apps/ai2apps-acefox/Sources/AI2AppsSupervisorCore/LaunchPlan.swift`
  - `apps/ai2apps-acefox/Tests/AI2AppsSupervisorCoreTests/SupervisorCoreTests.swift`
- 纳入 Build：待定。

### NXR-026：Mini-App ACPF 启动请求校验修复

- 状态：`ready`
- 类型：App-Shell Mini-App、ACPF 启动可靠性。
- 用户可见问题：Read Aloud 的直接配置入口会提交带 `returnTo` 但没有合法
  `resumeToken` 的 Intent，触发 ACPF 请求模型 422；Video Studio 在进入 ACPF 前保存的
  私有草稿包含后端严格 schema 未声明的 `pipelineId`，因此同样在配置档位界面出现前失败。
- 修复：Read Aloud 为每次非 Probe 配置请求生成稳定的非空恢复 Token，已有动作 Token
  继续优先复用；Video Studio 的 ACPF 私有草稿只提交后端声明并实际恢复的字段，不再携带
  冗余 `pipelineId`。
- 需要进入 App 的文件：
  - `ai2apps/web/static/js/readaloud.js`
  - `ai2apps/web/static/js/video_studio.js`
- 发行测试：
  - `tests/test_ai2apps_readaloud.py`
  - `tests/test_ai2apps_video_studio.py`
  - `tests/test_ai2apps_provisioning.py`
- 验证（2026-09-06）：JavaScript 语法检查通过；Read Aloud、Video Studio 与 ACPF
  专项回归 `53/53` 通过。固定 `AI2Apps-app-dev.app` 强制刷新后，实机分别从 Train
  Character 的“Configure voice environment”和 Text to Video 的“Configure generation
  environment”打开 ACPF 配置档位对话框，不再出现 `Request validation failed` 或
  `Video Studio draft is invalid`；验证停在档位选择并取消，没有启动安装或下载。
- Release notes 建议：修复 Read Aloud 与 Video Studio Mini-App 无法打开本地模型配置的
  问题。
- 纳入 Build：待定。

### NXR-027：已安装 Package 的统一 Studio Mini-App Registry 与可信挂载

- 状态：`ready`
- 类型：App-Shell 平台、Package 兼容扩展、Studio 扩展机制。
- 用户可见结果：已安装且启用的普通 App Package 可以在签名覆盖的 `app.yaml` 中用可选
  `mini_apps` 一次声明多个 Mini-App 及其 Studio placements；Video Studio、Read Aloud 与
  Imagine Studio 的既有 Mini-App 列表接口通过统一 Registry 合并内置项和已安装项。平台新增
  通用 discovery/mount API，挂载时复用 AppInstance、`app_mounts`、资源摘要校验、权限检查与
  现有 constrained/sandbox CSP 路由。Video Studio、Read Aloud 与 Imagine Studio 已接入共用
  客户端：Package Mini-App 会出现在已安装列表中，选中后以 Registry 返回的受限
  `content_url` 加载其中栏 WebUI。
- 向后兼容：没有 `mini_apps` 的旧 App Package 行为不变；Cloud 仍发布和下发既有
  `ai2apps.package-manifest.v1`、`type: app` 制品，不需要新的 Package 类型或 Cloud API。
  内置 ID 保留；多个 Package 的同 ID 冲突会从发现结果隐藏并拒绝挂载，不能覆盖内置实现。
- 安全边界：Package Mini-App 不允许 `host-adapter`，只允许 `schema`、`safe-html` 或
  `sandbox`；入口必须存在于签名文件索引；挂载要求匹配的 Studio AppInstance，session 和
  actor 权限继续由现有 Extension Manager 校验。
- 需要进入 App 的文件：
  - `ai2apps/extensions/archive.py`
  - `ai2apps/extensions/manager.py`
  - `ai2apps/studio/registry.py`
  - `ai2apps/api/studio_mini_apps.py`
  - `ai2apps/api/router.py`
  - `ai2apps/api/video_studio.py`
  - `ai2apps/api/readaloud.py`
  - `ai2apps/api/imagine_studio.py`
  - `ai2apps/web/static/js/studio_mini_apps.js`
  - `ai2apps/web/static/js/video_studio.js`
  - `ai2apps/web/static/js/readaloud.js`
  - `ai2apps/web/static/js/imagine_studio.js`
  - `ai2apps/web/static/css/studio_mini_apps.css`
  - `ai2apps/web/templates/system_apps/video_studio.html`
  - `ai2apps/web/templates/system_apps/readaloud.html`
  - `ai2apps/web/templates/system_apps/imagine_studio.html`
  - `docs/ai2apps-studio-mini-app-package-contract-v1.md`
- 发行测试：
  - `tests/test_ai2apps_extensions.py`
  - `tests/test_ai2apps_video_studio.py`
  - `tests/test_ai2apps_readaloud.py`
  - `tests/test_ai2apps_imagine_studio.py`
  - `tests/test_ai2apps_platform_api.py`
  - `tests/test_ai2apps_studio_mini_app_client.py`
- 验证（2026-09-06）：合并后的 Registry、Extension、三个 Studio、客户端和平台 API 专项
  回归 `55/55` 通过；新增用例覆盖已安装 Package
  discovery、Studio mount、content URL、旧 Mini-Entry/移动回退、未索引/特权入口拒绝、内置
  ID 保留及多 Package 冲突；四个 JavaScript 文件语法检查、专项 Ruff 与 `git diff --check`
  通过。当前工作树另有
  Video Studio Mini-App Chat 改动使既有 `test_video_studio_uses_first_party_surface_and_async_video_api`
  关于 `await this.generate()` 的断言失败；该行不属于本项改动，发布候选合并时需由对应改动处理。
- 当前边界：本项建立统一发现和可信 WebUI 挂载路径；跨 Package 的 Run/Step/Artifact、
  Asset-drop、Capability Broker 与 Coder 模板仍按后续独立合同推进。
- Release notes 建议：Studio 现在可以从已安装的兼容 Package 发现并安全挂载 Mini-App，
  同一 Package 可向多个 Studio 提供多个创作入口。
- 纳入 Build：待定。

### NXR-028：Mini-App Chat 对话控制机制

- 状态：`ready`
- 类型：App-Shell 平台、Studio UI、模型 Tool 调用、安全协议。
- 用户可见结果：Video Studio、Read Aloud 与 Imagine Studio 会根据当前 Mini-App 的
  `ai2apps.mini-app-chat/v1` 能力显示 Chat 入口；Chat-Mini-Entry 在每轮读取 Mini-App 提供的
  System Prompt、当前状态 Context 和白名单 Tool，通过对话更新可见草稿或启动当前操作。
  三个 Studio 的全部现有内置 Mini-App 均已接入。每个内置 Mini-App 另有独立 `help.md`；
  帮助正文不进入常驻 Context，只有模型判断用户在询问用法、输入、设置或故障排查时，才通过
  保留的 `read_mini_app_help` Tool 按需加载。Studio 左侧的 Mini-Apps、Assets、Chat 标签保持
  单行等分布局；Chat-Mini-Entry 将当前 Mini-App 说明与模型选择拆成两行，模型下拉框独占整行。
- 安全边界：模型没有通用 DOM、JavaScript、HTTP、文件系统或浏览器 Tool；同源且 channel
  绑定的 iframe 协议只允许调用当前合同中的 Tool，Studio 在执行前重新校验当前 Mini-App、
  Tool 名和参数。生成、渲染、导出等操作由 Studio 侧强制二次确认；能力扩张继续进入既有
  Capability Broker，浏览器操作继续遵守 WebDriver BiDi 单协议边界。
- 帮助边界：Tool 不接受资源路径，只能读取当前 Mini-App 绑定的 Markdown；Package 的帮助
  文件必须进入签名文件索引，内置与 Package 帮助均限制为 32 KiB，普通对话不加载正文。
- Package 扩展：签名 `app.yaml` 可声明可选 `chat` 合同；安装时校验 System Prompt、
  `studio-bridge` Context transport、签名 `help.md`、Tool 名、JSON object input schema 与确认策略。未声明
  Chat 的 Package Mini-App 不显示入口。
- 定义定位：Mini-App-Chat 是建议能力，不是 Mini-App 安装、发现、挂载或运行的强制条件；
  建议作者至少采用 Help-only 配置（按需 `help.md`、最小 Context、`tools: []`），需要对话控制时
  再增加状态与操作 Tool。
- 需要进入 App 的文件：
  - `ai2apps/studio/mini_app_chat.py`
  - `ai2apps/studio/registry.py`
  - `ai2apps/extensions/archive.py`
  - `ai2apps/web/static/js/mini_app_chat.js`
  - `ai2apps/web/static/js/chat_mini.js`
  - `ai2apps/web/static/js/video_studio.js`
  - `ai2apps/web/static/js/readaloud.js`
  - `ai2apps/web/static/js/imagine_studio.js`
  - 三个 Studio 模板与 `ai2apps/web/static/css/mini_app_chat.css`
  - `ai2apps/web/static/help/mini_apps/*/help.md`
  - `docs/ai2apps-mini-app-chat-architecture.md`
  - `docs/ai2apps-studio-mini-app-package-contract-v1.md`
- 发行测试：
  - `tests/test_ai2apps_mini_app_chat.py`
  - `tests/test_ai2apps_chat_mini.py`
  - `tests/test_ai2apps_video_studio.py`
  - `tests/test_ai2apps_readaloud.py`
  - `tests/test_ai2apps_imagine_studio.py`
  - `tests/test_ai2apps_extensions.py`
- 验证（2026-09-07）：五个相关 JavaScript 文件通过 `node --check`，Python 合同模块通过
  编译与 Ruff 检查；Chat Mini、三个 Studio、Mini-App Chat 合同和 Extension 专项回归 `55/55`
  通过。实时合同同时执行 16,000 字 System Prompt、64 KiB Context、64 个 Tool、Tool 名、
  object input schema 与确认策略上限校验；切换 Mini-App 会清空旧对话上下文。帮助正文通过
  `read_mini_app_help` Tool 懒加载，不随 System Prompt 和状态 Context 常驻发送。2026-09-07 已在
  `AI2Apps-App-Dev` 的 Read Aloud 窄侧栏实机刷新验证：三个入口同排，模型选择为独立全宽行。
- Release notes 建议：Studio 的每个内置 Mini-App 现在都可以通过专属 Chat 入口理解当前
  草稿，并在显式 Tool 与确认边界内按自然语言修改设置和执行工作。
- 纳入 Build：待定。

### NXR-029：Discover 独立 Mini-App 目录

- 状态：`ready`
- 类型：Discover UI、App Package 构建合同、Mini-App Registry 索引、Cloud 查询合同。
- 用户可见结果：Discover 一级筛选调整为 `All / Apps / Mini-Apps / Agents / Models / Services`；
  Mini-Apps 拥有效率、图像、视频、音频、文档、自动化、开发和工具等独立二级目录，并允许
  Package 使用可扩展分类。一个 App Package 可同时显示一张完整 App 卡片和多张 Mini-App
  组件卡片。
- 生命周期边界：Mini-App 仍不是新的 Package 类型；组件卡片的安装、升级、签名验证、权限、
  回滚和卸载全部绑定所属 App Package。已安装旧 Package 直接从本地已验证 `app.yaml` 生成组件
  目录，不要求重新安装。
- Package 合同：构建器从 `app.yaml.mini_apps` 自动生成签名 `ai2apps.json.miniApps` 投影，包含
  canonical component ID、名称、版本、生命周期、Catalog 分类和 Studio placements；手写索引
  与 App 定义不一致时拒绝构建，安装时再次交叉校验。
- 需要进入 App 的文件：
  - `ai2apps/packages/contract_v1.py`
  - `ai2apps/packages/registry.py`
  - `ai2apps/web/static/js/discover.js`
  - `ai2apps/web/templates/system_apps/discover.html`
  - `ai2apps/web/i18n/en.json`
  - `ai2apps/web/i18n/zh.json`
  - `docs/ai2apps-studio-mini-app-package-contract-v1.md`
  - `docs/ai2apps-cloud-mini-app-discovery-requirements.md`
- 发行测试：`tests/test_ai2apps_discover_categories.py`、`tests/test_ai2apps_registry_v1.py`、
  `tests/test_ai2apps_extensions.py`。
- 当前验证（2026-09-07）：合同、Registry、Extension、Coder 与 Discover UI 联合回归 `89/89` 通过；
  Ruff、JavaScript 语法、i18n JSON 与 `git diff --check` 通过。Cloud 尚需按交接文档接受并索引
  新的签名 `miniApps` 字段，客户端在此之前保留 App Package 查询兼容路径。固定 App Dev 已
  完整重开至 Local 端口 `56501`；实机确认一级 `Mini-Apps` 以及效率、图像、视频、音频、文档、
  自动化、开发和工具二级目录均正常显示。当前生产 Cloud 尚无 `miniApps` 索引，因此目录按
  预期显示为空，不伪造独立 Package。
- Release notes 建议：Discover 新增独立 Mini-Apps 目录，可按任务领域查找组件；安装仍安全地
  复用所属 App Package，不产生重复 Package 或版本。
- 纳入 Build：待定。

### NXR-031：Discover 统一游标分页

- 状态：`ready`
- 类型：Discover UI、Catalog 查询兼容层、Cloud 分页合同。
- 用户可见结果：Discover 的 Apps、Mini-Apps、Agents、Models、Services 与混合 All 目录统一使用
  24 条首屏和显式“加载更多”；搜索词或分类改变时从第一页开始，返回旧组合时恢复已加载内容与
  下一页游标，避免重复请求和滚动内容丢失。
- 兼容边界：Desktop 接受 `nextCursor`、`next_cursor` 及分页 envelope；旧 Cloud 返回满页但不返回
  游标时，Desktop 自动按旧接口上限预取 100 条并在本地以 24 张卡片分页，避免升级过渡期隐藏
  既有 Package。追加结果按卡片稳定 ID 去重，Mini-App 使用 `packageId#componentId`。
- Cloud 交接：`docs/ai2apps-cloud-discover-pagination-requirements.md` 要求 Cloud 提供查询绑定的不透明
  游标、混合 All 排序、模型原生过滤以及 Mini-App 组件级分页。Cloud 升级前，Mini-App 仍可按
  Package 页展开，模型仍使用 Local 兼容过滤，因此页面数量可能不足 24，但不会破坏现有目录。
- 需要进入 App 的文件：
  - `ai2apps/web/static/js/discover.js`
  - `ai2apps/web/templates/system_apps/discover.html`
  - `ai2apps/web/i18n/en.json`
  - `ai2apps/web/i18n/zh.json`
  - `docs/ai2apps-cloud-discover-pagination-requirements.md`
- 发行测试：`tests/test_ai2apps_discover_categories.py`、Catalog API 与 Cloud Client 回归。
- 当前验证（2026-09-07）：Discover、Registry 与 Cloud Client 联合回归 `86/86` 通过；JavaScript
  语法、i18n JSON 和 `git diff --check` 通过（沙箱退出时仅有预期的 Metal unavailable 提示）。
  固定 App Dev `AI2Apps-App-Dev: M5Max128G · App-Dev 127.0.0.1:56501` 曾以 6 条试验页长完成
  游标追加、加载态和去重验收；最终产品页长已按用户确认恢复为 24，相关 Discover 定向测试
  `20/20` 与 JavaScript 语法检查再次通过。
- Release notes 建议：Discover 的每个目录现在都可按需加载更多 Package，同时保留当前筛选和
  已加载结果。
- 纳入 Build：待定。

### NXR-032：App Dev 重启 Local 保留实时源码根

- 状态：`ready`
- 类型：App Dev Helper、Local 进程监督器；仅影响固定开发环境。
- 问题：Helper 首次启动会把已验证的 `AI2AppsDevelopmentSourceRoot` 传给
  `LocalProcessSupervisor`，但用户选择重启 Local 后，`replaceSupervisor()` 重建监督器时漏传该
  参数，导致新 Local 静默退回 App 内嵌旧源码。表现为 Discover 新筛选和分页在重启后消失。
- 修复：Helper 在生命周期内保留已验证的开发源码根；首次启动和每次重建监督器现在统一经过
  `makeLocalSupervisor()`，由该唯一入口同时注入控制凭据、Development Runtime 标记和源码根，
  避免两段重复构造逻辑以后再次漂移。生产 App 没有 Development 标记，源码根仍为 `nil`，不会
  获得源码挂载能力。Python 回归门禁还会要求 Helper 只保留一个底层 Supervisor 构造点，并确认
  首次启动与重启都调用同一工厂。
- 需要进入 App 的文件：
  - `apps/ai2apps-acefox/Sources/AI2AppsHelper/main.swift`
  - `tests/test_ai2apps_helper_control.py`
- 当前验证（2026-09-07）：唯一 Supervisor 工厂重构后，Swift Helper/Supervisor 全量测试 `72/72`
  通过；Helper 控制与 Discover 回归门禁 `28/28` 通过。固定 App Dev 已再次通过
  `build-app-dev-environment.sh` 重建并完成签名/Release App 校验。首次启动端口 `56108` 的 Discover
  显示当时配置的首屏、Mini-Apps 和 `Load more`；随后通过受保护 Helper 接口真实执行
  `local.restart`，新进程端口 `56624` 再次打开 Discover 仍显示相同内容，确认重启继续使用当前
  开发源码。
- Release notes 建议：不适用；这是开发环境可靠性修复。
- 纳入 Build：App Dev 环境专用，不进入生产 Build。

### NXR-030：Media Voice Studio Suite 五条 Mini-App 执行链路

- 安装入口位置修正（2026-09-10）：按用户澄清，删除 STT/TTS 下拉框下方按钮，将“安装更多模型”放在两个下拉菜单末尾。动作项不写入 audioSettings，触发 ACPF 前立即恢复实际模型值，取消安装不改变原模型。新增执行实际 JavaScript 的动作项与正常选择回归测试。
- 安装更多模型（2026-09-10）：Chat STT/TTS 选择器下新增本地化入口，进入 ACPF 全部能力配置列表；新增 installMore 浏览模式避免已有可用模型时提前返回，已安装 Checkpoint 对应项显示“已安装”并禁选，全部已安装时仍可查看列表但无法继续安装。保持 ACPF 原有确认、许可证和下载流程。变更涉及 Local Python，App-Dev 需重启 Local 后验收。
- Chat 语音模型可用性修复（2026-09-10）：STT/TTS 列表只保留已就绪模型，综合目录、管理目录和运行状态排除缺权重、隐藏、加载失败项；Package 需明确 checkpoint_ready 才显示，已安装但尚未驻留内存的普通模型不因 loaded=false 被误排除。旧选项不可用时回退至可用项，无可用项则清空。新增实际 JS 判定回归测试，避免未安装 Base/VoiceDesign 仍可选择后才报 Checkpoint is not installed。
- 状态：`ready_for_package_rebuild`
- 类型：Studio Package、Local Capability Broker、语音模型调用。
- 用户可见结果：`ai2apps/media-voice-studio-suite 0.1.0` 在一个普通 App Package 中交付五个
  音视频 Mini-App；其中“录音文本记录”已可从 Read Aloud 或 Video Studio 的可信 mount
  调用本地 MLX WhisperX Detailed Transcription Compact/Quality，显示分段时间和匿名说话人，
  并允许用户为角色指定名称后导出 JSON。“人声和背景音分离”也已可通过同一 Broker 调用
  capability contract 匹配的 MLX Demucs provider，选择二轨/四轨 profile 并下载包含 WAV stems
  与 `separation.json` 的 ZIP。视频字幕可生成 SRT/WebVTT/ASS、调用现有 Standard 模型路由翻译、
  输出双语字幕并选择烧录 MP4。录音和视频角色换声采用两阶段交互：先识别匿名说话人，再使用
  授权参考声音只替换所选角色并保留其他对白、背景和原视频画面。
- App Shell 边界：该 Package 是纯 Mini-App provider，声明 `navigation.launcher: false`，不再作为
  独立 App 出现在 App Launcher、Dock、App 建议或 Mobile App 列表；五个 Mini-App 仍只通过其
  Read Aloud / Video Studio placement 发现和挂载。真正提供独立顶层 App 的混合 Package 保持
  默认可启动。
- 安全边界：Host 每次调用重新核验 actor、mount、Studio、Mini-App canonical ID、Provider
  App、有效 Package digest 和声明能力；详细转写只允许固定模型配置，音轨分离只选择已验证
  capability contract 明确支持所选 profile 的 `audio_processing` provider。媒体在 Host 中
  规范化为有界 PCM WAV，Mini-App 不取得 Worker endpoint、checkpoint 路径或任意本地路径。
  参考换声只选择 capability contract 声明 `reference_audio` 的 provider，并在 Host API 再次
  强制校验权利确认；视频字幕和音轨替换只使用内嵌 PyAV，不启动外部 ffmpeg。
- 需要进入 App 的文件：
  - `ai2apps/studio/capability_broker.py`
  - `ai2apps/studio/media_workflows.py`
  - `ai2apps/studio/__init__.py`
  - `ai2apps/api/studio_mini_apps.py`
  - `packages/ai2apps-media-voice-studio-suite/*`
  - `docs/ai2apps-studio-mini-app-package-contract-v1.md`
- 发行测试：
  - `tests/test_ai2apps_studio_capability_broker.py`
  - `tests/test_ai2apps_studio_media_workflows.py`
  - `tests/test_ai2apps_media_voice_studio_suite.py`
  - `tests/test_ai2apps_studio_mini_app_client.py`
  - `tests/test_ai2apps_extensions.py`
- 当前验证（2026-09-07）：Broker mount/digest/声明约束、详细转写、Demucs、Seed-VC provider
  probe、WAV 规范化、目标角色时间窗替换、背景保留、SRT/VTT/ASS、CJK 字幕烧录、MP4 音轨替换、
  JSON/ZIP/WAV/MP4 artifact 透传、multipart API、Registry 和 Extension 回归共 `85 passed`；Ruff、
  JavaScript 语法和 `git diff --check` 通过。Package Contract 重复构建字节一致，并修复 App Package
  误将自身 `dist/` 制品再次打包的递归问题。固定 `AI2Apps-App-Dev` 已重启并在真实 OpenAPI
  中加载三类 Studio Mini-App mount/capability 路由。正式 Publisher 签名制品与 envelope
  已使用注册公钥指纹离线验签通过，详见
  `docs/ai2apps-media-voice-studio-suite-0.1.0-signed-build.md`。正式候选使用显式的旧 Cloud schema
  兼容构建：外层不携带可选 `miniApps` 搜索投影，五个组件仍全部保留在已索引、已签名的
  `app.yaml`，安装后发现机制不变。Cloud 组件级 Discover 仍按已交付需求后续升级；真实
  checkpoint 端到端运行在 Package 安装后继续作为发布验收。
- App Launcher 修复验证（2026-09-08）：新增 `navigation.launcher: false` 的 manifest 类型校验和
  Launcher catalog 过滤；确认 provider Package 从 `list_apps()` 消失后，其 Studio Mini-App 仍可
  发现、创建 provider AppInstance 并完成可信 mount。Extension、Development source mount、
  Media Voice Suite、Capability Broker、Mini-App client 与 Shell 回归 `158/158` 通过，Ruff 与
  `git diff --check` 通过。现有 0.1.0 已签名候选早于该 manifest 改动，正式发布前必须按标准
  Package runbook 重新生成签名制品与 receipt，不得继续使用旧候选。
- Studio 原生 UI 对齐（2026-09-09）：五个 Package Mini-App 的共享 WebUI 已改用与内置 Studio
  一致的白色中性表面、紧凑标题、分隔线区块、表单密度、黑色主按钮和标准状态色；capability ID
  默认折叠为可展开的“所需能力”诊断信息。Read Aloud、Video Studio 与 Imagine Studio 的宿主
  标题栏在 Package iframe 挂载时固定置于其上方，不再落到内容底部。变更只涉及 UI Entry 与
  Studio 外围布局，没有放宽 sandbox、mount、CSP、Capability Broker 或签名安装边界；五个入口
  统一使用版本化静态资源，并新增视觉契约回归门禁。相关 Studio、Package、源码热挂载与
  Extension 回归 `60/60` 通过，JavaScript 语法和 `git diff --check` 通过；固定
  `AI2Apps-App-Dev: M5Max-128G 127.0.0.1:57115` 已通过强制刷新实机确认标题、依赖按钮、折叠能力
  信息和 Package 工作区顺序正确，并抽查 Video Speaker Voice Replacement 与 Detailed
  Transcription 两个入口共享同一视觉层。
- Package 单滚动面修复（2026-09-09）：新增 source-bound、版本化且高度有界的
  `ai2apps:mini-app-resize/v1` 协议，Package UI 用 `ResizeObserver` 报告内容高度，三个 Studio
  宿主按当前 iframe 的 `contentWindow` 核验消息后扩展中栏。宿主标题与 Package 内容现在随 Studio
  页面一起滚动，不再保留压缩可用面积的 iframe 内层纵向滚动；未实现协议的旧 Package 仍保留
  620px 兼容高度和内部滚动，不改变既有 Package 可用性与安全边界。共享 Client、三个 Studio、
  Media Voice Package、源码热挂载和 Extension 联合回归 `60/60` 通过，两个 JavaScript 文件语法及
  `git diff --check` 通过；固定 App-Dev 已强制刷新并重新挂载 Detailed Transcription，确认新版
  resize Client 与 Package Entry 同时加载。
- Release notes 建议：音视频语音套件现在提供五个可执行 Mini-App：角色化详细转写、音轨分离、
  录音角色换声、可翻译/烧录的视频字幕，以及保留画面的视频角色换声。
- 纳入 Build：待定。

### NXR-033：Development Bundle 直接热挂载 Package 源码

- 状态：`ready`
- 类型：客户端开发体验、Package/App/Mini-App 基础设施
- 用户可见结果：开发 App Package 时不再需要先构建、签名并安装 `.ai2app`；固定
  `AI2Apps-App-Dev` 和重新构建后的通用 `AI2Apps-dev.app` 可从当前仓库
  `packages/<package>/` 直接发现 App 与 Studio Mini-App。HTML/CSS/JavaScript 刷新生效，
  `app.yaml` 在重新读取目录时热加载。
- 安全与兼容边界：只在 Helper 同时提供 Development Runtime 标记和 Bundle 固定绝对源码根
  时启用；只扫描 `packages/` 的非符号链接直接子目录；源码资源继续经过 AppInstance 权限、
  sandbox 和路径边界检查。开发挂载不创建 Package Store 安装记录，生产 Helper、签名安装、
  Cloud Registry 和旧 Package 机制保持不变。
- 需要进入 App 的文件：
  - `ai2apps/extensions/development.py`
  - `ai2apps/extensions/manager.py`
  - `ai2apps/platform_runtime.py`
  - `apps/ai2apps-acefox/scripts/build-dev-app.sh`
  - `docs/ai2apps-studio-mini-app-package-contract-v1.md`
  - `docs/ai2apps-app-development-guide.md`
  - `docs/ai2apps-studio-app-ui-design-standard-v1.md`
- 发行测试：
  - `tests/test_ai2apps_development_packages.py`
  - `tests/test_ai2apps_extensions.py`
  - 在固定 `AI2Apps-App-Dev` 中从源码发现 Media Voice Studio Suite，打开 Package Mini-App，
    修改源码并刷新确认实时生效。
- 当前验证（2026-09-07）：开发源码加载器已通过真实 Media Voice Studio Suite manifest
  校验并发现 5 个 Mini-App；Package/Extension/Studio 合同回归 `62/62` 通过，确认资源热修改、
  `app.yaml` 热加载、重复资源请求不产生定义 revision 写放大、无安装记录以及缺少
  Development Runtime 标记时 fail-closed；新增同一数据库先挂载源码、再无标记重启的回归，
  确认旧 development 定义会被停用。Ruff、Shell 语法、`git diff --check` 均通过。
- 标准流程文档（2026-09-07）：非内置 Mini-App 的规范生命周期已统一为“App Package 源码
  合同 → Development source mount → 真实 Studio 热修改联调 → 签名制品 → 干净实例安装态
  回归 → 标准发布”。Package 主合同、通用 App 开发指南和 Studio/Mini-App 设计规范均已建立
  交叉入口，并明确源码态不是可信安装身份、不能替代签名制品与安装态 Release Gate。
- 实机验收（2026-09-07）：固定 `AI2Apps-App-Dev` 仅重启 Local 后运行于端口 `58279`；
  Video Studio 从源码显示 Media Voice Suite 的 4 个视频相关 Mini-App，并成功把 Detailed
  Transcription 挂载为 sandbox。临时把 `app.yaml` 名称改为 `SOURCE HOT RELOAD` 后刷新即在
  界面出现，恢复源码并刷新后正常还原；平台数据库中该 App 的 development source 定义为
  enabled，`interactive_packages` 安装记录为 0。通用 `AI2Apps-dev.app` 也已用标准脚本重建，
  旧 App 可恢复地归档为 `AI2Apps-dev-20260907-131241.app`，新 Bundle 通过严格 codesign，
  主 App 与 Helper 均固定源码根；新 `dev` Local 在端口 `59685` 启动并同样确认 development
  定义启用、正式安装记录为 0。
- 纳入 Build：待定。

### NXR-037：AI2Apps Official Cloud Connector 双许可证边界

- 状态：`ready`
- 类型：发行许可、Cloud Connector、品牌治理。
- 用户可见变化：AI2Apps 客户端与本地 Runtime 继续默认使用 Apache-2.0；客户端内的
  Official Cloud/OpenAI Connector 从本版本起采用 BSL 1.1。仅连接 AI2Apps 官方 Cloud
  的生产客户端无需商业授权；实现、连接或提供替代 Cloud 服务需要另行取得商业授权。
- 转换规则：本版本的 Change Date 为 `2029-09-07`，届时 Connector 自动转换为
  Apache-2.0。既有 Apache-2.0 版本不追溯撤销授权。
- 商标边界：软件许可证不授予 AI2Apps 名称、Logo、图标或其他来源标识的权利；允许依法
  进行真实、指称性兼容说明，但修改版不得造成官方、合作、认证或背书混淆。
- 需要进入 App 的文件：`LICENSE-POLICY.md`、
  `LICENSES/AI2APPS-CLOUD-CONNECTOR-BSL-1.1.md`、`TRADEMARKS.md`、`NOTICE`、
  `README.md`、`README.zh.md`、`pyproject.toml`、`docs/CONTRIBUTING.md`，以及许可证
  清单列明的五个 Cloud Connector Python 文件。
- 当前验证：许可证元数据、文件级 SPDX 标识、英文/中文说明及发行 NOTICE 已对齐；
  setuptools 已成功解析 Core Metadata 并把全部许可证文件加入 wheel manifest，wheel 的后续
  native build dependency gate 因本机缺少 `cmake>=3.27` 停止；`git diff --check` 通过。
- 纳入 Build：待定。

### NXR-039：未完工内置 App 的 Launcher 开发中状态

- 状态：`ready`
- 类型：App Shell、产品可用性边界。
- 用户可见变化：Sharing、Environment、Messager、Bench 和 Agents 继续显示在 App Launcher 中，但卡片统一
  置灰并显示本地化的“正在开发”，不能点击、Pin 到 Dock 或从旧实例入口打开。
- 安全与兼容边界：内置 manifest 使用显式 `navigation.status: development`；Shell 启动函数、
  App Runtime 启动入口和内置 App 直达路由均拒绝启动，Messager 同时从 Mobile 可启动目录和
  App 建议中排除。其他内置 App 以及 `navigation.status` 缺省为 `active` 的第三方 App 行为不变。
- 需要进入 App 的文件：`ai2apps/apps/system.py`、`ai2apps/extensions/archive.py`、
  `ai2apps/extensions/manager.py`、`omlx/admin/routes.py`、`ai2apps/web/static/js/shell.js`、
  `ai2apps/web/static/css/shell.css` 和 `ai2apps/web/i18n/*.json`。
- 发行测试：`tests/test_ai2apps_extensions.py`、`tests/test_ai2apps_shell.py`。
- 实验标记补充（2026-09-10）：Terminal 与 Coder 的 manifest 新增独立的
  `navigation.experimental` 标记，由目录 API 传到 Launcher，在 App 图标右侧显示本地化的
  “实验 / Experimental”徽标，与图标底部对齐；名称独立成行。仍保持 active，允许正常启动与 Pin。涉及
  `ai2apps/apps/system.py`、`ai2apps/extensions/manager.py`、`omlx/admin/routes.py`、
  Shell JS/CSS 与九种语言文案。按用户要求仅修改源码，未更新、启动或测试 App。
- Agents 补充（2026-09-10）：`ai2apps.agents` 复用开发中状态，在 Launcher 置灰并显示
  本地化的 “In development”，禁用启动与 Pin；同步调整目录状态和直达入口回归。
  Shell 回归 `114/114` 通过，`git diff --check` 通过；尚未做运行中 App 的界面验收。
- Bench 补充（2026-09-09）：`ai2apps.benchmark` 复用开发中状态，Launcher 置灰并显示
  “In development”（随界面语言本地化）；同步调整目录状态与直达入口回归。
  Shell 回归 `114/114` 通过，`git diff --check` 通过；尚未做运行中 App 的界面验收。
- 当前验证（2026-09-08）：App/Extension 与 Shell 契约回归 `135/135` 通过；相关 Python 文件
  Ruff 通过，九种语言 JSON 全部可解析，Shell JavaScript 语法及 `git diff --check` 通过。
- 纳入 Build：待定。

### NXR-040：Read Aloud 更名为 Voice Studio

- 状态：`ready`
- 类型：App Shell、品牌命名与本地化。
- 用户可见变化：内置 `ai2apps.readaloud` 的产品展示名统一为 `Voice Studio`，中文显示名
  同步为“语音工坊”；Launcher、Studio 页头、项目弹窗、辅助功能文案及运行反馈不再显示
  旧品牌名 `Read Aloud`。
- 兼容边界：App ID、路由、模块名、持久化表和既有项目数据继续使用 `readaloud` 身份，
  本次仅变更用户可见品牌与默认标题，不触发数据迁移。
- 需要进入 App 的文件：`ai2apps/apps/system.py`、`ai2apps/api/readaloud.py`、
  `ai2apps/readaloud/tasks.py`、`ai2apps/web/templates/system_apps/readaloud.html`、
  `ai2apps/web/static/js/readaloud.js`、`ai2apps/web/i18n/en.json`、
  `ai2apps/web/i18n/zh.json`，以及对应产品/Studio 规范与回归测试。
- 当前验证（2026-09-09）：Ruff、英中 JSON、JavaScript 语法和 `git diff --check` 通过；
  Read Aloud/Shell 合同回归 `121/121` 通过。固定 `AI2Apps-App-Dev` 的 `app-dev` Local 已
  通过实例专属 Helper 控制通道重启，实机确认 Dock、Quick Start、活动 App、Studio 页头、
  副标题及辅助功能导航均显示 `Voice Studio`，URL 与 App ID 仍为 `ai2apps.readaloud`。
- 纳入 Build：待定。

### NXR-045：Chat 云端多模态模型图片上传能力判断

- 状态：`ready`
- 用户可见结果：修复 GPT 5.6 Luna 等云端模型在运行状态表中缺少 `vlm` 标记时，Chat 隐藏图片上传入口的问题。
- 实现：图片输入判断同时读取模型目录类型、模型能力声明和运行状态；保留目录返回的原始 capabilities，识别图片输入与识图能力。纯图片生成能力不会开启图片输入。
- 文件：`ai2apps/web/templates/chat.html`、`tests/test_chat_ui_overhaul.py`。
- 验证：执行实际 JavaScript 判断函数，覆盖目录 VLM、数组及对象能力、明确关闭、纯文本、图片生成和运行状态回退。
- Test 验证（2026-09-09）：通过固定 `build-test-app.sh` 重建并启动 `AI2Apps-test.app`（0.1.0 / Build 2195，当前工作区快照）；包校验和深层严格签名校验通过，包内 Chat HTML 与工作区逐字节一致，`test` Local `/health` 返回 `healthy`。保留实例数据，旧包已归档；尚未进行真实图片发送验收。本次不是生产发布。
- 纳入 Build：待定。

### NXR-046：Video Studio 模型下拉框接入“安装更多模型”

- 状态：`ready`
- 类型：Video Studio、内置 Mini-App、ACPF 模型配置入口。
- 用户可见变化：文生视频、图生视频和参考素材视频 Mini-App 共用的模型下拉框在末尾新增
  本地化“安装更多模型”；没有可用视频模型时仍可直接进入安装流程。
- 交互与兼容边界：该菜单项仅作为操作，不写入 Studio 草稿、Shell 状态或视频生成请求；
  选择后立即恢复原模型，并以 `installMore: true` 启动共享 ACPF，已有模型就绪时也不会被
  `already_ready` 快速路径跳过。安装完成后刷新完整模型目录并保留仍有效的原选择，取消或
  失败同样不改变选择；并发刷新只允许最新请求发布结果。Package Mini-App 的质量/Profile
  下拉框不是模型 ID 选择器，继续通过 mount-bound Capability Setup 使用 ACPF。
- 需要进入 App 的文件：`ai2apps/web/templates/system_apps/video_studio.html`、
  `ai2apps/web/static/js/video_studio.js`、`ai2apps/web/i18n/en.json`、
  `ai2apps/web/i18n/zh.json`、`tests/test_ai2apps_video_studio.py`。
- 当前验证（2026-09-10）：Video Studio 与 ACPF 回归 `51/51` 通过；Ruff、英中 JSON、
  JavaScript 语法和 `git diff --check` 通过。
- 纳入 Build：待定。

### NXR-052：Studio Mini-App 列表可读性提升

- 状态：`ready`
- 类型：Imagine Studio、Voice Studio、Video Studio 界面样式。
- 用户可见变化：三个 Studio 左侧 Mini-App 列表的主图标由 14–15px 放大到 18px，标题由
  10px 放大到 12px，说明文字由 8px 放大到 10px；Imagine Studio 的补充信息和收藏图标
  同步适度放大。
- 布局边界：不改变 Mini-App 卡片的宽度、最小高度、内边距、网格列、图标容器尺寸或列表
  间距，仅调整卡片内容的字体、行高与 SVG 尺寸。
- 需要进入 App 的文件：`ai2apps/web/static/css/imagine_studio.css`、
  `ai2apps/web/static/css/readaloud.css`、`ai2apps/web/static/css/video_studio.css`。
- 当前验证（2026-09-10）：Video/Voice/Imagine Studio 回归 `25/25` 通过；样式合同检查确认三类
  卡片仍保持原有 `62px`、`58px`、`70px` 最小高度以及原有宽度、内边距、网格列和图标容器。
  固定 `AI2Apps-App-Dev: M5Max-App-Dev 127.0.0.1:62433` 已逐一打开三个 Studio 实机验收，
  左侧图标和文字明显增大，卡片尺寸、排列和单行截断保持正常。
- 纳入 Build：待定。

- 右侧状态统一（2026-09-10）：三个 Studio 的列表使用深灰色下载图标表示依赖待准备，
  可用条目显示收藏星标（未收藏浅灰、已收藏深灰）；规划条目显示灰色不可用标记。
  Voice/Video 新增独立收藏按钮与本地持久化，点击收藏不切换当前 Mini-App；Imagine 保留
  原有收藏存储。卡片尺寸保持不变。涉及上述 CSS 以及三个 Studio 模板、Voice/Video JS。
  回归 `25/25`、JS 语法与差异检查通过；App-Dev（端口 49562）确认新版模板加载、Voice
  就绪条目显示星标而缺依赖条目显示灰色下载图标，Video 收藏切换不会改变当前 Mini-App。

- 列表顶部简化（2026-09-10）：Imagine Studio 移除搜索与“全部 / 收藏 / 最近”筛选区，
  直接展示已安装列表，与 Voice/Video 保持一致；列表不再受隐藏筛选条件影响，保留原有
  可用项优先顺序和卡片收藏。同步更新 Studio 手册与现有模板回归。

- 三列独立滚动（2026-09-10）：共享 `ai2apps/web/static/css/studio_mini_apps.css` 将三个
  Studio 限制在宿主视口内，工作区三列独立滚动；左栏选择区固定，列表占据剩余高度并可
  滚到底。修复 Imagine 列表被裁切；窗口变窄时输出不再堆叠到页面下方。Package 内容
  高度协议保留，内容扩展只影响中栏滚动范围。手册第 4.1 节同步更新，并替代此前整页
  滚动的要求。App-Dev 已实测 Imagine 列表到底，顶部选择区与其它列位置保持不变。
  Voice 三列布局与 Video 中栏独立滚动已实机确认；三个 Studio 回归 `25/25` 通过，
  `git diff --check` 通过。

- Coder 入口统一（2026-09-10）：Voice/Video 列表末尾说明文字替换为与 Imagine 一致的
  全宽“在 Coder 中创建”按钮，使用相同 Shell 启动入口并传入当前 Studio placement。
  涉及两个 Studio 模板/JS、共享 Studio CSS、英中文案，手册同步补充。

- Header 统一（2026-09-10）：三个 Studio 使用共享 64px Header，左侧图标与名称，右侧
  依次为刷新/左栏/右栏图标按钮；移除副标题与云端/本地徽标。Imagine 本地模型配置移到
  中栏模型设置下方，Voice 中栏重复开关移除。涉及三个模板、共享 CSS、英中文案，
  手册第 4.2 节记录尺寸、状态、本地化及移动端规则。
  三个 Studio 已在固定 App-Dev 实机确认 Header 对齐及 Image 模型配置入口位置；
  更新旧副标题断言后，Voice 回归 `8/8`，Video/Imagine 回归 `17/17` 通过，JSON 与差异检查通过。

- Mini-App Header 精简（2026-09-10）：三个中栏只显示名称与信息展开入口，版本/来源/说明
  收进详情；移除重复创建标题、常驻就绪徽标，保留配置及 Run 操作。Imagine 补齐白色卡片。
  涉及三个 Studio 模板、共享 CSS、英中文案；Mini-App 开发合同及设计手册同步记录规范。
  实机确认 Voice 单标题及信息展开、Image 白色卡片与直接输入布局；更新旧重复标题断言后
  Video/Voice 回归 `14/14`、Imagine 回归 `11/11` 通过，差异检查通过。

### NXR-PROCESS-001：建立下一版 Release 滚动台账

- 状态：`ready`
- 类型：发布治理；不改变 App 二进制功能。
- 内容：建立本文件，并将登记、构建门禁、归档和重置规则加入 `AGENTS.md` 与
  `docs/ai2apps-desktop-release-runbook.md`。
- 验收：未来 Desktop 发布必须先逐项处理本文件，不再仅根据工作区 diff 临时整理范围。
- 纳入 Build：不适用；随下一次源码提交生效。

### NXR-ZIMAGE-BASE：独立普通版 Z-Image Package（ready）

- 2026-09-11 最终 App 验收通过（覆盖下方历史阻塞）：port 59377 重启后 ACPF Retry 达到 ready，无重复下载。Imagine Studio 真实 Base / 1024² / 30 步 / CFG4 文生图成功；result isr_6a08567f2ff94a419bc9117e8863d297，Artifact imagine-text-to-image-ffa5f17d.png。Add to Gallery 成功；完整页面刷新恢复模型/参数/图片/成功 Run/Artifact，截图目视通过。首次约五分钟含量化缓存创建，不作为暖态性能指标。97 项回归通过，发布包未改动，无剩余 App 验收门禁；未来 Desktop Build 仍须纳入本地 validator、profile、discovery 与 UI 改动。

- 最新验收（覆盖下方历史阻塞）：App-Dev 重启后已安装正式 Package、下载全部 19.13 GiB 权重，Service running / health ok。95% 校验误判原因为普通版 Runtime scheduler 未进入精确后端合同；已补 (z-image, mflux-native-cfg)，保留缺失分片拒绝检查。Base ACPF verify 已与签名 Service 的 image-generation 能力名对齐。97 项回归通过。仍须再重启 Local 加载修复，再重试现有安装并验证 App 出图/刷新恢复；Helper 自动控制连续超时，等待用户重启。已发布包未改动；此前发布认证阻塞已解除。

- 0.1.0 和对应 checkpoint 已发布，Registry128 / Index63；最终包 SHA256 1650f2b5723e73af4ab267fb5c984cbeee9faf5ebc3c4e8d005f63b5760d7ac1。详见 docs/ai2apps-z-image-base-0.1.0-release.md。
- 新增版本有界 discovery/install/profile 兼容映射，标准 smoke 工具支持独立模型验签公钥；最终签名包独立 Sandbox 启动通过，43 项测试通过。当前 App-Dev 须重启 Local 加载映射后完成最终 App 安装/出图；历史认证阻塞已解除，Cookie 授权已关闭。

- 新增 packages/ai2apps-model-z-image-base-mlx，固定官方普通版 checkpoint；30 步、CFG 4、negative_prompt，使用原生 mflux CFG 管线，不复用 Turbo fusion。
- Imagine Studio 排除普通版的 Turbo 专用参数，保留 Turbo 不变；仅声明文生图，不宣传指令编辑。
- 2026-09-11：真实官方普通版 Q8 / 1024² / 30 步 / CFG 4 出图通过，166.278 秒、Metal 峰值 17,950,257,918 bytes；双源 17 文件共 20,538,488,386 bytes SHA-256 一致。ACPF 独立普通版入口、CFG/negative prompt 控件与草稿恢复已接入，19 项回归通过，JS 语法与 diff 检查通过。
- 发布门禁：Installation 会话查询 Publisher 返回 active user session required；等待本次 Package/Checkpoint 发布的浏览器 Cookie 授权及管理员验证。尚未发布、尚未完成真实签名安装/Sandbox/App 出图验收；不得进入发布候选。32 GiB 内存门槛为基于实测峰值的保守估计，未声称在 32 GiB 机器实测。
- 回退：移除新 Package 和前端普通版排除条件；不涉及已有 Turbo 安装数据。

## 5. 构建下一版前的强制门禁

### NXR-INTERNAL-2250：图像能力配套内部候选（in_progress）

2026-09-11 用户明确授权当前混合工作区的 dirty-tree 内部测试候选；不授权自动 stable 推送或四个模型包发布。Build 2250 内部 App/DMG 已通过标准构建、Developer ID 签名、包体一致性及 2249→2250 内部候选资格检查，未安装、启动、公证或上传；生产仍保持 2249。Swift 76 项通过；Python 首轮 1337 通过/6 个旧静态断言失败，修正后对应模块共 162 项复测通过。候选内 Python 验证 editing-only 与四个新版本映射均通过，未知未来版本继续拒绝；关键源码与包内文件哈希一致。65 个原台账标题仍仅作为内部测试范围，blocked/in_progress 不提升；仍待真实界面、升级及推理验收。详见 `docs/ai2apps-desktop-build-2250-internal-candidate.md`。

### NXR-IMAGE-CAPABILITY-SPLIT：图像操作能力收紧与 Package 升版（Package published / Desktop pending）

2026-09-12 最新状态：用户明确说明当前仍为开发阶段、没有真实生产用户，解除生产 Desktop 升级前置。四个既有签名制品已通过标准脚本发布并回读确认 published：Z-Image Turbo 0.1.3、Ideogram 4 0.1.2、Qwen Image 0.1.2、FLUX.2 Klein 0.1.4。Repository metadata 131→134。本次不发布 Desktop、不扩展音视频测试；新版 Host 验证器及安装映射仍需纳入未来 Desktop。旧版客户端限制不视为已修复。完整 submission 和摘要见 `docs/ai2apps-image-capability-release-2026-09-11.md`。下方未发布记录为历史状态。

最新状态（覆盖下方早期未签名记录）：用户明确追加签名授权后，四个候选已通过标准构建器签署；343 项最终回归通过。四个最终签名包分别在独立临时实例完成验签、安装、Runtime 1.6.2 依赖锁定及 Managed Worker readiness。没有创建生产 submission，未声称真实出图或公开 Registry 验收完成。摘要及剩余客户端生产门禁见 `docs/ai2apps-image-capability-release-2026-09-11.md`。Cloud 查询仍只用授权 App-Dev Cookie；既有 Keychain 私钥仅由构建器用于签名，未导出。

本次追加 Host 修复：缺少 modelInstall 的兼容格式按专用版本有界安装映射检查，不再混用旧 discovery 范围；新兼容版本的 fallback 核对实际 Service 模型，历史包维持原有校验行为。未知未来版本继续拒绝。该修复必须纳入配套 Desktop。

- 四个目标：Z-Image Turbo 0.1.3、Ideogram 4 0.1.2、Qwen Image 0.1.2、FLUX.2 Klein 0.1.4；尚未签署/发布，旧 dist 保留不变。
- Host 接受 editing-only 合同；Turbo/Ideogram 编辑禁用策略同时作用模型目录和 JSON 调用；Qwen Edit 与生成版分开；参考图数量在合同、前端和 Host 调用前校验；ACPF 分离 image.generation/image.edit，并修正 Qwen Service 验证能力名。
- 模型权重 revision/distribution 不变，无新权重下载要求。新 Qwen editing-only 声明要求包含本次校验修复的 Desktop 客户端；旧客户端不得被宣称已兼容。
- 发布使用本次用户授权的 App-Dev Cookie；签名仍需标准构建器的既有 Publisher 私钥，当前未读取 Keychain。待测试、签名安装及生产发布验收。
- 回归：核心 129 项通过；扩展合同/模型发现 186 项通过（Metal 导入需要非沙箱测试环境）。Node 语法检查通过。没有新签名制品或生产 submission。
- 发布门禁：旧 Host 拒绝 editing-only 合同；Qwen 必须先有兼容 Desktop 发布或可靠的客户端版本门禁。当前公共 ai2apps 版本约束不能区分该修复，不发布虚假 generation 能力来绕过。Cloud 尚不接受 modelInstall 时，其他新版本也需要随 Desktop 下发有界安装映射。签名权限与 Cloud Cookie 登录权限分开处理。


发布负责人必须逐项执行：

1. 匿名读取生产 `stable.json`，确认本文件基线 Build 仍是当前生产 Build；不一致时先更新
   基线和回执引用。
2. 为每个 `ready`/`blocked` 项明确决定：纳入、修复后纳入或 `deferred`。不得默默遗漏。
3. `blocked` 项不得进入候选，除非阻塞已解除、证据已补齐并改为 `ready`。
4. 将每个拟纳入项映射到具体源码文件、测试、配置/迁移、用户可见 Release notes 和回退
   方式。
5. 对上一版最终 DMG 的实际内嵌内容与候选 staging App 做内容差异核对；不要只比较 Git
   commit，尤其不能把未跟踪文件当作可重现来源。
6. 正式发布要求所有拟纳入文件已提交并推送，工作树满足 Desktop Runbook 的 clean-tree
   门禁。任何 dirty-tree 例外都必须重新获得明确批准。
7. 在 Release notes 与 Build 回执中逐项引用本文件的 NXR ID。

如果候选构建包含本文件未登记的用户可见或安全相关差异，停止构建，先补登记和测试证据。

## 6. 发布完成后的归档与重置

当新 Build 完成端到端验收后：

1. 将所有实际纳入项的 NXR ID、说明、测试和例外复制到该 Build 的不可变发布回执；
2. 把对应项状态改为 `included`，填写纳入 Build；
3. 保留 `deferred` 项并更新目标版本，不得丢失；
4. 将本文件生产基线更新为新 Build、生产清单摘要和新回执；
5. 从“下一版候选工作”移走已经归档的 `included` 详情，只保留新基线之后的开放项；历史
   事实以 Build 回执为准；
6. 重新匿名核对 `stable.json`，确认台账基线与生产一致。

台账更新本身必须和导致状态变化的源码或发布回执一起进入版本控制，不能只存在于聊天记录。

<!-- Checkpoint migration status: HF DS4.1F / MS Qwen SDK uploads completed, remote integrity gates pending. User explicitly confirmed HF Avdpro / MS ai2apps. HF Qwen metadata fix committed successfully at a1de2bbd1727b3c46162a0f8bd426316e6f8dd37; approval block resolved. MS DS4.1F remains uploading. See docs/chat-checkpoint-migration-2026-09-14.md. -->

### NXR-VIDEO-STUDIO-READY-PROVIDER：优先恢复已安装的视频模型（ready）

- 状态：`ready`
- 类型：Video Studio、ACPF、模型选择恢复。
- 用户可见结果：设备已经安装并验证 OpenVDN DMD8 等视频模型时，重新打开 Video Studio 会
  直接恢复一个已就绪的模型，不再因为 ACPF 推荐的高规格 H3 8-bit 尚未下载而显示“当前设备
  没有经过此 App 验证的本地配置方案”并再次要求配置。
- 根因与修正：Provider 目录和共享 Checkpoint 均正常；OpenVDN DMD8 及其 H3 4-bit 基座已经
  被 Worker 标为 `ready`。旧的首次选择逻辑只检查推荐模型 ID 是否存在，未检查它是否就绪，
  因而在 128 GiB 设备上优先选中尚未安装的 H3 8-bit。现在仅在推荐项已就绪时优先选它；否则
  先选任一已就绪模型，再回退到推荐或目录首项，以保留无模型设备进入安装流程的行为。用户
  选定及 ACPF 安装完成后的模型 ID 会写入 Video Studio Shell 状态；刷新或重开后仍可用时直接
  恢复；初始化空 Mini-App 草稿也不再覆盖刚恢复的模型 ID，例如不会把已选择的 OpenVDN
  DMD8 降回仅作为依赖安装的 H3 4-bit 基座。
- 需要进入 App 的文件：`ai2apps/web/static/js/video_studio.js`、
  `tests/test_ai2apps_video_studio.py`。
- 纳入 Build：待定。

<!-- HF Qwen 73 / DS 172 files checked: only Hub-added .gitattributes differs, all other SHA256/size values match. Normalize metadata before distribution signing; not a completed publication gate. -->

### NXR-SHARED-CHECKPOINT-REUSE：跨实例共享 checkpoint 复用修正（runtime_published）

- 2026-09-18：App-Dev 安装 DeepSeek V4.1 Flash 时错误重新下载 475.27GB。根因是首次整理只扫描
  实例 cache，漏掉仓库 `artifacts/chat-checkpoint-migration-20260914` 的已验证 SSD checkpoint；
  该快照也没有 `.ai2apps/distribution.json`，因此安装器无法识别。现已通过正式本地导入工具对
  171 个分发文件完成签名清单和 SHA-256 校验，并以 APFS clone/hardlink 形式发布到机器共享
  `checkpoint-cache-v1`；App-Dev Worker 目录与共享快照 inode 一致，不占用第二份 475GB。
- 修正大快照复用：共享 cache 检查和 Worker 物化移出 asyncio 事件循环；取消 provisioning 会
  同时取消底层 runner，避免界面取消后继续下载；首次完整 SHA 后写入只读 inode/device/size/
  mtime 收据，后续快速复核，任一身份变化都会退回完整 SHA。安装界面在复核阶段显示
  “Checking shared checkpoint cache”，不再把本地扫描误报为网络下载。
- 修正 SSD 完整性边界：`.gitattributes` 是 Hub 仓库元数据，Checkpoint Distribution 明确不
  分发；旧 `ssd-checkpoint.json` 即使记录它，Runtime 也不再把它当作推理载荷。其它声明文件、
  metadata digest、专家清单和模型布局检查保持严格。
- 2026-09-18 Runtime 1.7.1 候选完成：104 项 Runtime/Checkpoint/Installer/Provider 定向回归通过；
  Apple 公证请求 `9c90a4aa-728b-4863-8a42-11c38cb60636` Accepted，staple/Gatekeeper 通过；
  最终 Publisher 签名 Package SHA-256 为
  `df6f95e37a8e48073597b2aa6a5d2aa86c4e4be2f872c34a989d666290f19982`。精确签名制品在隔离实例
  安装成功，DS4.1 Worker 达到 running；1.7.1 内置 CPython 对真实共享 DS4.1 快照完成检查，
  `.gitattributes` 缺失时仍正确通过全部推理载荷、metadata digest、专家清单和布局门禁。
- App-Dev 与 Test 已通过规定脚本重建、release-bundle 与 deep/strict 签名验证；App-Dev 已以
  `app-dev` 实例重启，原生标题为 `AI2Apps-App-Dev: HunterPoints 127.0.0.1:53678`。ModelScope
  不可变 revision `75866a48aa1c36cd1f2c646feeda98a449b2c77e` 的大小/SHA、四段匿名
  `200 + Content-Range` 字节和完整匿名下载均匹配。GitHub 同一草稿的前两次精确资产上传在服务端
  保存阶段返回 HTTP 500，失败 starter 已清理；第三次上传成功并发布为
  `package-runtime-omlx-v1.7.1`，GitHub 摘要、四段 HTTP 206 和完整匿名下载均匹配。详见
  `docs/ai2apps-mlx-runtime-1.7.1-shared-checkpoint-release.md`。
- Runtime 1.7.1 已正式发布：submission `13bd374a-066c-48f3-988b-fce01504cebd`、review
  `8d983fe2-c232-493d-9eab-308e299b45eb`；GitHub 与 ModelScope 两个不可变 Source 均完成
  分片验证和激活。最终 Repository metadata 为 157，snapshot digest 为
  `92b35944484e26cfd4786bfaf88940a1f9f0648450b5e6c6a04acf69f4ef8252`；全新匿名客户端验证
  Package 精确字节和 Publisher envelope 均与本地最终制品一致。App-Dev Discover 已显示
  `Local 1.7.0 / Cloud 1.7.1` 和 Upgrade 入口。
- 纳入 Build：Runtime 1.7.1 及下一版 Desktop；无需模型 Package 或 Checkpoint 重发。Runtime
  发布闭环完成；下一版 Desktop 的正式纳入和升级验收由 Desktop Release 流程继续跟踪。
- 2026-09-18 App-Dev 实机 Retry 暴露后续权限边界：共享 Distribution 已正确复用，但 Worker
  视图整体只读，SSD 激活阶段仍需写入 Package-owned Scope profile 与 `ai2apps-model.json`，因而在
  `.ai2apps/scope-assets` 返回 `EACCES`。安装器现仅在元数据提交事务期间临时开放模型根目录与
  `.ai2apps` 的 owner-write；权重、专家和其它 payload 文件始终只读，提交完成或异常退出都会恢复
  原始目录权限，新生成的 Scope/manifest 文件在只读视图内也恢复为只读。新增 DS4.1 只读
  Distribution 激活回归；Checkpoint/Runtime 56 项通过，扩展安装套件 80 项中 78 项通过，另两项为
  既有 Qwen 测试仍断言已被 SSD Checkpoint 替换的旧仓库身份，与本修正无关。App-Dev 已对现有
  475.27GB 共享快照完成原地激活，没有重新下载；生成的 manifest、Scope asset 与模型目录均恢复
  只读。Local 重启后真实本地 DeepSeek V4.1 对话对 `20+20` 返回 `40`，不再出现
  `SSD checkpoint is not activated`。该激活逻辑属于 Desktop Local，而非安装的 Runtime；Runtime
  1.7.1 无需重发，修正必须纳入下一版 Desktop Build。

### NXR-ORNITH-FULL-SSD：Ornith SSD Full 专家注入修复（released_verified）

- App-Dev 实机发现 Ornith 0.1.2 的默认 Full 分支关闭 Qwen3.6 外部专家策略，SSD backbone
  因缺少已拆出的 40 层三组专家张量而报告 `Missing 120 parameters`。Ornith 0.1.3 候选在 Full
  模式配置 256 专家 Flesh 注入；Runtime 1.7.2 候选让 Full/Flesh 使用规范 expert ID 0..255，
  不再错误要求只为缓存档位训练的 Top120 Scope profile 包含 Top256 排名，并同步修正文本
  Qwen3.6 Full 路径的无效零 tail 参数。
- 46 项 Runtime/Qwen3.6/Ornith/Package 定向回归通过。临时隔离 Worker 使用当前正式 SSD
  checkpoint 完成真实 Metal Full 加载和 30-token 响应，原 120 参数错误消失，最终答案为 `40`。
- Runtime 1.7.2 已完成 Apple 公证、staple、Gatekeeper、Publisher 签名和 Registry 发布；
  Ornith 0.1.3 也已签名并发布。Runtime 最终 Package 为 375527678 bytes，SHA-256
  `2ec01b8d5bd37b362d7b95fa98a7253d3f2251b0495d0c0599ac0be88240f501`。Cloud、ModelScope、
  GitHub 三源均已通过完整 SHA/大小/piece/Range 校验并激活，最终 Repository metadata v161。
  App-Dev 安装精确发布制品后复用了现有 Ornith checkpoint；Worker 元数据确认为默认 Full，
  真实 Chat 对 `20+20` 返回 `40`，原 120 参数缺失未复现。该修复已由独立 Runtime/模型
  Package 交付，不要求新 checkpoint 或 Desktop 重发。详见
  `docs/ai2apps-mlx-runtime-1.7.2-ornith-full-ssd-candidate.md` 与
  `artifacts/runtime-1.7.2/build-receipt.json`。

- Experimental L2 prefetch: L2_RECYCLE_CANCELLED reclaims cancelled unread reservations while retaining the 64 actual reads/token cap. Scheduler unit checks pass; model performance validation pending. Production defaults unchanged.

- Experimental L2 credit-limited notices merge hit/miss metadata readbacks and spend only saved boundaries on early notifications; all-hit host IDs are masked. Exact model and timing checks running; production Runtime unchanged.

- L2 credit notification prototype adds bounded adjacent-layer batching; strict32-token model validation in progress. Production unchanged.

- Experimental L2 startup notification can replace duplicated first-layer cache-hit readback; strict exact-routing/parity and boundary-count gates added. Model validation running; production unchanged.

- L2 experimental entry now resolves its resident predictor relative to its source location to support frozen acceptance snapshots. Independent test running against isolated copies; no production activation.

- L2 isolated independent acceptance completed:24 unseen conversations,70.3071% timely miss coverage, cap64 reads/token,62.971GB sampled peak, exact main output parity, counted route readbacks/notifications never exceed baseline per token; pooled TPS+7.44%, waste82.03MB/token, total expert SSD reads+7.84%. Confidence interval crosses70%; see `docs/dsv41f-l2-independent-acceptance-2026-09-16.md`. Experimental legacy-path result only; production miss-resume/vision/Package integration remains unaccepted and defaults unchanged. Prior “running” bullets above are historical status, superseded by this result.

- L2 follow-up research in progress: residual-depth predictor trainer and serial two-seed ablation added, with identity initialization and train/validation family separation. Scope and remaining cross-layer L2/SSD scheduling work recorded in `docs/dsv41f-l2-next-experiments-2026-09-16.md`; no Runtime defaults or Package activation.

- L2 cross-layer research prototype (2026-09-17): isolated READY snapshots, bounded staging reads, GPU staging-use flags, proposals piggybacked on existing window completion, conditional invalid-suffix notifications, and optional host/command-buffer timing diagnostics added under `resume_probe/`. A copied diagnostic runner now includes lazy KV roots in its existing completion evaluation and supports fixed input token sequences. Early incorrect smoke runs are retained and excluded; corrected Block6 matches legacy golden logits for8decode steps. The27-case development matrix is running; no production activation or broad correctness/performance claim yet. Residual-depth results documented in `docs/dsv41f-l2-depth-ablation-2026-09-17.md` show no repeatable gain.

- L2 three-direction development experiments completed (2026-09-17, experimental/deferred; supersedes earlier running status): all 21 optimized-window cases completed; exact Top6 legacy-logit gates and <65GB sampled footprint passed. Residual depth has no repeatable gain; cross-layer L2 candidates remain slower than packet control. Deadline lead1 improved the separate paired development probe by ~2.3%, not a production claim. Lazy prefill KV-root fix stays in isolated runner; no production Runtime/default/Package activation. See `docs/dsv41f-l2-three-direction-results-2026-09-17.md`; long-context and independent acceptance remain required before release.

- L2 window regression correction (2026-09-17, in_progress, isolated experiment): restore previous packet/window admission and first-miss native-tail fallback in resume_probe; packet fallback retains L2 READY consumption and fused prediction delivery. Add discarded-suffix counters. Performance/parity gates pending; no production activation.

- L2 window regression correction completed in isolated experiment (2026-09-17; supersedes in_progress above): restored old admission and first-miss packet tail; normal/all-miss paired full TPS +1.33%/−0.35% (equivalent within observed variation), exact golden logits, zero discarded suffix in low-hit runs. Same-token all-hit 2/4-layer execution 86.46/81.64ms vs packet92.02ms; zero SSD, exact output. Four predictor transition gates passed (rank64 dtype retry recorded). Production/default Runtime unchanged; long-context L2/Burst integration remains deferred. See `docs/dsv41f-l2-window-recovery-2026-09-17.md`.

- Always-resume executor correction (2026-09-17, in_progress, experimental): user requires no packet admission/fallback. Added explicit resume mode that uses GPU guarded continuation on every segment and resumes current MoE after every miss; GPU router-visit instrumentation added. Correctness and all-miss performance not yet accepted; previous adaptive fallback result is not evidence for this requirement. No production activation.

- Always-resume follow-up (2026-09-17; semantics verified, performance not accepted, experimental/deferred): full40 controller has no packet admission/fallback; normal4token142MISS+4DONE and all-miss2token80MISS+2DONE, exact logits/KV/Engram, GPU each layer once. CPU still reconstructs skipped suffixes: full40 no-diagnostic0.580TPS, not releasable. Added isolated v3 backend integer-key/resource-declaration cache and async guarded submit; 18-case gates pass, speed goal still fails. Docs `dsv41f-always-resume-2026-09-17.md` supersede interpreting adaptive recovery as fulfillment. No production Runtime/Package switch.

- Forward-only ICB continuation (2026-09-17, in_progress, isolated experiment): token graph/Metal commands are captured once, real Router misses patch only the current six slot indices and replay the remaining captured groups. Removes suffix rebuilding and rollback snapshots; adds token-scoped Residency Sets, pooled ICB/parameter storage, exact replay ranges, and deferred allocation retirement compatible with normal MLX donation. Natural four-token logits and full state match packet reference exactly; all-miss diagnostics show one graph and one GPU execution per layer, zero packet fallback, 40 MISS + DONE per token, <65GB sampled peak. Frozen 32-token ABBA performance gate is running; no production Runtime, Package or default activation. See `artifacts/dsv41-resume-replay-20260917/`.

- Captured continuation outcome (2026-09-17; supersedes in_progress above): retained isolated v12 after full-state parity and Metal validation smoke. No repeated suffix construction, no packet fallback, exact per-layer execution and <65GB peak. Frozen ABBA still fails non-regression: all-miss 2.00977 vs 2.05591 TPS (-2.24%); natural 3.95339 vs 4.84065 TPS (-18.33%). Later native-prefix/event/residency/retirement/submission variants did not establish a passing gate and are archived outside the retained implementation. No production/default switch. Report: `docs/dsv41f-captured-continuation-2026-09-17.md`; retained binary/source receipt: `artifacts/dsv41-resume-replay-20260917/retained-receipt.json`.
