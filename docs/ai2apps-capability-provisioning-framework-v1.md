# AI2Apps Capability Provisioning Framework（ACPF）v1.1

状态：规范、当前实现基线与 App 接入指南。本文档是 Chat、Read Aloud、Video Studio
以及新 AI2Apps App 实现按需能力配置时的唯一规范入口。

v1.1 根据 Video Studio 首次端到端验证更新，重点明确：能力配置与业务提交是两个阶段，
默认不得因为配置完成而自动执行昂贵或不可逆的业务操作。

简称：**ACPF**，中文名：**AI2Apps 能力配置框架**。

本文中的“必须”“不得”“应该”和“可以”分别对应规范性要求 MUST、MUST NOT、
SHOULD 和 MAY。

## 0. 当前实现基线与迁移门槛

截至 v1.1，平台已经具备 Device Profile、内置 Capability Profile Registry、`probe`、
`ensure`、持久化 Provisioning Session、共享 Setup Sheet、Discover Package 安装、
Checkpoint 下载、Local 重启恢复、原 App 返回和 Provider ready 验证的首版实现。Video
Studio 的 `video.generation` 已接入并完成 Q8/Q4 定向配置验证。

截至 2026-08-27，共享实现已经完成以下 P0 门槛；Chat、Read Aloud 和其它 App 必须基于该
契约接入，不得恢复旧的草稿透传或 Shell acknowledgement 行为：

1. 支持本文定义的 `configure_only` 和 `resume_action` 完成策略；
2. ACPF Session 和共享 Client 存储中只出现 opaque draft token，不保存 Prompt、聊天内容、
   附件、媒体内容或音色样本；
3. Setup Sheet 的标题、说明和图标由 capability presentation 元数据驱动，不得硬编码
   Video Studio 文案；
4. Shell 只负责返回目标 App，由目标 App 在成功恢复后唯一执行 return acknowledgement；
5. 服务端必须把请求中的 `appId` 与可信 App/实例身份绑定，不得把页面自报的 `appId`
   当作授权依据；
6. `resume_action` 必须携带稳定的业务幂等键，并通过“恢复后恰好执行一次”测试。
7. Checkpoint 激活后的 Service Restart，以及 dormant Service 的 Ready、健康和协议验证，属于
   ACPF 配置与生命周期操作，不创建模型推理任务，也不取得 Worker 推理 Scheduler Lease；若未来
   增加真实 Smoke Inference，必须通过 Host-owned Model Invocation Service 单独提交。

当前实现对应的强制行为是：

- Client 自动从 Host mount 上下文附带 `appInstanceId`，服务端从 AppInstance 反查 canonical
  App ID，并拒绝请求自报 `appId` 与可信身份不一致的调用；
- `intent` 在 API 边界归一化为 `returnTo`、opaque `resumeToken`、`completionPolicy` 和可选
  `idempotencyKey`；旧 App 误传的 `draft` 等字段会被丢弃，不进入 Session 或共享 Client 存储；
- 共享 Client pending storage 只保存 `sessionId`、`appId` 和 opaque `resumeToken`；
- Setup Sheet 从可信 capability `presentation` 读取标题、说明、图标、按钮和步骤文案；
- Shell 只导航回目标 App。目标 App 恢复自己的 draft，并在业务恢复完成后显式 acknowledge；
- 活动 Session 使用 AppInstance、capability、action 和包含 requirements/profile/stack 的稳定
  request fingerprint 去重，不同 `modelId` 不会错误复用同一个 Session；
- `resume_action` 缺少 `idempotencyKey` 会在 API 边界被拒绝；acknowledgement 必须回传相同 key，
  重复 acknowledgement 幂等。业务 API 仍必须用同一 key 保证最终副作用恰好一次。

尚未实现或未达到本文目标的能力必须在代码和测试中标记为 pending，不得通过修改本文档把
缺口描述成已完成。当前主要后续项包括：通用兼容候选枚举、下载成本与许可展示、完整错误
分类、Worker 轻量推理健康验证、签名 profile overlay、CUDA/ROCm Device Profile。

## 1. 定义与边界

ACPF 解决下面这个产品问题：用户执行一项 AI 操作时，如果当前设备还没有满足该操作
所需的 Runtime、Service Package、模型 Checkpoint 或运行配置，AI2Apps 应在当前 App
内给出设备适配的方案，完成可信安装、必要的重启和健康验证，然后恢复到原 App 与原功能。
是否继续业务操作由该 action 的完成策略决定，不是 ACPF 的隐式副作用。

ACPF 的配置单位是**操作所需的能力**，不是整个 App。一个 App 可以声明多项独立能力：

| App | 功能操作 | ACPF capability |
| --- | --- | --- |
| Chat | 发送文字消息 | `text.chat` |
| Chat | 可选本地文字聊天增强 | `text.chat.local` |
| Chat | 上传图片并对话 | `vision.chat` |
| Chat | 语音输入 | `audio.speech_recognition` |
| Read Aloud | 文本朗读 | `audio.speech_generation` |
| Read Aloud | 音色克隆 | `audio.voice_clone` |
| Video Studio | 文生/图生视频 | `video.generation` |
| Video Studio | 音频驱动数字人 | `video.digital_human` |
| Video Studio | 参考素材驱动 | `video.reference_generation` |
| Knowledge | 关键词知识检索 | `knowledge.lexical_search`（Core 内置） |
| Knowledge / Chat | 语义知识检索 | `knowledge.semantic_retrieval` |
| Knowledge | 图片知识理解 | `knowledge.image_understanding` |
| Knowledge | 音频知识理解 | `knowledge.audio_understanding` |

ACPF 不替代以下系统：

- Capability Policy、CapabilityRequest 和 GrantLease 仍负责权限判断与授权；
- Discover 仍负责可信目录、Package 获取、签名验证和发布者信息；
- Package Manager 仍负责安装、升级、依赖锁定、启停和回滚；
- Model Worker 协议仍负责模型服务和推理；
- Models App 仍是高级模型管理工具；
- default model routing 仍负责已可用模型的系统默认路由。

为避免术语冲突，本文中的 capability 指“可配置的产品能力”，权限系统中的 capability
指“调用权限”。一次 ACPF 操作仍必须经过现有权限系统，配置成功不能自动授予额外权限。

## 2. 核心原则

1. **按操作触发**：打开 App 时可以静默探测，但不得仅因打开 App 就下载大型模型。
2. **App 有推荐意见**：App 声明自己测试、认可并排序过的能力栈，而不是只声明抽象模型类型。
3. **平台统一执行**：App 不自行实现下载器、依赖解析、重启或 checkpoint 校验。
4. **硬件中立**：设备匹配基于 Metal、CUDA、ROCm、内存模型和容量等事实，不依赖具体产品名。
5. **优先复用**：已经可用或可低成本修复的兼容栈优先于重新下载“理论最佳”栈。
6. **显式确认成本与许可**：开始下载前展示方案、下载量、磁盘占用、许可和重启影响。
7. **可恢复**：下载、安装、重启和验证由持久化 Provisioning Session 管理。
8. **恢复不等于提交**：配置成功后恢复原 App、原功能和草稿引用；默认只提示环境就绪。
   只有显式声明 `resume_action` 且具备业务幂等保护的 action 才自动继续。
9. **失败关闭**：没有经过 App 推荐且没有兼容性证明的硬件/Package 组合不得被猜测为可用。
10. **统一 UE**：Chat、Read Aloud、Video Studio 和第三方 App 使用同一套“Capability Choice
    Sheet + Setup Sheet”两阶段系统界面；用户选择档位前不得创建 Provisioning Session。
11. **控制面独立**：Local、ACPF、Discover 和 Models 的启动不得导入可选推理 Runtime；卸载、
    损坏或升级 MLX/CUDA/ROCm Runtime 不能阻止 AI2Apps 控制面启动和修复自身。

## 3. 架构

```text
App action
  -> ACPF Client SDK: probeCapability()
  -> Capability Registry
  -> Device Profiler + Installed Asset Inventory
  -> Capability Resolver
  -> Provisioning Planner
  -> shared Capability Choice Sheet (read-only; no Session)
       -> show every trusted tier
       -> recommend one tier for this device
       -> disable impossible tiers with reasons
       -> user selects and continues
  -> ACPF Client SDK: ensureCapability(profileId)
  -> Provisioning Session (awaiting_confirmation)
  -> shared Setup Sheet (selected tier + exact side effects)
       -> Discover / Package Manager
       -> Runtime dependency resolver
       -> Checkpoint installer
       -> restart coordinator
       -> provider health and readiness verifier
  -> resolved Provider Handle
  -> return original App feature
       -> configure_only: restore draft and wait for user confirmation
       -> resume_action: execute once with an idempotency key
```

### 3.1 Capability Registry

登记 App 的能力需求、推荐栈、触发行为和恢复策略。Registry 只接受已安装且通过信任校验
的 App 声明。App 更新、禁用或卸载后必须同步更新登记结果。

### 3.2 Device Profiler

返回规范化的设备事实，不返回模型选择。当前 v1 wire format 至少包括：

```json
{
  "schema": "ai2apps.device-profile/v1",
  "os": "macos",
  "architecture": "arm64",
  "system_memory_gib": 128,
  "accelerator": {
    "vendor": "apple",
    "api": "metal",
    "unified_memory_gib": 128
  }
}
```

未来兼容扩展中，NVIDIA 使用 `vendor=nvidia, api=cuda`，AMD 使用
`vendor=amd, api=rocm`，并增加 `device_memory_gib`、驱动和计算能力等字段。独立显存和统一
内存必须分开表达。瞬时空闲内存只能用于判断“现在是否适合加载”，不得代替总容量决定永久
量化方案，以免其它正在运行的 App 改变推荐结果。

### 3.3 Installed Asset Inventory

统一列出当前 Installation 已有的：

- Runtime Package 版本、digest、状态和能力；
- Provider Package 版本、digest、依赖锁和状态；
- 固定 revision 的 Checkpoint 完整性；
- Worker 健康状态和 `checkpoint_ready`；
- 正在进行或可恢复的下载、安装和重启任务；
- 可复用的共享模型缓存引用。

### 3.4 Capability Resolver

判断已有 Provider 是否满足 App 的 operation requirements。如果已有兼容且健康的 Provider，
直接返回 Provider Handle，不打开配置向导。

### 3.5 Provisioning Planner

将 App 推荐列表、设备事实、Package 真实依赖、现有资产、用户/组织策略和磁盘条件合并成
一个可解释的执行计划。Planner 只规划可信目录中存在且兼容性校验通过的不可变版本。

### 3.6 Provisioning Session

持久化整个执行过程。Local 或桌面 App 重启后必须能够继续，不依赖页面内 JavaScript 状态。

### 3.7 通用 Component Stack

ACPF 不得假定每项能力都恰好是 Runtime → Model Provider → Checkpoint。Profile 可以继续使用
兼容的三段式 `stack.runtime/provider/checkpoint`，也可以声明通用 `stack.components`：

```yaml
stack:
  components:
    - id: rag-runtime
      kind: package
      phase: runtime
      package_id: ai2apps/runtime-knowledge-rag
      service_key: ai2apps.runtime.knowledge-rag
      version: ">=0.1.0,<1.0.0"
    - id: vector-service
      kind: package
      phase: provider
      package_id: ai2apps/service-knowledge-lancedb
      service_key: ai2apps.knowledge-vector.lancedb
      version: ">=0.1.0,<1.0.0"
    - id: embedding-provider
      kind: package
      phase: provider
      package_id: ai2apps/model-multilingual-e5-small
      service_key: ai2apps.model.multilingual-e5-small
      version: ">=0.1.0,<1.0.0"
    - id: embedding-checkpoint
      kind: checkpoint
      phase: checkpoint
      model_id: ai2apps.model.multilingual-e5-small/default
    - id: semantic-ready
      kind: verify
      service_key: ai2apps.knowledge-vector.lancedb
      capabilities: [knowledge-vector-index-v1]
```

`kind=package` 统一交给 Discover/Package Manager；`phase` 只决定 Setup Sheet 和恢复状态，不改变
信任规则。`kind=checkpoint` 交给 Model Installer；`kind=verify` 不安装任何内容，只检查已登记
Service 的运行状态、版本和 capability。组件可以复用已安装 Package，Profile 不得通过 command、
URL 或任意 Python requirement 绕过 Registry。通用栈的返回值是 Provider/Service Handle，不要求
一定存在 `modelId`。

## 4. App 能力配置文件

规范文件名为 `capability-profiles.yaml`，schema 为
`ai2apps.capability-profiles/v1`。发布型 App 应在签名的 `ai2apps.json` 中引用：

```json
{
  "capabilityProfiles": {
    "schema": "ai2apps.capability-profiles/v1",
    "path": "capability-profiles.yaml"
  }
}
```

系统内置 App 在完全 Package 化之前，将等价文件放在
`ai2apps/provisioning/profiles/<app-id>.yaml`。两种来源进入同一 Registry，不得使用两套
解析逻辑。

### 4.1 Video Studio 示例

```yaml
schema: ai2apps.capability-profiles/v1
app_id: ai2apps.video-studio
version: 1

capabilities:
  video.generation:
    trigger: on_action
    requirements:
      operations: [text_to_video, image_to_video]
      output_formats: [mp4]
      synchronized_audio: true
    profiles:
      - id: apple-metal-h3-q8
        priority: 100
        device:
          os: [macos]
          architectures: [arm64]
          accelerator:
            vendor: apple
            api: metal
            unified_memory_gib: {minimum: 48}
        recommendation_memory_gib: {minimum: 64}
        stack:
          runtime:
            package_id: ai2apps/runtime-omlx
            service_key: ai2apps.runtime.omlx
            version: ">=1.4.0,<2.0.0"
          provider:
            package_id: ai2apps/model-minimax-h3
            service_key: ai2apps.model.minimax-h3
            version: ">=0.7.0,<1.0.0"
          checkpoint:
            model_id: ai2apps.model.minimax-h3/fl2va-8bit

      - id: apple-metal-h3-q4
        priority: 90
        device:
          os: [macos]
          architectures: [arm64]
          accelerator:
            vendor: apple
            api: metal
            unified_memory_gib: {minimum: 32}
        recommendation_memory_gib: {minimum: 32, maximum_exclusive: 64}
        stack:
          runtime:
            package_id: ai2apps/runtime-omlx
            service_key: ai2apps.runtime.omlx
            version: ">=1.4.0,<2.0.0"
          provider:
            package_id: ai2apps/model-minimax-h3
            service_key: ai2apps.model.minimax-h3
            version: ">=0.7.0,<1.0.0"
          checkpoint:
            model_id: ai2apps.model.minimax-h3/fl2va-4bit

  video.digital_human:
    trigger: on_action
    requirements:
      operations: [audio_driven_portrait]
      required_inputs: [portrait, audio]
      output_formats: [mp4]
    profiles:
      - id: apple-metal-echomimic-v3
        priority: 100
        device:
          os: [macos]
          architectures: [arm64]
          accelerator:
            vendor: apple
            api: metal
            unified_memory_gib: {minimum: 32}
        recommendation_memory_gib: {minimum: 32}
        stack:
          runtime:
            package_id: ai2apps/runtime-omlx
            service_key: ai2apps.runtime.omlx
            version: ">=1.4.0,<2.0.0"
          provider:
            package_id: ai2apps/model-echomimic-v3-mlx
            service_key: ai2apps.model.echomimic-v3-mlx
            version: ">=0.1.0,<1.0.0"
          checkpoint:
            model_id: ai2apps.model.echomimic-v3-mlx/default
```

### 4.2 其它硬件候选

App 应为自己实际验证过的平台增加独立 profile。例如：

```yaml
- id: nvidia-cuda-h3-int8
  priority: 100
  device:
    os: [linux, windows]
    architectures: [x86_64, arm64]
    accelerator:
      vendor: nvidia
      api: cuda
      device_memory_gib: {minimum: 40}
      compute_capability: {minimum: "8.0"}
  stack:
    runtime:
      package_id: ai2apps/runtime-cuda-torch
      service_key: ai2apps.runtime.cuda-torch
      version: ">=1.0.0,<2.0.0"
    provider:
      package_id: ai2apps/model-minimax-h3-cuda
      service_key: ai2apps.model.minimax-h3-cuda
      version: ">=1.0.0,<2.0.0"
    checkpoint:
      model_id: ai2apps.model.minimax-h3-cuda/fl2va-int8
```

AMD/ROCm 必须拥有经过验证的 Runtime、Provider Package 和 profile。没有 profile 时显示
“当前设备暂无经过此 App 验证的本地方案”，不得把 CUDA 或 MLX 方案自动套用到 AMD。

### 4.3 字段规则

- `app_id` 必须与调用 App 的可信身份一致。
- capability ID 使用稳定的小写点分命名，描述产品能力而不是模型品牌。
- `trigger` 可以是 `on_action`、`on_feature_request` 或 `recommended_optional`；启动时都只能 probe，
  不得因为 recommendation 自动下载。
- `priority` 只比较同时匹配设备且满足策略的候选，数值越高越优先。
- `device` 表示技术兼容边界；`recommendation_memory_gib` 表示默认推荐区间。用户可以在高内存
  设备上显式选择仍处于兼容边界内的低精度方案，例如在 128 GiB Mac 上选择 H3 Q4。
- Profile 可以提供用户可读的 `label` 和 `description`。低于 `device` 硬边界的 Profile 必须显示
  但置灰，并给出内存、平台、架构或 Accelerator 原因；前端置灰不能替代服务端重复校验。
- Runtime、Provider 和 Checkpoint 必须使用稳定 ID；Package 必须使用版本范围。
- Runtime 和 Provider 必须同时声明 `package_id`、`service_key` 和 `version`。
- capability 可以声明可信 `presentation`，字段包括 `eyebrow`、`title`、`description`、`icon`、
  `confirm_label`、`ready_label` 以及按 `runtime/provider/checkpoint/verify` 索引的 `steps`。共享
  Setup Sheet 只读取经过 Registry schema 校验的 presentation，不接受请求临时覆盖；
- App 不得在配置中放下载 URL、任意命令、密钥或可执行代码。
- v1.1 不支持 profile 内嵌 `fallbacks`；每个用户可选方案使用独立 profile。未来增加 fallback
  字段时仍须通过所有兼容性、许可和磁盘检查。
- App 可以提供 `quality`, `balanced`, `economy` 标签，但默认候选必须唯一可解释。

## 5. Package 供给声明

App 推荐是产品意见，Package manifest 是技术事实，两者缺一不可。Provider Package 必须继续
在 `service.yaml` 声明 model capabilities、固定权重 revision、Runtime 依赖和平台兼容性。

```yaml
models:
  - id: ai2apps.model.minimax-h3/fl2va-8bit
    model_type: video_generation
    capabilities: [video_generation, text_to_video, image_to_video, synchronized_audio]
    weights:
      provider: huggingface
      repo_id: ddalcu/MiniMax-H3-FL2VA-MLX-Serve-8bit
      revision: 64314cde0ac6d90f132bc94ae58e0c82f77396c6
      preparation: {recipe: native}

requires:
  services:
    - id: ai2apps.runtime.omlx
      version: ">=1.4.0,<2.0.0"
      capabilities: [mlx, model-worker-v1, video-generation]
```

Planner 必须取 App 版本范围、Package 依赖和仓库可用版本的交集。App 声明不得放宽 Package
自己的依赖。最终计划必须锁定 Package version、digest 和 checkpoint revision。

### 5.1 模型能力与 Host 策略

模型支持的输入组合、分辨率、比例、FPS、时长、输出格式、量化和驻留方式属于 Provider
Package 的技术事实。App 的控件必须随当前所选模型读取这些能力，不得维护一份与 Package
脱节的固定列表；服务端必须使用同一份有效能力再次验证请求。

Host 可以发布临时安全或兼容策略来收窄、禁用或纠正已发布 Package 的能力，例如暂时禁用
H3 BF16/FP16。此类策略必须集中定义，并同时作用于 Provider catalog、ACPF Resolver 和业务
请求校验。策略不得声明 Worker 实际无法验证的能力，并应该在下一版签名 Package 修正后移除。

### 5.2 可用 Provider 与可配置候选

App 的模型选择器应合并两类信息：

1. Provider catalog 中已安装或 Package 已声明的模型及其 `ready` 状态；
2. Capability Registry 针对当前设备返回的兼容 profile，即使其 Package 尚未安装。

未 ready 的候选显示“需配置”，不得使用伪模型选项表达空状态。用户显式选择候选时，App 在
`requirements.modelId` 中传入稳定 Model ID；Planner 必须只选择包含该 Model ID 且仍兼容当前
设备的 profile。未显式选择时才使用设备默认推荐。

通用候选枚举 API 尚未完成前，App 可以用 `probe` 展示默认推荐，但不得自行猜测其它量化或
从任意下载地址拼装候选。

## 6. 推荐与解析算法

Planner 按以下顺序评估：

1. 用户通过 `requirements.modelId` 显式指定且兼容当前设备的 profile；
2. 已经健康、ready 且满足 requirements 的 Provider；
3. 已安装，只需启动、重启、升级小依赖或修复引用的候选；
4. App 对当前设备最高优先级的推荐 profile；
5. 其它设备兼容 profile，作为用户可选方案。

排序成本至少包含：

- 是否已经完整安装；
- 是否需要下载，预计下载量和安装后磁盘占用；
- 是否需要重启；
- Runtime/Provider 是否已经被其它能力复用；
- 设备容量与推荐门槛，而非瞬时空闲内存；
- App priority、质量档位和组织策略；
- 用户是否允许本地、Cloud 或远端 Node fallback。

“推荐”不等于总是下载新模型，但必须服从 Host 的临时安全策略。例如 H3 BF16/FP16
当前因输出质量问题处于禁用状态：即使 Checkpoint 已完整安装，也不能被复用、显示为可用
Provider 或接受生成任务。所有 64 GiB 及以上 Apple Metal 设备暂时推荐 Q8；32–63 GiB
推荐 Q4。解除禁用必须同时恢复 ACPF profile、Provider catalog 和任务服务端策略，并通过
固定质量回归用例。

Planner 必须返回可解释原因：

```json
{
  "profileId": "apple-metal-h3-q8",
  "recommendation": "recommended",
  "reasons": [
    "Matched Apple Metal with 128 GiB unified memory",
    "Q8 is the Video Studio balanced default for 64 GiB and above",
    "MLX Runtime 1.4.0 is already installed"
  ],
  "profileOptions": [
    {
      "profileId": "apple-metal-h3-q8",
      "label": "MiniMax H3 Q8 · 高质量",
      "compatible": true,
      "recommended": true,
      "selected": true,
      "disabledReasons": []
    },
    {
      "profileId": "apple-metal-h3-q4",
      "label": "MiniMax H3 Q4 · 节省内存",
      "compatible": true,
      "recommended": false,
      "selected": false,
      "disabledReasons": []
    }
  ]
}
```

## 7. 生命周期状态机

Provisioning Session 状态：

```text
planning
  -> awaiting_confirmation
  -> installing_runtime
  -> awaiting_restart
  -> installing_provider
  -> downloading_checkpoint
  -> activating
  -> verifying
  -> ready

任意执行态 -> failed -> retrying
任意可取消态 -> cancelled
```

Session 至少持久化：

```json
{
  "id": "prv_...",
  "appId": "ai2apps.video-studio",
  "appInstanceId": "appi_...",
  "capability": "video.generation",
  "actionId": "configure-generation",
  "profileId": "apple-metal-h3-q8",
  "requestFingerprint": "sha256...",
  "status": "downloading_checkpoint",
  "intent": {
    "returnTo": "/apps/ai2apps.video-studio",
    "resumeToken": "opaque-app-draft-token",
    "completionPolicy": "configure_only"
  },
  "plan": {"steps": []},
  "operations": [],
  "progress": {"phase": "downloading_checkpoint", "percent": 52},
  "error": null,
  "createdAt": "...",
  "updatedAt": "..."
}
```

`completionPolicy` v1.1 允许：

- `configure_only`：默认值。恢复 App 和草稿后只提示能力已经可用，等待用户确认并再次提交；
- `resume_action`：仅用于 App 已持久化业务草稿、提供稳定幂等键且明确希望自动续接的 action。

共享 Client 在 Provider 原本就绪时返回 `outcome=already_ready`；如果经过 Setup Session 才就绪，
返回 `outcome=configured` 和 `completion`。它不得自动 acknowledge：

```json
{
  "status": "ready",
  "outcome": "configured",
  "completion": {
    "policy": "resume_action",
    "shouldResumeAction": true,
    "idempotencyKey": "stable-business-key"
  }
}
```

原始 Prompt、表单、聊天内容、附件和媒体引用属于 App Session，不得复制进 ACPF Session、
共享 Client 的 pending storage 或全局安装日志。`resumeToken` 只引用 App 自己持久化的 action
draft，必须是不可反推出内容的 opaque token。Checkpoint 下载状态和 Package 操作 ID 可以进入
ACPF Session。

### 7.1 重启恢复

需要重启时必须：

1. 原子提交 ACPF Session 为 `awaiting_restart`；
2. 保存 `returnTo`、App instance、用户和 resume token；
3. 发起本 Installation 范围的受控重启；
4. 桌面壳启动后查询未完成或待返回的 ACPF Session，并导航到 `returnTo`；
5. Shell 不得确认 return 已消费，也不得读取 App draft；
6. 目标 App 重新打开同一个 Setup Sheet，而不是 AI2Apps Home 或 Models；
7. 重新探测事实，不盲信重启前状态；
8. 从第一个未完成且幂等的 step 继续；
9. App 成功恢复草稿和 capability 状态后调用 `acknowledge-return`。只有目标 App SDK 拥有该
   acknowledgement，Shell 不得重复调用。

## 8. API 与 Client SDK

v1.1 平台 API：

```text
POST /v1/platform/capabilities/probe
POST /v1/platform/capabilities/ensure
GET  /v1/platform/provisioning/sessions
GET  /v1/platform/provisioning/sessions/{session_id}
POST /v1/platform/provisioning/sessions/{session_id}/confirm
POST /v1/platform/provisioning/sessions/{session_id}/select-profile
POST /v1/platform/provisioning/sessions/{session_id}/retry
POST /v1/platform/provisioning/sessions/{session_id}/cancel
POST /v1/platform/provisioning/sessions/{session_id}/acknowledge-return
```

v1.1 Client 使用 Session GET 轮询状态。`events`/SSE 可以作为后续优化增加，但不能成为 App
恢复正确性的唯一依赖。

除 Shell 用于寻找 return target 的 Session 列表外，Session GET/confirm/retry/cancel/acknowledge
都必须携带 SDK 从 Host mount 获得的 AppInstance 上下文。`resume_action` 的
`acknowledge-return` body 必须携带与 intent 相同的 `idempotencyKey`；`configure_only` 使用空 body。

`probe` 是只读、无安装副作用的快速检查，并返回标准 Capability Choice Sheet 所需的
`profileOptions`。共享 Client 必须先展示候选、推荐项与硬不兼容原因，只有用户点击继续后，才以
所选 `requirements.profileId` 调用 `ensure`。因此选择阶段不创建 Session，也不占用下载/安装队列。

`ensure` 允许返回 ready Provider 或创建 `awaiting_confirmation` Provisioning Session，但未经
Setup Sheet 的第二次确认，不得开始需要许可接受、下载、安装或重启的步骤。`select-profile` 仅作为
旧 Client/恢复场景的兼容 API，只允许用于 `awaiting_confirmation` Session，不是标准 UE 的主路径；
选择不满足硬件边界的档位返回 422，不能通过绕过前端强制安装。

请求示例：

```json
{
  "appId": "ai2apps.video-studio",
  "appInstanceId": "appi_...",
  "capability": "video.generation",
  "actionId": "configure-generation",
  "requirements": {
    "operations": ["text_to_video"],
    "outputFormats": ["mp4"],
    "synchronizedAudio": true,
    "modelId": "ai2apps.model.minimax-h3/fl2va-4bit"
  },
  "intent": {
    "resumeToken": "opaque-app-draft-token",
    "returnTo": "/apps/ai2apps.video-studio",
    "completionPolicy": "configure_only"
  }
}
```

`appId` 和 `actionId` 是顶层字段。`modelId` 只在用户明确选择特定兼容模型时发送；省略时由
Planner 使用设备默认推荐。服务端必须从可信 App principal 校验 `appId`。

已就绪响应：

```json
{
  "status": "ready",
  "provider": {
    "modelId": "ai2apps.model.minimax-h3/fl2va-8bit",
    "serviceKey": "ai2apps.model.minimax-h3"
  }
}
```

需要配置响应：

```json
{
  "status": "setup_required",
  "sessionId": "prv_...",
  "session": {
    "id": "prv_...",
    "status": "awaiting_confirmation",
    "plan": {},
    "intent": {}
  }
}
```

`probe` 返回 `{status, device, provider, plan}`，其中 `plan.profileOptions` 是标准字段。每个选项至少
包含 `profileId`、`label`、`compatible`、`recommended`、`selected` 和 `disabledReasons`。App
不得自行重新排序、隐藏硬不兼容项或覆盖平台推荐；它只负责发起能力请求。

Capability 可以声明 `selection_mode: multiple`。此时 Choice Sheet 使用复选语义，推荐项默认勾选，
用户可以增加或移除其它兼容模型；继续按钮必须显示所选数量。Client 用 `requirements.profileIds`
提交非空、去重后的选择。Planner 把这些 Profile 的 Runtime、Package、Checkpoint 和验证步骤合并
为一个 Plan，共享 Runtime/Package 去重，并只创建一个可恢复 Session。任一所选 Profile 不兼容时
整个请求失败关闭，不能静默跳过该模型。

Client SDK 的最低接口：

```ts
type EnsureResult =
  | { status: "ready"; provider: ProviderHandle }
  | { status: "setup_required"; sessionId: string; session: ProvisioningSession }
  | { status: "unsupported"; reasons: string[] };

AI2Apps.capabilities.probe(request): Promise<ProbeResult>;
AI2Apps.capabilities.ensure(request): Promise<EnsureResult>;
AI2Apps.capabilities.resume(appId): Promise<EnsureResult | null>;
AI2Apps.capabilities.acknowledge(sessionId, {appId, idempotencyKey?}): Promise<void>;
```

当前共享 Web Client 的 `ensure` 先执行 `probe`：能力未就绪时打开 Capability Choice Sheet，用户
继续后携带所选 `profileId` 调用 `ensure`，再打开 Setup Sheet，并在 Session ready 后 resolve。
后续拆分 `openChoice(plan)` 或 `openSetup(sessionId)` 时必须保持相同的前置选择边界、Session 与恢复
语义，不能提前或重复创建 Provisioning Session。

SDK 必须自动附带可信 App identity 和 App instance；App 不应自行填写 `appInstanceId`，页面传入的
`appId` 也不能作为授权依据。服务端以 AppInstance 绑定的签名或内置 App definition 为准。

## 9. App 接入指南

### 9.1 新 App

1. 为每一个可能产生独立模型栈的用户操作定义 capability ID。
2. 写 `requirements`，只表达操作真正需要的格式和特性。
3. 为已测试的 Apple、NVIDIA、AMD 等设备类别配置有序 profile。
4. 为 action 选择 `configure_only` 或 `resume_action`；默认使用 `configure_only`。
5. 在执行按钮回调中把 action draft 保存到 App 自己的 Session，只把 opaque token 传给 ACPF。
6. `ready` 时用返回的 Provider Handle 执行，不能再次自行挑选硬编码模型。
7. 能力未就绪时由共享 Client 依次打开 Capability Choice Sheet 和 Setup Sheet，不实现 App 私有
   档位选择器或安装弹窗。
8. 配置完成后恢复 draft；`configure_only` 显示“环境已配置”并等待用户再次确认，
   `resume_action` 使用原业务幂等键自动执行一次。
9. 处理 `unsupported`、用户取消和 retryable/non-retryable 错误。
10. 为 probe、首次配置、重启恢复、configure-only 和 exact-once resume 编写集成测试。

示例：

```javascript
async function generateVideo() {
    const draftToken = await appSession.persistDraft(currentForm());
    if (selectedProvider?.ready) {
        return submitVideo(selectedProvider.id, await appSession.loadDraft(draftToken));
    }
    const result = await AI2Apps.capabilities.ensure({
        appId: 'ai2apps.video-studio',
        capability: 'video.generation',
        actionId: 'configure-generation',
        requirements: {
            operations: [mode === 't2v' ? 'text_to_video' : 'image_to_video'],
            outputFormats: ['mp4'],
            synchronizedAudio: true,
            ...(selectedModelId ? {modelId: selectedModelId} : {}),
        },
        intent: {
            resumeToken: draftToken,
            returnTo: '/apps/ai2apps.video-studio',
            completionPolicy: 'configure_only',
        },
    });
    if (result.status === 'ready') {
        restoreForm(await appSession.loadDraft(draftToken));
        showReady('视频生成环境已配置，请确认参数后加入生成队列');
        return;
    }
    showUnsupported(result.reasons);
}
```

真实业务提交按钮在 Provider 已 ready 时可以直接调用 `submitVideo`。配置按钮和业务提交按钮
可以是同一个视觉入口，但其 enabled 条件必须分开：配置不依赖 Prompt、附件或其它业务输入，
业务提交仍必须执行完整表单校验。

### 9.2 Chat 升级指南

Chat 与 Video Studio 的可用性门槛不同。注册用户登录后，账号下发的 AI2Apps Cloud
OpenAI 等模型就是 `text.chat` 的可用 Provider；Chat 必须立即把这些模型放入模型列表，不能因为
设备尚未安装本地 Runtime 或模型而阻止输入、发送消息或弹出强制 Setup Sheet。

本地聊天模型属于可选增强，使用独立 capability `text.chat.local`。推荐流程必须满足：

1. Chat 加载模型目录后优先保证 Cloud Provider 可选并可直接发送；
2. 当没有本地 conversation model 且设备存在可信推荐 profile 时，在 Chat 内显示低干扰推荐卡；
3. 推荐卡明确说明云端模型仍可使用，本地模型的价值是离线、隐私和低延迟；
4. 只有用户点击“选择并安装本地模型”后才 `ensure text.chat.local`，不得在启动或首次发送时自动下载；
5. 安装完成后刷新模型列表并加入本地 Provider，不自动切换正在使用的 Cloud 模型；
6. 设备没有可信本地 profile 时隐藏推荐入口，不影响 Cloud Chat。

当前 Apple Metal 本地 Chat 档位：16–32 GiB 推荐 Qwen3.6 35B 4-bit；32–64 GiB 推荐
DeepSeek V4 Flash 2-bit；64 GiB 及以上推荐 DeepSeek V4 Flash 高质量档。DeepSeek 2-bit 的
硬下限是 32 GiB，高质量档硬下限是 48 GiB，因此在 8 GiB 等设备上必须显示为不可选择并说明
最低内存要求；Cached-MoE 只降低常驻/活动专家成本，不能绕过 Profile 的硬件安全下限。

Registry 还提供经过 Package/Checkpoint 契约校验、但暂不抢占默认推荐的新模型：Qwen3.5
0.8B/2B（8 GiB 起）、Qwen3.8 27B NVFP4（24 GiB 起）、Ornith 1.5 35B Vision（32 GiB 起）和
GLM-5.3 Flash 4-bit MTP（64 GiB 起）。它们显示在同一个 Choice
Sheet 中，由用户主动复选；在完成针对各设备档位的质量与性能验收前标记为非默认推荐。

只有 Discover 公共 Registry 已发布且可匿名回读的 Package 才能进入 Choice Sheet。Qwen3.8
Flash Next 4-bit 的本地 Profile/Package 已完成，但截至 2026-08-30 发布清单仍未完成，因此暂不
登记为可下载选项；发布并完成 catalog 回读后再加入，避免向用户展示无法兑现的安装入口。

`text.chat.local` 使用 `selection_mode: multiple`：Choice Sheet 展示 Registry 中所有受信任的本地
聊天模型，按设备勾选一个推荐模型，同时允许用户复选任意其它兼容模型。所选模型进入同一个
Provisioning Session，一次确认后按合并计划下载安装；共同的 oMLX Runtime 只安装一次。配置完成
后 Chat 刷新模型目录，所有成功安装的模型都应可选。

其它按功能触发的能力建议拆分：

- 文字消息只在当前没有任何满足 `text.chat` 的 Cloud、Fusion 或 Local Provider 时才进入缺失能力处理；
- 第一条带图片消息应先检查当前 Cloud/Local Provider 是否满足 `vision.chat`，只有确实没有兼容
  Provider 时才 ensure；
- 第一次录音前 ensure `audio.speech_recognition`；
- 第一次朗读回复前 ensure `audio.speech_generation`。

ASR/TTS 按钮在能力缺失时不得使用 HTML `disabled` 或表现为不可交互的灰色按钮。按钮保持可点击，
Hover Tip 说明“需要配置，点击查看推荐下载方案”。点击先展示只读探测生成的 Capability Choice
Sheet；用户选定档位并继续后才创建 `awaiting_confirmation` Session 和展示 Setup Sheet。在用户
点击 Setup Sheet 的确认按钮前，不得下载 Package/Checkpoint、启动模型、
申请麦克风权限、开始录音或朗读。用户取消时保留原 Chat 状态且不产生安装副作用。配置成功后只
刷新 Voice 模型和角色选择，用户需要再次点击麦克风或朗读按钮才执行语音操作。

当前 Apple Metal 音频推荐档位：

- ASR：8 GiB 及以上推荐 Qwen3 ASR 0.6B 4-bit；
- TTS：8–16 GiB 推荐 Qwen3 TTS 0.6B CustomVoice 6-bit；
- TTS：16 GiB 及以上推荐 Qwen3 TTS 1.7B CustomVoice 8-bit；
- 8 GiB 设备上的 1.7B TTS 属于硬不兼容档位，必须置灰而不是仅取消“推荐”标签。

音频 Registry 同时列出可选的 SenseVoice Small、Qwen3 TTS Base/VoiceDesign、CosyVoice 3
4-bit/8-bit、VibeVoice Realtime 和 Fish Audio S2 Pro。Fish S2 Pro 必须在下载前展示研究/非商业
许可及商业用途另行授权要求；CosyVoice 必须连同 S3Tokenizer 依赖配置；SenseVoice 必须连同标点
恢复依赖配置。能力 UI 应依据模型的 `audio_capabilities` 显示角色、参考音频、声音克隆、情绪、
语速、长文本和多说话人控件，不能把所有 TTS 模型假定为同一能力集。

Chat 应把草稿和附件先保存到 Chat Session，ACPF 只持有 opaque resume token。已经配置的
default model 可以作为 Resolver 候选，但必须满足当前 capability requirements。

Chat 使用 canonical App ID `ai2apps.general-chat`。Capability Profile、页面 `data-app-id`、
principal、draft owner 和 `returnTo` 必须统一使用这个身份。

Chat 的发送动作可以使用 `resume_action`，但仅在以下条件全部满足后：消息草稿已经写入 Chat
Session、附件已有稳定引用、发送请求携带稳定 idempotency key、重启恢复测试证明同一用户消息
恰好提交一次。未满足时使用 `configure_only`，配置完成后保留输入框内容并提示用户再次发送。

### 9.3 Read Aloud 升级指南

至少拆分：

- 普通朗读：`audio.speech_generation`；
- 音色设计/克隆：`audio.voice_clone`；
- 如果需要参考音频清理：`audio.processing`。

普通 TTS 不得因为用户从未使用音色克隆而下载克隆模型。Read Aloud 的播放队列和文本位置
必须在重启前持久化。默认使用 `configure_only`；只有每个片段都有稳定幂等键时才可以使用
`resume_action` 从未提交片段继续，并且不得重复已生成片段。

### 9.4 Video Studio 升级指南

至少拆分：

- 普通文生/图生视频：`video.generation`；
- 数字人：`video.digital_human`；
- Ref2VA：`video.reference_generation`。

打开 Video Studio 只 probe 并在相关区域显示状态。第一次点击“加入生成队列”才 ensure。
当 Provider 未 ready 时，主要动作是“配置生成环境”，且不依赖 prompt 或关键帧是否已经填写。
H3 配置成功后恢复 prompt、关键帧、时长、分辨率、preset 和 seed，提示环境已经配置完成，
不得自动创建生成任务。用户确认模型和参数后再次点击才加入队列。进入数字人功能时不得把
H3 ready 错认为 EchoMimic ready。

模型下拉菜单不放置“无可用视频模型”之类的伪模型项。已安装 Q8 时选择兼容但未 ready 的 Q4，
必须通过 `requirements.modelId` 触发 Q4 profile，并复用已满足的 Runtime/Service Package、
只安装缺失的 Q4 Checkpoint。

#### 9.4.1 Video Studio 项目迁移状态（2026-08-25）

Video Studio 的 v1.1 P0 调用侧迁移已经落入当前实现：

1. `intent` 只发送 `returnTo`、opaque `resumeToken` 和显式
   `completionPolicy: configure_only`，不再发送 `draft` 或 Prompt；
2. Prompt、模式、首尾帧、分辨率、时长、preset、steps 和 seed 保存在按用户、Installation 和
   AppInstance 隔离的 Video Studio Draft Repository。关键帧以私有文件资源保存，恢复完成后删除；
3. App 分别恢复 `video.reference_generation` 与 `video.generation`；任一 capability 返回
   `outcome=configured` 后，App 先用 opaque token 恢复并校验 draft，再由 App 调用
   `AI2AppsCapabilities.acknowledge(session.id, {appId: APP_ID})`；
4. Video Studio 不再读取 `resumed.session.intent.draft`，也不再用业务 `localStorage` 作为 ACPF
   草稿存储；
5. 保持 `configure_only`：配置完成只显示环境就绪，等待用户再次点击，不自动创建视频任务；
6. ACPF 请求声明 `synchronizedAudio: true`，保持与 `video.generation` profile 的能力要求一致；
7. API、数据库迁移、opaque token、关键帧恢复、ACPF 内容边界和 App acknowledgement 已纳入
   自动化回归。发布验收仍须执行一次真实 Local 重启的 Desktop smoke test。
8. “参考素材”模式只展示声明 `reference_to_video` 的 Provider，并通过
   `video.reference_generation` 独立 probe/ensure。参考文件可能很大且在配置重启后已经失去浏览器
   File 授权，因此 draft 只恢复参数；完成页明确要求用户重新选择参考素材，不自动提交任务。

如果未来改为 `resume_action`，必须先为视频任务 API 提供稳定 `idempotencyKey` 和服务端去重，
业务提交成功后再以相同 key acknowledge，并补充重启/重复恢复下恰好创建一个任务的测试。

## 10. 统一 Capability Choice + Setup UE

共享向导由平台提供，显示在发起操作的 App 内。标题、说明、图标、完成文案和步骤名称来自
可信 capability presentation 元数据，并提供平台默认值；共享组件不得硬编码某个 App 或模型
名称。各 App 可以提供展示信息，但不得改变执行语义。

标准 UE 分成两个边界清晰的阶段：

1. **Capability Choice Sheet（决策阶段）**：Client 调用只读 `probe`，展示当前设备事实、全部
   可信档位和平台推荐；推荐项默认选中，用户可改选其它兼容档位；明确无法运行的档位置灰并显示
   硬件原因。取消不创建 Session、不下载、不安装，也不申请设备权限。
   当 capability 声明 `selection_mode: multiple` 时，同一 Sheet 允许复选多个兼容模型并显示数量。
2. **Setup Sheet（执行确认阶段）**：用户从 Choice Sheet 继续后，Client 才携带所选 `profileId`
   调用 `ensure` 并创建持久化 Session。Sheet 固定显示已选档位、下载量、磁盘占用、
   Runtime/Package/Checkpoint、许可和重启影响；用户再次确认后才开始副作用。
3. 展示逐步骤进度、速度、剩余量和可恢复状态；
4. 重启后自动回到同一 Setup Sheet；
5. 执行 checkpoint、Worker、Provider 的 Ready、健康和协议验证；
6. 显示完成并恢复原 App 状态；
7. 按 `completionPolicy` 等待用户再次确认，或以原幂等键自动续接一次。

这套两阶段 UE 是 ACPF 标准，不是 Chat 特例。Chat 本地模型、ASR、TTS、Video Studio 和第三方
App 必须复用共享 Client；产品页不得复制一份选择逻辑。平台推荐只提供默认决定，最终选择权属于
用户；服务端始终重新校验硬边界，确保前端篡改也不能选择设备肯定无法运行的档位。

不可用功能不应永久隐藏或只显示“没有模型”。推荐文案是“需要配置”，主要动作是“一键配置”。
高级入口可以允许用户选择其它兼容精度、Cloud Provider 或远端 Node。

## 11. 幂等、并发与失败恢复

- 同一用户、Installation、App、capability、等价 requirements 和等价 stack 的活动 Session
  必须合并。不同 `modelId`、profile 或版本约束不得误合并。
- Runtime、Package 和 checkpoint step 使用稳定幂等键，刷新页面不得创建重复下载。
- 多个 App 同时需要同一 Runtime 时，只执行一次安装，其余 Session 订阅同一底层 operation。
- 取消一个 Session 不得删除被其它 Session 或已安装 Provider 使用的共享资产。
- checkpoint 必须按固定 revision 验证完整布局；下载完成不等于 Provider ready。
- 重试从第一个未满足的事实开始，不能依赖简单的 step 序号。
- 回滚必须保持最后一个已验证的可运行栈，禁止半升级状态覆盖它。

错误至少区分：

```text
unsupported_device
no_trusted_profile
license_not_accepted
insufficient_disk
runtime_incompatible
package_dependency_conflict
checkpoint_download_failed
checkpoint_incomplete
restart_failed
provider_unhealthy
verification_failed
policy_denied
user_cancelled
```

错误对象必须包含 `retryable`、用户安全文案、当前 step 和建议动作，不得泄漏 token、内部路径
或未经清理的 Worker stderr。

## 12. 安全、许可和信任

- App profile 随 App 签名；Discover 策略覆盖必须由受信发布者签名并带版本/回滚保护。
- 远程策略只能替换为兼容且经过授权的候选，不能注入命令、下载 URL 或绕过 Package 验签。
- 模型许可、地域限制和使用约束必须在下载前确认；接受记录绑定用户、许可 digest 和版本。
- Runtime/Provider Package 继续服从现有权限、Sandbox、SBOM 和审计要求。
- ACPF 安装行为属于有副作用的系统操作，必须经过现有 App capability authorization。
- `resumeToken` 必须不透明、限用户、限 App、限 Installation，并具有过期与撤销机制。
- Setup Sheet 不得读取不属于当前 App Session 的草稿内容。
- 共享 Client 的 `localStorage`/pending storage 不得保存完整 CapabilityRequest 中的敏感
  `intent`；只保存恢复 Session 所需的 session ID、App ID 和 opaque token。
- `appId` 必须由服务端与可信 App principal、App instance 和 Installation 交叉验证。拥有通用
  `APP_USE` 权限不等于可以冒充另一个 App 的 profile。

## 13. 签名推荐策略覆盖

App 内置 profile 提供离线基线。AI2Apps 可以从 Discover 获得签名的 profile overlay，以便
支持新 GPU、新 Runtime 或更优 checkpoint，而不重新发布整个 App。

Overlay 必须声明：

- 目标 `app_id`、App version 范围和 capability；
- overlay version、发布时间、过期时间和前序版本；
- 发布者、签名、Package/version/checkpoint 约束；
- 新增、替换或撤销的 profile ID；
- 安全公告或撤销原因。

合并顺序为：App 内置基线 → 官方签名 overlay → 组织策略过滤 → 用户允许的高级选择。
组织和用户层可以禁用候选，不能绕过 Package 兼容性与信任校验。

## 14. 可观测性与隐私

建议记录以下不含内容的数据：

- capability、匹配的 profile ID 和设备类别；
- 选择原因和被过滤候选的结构化原因；
- 每个 step 的耗时、下载字节、重试和结果；
- restart/resume 是否成功；
- Provider 验证结果和稳定错误码。

不得记录 Prompt、聊天内容、上传媒体、音色样本或 resume draft。设备名可用于本地诊断；上传
遥测时应归一化为硬件能力档位，并遵循用户遥测设置。

## 15. 测试与发布门槛

每个 App capability/profile 至少需要：

1. 配置 schema 和签名验证测试；
2. 设备边界测试，例如 H3 当前策略的 31/32、47/48 和 63/64 GiB；
3. Runtime/Provider 版本交集测试；
4. 已安装资产优先复用测试；
5. 磁盘不足、下载中断和 checkpoint 不完整测试；
6. 重启后返回原 App 和原 Setup Session，并由目标 App 单次 acknowledge 的测试；
7. `configure_only` 配置完成后不创建业务任务、不要求业务输入且保留表单的测试；
8. 每个 `resume_action` 配置完成后原 action 恰好执行一次的测试；
9. 显式选择非默认兼容模型时定向 profile/Checkpoint 的测试；
10. 多 App 共享 Runtime 和下载去重测试；
11. 用户取消、许可拒绝和策略拒绝测试；
12. ACPF Session、pending storage 和日志不含 Prompt/附件内容的隐私测试；
13. 对每个声称支持的 Apple/NVIDIA/AMD profile 做真机 smoke test。

只有 Package 安装成功不能作为 release gate。最终 gate 是 Provider ready、轻量验证通过、
原 App 状态恢复成功；如果 action 声明 `resume_action`，还必须验证自动恢复恰好执行一次。

## 16. 实施顺序

建议按以下顺序实现：

1. `ai2apps.capability-profiles/v1` parser、Registry 和 Device Profiler；
2. Resolver 与只读 `probe`；
3. Planner、计划解释和 H3/128GB Q8 推荐；
4. 持久化 Provisioning Session 和统一 Setup Sheet；
5. Package/Checkpoint operation 适配与下载去重；
6. restart coordinator、`returnTo` 和 resume token；
7. Provider/Checkpoint/轻量推理验证；
8. Video Studio `video.generation` 接入；
9. **已完成（2026-08-25）** v1.1 共享 P0：完成策略、opaque draft、通用 Setup Sheet、单一
   return acknowledgement、App identity 绑定和等价请求指纹去重；
10. **已完成（2026-08-25）** Chat 非阻塞 `text.chat.local` 推荐入口与 canonical App ID；后续
    继续细化 `vision.chat`、语音识别和语音生成的 Provider-first 检查；
11. Read Aloud `audio.speech_generation` 和 `audio.voice_clone` 迁移；
12. Video Studio `video.digital_human` 接入；
13. NVIDIA/CUDA 和 AMD/ROCm profile 与真机 release gate；
14. Discover 签名 overlay。

## 17. 新 App 发布检查清单

- [ ] 每个独立模型栈对应独立 capability，而不是以 App 为单位配置。
- [ ] capability ID、requirements 和 trigger 已声明。
- [ ] 每个默认 profile 都有真实设备测试记录。
- [ ] Runtime、Provider 和 Checkpoint 使用稳定 ID 与版本范围。
- [ ] Package 自身仍声明真实依赖和固定 revision。
- [ ] 操作前调用 ensure，而不是 App 启动时下载。
- [ ] action 已选择 `configure_only` 或 `resume_action`，默认不是自动提交。
- [ ] action draft 已持久化，ACPF 只保存 opaque resume token。
- [ ] 使用共享 Setup Sheet，没有 App 私有下载器。
- [ ] 重启后返回原 App、原功能和原配置会话。
- [ ] Shell 不消费 return acknowledgement，由目标 App 恢复成功后确认。
- [ ] `configure_only` 不自动提交；`resume_action` 有业务幂等键且仅执行一次。
- [ ] 配置入口不依赖尚未提交的 Prompt、附件或媒体是否完整。
- [ ] 显式模型选择通过 `requirements.modelId` 定向到兼容 profile。
- [ ] unsupported、取消、许可拒绝和重试均有明确 UE。
- [ ] 不记录用户 Prompt、媒体或音色内容。
- [ ] 已完成设备边界、断点恢复、去重和真机 smoke test。

## 18. 相关文档

- [AI2Apps 本地视频生成 v1 实现与验收](ai2apps-video-generation-v1-implementation.md)
- [AI2Apps default model routing](ai2apps-default-models.md)
- [AI2Apps Model Worker Package 开发手册](model-worker-package-manual.md)
- [Service/Package 运行模式与 Sandbox 开发指南](service-package-sandbox-development-guide.md)
- [AI2Apps Authority and Secret Baseline](security-authority-baseline.md)
- [AI2Apps Local Capability Sharing v1](ai2apps-local-capability-sharing-v1.md)

后续设计、Issue、代码注释和 App 接入文档应统一使用名称 **ACPF**，并链接本文档，避免出现
“模型安装向导”“Video Studio 配置器”等无法关联到系统机制的临时名称。
