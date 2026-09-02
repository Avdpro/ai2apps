# AI2Apps Studio App UI 设计规范 v1

状态：产品与架构设计基线。

适用范围：Video Studio、Read Aloud Studio、未来的 Image/Drawing Studio，以及其它以
“选择创作流程、配置专用工作区、运行生成任务、检查与导出产物”为主要交互的 AI2Apps
创作型 App。

相关规范：

- [AI2Apps App 开发指南](ai2apps-app-development-guide.md)
- [AI2Apps Platform Architecture](ai2apps-platform-architecture.md)
- [AI2Apps Capability Provisioning Framework（ACPF）v1.1](ai2apps-capability-provisioning-framework-v1.md)
- [AI2Apps Gallery 产品、技术与开发计划 v1](ai2apps-gallery-product-technical-development-plan-v1.md)
- [AI2Apps Coder](ai2apps-coder.md)

本文中的“必须”“不得”“应该”和“可以”分别对应 MUST、MUST NOT、SHOULD 和 MAY。

## 1. 设计目标

Studio App 不应被设计成一个不断增加“生成模式”Tab 的大型表单。它应是一个稳定的创作
Shell，在同一工作区中承载多个可发现、可安装、可独立升级和可由用户扩展的 Pipeline。

统一产品模型为：

> Studio App 管理创作上下文、素材入口和渲染结果；Pipeline 管理专用创作体验；ACPF
> 管理运行能力配置；Executor 管理实际执行；Gallery 管理跨 App 资产；Coder 管理扩展开发。

本规范的目标是：

1. Video、Audio、Image 等 Studio 使用一致的三列信息架构；
2. 每个 Pipeline 可以拥有真正独立的 WebUI，而不受统一表单能力限制；
3. 不同 Pipeline 仍共享一致的素材、任务、进度、产物、下载和恢复体验；
4. Pipeline 所需 Runtime、Service Package、模型和 Checkpoint 统一通过 ACPF 配置；
5. 用户可以通过 Coder 创建、验证、预览和安装私人 Pipeline；
6. ComfyUI 可以作为一类 Pipeline 的图执行与高级编辑后端，但不成为唯一实现方式。

## 2. 术语

### 2.1 Studio App

AI2Apps 中面向某一媒体领域的创作型 App，例如 Video Studio、Read Aloud Studio 和
Image Studio。Studio App 对用户提供稳定入口，并拥有本文定义的 Studio Shell。

### 2.2 Studio Shell

挂载在 AI2Apps 全局 Shell 内部的 Studio 级 UI 框架。Studio Shell 不等于 AI2Apps
Desktop Shell。它拥有三列布局、Pipeline 选择、Gallery Mini-Entry 挂载、Run/Artifact
工作区和跨 Pipeline 的恢复状态。

### 2.3 Pipeline

完成一种明确创作目标的可版本化组件，例如“快速视频生成”“动画制作”“直播制作”
“多人有声书”“商品海报”或“局部重绘”。Pipeline 可以包含：

- 专用 WebUI；
- 输入与输出契约；
- 能力需求和 ACPF 推荐 Profile；
- Executor 与 Workflow；
- 草稿、项目或会话状态；
- 可选的高级编辑入口，例如 ComfyUI Workflow 编辑器。

Pipeline 不是模型别名。一个 Pipeline 可以编排多个模型、工具、转换器和合成步骤；同一模型
也可以被多个 Pipeline 使用。

### 2.4 Pipeline Run

用户发起的一次 Pipeline 执行。Run 可以包含多个 Step 和底层 Task。Studio Shell 只依赖
标准 Run/Step/Artifact 协议，不依赖具体模型或 Executor。

### 2.5 Render Workspace

三列布局的右栏。它统一展示当前 Run、实时预览、Step 进度、生成产物、历史记录和通用操作。
“Render”在本文中泛指媒体生成或处理结果；在 Read Aloud 中包括音频，在 Image Studio 中
包括图片和图层，在 Video Studio 中包括视频、帧和直播监看。

## 3. 核心设计原则

### 3.1 顶层按创作目标选择 Pipeline

顶层导航优先表达用户目标，而不是机械地罗列模型 API。某种输入形态如果具有独立的素材
约束、能力依赖、配置流程和专用 WebUI，可以成为独立 Pipeline；否则应保留为 Pipeline
内部选项。Video Studio 的文生、图生和参考素材生成属于前一种情况，因此是三个内置
Pipeline，而不是中栏的模式 Tab。新增 Pipeline 仍需证明其创作流程差异，不能把每个模型或
参数变体都提升为顶层入口。

### 3.2 中栏由 Pipeline 拥有，左右栏由 Studio Shell 拥有

Pipeline 可以完全定制中栏，但不得重画 Pipeline 列表、伪造 Gallery、覆盖 AI2Apps 全局
Shell，或自行实现一个不兼容的任务与下载系统。

### 3.3 配置与业务执行分离

Pipeline 可以在加载时静默 `probe`，但不得仅因用户选中或打开 Pipeline 就下载大型模型。
需要配置时必须通过 ACPF 显示方案、成本、许可和重启影响。默认使用 `configure_only`：配置
完成后恢复草稿并等待用户再次确认，不自动执行昂贵生成。

### 3.4 产物先进入平台对象模型

Pipeline 输出必须先登记为受权限控制的 Artifact，并按产品策略登记或关联 Gallery Asset。
Pipeline WebUI 不得把任意宿主文件路径当作跨 App 交换协议。

### 3.5 专用体验优先，声明式 UI 是可选工具

简单 Pipeline 可以用 JSON Schema/UI Schema 生成表单；复杂 Pipeline 必须允许提供独立
WebUI。动画时间线、多人有声书、直播切场和图像蒙版不能被强制压缩成通用参数表。

## 4. 标准三列布局

桌面端 Studio App 的逻辑布局必须包含以下三个区域：

```text
┌──────────────────┬────────────────────────────────┬──────────────────────┐
│ Pipeline /       │ 当前 Pipeline 专用 WebUI       │ Render Workspace     │
│ Gallery Mini     │                                │                      │
│ Entry            │ 素材、脚本、分镜、参数、控制台 │ 预览、进度、产物、历史 │
└──────────────────┴────────────────────────────────┴──────────────────────┘
```

区域所有权：

| 区域 | 所有者 | 主要职责 |
| --- | --- | --- |
| 左栏 | Studio Shell | Pipeline 发现与切换；Gallery Mini-Entry |
| 中栏 | 当前 Pipeline | 专用创作 WebUI、草稿和 Pipeline 操作 |
| 右栏 | Studio Shell | Run、Step、Preview、Artifact、导出与恢复 |

推荐桌面尺寸：

- 左栏：`260–320 px`，可折叠；
- 中栏：`minmax(520 px, 1fr)`；
- 右栏：`360–460 px`，可折叠或进入专注预览；
- 列间距：`12–20 px`。

三列是逻辑架构，不要求在所有宽度永久同时展开。窗口不足时应按以下顺序降级：

1. 左栏折叠为可随时展开的侧栏；
2. 右栏折叠为 Preview/Run 抽屉或下方工作区；
3. 中栏保持主要编辑区域，不得被压缩到 Pipeline 声明的最小宽度以下；
4. Mobile 使用分层导航：Pipeline/Assets、Create、Output 三个页面或 Sheet。

不得通过把每一列缩到无法操作的宽度来“保留三列”。

## 5. 左栏：Pipeline 与 Gallery

### 5.1 双模式入口

左栏顶部必须允许在以下两种视图间切换：

- **Pipelines**：发现、选择和管理当前 Studio 支持的 Pipeline；
- **Assets**：挂载 Gallery Mini-Entry，浏览和拖入可用素材。

切换只改变左栏内容，不卸载当前 Pipeline，也不清除中栏草稿、右栏 Run 或 Gallery 选择。

### 5.2 Pipeline 列表

Pipeline 列表至少提供：

- 搜索、分类、收藏和最近使用；
- 官方、已安装、用户自建和第三方来源标识；
- 名称、图标、版本和简短用途；
- `Ready`、`Needs setup`、`Unavailable`、`Broken` 状态；
- 当前运行 Run 数量；
- 打开详情、在 Coder 中编辑、更新和禁用等受权限操作。

Studio 可以提供内置分类，但分类不得决定 Executor：

- 快速创作；
- 项目制作；
- 实时/直播；
- 专用工作流；
- 我的 Pipeline。

切换 Pipeline 前，Studio Shell 必须给当前 Pipeline 保存草稿的机会。若存在未持久化且无法
自动保存的状态，必须明确提示，不得静默丢失。

### 5.3 Gallery Mini-Entry

Assets 视图必须复用 Gallery 的同一用户级 AppInstance 和标准 Mini-Entry，不得在每个 Studio
复制一套私有素材库。关闭或切走 Assets 视图不得停止 Gallery 服务或清除其集合、滚动和选择
状态。

Gallery 向 Pipeline 交付的是授权后的 Asset/Resource 引用，例如：

```json
{
  "schema": "ai2apps.asset-reference/v1",
  "assetId": "asset_example",
  "resourceHandle": "rh_example",
  "kind": "image",
  "mediaType": "image/png",
  "name": "character.png"
}
```

不得把 Gallery Blob 根路径、任意本地绝对路径或其他用户的 Asset ID 直接交给 Pipeline。

### 5.4 拖放

左栏到中栏的拖放必须经过 Studio Shell/Host Bridge：

1. Gallery 发出标准 Asset drag payload；
2. Studio Shell 判断当前 Pipeline 是否声明对应 drop target；
3. 平台检查用户、AppInstance、Pipeline 和 Asset 权限；
4. 平台签发短期 Resource Handle；
5. Pipeline WebUI 收到规范化 `asset.drop` 事件；
6. Pipeline 决定插入角色、参考图、音频、镜头或其它具体位置。

Pipeline 不得信任浏览器 `dataTransfer` 中自报的路径或权限信息。

## 6. 中栏：Pipeline 专用 WebUI

### 6.1 独立 UI Entry

每个复杂 Pipeline 应提供独立 UI Entry。UI 应运行在平台管理的 App Mount、sandbox frame
或等价隔离环境中，并通过 Pipeline Bridge 与 Studio Shell 通信。

Pipeline UI 可以：

- 定义自己的表单、画布、时间线、分镜、角色卡、场景列表或直播控制台；
- 读取当前 Pipeline 的草稿或项目；
- 请求 Capability probe/ensure；
- 声明素材 drop target；
- 创建、取消或重试 Run；
- 把选中的 Run/Artifact 请求同步到右栏；
- 打开 Coder 或高级 Workflow 编辑入口。

Pipeline UI 不得：

- 直接安装、升级或删除 Package/Checkpoint；
- 绕过 ACPF、Capability Policy、GrantLease 或 Package Manager；
- 直接访问 Gallery 根存储、其它 App 私有状态或任意宿主路径；
- 绘制伪造的 AI2Apps 权限、安装、许可或系统确认界面；
- 吞掉右栏统一 Run/Artifact 状态，使任务只能在 Pipeline 私有 UI 中恢复。

### 6.2 声明式 UI

平台可以为简单 Pipeline 提供 schema renderer。声明式 UI 只是一种 UI Entry 实现，不是
Pipeline 协议本身。Pipeline 升级为自定义 WebUI 时，应保留相同的 inputs、requirements、
Run 和 Artifact 契约。

### 6.3 ComfyUI

ComfyUI 可以用于：

- 表示和执行离线或批处理 Workflow；
- 作为高级用户的节点图编辑入口；
- 由 Pipeline Package 提供受版本控制的 Workflow、Custom Nodes 和模型需求；
- 将节点级进度映射为标准 Pipeline Step。

ComfyUI 不应成为：

- 所有 Pipeline 必须使用的 UI；
- Pipeline Registry 或 Package Manager；
- ACPF 的替代品；
- 直播会话、低延迟交互或其它非 DAG 执行模型的强制抽象。

普通用户默认看到专用 WebUI。需要时 Pipeline 可以声明“在 ComfyUI 中编辑”入口，并明确
区分专用参数与底层 Workflow 的版本和兼容性。

## 7. 右栏：Render Workspace

右栏必须由 Studio Shell 统一实现，并能够适配图片、音频、视频、复合项目和实时会话。

### 7.1 标准区域

右栏至少包含：

1. **Preview**：当前输出或实时监看；
2. **Run 状态**：Pipeline、版本、状态、总进度和开始时间；
3. **Step 列表**：排队、运行、完成、失败、跳过和重试；
4. **Artifacts**：中间产物和最终产物；
5. **History**：当前项目/草稿关联的历史 Run；
6. **Actions**：取消、重试、比较、下载、保存到 Gallery、在来源中打开。

Preview 根据 Artifact kind 选择标准适配器：

- image：缩放、对比、透明背景和版本；
- audio：播放、波形、角色/段落定位；
- video：播放、帧定位、片段和下载；
- live：监看、连接状态、延迟、录制与会话控制；
- project：时间线摘要和最终导出集合。

### 7.2 Run 与 Step

一个 Pipeline Run 可以包含一个或多个 Step；Step 可以进一步关联一个或多个底层 Model
Task、Process Execution 或远程 Node Operation。右栏不得假设“一次点击等于一个模型请求”。

标准状态建议为：

- Run：`draft`、`queued`、`running`、`waiting_input`、`succeeded`、`failed`、
  `cancelled`、`expired`；
- Step：`pending`、`running`、`succeeded`、`failed`、`skipped`、`cancelled`；
- Live Session：`starting`、`live`、`paused`、`degraded`、`stopping`、`ended`。

右栏必须能在页面刷新、App 切换和 Desktop 重启后恢复非终态 Run。浏览器 `localStorage`
只能保存展示偏好，不能成为 Run、Step 或 Artifact 的事实来源。

### 7.3 Artifact 与 Gallery

下载必须遵循 App 开发指南，使用平台返回的原生 `download_url`，不得先把大型产物完整加载
到 JavaScript 内存再构造 Blob。

最终产物应该按 Studio 产品策略自动登记或建议保存到 Gallery。中间产物是否进入 Gallery
由 Pipeline 输出声明和用户偏好决定，但必须保留 Run/Step 来源和模型 revision。

## 8. Pipeline 类型

首版协议至少区分三种生命周期：

### 8.1 `clip`

一次输入产生一个或少量媒体产物。适用于快速视频、单段朗读、单图生成和局部编辑。

### 8.2 `project`

拥有长期项目、素材、场景/章节/画板、多个 Run 和最终导出。适用于动画、有声书、多人剧、
漫画、广告和多页面视觉设计。

### 8.3 `live_session`

拥有开始、暂停、恢复、降级、切场、停止和录制生命周期。适用于直播、实时数字人、实时字幕
和交互式演播。`live_session` 不得被伪装成一个永不结束的普通生成 Task。

## 9. Pipeline Package 建议契约

下面是目标方向，具体字段必须在实现前形成版本化 JSON Schema 并进入 Package validator：

```yaml
schema: ai2apps.video-pipeline/v1
id: example.animation-studio
name: Animation Studio
version: 1.0.0
kind: project

studio:
  domain: video
  categories: [animation, project]

ui:
  entry: web/index.html
  minimum_width: 520
  drop_targets:
    - id: character_reference
      accepts: [image]
    - id: voice_reference
      accepts: [audio]

executor:
  kind: comfyui
  workflow: workflows/animation.json
  editor_entry: comfyui

requirements:
  capabilities:
    - video.generation
    - image.generation
    - audio.speech_generation
  profiles:
    - animation.local.quality
    - animation.local.fast

outputs:
  - id: preview
    kind: video
    media_types: [video/mp4]
    final: false
  - id: master
    kind: video
    media_types: [video/mp4]
    final: true
```

不同 Studio domain 可以拥有不同 schema 名称，或在稳定后收敛为
`ai2apps.media-pipeline/v1`。在协议评审完成前不得把示例字段当作已实现 API。

Pipeline Package 的信任、签名、索引、安装、升级、禁用和回滚必须复用 AI2Apps Package
系统。Pipeline 不能以未受管脚本目录绕过 Package 权限边界。

## 10. Pipeline Bridge

Studio Shell 与 Pipeline UI 之间需要版本化 Bridge。建议最小事件/方法集：

```text
studio.context.get
pipeline.ready
pipeline.draft.changed
pipeline.requirements.probe
pipeline.requirements.ensure
pipeline.run.create
pipeline.run.cancel
pipeline.run.retry
pipeline.run.select
pipeline.artifact.select
gallery.asset.drop
gallery.assets.pick
coder.open.pipeline
```

Bridge 必须携带可信的 AppInstance、Pipeline identity、版本和当前 Studio domain。Pipeline
自报的 ID、来源、权限或 Package 状态不能成为授权依据。

事件 payload 必须使用有界、版本化结构；大文件通过 Resource Handle、Artifact URL 或
流式 Host Broker 传递，不得经 `postMessage` 复制完整二进制内容。

## 11. ACPF 集成规范

Pipeline 对其专用体验负责，平台对能力解析和安装负责。标准流程为：

```text
选择 Pipeline
  -> Studio Shell 读取可信 Pipeline requirements
  -> 静默 probe，仅更新 Ready/Needs setup 状态
  -> 用户在 Pipeline UI 发起需要能力的明确操作
  -> Pipeline 保存私有草稿，向 ACPF 只传 opaque resume token
  -> ACPF 展示兼容方案、下载量、磁盘、许可和重启影响
  -> 用户确认后由 Package Manager/Checkpoint Installer 执行
  -> Provider health 验证
  -> 返回同一 Pipeline UI
  -> Pipeline 恢复草稿并 acknowledge
  -> configure_only 默认等待用户再次确认 Run
```

强制要求：

- Pipeline Package 只能声明经过信任校验的 capability/profile；
- Pipeline UI 不得把任意 Package ID 列表直接当作安装命令；
- requirements 必须由 ACPF Registry 解析为可信 Runtime、Service Package 和 Checkpoint
  组合；
- 同一 Pipeline 的不同操作可以使用不同 capability，例如预览、最终渲染和直播；
- 选中 Pipeline 不等于授权下载；
- 配置成功不等于自动发起生成；
- 草稿正文、媒体和声音样本不得进入 ACPF Session 或共享 Client pending storage；
- Pipeline 更新导致 requirements 变化时必须重新 probe，不得沿用失效的 ready 结论。

## 12. Coder 扩展流程

Studio 左栏和 Pipeline 详情应提供“在 Coder 中创建/编辑 Pipeline”入口。Coder 应提供
按 Studio domain 区分的模板，例如：

- Video Pipeline；
- Read Aloud Pipeline；
- Image Pipeline；
- ComfyUI-backed Pipeline；
- Live Session Pipeline。

建议开发流程：

1. Coder 创建包含 Pipeline manifest、UI、Executor 和测试的 Project；
2. Validate 校验 manifest、资源索引、CSP、Bridge、requirements 和 output contract；
3. Run 在隔离 Preview 中加载 Pipeline WebUI；
4. “在 Studio 中预览”使用 TestFlight identity 挂载到对应 Studio；
5. 测试 Asset drop、ACPF probe、草稿恢复、Run 进度和 Artifact 输出；
6. Build 生成 development Project Bundle；
7. Submit to TestFlight 后仅当前开发环境可见；
8. 正式发布仍遵守签名 Package 发布流程。

私人 Pipeline 也必须经过 validator、隔离执行和权限检查。Coder 的可编辑源码身份不得在
运行时冒充已签名正式 Pipeline。

## 13. 各 Studio 的映射

### 13.1 Video Studio

推荐 Pipeline：

- 文生视频：提示词与分镜批量生成；
- 图生视频：首帧或首尾关键帧驱动生成；
- 参考素材视频：图片、视频与声音参考驱动生成；
- 动画制作：角色、风格、分镜、连续性、配音和合成；
- 直播制作：主播、场景、实时脚本、字幕、切场、推流和录制；
- 数字人口播；
- 商品广告、MV、短剧、视频扩展和修复。

右栏主要 Preview 类型为 video/live，Run 可以包含脚本、图像、语音、视频和合成 Step。

### 13.2 Read Aloud Studio

推荐 Pipeline：

- 快速朗读：选择已持久化台词，快速生成本地试听；
- 有声书制作：来源文本、章节、旁白与长文本演出；
- 多角色演播：角色、音色、情绪、语速与对白编排；
- 音色设计：虚构音色、音色档案与权利门禁；
- 训练角色：录制或上传已授权的参考音频，使用本地 ASR 或手工输入逐字稿，保存训练素材；
- 播客制作：主持人、嘉宾、音乐、广告位与混音；
- 实时朗读/伴读：实时生成、跟读、文本位置和播放进度同步。

中栏可以是剧本编辑器、角色与音色分配、章节结构或时间线。右栏统一展示音频预览、波形、
章节/台词 Step、失败分片、混音结果和导出 Artifact。

首轮落地状态（2026-08-26）：快速朗读、有声书制作、多角色演播、音色设计和训练角色作为
五个内置 Pipeline；播客制作和实时伴读只展示为规划项。前三者请求
`audio.speech_generation`；音色设计和训练角色请求 `audio.voice_clone`；训练角色仅在用户
主动转写时额外请求 `audio.speech_recognition`，手工输入逐字稿时不要求安装 ASR。所有能力
均通过 ACPF `configure_only` 配置。训练录音先作为当前用户的私有 Gallery Asset 持久化，
Voice Profile 只保存其 `referenceAssetId`、逐字稿和权利确认；配置完成后不自动训练或合成。
Studio 页面文案使用 App Shell 的 `en`/`zh` locale，同一次 Shell 语言切换会随顶层重载同步。

### 13.3 Image/Drawing Studio

推荐 Pipeline：

- 快速绘图；
- 商品海报；
- 角色设定表；
- 局部重绘与扩图；
- 风格迁移；
- 批量变体；
- 漫画/分镜项目。

中栏可以是提示词表单、画布、蒙版、图层、参考板或版式编辑器。右栏统一展示当前图像、
版本比较、放大结果、中间 Artifact 和导出历史。

## 14. 状态与恢复

Studio Shell 必须分别保存：

- 当前用户和 AppInstance 的左栏模式、宽度和折叠状态；
- 当前 Pipeline ID、版本和最近使用顺序；
- 当前 Project/Draft/Live Session；
- 当前选中的 Run、Step 和 Artifact；
- Gallery Mini-Entry 的独立持久状态引用。

职责边界：

- 布局偏好可以是设备本地状态；
- Pipeline 草稿和项目必须由 Pipeline/平台后端持久化；
- Run、Step、Task 和 Artifact 必须由平台后端持久化；
- ACPF pending storage 只保存 Session ID、App ID 和 opaque resume token；
- 敏感素材、声音样本和 Prompt 不得为了跨 App 恢复而写入共享 Shell storage。

## 15. 安全、权限与信任

1. Pipeline UI、Executor、Package 和输出都必须绑定 canonical 安装身份和版本；
2. Studio Shell 不信任 iframe、drag payload 或页面自报的 App/Pipeline ID；
3. Pipeline 的 Gallery 访问必须按 Asset/Resource Handle 授权；
4. ACPF 配置不能隐式授予模型调用、文件、网络、麦克风、摄像头或推流权限；
5. Live Pipeline 的摄像头、麦克风、屏幕捕获和外部推流必须逐项声明并获得用户授权；
6. 第三方 Pipeline 不得伪装平台安装、许可、账户或安全 UI；
7. Output Artifact 必须记录来源 Pipeline、版本、Executor、模型 revision 和 Run；
8. 禁用或卸载 Pipeline 后，历史 Run 和 Artifact 仍应可读；重新执行需要重新满足依赖和权限；
9. Pipeline iframe/CSP、Package 资源索引和 TestFlight 隔离遵循 App/Coder 现有规范。

## 16. 可访问性与交互一致性

- 三列均必须支持键盘导航和可见焦点；
- Pipeline/Assets 切换、折叠状态和 Run 状态必须具有可访问名称；
- 拖放必须提供“选择并插入”的键盘等价操作；
- 不得只靠颜色表示 Ready、Running、Failed 或选中状态；
- Preview 播放器使用宿主支持的标准媒体控制，并提供字幕/文本等价物；
- 长时间 Run 必须持续显示阶段、进度或可解释的等待状态；
- Pipeline 切换、配置完成和任务失败必须有明确反馈，但不得使用阻塞式重复弹窗；
- Studio Shell 统一提供错误、空状态、离线、未配置和恢复中的基础视觉语言。

## 17. 实施顺序

### Phase 1：Studio Shell 基线

- 实现三列布局、折叠和响应式降级；
- 左栏 Pipeline/Assets 双视图；
- 挂载 Gallery Mini-Entry；
- 右栏标准 Run/Artifact Workspace；
- 将现有 Video Studio 三种模式迁移为三个独立的内置 Pipeline。

验收：迁移后现有文生、图生、参考素材、队列、下载、合并和 ACPF 功能不回退；窗口缩放和
App 切换不丢失状态。

Video Studio 首轮落地状态（更新于 2026-08-26）：

- 已建立三列 Studio Shell，文生视频、图生视频和参考素材视频作为三个独立内置 Pipeline；
- 左栏已支持 Pipeline/Assets 切换，并挂载 Gallery Mini-Entry；
- Gallery 图片、视频和音频可通过标准 drag payload 路由到对应 Pipeline 和素材槽位；
- 右栏保留现有预览、任务队列、下载和片段合并行为；
- 现有 `video.generation`、`video.reference_generation`、草稿恢复和 ACPF configure-only
  流程保持不变；
- Pipeline Registry、第三方 Pipeline Bridge、Coder 模板以及直播/动画专用执行器仍属于后续
  Phase，不在本轮用临时私有协议提前固化。

### Phase 2：Pipeline Registry 与 Bridge

- 定义并验证 Pipeline schema；
- 建立可信 Registry、Pipeline Mount 和版本身份；
- 实现 Asset drop、Run、Artifact、ACPF 和 Coder Bridge；
- 建立 Pipeline 草稿与 Run/Step 数据模型。

验收：两个结构明显不同的 Pipeline 可以共享左右栏，同时提供不同中栏 WebUI。

### Phase 3：跨 Studio 验证

- Video Studio：文生/图生/参考素材内置 Pipeline + 动画项目；
- Read Aloud Studio：快速朗读 + 多角色有声书；
- Image Studio：快速绘图 + 局部重绘/画布；
- 校验 image/audio/video/project Preview adapter。

验收：三个 Studio 不复制 Pipeline 列表、Gallery、Run、Artifact 和 ACPF UI 逻辑。

### Phase 4：Coder 与第三方扩展

- Pipeline Project 模板；
- Validate、Preview、TestFlight 和 Studio deep-link；
- 私人 Pipeline 安装与版本更新；
- ComfyUI workflow validator 和高级编辑入口。

验收：用户可以在 Coder 中创建最小 Pipeline，在对应 Studio 中预览，通过 ACPF 配置已声明
能力，生成标准 Artifact，并在 Gallery 中复用。

### Phase 5：Live Session

- 标准 Live Session 状态和控制协议；
- 直播监看、延迟、降级、录制和推流状态；
- 摄像头、麦克风、屏幕和外部目标授权；
- 中断恢复和安全停止。

验收：直播 Pipeline 不依赖伪造的长任务，可以在右栏准确恢复和结束会话。

## 18. 开发验收清单

新增或升级 Studio/Pipeline 时至少检查：

- [ ] 顶层按创作目标选择 Pipeline，而不是继续增加输入模式 Tab；
- [ ] 左栏可在 Pipeline 与 Gallery Mini-Entry 间切换；
- [ ] 中栏是隔离、独立且可恢复的 Pipeline WebUI；
- [ ] 右栏复用标准 Run/Step/Artifact Workspace；
- [ ] Pipeline 打开时只 probe，不自动下载大型依赖；
- [ ] 缺失能力通过 ACPF ensure，Pipeline 不自行安装；
- [ ] ACPF 默认 configure-only，配置完成后不自动生成；
- [ ] 草稿通过 opaque token 恢复，不进入共享 pending storage；
- [ ] Gallery 交付 Asset/Resource Handle，不暴露根路径；
- [ ] 拖放存在权限校验和键盘等价操作；
- [ ] Run/Step/Artifact 可在刷新、App 切换和 Desktop 重启后恢复；
- [ ] 下载使用 Artifact 原生 URL，不在前端缓存大型 Blob；
- [ ] Pipeline 可声明 ComfyUI executor，但专用 WebUI 不被 ComfyUI 强制替代；
- [ ] Coder Preview/TestFlight 与正式签名身份隔离；
- [ ] Desktop、普通浏览器、窄窗口和至少一个移动布局完成验证；
- [ ] 权限、许可、安装、失败、降级和不可用状态有明确且不可伪造的 UI。

## 19. 非目标

本规范不试图：

- 定义所有媒体模型的底层推理协议；
- 用一个通用节点系统替代所有专用 Pipeline UI；
- 让 Studio Shell 直接执行第三方代码；
- 让 ACPF 替代权限、Discover、Package Manager、Model Worker 或默认模型路由；
- 要求所有 Studio 在视觉细节上完全相同。

一致性要求针对信息架构、职责边界、状态与安全契约。每个 Studio 和 Pipeline 可以在这些
边界内形成适合其媒体和创作任务的独特体验。
