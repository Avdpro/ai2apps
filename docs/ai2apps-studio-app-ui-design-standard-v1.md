# AI2Apps Studio App 与 Mini-App 设计规范 v1

状态：产品与架构设计基线。

适用范围：Video Studio、Voice Studio、Imagine/Image Studio，以及其它以
“选择创作应用、配置专用工作区、运行生成或处理任务、检查与导出产物”为主要交互的
AI2Apps 创作型 App。

2026-09-04 术语决策：旧版文档把“自带专用 UI 的创作单元”称为 Pipeline。该用法与
通常的无 UI 处理 Pipeline 混淆。本版统一改称 **Mini-App**，并将 **Pipeline**
保留给无 UI、可编排和可复用的执行层。

相关规范：

- [AI2Apps App 开发指南](ai2apps-app-development-guide.md)
- [AI2Apps Platform Architecture](ai2apps-platform-architecture.md)
- [AI2Apps Capability Provisioning Framework（ACPF）v1.1](ai2apps-capability-provisioning-framework-v1.md)
- [AI2Apps Gallery 产品、技术与开发计划 v1](ai2apps-gallery-product-technical-development-plan-v1.md)
- [AI2Apps Coder](ai2apps-coder.md)
- [Studio Mini-App Package Contract v1](ai2apps-studio-mini-app-package-contract-v1.md)
- [AI2Apps App-Shell App 开发环境](ai2apps-app-dev-environment.md)

本文中的“必须”“不得”“应该”和“可以”分别对应 MUST、MUST NOT、SHOULD 和 MAY。

## 1. 设计目标

Studio App 不应被设计成一个不断增加“生成模式”Tab 的大型表单。它应是一个稳定的创作
Shell，在同一工作区中挂载多个可发现、可安装、可独立升级和可由用户扩展的 Mini-App。
同一 Mini-App 可同时出现在多个 Studio 中；Studio 是它的宿主视图，不是它的所有者。

统一产品模型为：

> Studio App 管理创作上下文、素材入口和渲染结果；Mini-App 管理面向人的专用创作体验；
> Pipeline 管理无 UI 的处理流程；Capability Provider 让 Package 内外组件按契约共享无头能力；
> Agent Tool 管理面向 Agent 的结构化调用；ACPF 管理运行
> 能力配置；Executor 管理实际执行；Gallery 管理跨 App 资产；Coder 管理扩展开发。

本规范的目标是：

1. Video、Audio、Image 等 Studio 使用一致的三列信息架构；
2. 每个 Mini-App 拥有真正独立的 WebUI，而不受统一表单限制；
3. Mini-App 全局安装一次，可通过显式 placement 挂载到多个 Studio；
4. 不同 Mini-App 仍共享一致的素材、任务、进度、产物、下载和恢复体验；
5. Mini-App 所需 Runtime、Service Package、Pipeline、模型和 Checkpoint 统一通过可信契约与 ACPF 配置；
6. 一个 Package 可以原子地交付多个 Mini-App 和它们共享的 Pipeline/Service，不复制核心实现；
7. Mini-App 通过版本化 Capability 契约调用共享能力，而不是互相调用 UI；
8. 用户可以通过 Coder 创建、验证、预览和安装私人 Mini-App；
9. ComfyUI 可以作为 Mini-App 使用的图执行与高级编辑后端，但不成为唯一实现方式。

## 2. 术语

### 2.1 Studio App

AI2Apps 中面向某一媒体领域的创作型 App，例如 Video Studio、Voice Studio 和
Image Studio。Studio App 对用户提供稳定入口，并拥有本文定义的 Studio Shell。

### 2.2 Studio Shell

挂载在 AI2Apps 全局 Shell 内部的 Studio 级 UI 框架。Studio Shell 不等于 AI2Apps
Desktop Shell。它拥有三列布局、Mini-App 发现与挂载、Gallery Mini-Entry、Run/Artifact
工作区和跨 Mini-App 的恢复状态。

### 2.3 Mini-App

完成一种明确用户目标、必须自带 UI Entry 的可版本化交互组件，例如“视频语音替换”
“视频拆帧”“多人有声书”“商品海报”或“局部重绘”。Mini-App 可以包含：

- 专用 WebUI；
- 输入与输出契约；
- 面向多个 Studio 的 placement；
- 能力需求和 ACPF 推荐 Profile；
- 对 Pipeline、Executor、Workflow、Model 或 Service 的可信引用；
- 草稿、项目或会话状态；
- 可选的高级编辑入口，例如 ComfyUI Workflow 编辑器。

Mini-App 不归属于某一 Studio。Package 只安装一次，同一 canonical Mini-App identity
可挂载到多个 Studio，共享版本、信任、依赖和用户预设，但接收不同的宿主上下文。

### 2.4 Mini-App 与 Mini-Entry

Mini-App 是可发现、可安装、可运行的组件身份；Mini-Entry 是 App 在嵌入式宿主中的一个
UI Entry/surface。两者不是同义词。当前 Coder 已支持两种 Mini-App 来源：

- 独立 `mini-app.yaml` 和 `type: "mini-app"`；
- 由完整 App 的 `mini_entry` 发现出来的合成 Mini-App 组件。

面向 Studio 的专用创作 Mini-App 应优先使用独立身份。完整 App 的 Mini-Entry 只有在声明
合法 placement 和输入输出契约后，才应出现在 Studio 的 Mini-App 列表中。

### 2.5 Pipeline

Pipeline 是无 UI、可编排、可复用的执行图或处理流程。它定义输入、步骤、失败语义和输出，
但不拥有用户界面。一个 Mini-App 可调用多个 Pipeline，多个 Mini-App 也可共享同一
Pipeline。Agent Tool 同样可调用 Pipeline，但 Agent Tool 不因此获得 UI。

### 2.6 Capability Provider

通过稳定 Capability ID、版本化输入输出 Schema 和调用策略向其他组件提供无 UI 能力的可信
Component。Pipeline、Service 或平台 Runtime 可以是 Provider；Mini-App 不应为了复用代码而直接调用
另一 Mini-App。

### 2.7 创作套件 Package

对用户呈现为一个创作能力套件、并在一个签名 Package 中交付多个 Mini-App、共享 Pipeline、
Service 和静态资源的多组件 Package。“创作套件”是产品呈现，不是第二套安装格式。

### 2.8 Mini-App Run

用户在 Mini-App 中发起的一次业务执行。Run 可包含多个 Pipeline Run、Step 和底层 Task。
Studio Shell 只依赖标准 Run/Step/Artifact 协议，不依赖具体 Pipeline、模型或 Executor。

### 2.9 Render Workspace

三列布局的右栏。它统一展示当前 Run、实时预览、Step 进度、生成产物、历史记录和通用操作。
“Render”在本文中泛指媒体生成或处理结果；在 Voice Studio 中包括音频，在 Image Studio 中
包括图片和图层，在 Video Studio 中包括视频、帧和直播监看。

## 3. 核心设计原则

### 3.1 顶层按用户目标选择 Mini-App

顶层导航优先表达用户目标，而不是机械地罗列模型 API。某种输入形态如果具有独立的素材
约束、能力依赖、配置流程和专用 WebUI，可以成为独立 Mini-App；否则应保留为 Mini-App
内部选项。Video Studio 的文生、图生和参考素材生成在当前实现中是三个内置 Mini-App，
而不是中栏的模式 Tab。新增 Mini-App 仍需证明其用户流程差异，不能把每个模型或
参数变体都提升为顶层入口。

### 3.2 中栏由 Mini-App 拥有，左右栏由 Studio Shell 拥有

Mini-App 可以完全定制中栏，但不得重画 Mini-App 列表、伪造 Gallery、覆盖 AI2Apps 全局
Shell，或自行实现一个不兼容的任务与下载系统。

### 3.3 配置与业务执行分离

Mini-App 可以在加载时静默 `probe`，但不得仅因用户选中或打开 Mini-App 就下载大型模型。
需要配置时必须通过 ACPF 显示方案、成本、许可和重启影响。默认使用 `configure_only`：配置
完成后恢复草稿并等待用户再次确认，不自动执行昂贵生成。

### 3.4 产物先进入平台对象模型

Mini-App 输出必须先登记为受权限控制的 Artifact，并按产品策略登记或关联 Gallery Asset。
Mini-App WebUI 不得把任意宿主文件路径当作跨 App 交换协议。

### 3.5 专用体验优先，声明式 UI 是可选工具

简单 Mini-App 可以用 JSON Schema/UI Schema 生成表单；复杂 Mini-App 必须允许提供独立
WebUI。动画时间线、多人有声书、直播切场和图像蒙版不能被强制压缩成通用参数表。

### 3.6 跨 Studio 复用是一等能力

Studio 与 Mini-App 是多对多关系。例如“把视频里的语音替换成用户指定音色”可同时挂载到
Voice Studio 和 Video Studio；“把视频拆成单帧图片”可同时挂载到 Imagine Studio 和
Video Studio。这些 placement 必须指向同一 Mini-App identity，不得通过复制 Package 形成两个分叉实现。

Studio 不应仅根据媒体类型自动收录所有 Mini-App。Mini-App 必须显式声明 placement，平台再使用
input/output 契约验证兼容性，防止 Studio 列表被大量“技术上可用、产品上不合适”的项目污染。

### 3.7 共享能力，不共享 Mini-App 调用链

多个 Mini-App 需要同一核心功能时，应共同声明对 Capability 的需求，由 Package 内 Pipeline/
Service 或其他可信 Provider 实现。例如“添加字幕”“替换角色配音”和“生成其他语言配音”
可共享 `media.audio.extract` 和 `media.video.audio_mux`。

Mini-App 不得把另一 Mini-App 的 UI Entry、页面路由或私有 JavaScript/Python 模块当作能力 API。
共享静态 UI 资源应使用 Package 内受索引的 shared resources；可调用业务能力必须通过 Capability
Broker 和版本化契约暴露。

## 4. 标准三列布局

桌面端 Studio App 的逻辑布局必须包含以下三个区域：

```text
┌──────────────────┬────────────────────────────────┬──────────────────────┐
│ Mini-Apps /      │ 当前 Mini-App 专用 WebUI       │ Render Workspace     │
│ Gallery Mini     │                                │                      │
│ Entry            │ 素材、脚本、分镜、参数、控制台 │ 预览、进度、产物、历史 │
└──────────────────┴────────────────────────────────┴──────────────────────┘
```

区域所有权：

| 区域 | 所有者 | 主要职责 |
| --- | --- | --- |
| 左栏 | Studio Shell | Mini-App 发现、挂载与切换；Gallery Mini-Entry |
| 中栏 | 当前 Mini-App | 专用创作 WebUI、草稿和业务操作 |
| 右栏 | Studio Shell | Run、Step、Preview、Artifact、导出与恢复 |

推荐桌面尺寸：

- 左栏：`260–320 px`，可折叠；
- 中栏：`minmax(520 px, 1fr)`；
- 右栏：`360–460 px`，可折叠或进入专注预览；
- 列间距：`12–20 px`。

三列是逻辑架构，不要求在所有宽度永久同时展开。窗口不足时应按以下顺序降级：

1. 左栏折叠为可随时展开的侧栏；
2. 右栏折叠为 Preview/Run 抽屉或独立输出页面；
3. 中栏保持主要编辑区域，不得被压缩到 Mini-App 声明的最小宽度以下；
4. Mobile 使用分层导航：Mini-Apps/Assets、Create、Output 三个页面或 Sheet。

不得通过把每一列缩到无法操作的宽度来“保留三列”。

### 4.1 页面高度与独立滚动（2026-09-10）

Studio App 必须限制在当前宿主视口高度内，整体页面不得上下滚动。页头和移动端导航
占据固定区域，剩余高度由工作区使用；左、中、右三列分别在各自区域内上下滚动。
某一列内容变长不得撑高页面、移动其它列或把输出区推到页面下方。

左栏的 Mini-Apps / Assets / Chat 内容选择区必须固定在栏顶，滚动发生在其下的内容区域。
Mini-App / Mini-Entry 长列表必须能滚动到底，包含规划条目与底部操作；不得用隐藏溢出
裁掉列表，也不得让内容选择区随列表滚走。素材和 Chat 视图同样使用栏内剩余高度。

中栏的宿主标题与 Mini-App 内容组成同一个列内滚动面；右栏预览和历史在输出列内滚动。
Package UI 的高度消息继续由宿主核验后用于中栏内容高度，不得扩展整个 Studio 页面。
各滚动区域必须阻止滚轮继续传递到整体页面。窄窗口采用折叠、抽屉或移动端单面板导航，
当前面板仍在视口剩余区域内滚动，不恢复整页纵向滚动。

实现时须为 flex/grid 高度链设置可收缩的 `min-height: 0`，并在实际滚动节点设置
`overflow-y: auto`；不得只给最外层 `overflow: hidden`。验收须分别滚动三列，确认其它列
和页头不动，并在左栏滚到底后确认顶部选择区仍可操作。

### 4.2 Header 样式与操作（2026-09-10）

三个 Studio 共用同一 Header：左侧为品牌图标和 Studio 名称，右侧依次为刷新、左栏开关、
右栏开关，均使用图标按钮。不显示副标题、重复的 Studio 名称或云端/本地标记；取消的
环境标记不迁移到中栏作为徽标。模型选择中的来源信息仍可用于用户选择模型。

Header 固定高度 `64px`，桌面左右内边距 `24px`，白底、浅灰底部分隔线。品牌图标容器
`36 × 36px`、圆角 `10px`、内部图标 `20px`；标题 `17px`、字重 `700`，间距 `12px`。
右侧按钮 `34 × 34px`、圆角 `9px`、图标 `16px`、按钮间距 `8px`，统一中性灰色。
对应侧栏展开时，开关显示浅灰底并设置 `aria-expanded=true`；悬停提示与可访问名称须
本地化。刷新过程中禁用刷新按钮并显示旋转反馈。

模型与依赖配置入口置于中栏相关设置附近，不能因缺少模型而向 Header 临时插入按钮。
Voice 原中栏的重复布局开关移除。窄屏左右内边距 `15px`；已有单面板导航的 Studio 隐藏
不适用的左右栏开关，布局切换由移动导航承担。Header 固定在三列滚动区域之外。

## 5. 左栏：Mini-App 与 Gallery

### 5.1 双模式入口

左栏顶部必须允许在以下两种视图间切换：

- **Mini-Apps**：发现、选择和管理当前 Studio 挂载的 Mini-App；
- **Assets**：挂载 Gallery Mini-Entry，浏览和拖入可用素材。

切换只改变左栏内容，不卸载当前 Mini-App，也不清除中栏草稿、右栏 Run 或 Gallery 选择。

### 5.2 Mini-App 列表

Mini-App 列表至少提供：

- 收藏；搜索、分类和最近使用筛选可按实际需求提供；
- 官方、已安装、用户自建和第三方来源标识；
- 名称、图标、版本和简短用途；
- `Ready`、`Needs setup`、`Unavailable`、`Broken` 状态；
- 当前运行 Run 数量；
- 打开详情、在 Coder 中编辑、更新和禁用等受权限操作。

当前三个 Studio 的列表顶部统一直接显示“已安装”和条目数量，不常驻搜索、排序或
“全部 / 收藏 / 最近”筛选区（2026-09-10）。Imagine Studio 暂时移除该区域以增加列表
可见空间；卡片上的收藏操作与已保存收藏继续保留。后续确有需要时再设计低占用入口。

Studio 可以提供内置分类，但分类不得决定 Executor：

- 快速创作；
- 项目制作；
- 实时/直播；
- 专用工作流；
- 我的 Mini-App。

切换 Mini-App 前，Studio Shell 必须给当前 Mini-App 保存草稿的机会。若存在未持久化且无法
自动保存的状态，必须明确提示，不得静默丢失。

Studio 对 Mini-App 的分类、排序和展示名可以不同。例如同一“视频语音替换”Mini-App 可以在
Voice Studio 的“视频语音”分类下，也可以在 Video Studio 的“音频与对白”分类下。这些都是
placement 元数据，不会创建新的 Mini-App identity。

#### 5.2.1 卡片右侧状态与收藏（2026-09-10）

所有 Studio 必须使用以下规则，包括由 Mini-Entry 映射而来的 Mini-App 条目。卡片右侧
使用同一个位置展示当前状态，不得在不同 Studio 分别使用勾号、包裹和星标表示同一种状态。

| 条目状态 | 右侧显示 | 颜色与行为 |
| --- | --- | --- |
| 需要下载或准备依赖（`Needs setup`） | 下载图标：下箭头＋底线（Lucide `download`） | 深灰 `#57534e`；不使用红色或橙红色，不显示收藏星标 |
| 可用（`Ready`），未收藏 | 五角星（Lucide `star`） | 浅灰 `#a8a29e`；点击收藏 |
| 可用（`Ready`），已收藏 | 五角星（Lucide `star`） | 深灰 `#44403c`；点击取消收藏，不使用金色或橙色 |
| 规划中、不可用或损坏（`Unavailable` / `Broken`） | 灰色短横线（Lucide `minus`） | 不显示收藏按钮；通过状态文字或可访问说明保留具体原因，不暗示下载即可修复 |

状态必须依据 Mini-App 的实际可用性与依赖就绪结果确定，不能只根据 Package 已安装或
条目存在就显示可用。依赖准备完成后，下载图标应更新为收藏星标。收藏偏好与可用性分开
保存：暂时不可用时隐藏星标，但不得因此清除既有收藏。

收藏按钮必须独立于卡片选择按钮，不能嵌套按钮。点击星标只切换收藏，不切换 Mini-App、
不启动任务、不触发下载；收藏状态必须持久化，刷新或重新打开后恢复。按钮必须提供
可访问名称、`aria-pressed` 和键盘操作，提示用户当前条目可用以及可切换收藏。
下载图标表示需要准备依赖；仅显示、选中或打开条目不得自动下载，继续遵循 ACPF 的显式
配置流程。状态说明须随界面语言本地化，不能仅靠颜色表达可用性。

#### 5.2.2 卡片可读性与尺寸

三个 Studio 的 Mini-App 列表末尾统一提供全宽“在 Coder 中创建 / Create in Coder”按钮，
使用 `code-2` 图标、白底灰边框，随列表内容滚动。按钮沿用 Imagine Studio 样式，替代
仅介绍 Coder 的说明文字；启动 Coder 时携带 `template=mini-app` 和当前 Studio 的
`placement`，让创建入口保留宿主上下文。

列表主图标使用 `18px`，标题 `12px`，用途说明 `10px`；版本等补充信息可使用 `9px`。
右侧下载图标和收藏星标使用 `15px`，收藏点击区域保持 `25 × 25px`。
放大图标或文字时不得增加卡片宽度、高度、内边距、网格列宽或列表间距；长标题和说明
保持单行省略，不能挤压右侧状态控件。当前基线的卡片最小高度分别为 Video `62px`、
Voice `58px`、Imagine `70px`，主图标容器分别为 `34px`、`32px`、`34px`。

### 5.3 Gallery Mini-Entry

Assets 视图必须复用 Gallery 的同一用户级 AppInstance 和标准 Mini-Entry，不得在每个 Studio
复制一套私有素材库。关闭或切走 Assets 视图不得停止 Gallery 服务或清除其集合、滚动和选择
状态。

Gallery 向 Mini-App 交付的是授权后的 Asset/Resource 引用，例如：

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

不得把 Gallery Blob 根路径、任意本地绝对路径或其他用户的 Asset ID 直接交给 Mini-App。

### 5.4 拖放

左栏到中栏的拖放必须经过 Studio Shell/Host Bridge：

1. Gallery 发出标准 Asset drag payload；
2. Studio Shell 判断当前 Mini-App 是否声明对应 drop target；
3. 平台检查用户、AppInstance、Mini-App、mount 和 Asset 权限；
4. 平台签发短期 Resource Handle；
5. Mini-App WebUI 收到规范化 `asset.drop` 事件；
6. Mini-App 决定插入角色、参考图、音频、镜头或其它具体位置。

Mini-App 不得信任浏览器 `dataTransfer` 中自报的路径或权限信息。

## 6. 中栏：Mini-App 专用 WebUI

中栏只保留一个 Mini-App 名称标题，基础高度 56px、标题 16px 半粗体、左右内容内边距
20px，白底细分隔线，随中栏滚动。版本、来源和用途默认收起到右侧信息入口；移除
`CURRENT MINI-APP`、`CREATE` 和同义的重复业务标题。可用徽标不常驻，配置入口放在
相关控件附近，未就绪条目详情内保留配置入口。项目选择、Run 和实际输入控件继续保留，
操作提示靠近相关控件，空状态说明只在空状态出现。Package UI 不得重复宿主标题。
完整开发约束见 [Mini-App 开发合同](ai2apps-studio-mini-app-package-contract-v1.md#mini-app-workspace-header)。

### 6.1 独立 UI Entry

Mini-App 必须提供独立 UI Entry。UI 应运行在平台管理的 App Mount、sandbox frame
或等价隔离环境中，并通过 Mini-App Bridge 与 Studio Shell 通信。

Mini-App UI 可以：

- 定义自己的表单、画布、时间线、分镜、角色卡、场景列表或直播控制台；
- 读取当前 Mini-App 的草稿或项目；
- 请求 Capability probe/ensure；
- 声明素材 drop target；
- 创建、取消或重试 Run；
- 把选中的 Run/Artifact 请求同步到右栏；
- 打开 Coder 或高级 Workflow 编辑入口。

Mini-App UI 不得：

- 直接安装、升级或删除 Package/Checkpoint；
- 绕过 ACPF、Capability Policy、GrantLease 或 Package Manager；
- 直接访问 Gallery 根存储、其它 App 私有状态或任意宿主路径；
- 绘制伪造的 AI2Apps 权限、安装、许可或系统确认界面；
- 吞掉右栏统一 Run/Artifact 状态，使任务只能在 Mini-App 私有 UI 中恢复。

Package 提供的 Mini-App 即使运行在独立 sandbox 中，也必须与宿主 Studio 使用同一层级语言：

- Studio Shell 的当前 Mini-App 标题栏必须固定在 UI Entry 上方，不得被 iframe 内容挤到底部；
- 默认桌面布局必须把宿主标题栏和 UI Entry 组成同一个中栏内部滚动面，整体页面不滚动；Mini-App 应通过受限的
  `ai2apps:mini-app-resize/v1` 消息报告内容高度，不得建立一个占据中栏的嵌套纵向滚动区；
- UI Entry 内不得重复绘制页面级营销 Hero、彩色渐变背景或另一套悬浮卡片式 Shell；
- 应使用宿主一致的中性背景、字号密度、分隔线区块、表单控件、按钮和状态色；
- capability ID、模型路由等技术信息默认收起，在诊断时可展开，不应压过用户任务；
- Package 可以保留完成任务所需的专用交互，但视觉差异必须来自任务本身，而不是另建一套设计系统。

隔离的 UI Entry 不直接继承宿主 DOM/CSS。Package 因此应集中维护一个共享的 Studio 视觉层，
由其全部 Mini-App Entry 复用；Studio Shell 负责标题栏顺序和 iframe 外围布局。视觉对齐不得放宽
sandbox、mount、CSP、Capability Broker 或签名安装边界。

### 6.2 声明式 UI

平台可以为简单 Mini-App 提供 schema renderer。声明式 UI 只是一种 UI Entry 实现，不是
Mini-App 契约的全部。Mini-App 升级为自定义 WebUI 时，应保留相同的 inputs、requirements、
Run 和 Artifact 契约。

### 6.3 ComfyUI

ComfyUI 可以用于：

- 表示和执行离线或批处理 Workflow；
- 作为高级用户的节点图编辑入口；
- 由 Mini-App Package 提供受版本控制的 Workflow、Custom Nodes 和模型需求；
- 将节点级进度映射为标准 Run Step。

ComfyUI 不应成为：

- 所有 Mini-App 必须使用的 UI；
- Mini-App Registry 或 Package Manager；
- ACPF 的替代品；
- 直播会话、低延迟交互或其它非 DAG 执行模型的强制抽象。

普通用户默认看到专用 WebUI。需要时 Mini-App 可以声明“在 ComfyUI 中编辑”入口，并明确
区分专用参数与底层 Workflow 的版本和兼容性。

## 7. 右栏：Render Workspace

右栏必须由 Studio Shell 统一实现，并能够适配图片、音频、视频、复合项目和实时会话。

### 7.1 标准区域

右栏至少包含：

1. **Preview**：当前输出或实时监看；
2. **Run 状态**：Mini-App、版本、当前 Studio placement、状态、总进度和开始时间；
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

一个 Mini-App Run 可以包含一个或多个 Step；Step 可以进一步关联一个或多个 Pipeline Run、Model
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
由 Mini-App 输出声明和用户偏好决定，但必须保留 Mini-App、Pipeline Run/Step 来源和模型 revision。

## 8. Mini-App 生命周期类型

首版协议至少区分三种生命周期：

### 8.1 `clip`

一次输入产生一个或少量媒体产物。适用于快速视频、单段朗读、单图生成和局部编辑。

### 8.2 `project`

拥有长期项目、素材、场景/章节/画板、多个 Run 和最终导出。适用于动画、有声书、多人剧、
漫画、广告和多页面视觉设计。

### 8.3 `live_session`

拥有开始、暂停、恢复、降级、切场、停止和录制生命周期。适用于直播、实时数字人、实时字幕
和交互式演播。`live_session` 不得被伪装成一个永不结束的普通生成 Task。

## 9. Mini-App Package 建议契约

下面是目标方向，具体字段必须在实现前形成版本化 JSON Schema 并进入 Package validator：

```yaml
schema: ai2apps.mini-app/v1
id: ai2apps.video.voice-replacement
name: Video Voice Replacement
version: 1.0.0
kind: project

entry:
  kind: sandbox
  resource: web/index.html

ui:
  minimum_width: 520
  drop_targets:
    - id: source_video
      accepts: [video]
    - id: target_voice
      accepts: [audio, voice-profile]

inputs:
  - id: source_video
    kind: video
    required: true
  - id: target_voice
    kind: voice-profile
    required: true

outputs:
  - id: replaced_video
    kind: video
    media_types: [video/mp4]
    final: true
  - id: replaced_audio
    kind: audio
    optional: true

placements:
  - studio: ai2apps.voice-studio
    category: video-voice
    order: 30
  - studio: ai2apps.video-studio
    category: audio-dialogue
    order: 40

executor:
  pipelines:
    - ai2apps.pipeline.video-demux
    - ai2apps.pipeline.voice-replacement
    - ai2apps.pipeline.video-remux

requirements:
  capabilities:
    - audio.speech_recognition
    - audio.voice_synthesis
    - video.audio_replacement
```

当前 Coder 已使用 `ai2apps.mini-app/v1` 作为 Mini-App 源组件身份。Studio Registry 的首个
兼容实现允许普通 App Package 在签名覆盖的 `app.yaml.mini_apps` 中声明 `id`、`version`、
受限 `entry` 和 `placements`，并通过统一 API 完成发现和可信 WebUI 挂载；具体合同见
`docs/ai2apps-studio-mini-app-package-contract-v1.md`。上例的 `inputs`、`outputs`、
`executor.pipelines` 和 `requirements` 当前作为声明元数据透传，跨 Package 的执行、Capability、
Asset 与 Run/Artifact Bridge 仍须由后续版本化合同实现，不能把透传字段理解为 Host 已执行。

Mini-App-Chat 是建议能力而不是 Mini-App 的成立条件；没有该能力的 Mini-App 仍可正常安装、
发现、挂载和运行。作者最好至少提供按需加载的 `help.md`，让共享 Chat-Mini-Entry 能回答用法、
输入和故障排查问题而不把帮助正文常驻注入 Context；Help-only 实现可使用空 Tool 列表，完整的
Chat-control 实现再增加当前状态与显式操作 Tool。Studio 只能依据 Mini-App 的显式能力声明显示
Chat 入口，不得从 Mini-App 类型本身推断支持。

Mini-App Package 的信任、签名、索引、安装、升级、禁用和回滚必须复用 AI2Apps Package
系统。一个 Mini-App 只有一个 canonical 安装身份；placement 不安装副本，也不维护独立版本。
Mini-App 不能以未受管脚本目录绕过 Package 权限边界。

只承载 Studio Mini-App、没有独立 App 产品界面的 provider Package 应声明
`navigation.launcher: false`，避免 Package 容器被 App Launcher 或 Dock 当成可启动 App；该标记
不影响 Studio placement。确实同时交付独立 App 与 Mini-App 的混合 Package 保持默认可见。

### 9.1 Placement 解析

Studio 中的 Mini-App 列表必须同时满足：

1. Package 为该 Studio 声明显式 placement；
2. Mini-App 的 input/output kind 与 Studio 的 Asset/Artifact adapter 兼容；
3. Package 已安装、可信且当前版本未被禁用；
4. 当前 actor/profile 拥有看到该 placement 的权限。

placement 可声明 Studio 专用的 category、order、简短说明和默认输出去向，但不得改变
Mini-App 的 canonical ID、版本、发布者、权限或核心输入输出语义。

### 9.2 多组件创作套件

一个 Package 可以交付多个 Mini-App 以及它们共享的 Pipeline、Service 和静态资源。例如视频
本地化套件可以具有以下组件图：

```text
Video Localization Package
├── Pipeline: 从视频提取音频
├── Pipeline: 将音轨写回视频
├── Mini-App: 为视频添加字幕
├── Mini-App: 替换视频角色配音
└── Mini-App: 生成其他语言的配音
```

目标 Package descriptor 示例：

```yaml
schema: ai2apps.package/v1
id: ai2apps/video-localization-suite
name: Video Localization Suite
version: 1.0.0

components:
  - type: pipeline
    manifest: pipelines/extract-audio.yaml
  - type: pipeline
    manifest: pipelines/remux-video.yaml
  - type: mini-app
    manifest: mini-apps/video-subtitles.yaml
  - type: mini-app
    manifest: mini-apps/voice-replacement.yaml
  - type: mini-app
    manifest: mini-apps/multilingual-dubbing.yaml
```

Discover 可把该 Package 展示为一个“创作套件”，但安装后各 Mini-App 必须根据自己的
placement 独立出现在相应 Studio 中。共享 Pipeline 和 Service 是无头 Component，不应出现为用户
可打开的 Mini-App。

### 9.3 Capability 提供与需求

Mini-App 应依赖稳定 Capability 语义，而不是直接导入 Provider 的实现代码。Pipeline 或 Service
使用 `provides` 声明能力：

```yaml
schema: ai2apps.pipeline/v1
id: ai2apps.video-localization.extract-audio
version: 1.0.0

provides:
  - capability: media.audio.extract
    version: 1
    visibility: package

inputs:
  - id: video
    kind: video

outputs:
  - id: audio
    kind: audio

executor:
  service: ai2apps.media.ffmpeg
  operation: extract_audio
```

Mini-App 使用 `requirements.capabilities` 声明需求：

```yaml
requirements:
  capabilities:
    - capability: media.audio.extract
      version: ">=1,<2"
    - capability: media.video.audio_mux
      version: ">=1,<2"
```

Capability 的输入输出 Schema、错误语义、取消、幂等、资源限额和版本兼容性必须是契约的
一部分。更换 Provider 不得改变已承诺的语义。

### 9.4 Capability 可见性

`provides[].visibility` 至少区分：

- `private`：仅 Provider 组件内部使用；
- `package`：仅同一 canonical Package 版本内的其他组件使用，建议作为默认值；
- `public`：允许其他可信 Package 声明依赖。

`public` Capability 必须拥有稳定命名、独立版本、发布者授权、弃用策略和跨 Package 调用
审计。包内实现细节应优先使用 `package`，不应在契约未稳定时过早暴露为 `public`。

### 9.5 Capability 解析与调用

Capability Resolver 应按以下边界解析 Provider：

1. 对 `package` 需求，只在调用方所属的同一 Package 版本中查找匹配 Provider；
2. 对 `public` 需求，可在已安装且可信的 Provider 中按 policy 解析；
3. 已安装 Provider 不满足时，才将缺失 Capability 交给 ACPF 选择和配置可信实现；
4. 解析结果必须绑定 Provider component ID、Package ID/版本和契约版本，不得仅返回可变 endpoint。

Mini-App 通过 Host-owned Capability Broker 的 `capability.invoke` 调用 Provider。它不得直接读取共享
Pipeline/Service 的安装目录、导入其私有 Python/JavaScript 模块、拼接 Service endpoint 或绕过 Host
Broker。大型媒体输入输出必须使用 Resource Handle 和 Artifact，不得在组件间传递任意本地路径。

每次调用必须记录调用方 Mini-App、当前 Studio/mount、Provider component、双方 Package 版本、
Capability 版本、输入 Resource Handle、输出 Artifact 和终态。

### 9.6 安装、禁用、升级与卸载

多组件 Package 必须使用原子生命周期：

- 安装前验证完整 Component Graph、Capability 版本、签名、资源索引和权限；
- 一次安装交付 Package 内所有组件，不为每个 Studio 或 Mini-App 复制共享 Provider；
- 可单独禁用 Mini-App 入口，但不因此删除仍被依赖的 Provider；
- 不允许单独卸载仍被已启用 Component 依赖的 Pipeline/Service；
- 升级先在新版本上验证整个依赖图，再原子切换 canonical Package 版本；
- 卸载 Package 后，历史 Run 和 Artifact 仍可读，重新执行则需再次满足依赖。

本节的 `pipeline` Component、`provides`、版本化 Capability requirement、visibility、Resolver 和
`capability.invoke` 均为目标协议。当前 Coder 仅支持 `app`、`mini-app`、`agent`、`service` 源组件；
在相应 schema、validator、Package installer 和 Host Broker 落地前，不得把上述示例当作现行 API。

## 10. Mini-App Bridge 与宿主上下文

Studio Shell 与 Mini-App UI 之间需要版本化 Bridge。建议最小事件/方法集：

```text
studio.context.get
mini-app.ready
mini-app.draft.changed
mini-app.requirements.probe
mini-app.requirements.ensure
mini-app.run.create
mini-app.run.cancel
mini-app.run.retry
mini-app.run.select
mini-app.artifact.select
capability.invoke
gallery.asset.drop
gallery.assets.pick
coder.open.mini-app
```

Bridge 必须携带可信的 AppInstance、Mini-App identity、Package 版本、mount identity 和当前
Studio identity。Mini-App 自报的 ID、来源、权限或 Package 状态不能成为授权依据。

`studio.context.get` 至少应返回：

```json
{
  "studioId": "ai2apps.video-studio",
  "mountId": "mount_example",
  "miniAppId": "ai2apps.video.voice-replacement",
  "inputAssets": [
    {"kind": "video", "assetId": "asset_example", "resourceHandle": "rh_example"}
  ],
  "preferredOutputDestination": "video-project"
}
```

同一 Mini-App 可以根据可信 Studio context 调整默认布局、素材导入和结果去向，但不应因此维护
两套核心业务 UI 或两个 Package。

事件 payload 必须使用有界、版本化结构；大文件通过 Resource Handle、Artifact URL 或
流式 Host Broker 传递，不得经 `postMessage` 复制完整二进制内容。

`capability.invoke` 必须进入 Host-owned Capability Broker；Mini-App Bridge 只传递有界请求和可信句柄，
不向 UI 暴露 Provider endpoint、安装路径或内部凭据。

## 11. ACPF 集成规范

Mini-App 对其专用体验负责，平台对能力解析和安装负责。标准流程为：

```text
选择 Mini-App
  -> Studio Shell 读取可信 Mini-App requirements
  -> Capability Resolver 优先解析同 Package 已安装 Provider
  -> 静默 probe，仅更新 Ready/Needs setup 状态
  -> 用户在 Mini-App UI 发起需要能力的明确操作
  -> Mini-App 保存私有草稿，向 ACPF 只传 opaque resume token
  -> ACPF 展示兼容方案、下载量、磁盘、许可和重启影响
  -> 用户确认后由 Package Manager/Checkpoint Installer 执行
  -> Provider health 验证
  -> 返回同一 Mini-App UI 和 Studio placement
  -> Mini-App 恢复草稿并 acknowledge
  -> configure_only 默认等待用户再次确认 Run
```

强制要求：

- Mini-App Package 只能声明经过信任校验的 capability/profile；
- Mini-App UI 不得把任意 Package ID 列表直接当作安装命令；
- requirements 必须先由 Capability Resolver 解析已安装的同 Package/公开 Provider；未满足部分
  再由 ACPF Registry 解析为可信 Runtime、Service Package 和 Checkpoint 组合；
- Package 自带且已就绪的 Provider 不应触发额外安装引导；
- 同一 Mini-App 的不同操作可以使用不同 capability，例如预览、最终渲染和直播；
- 选中 Mini-App 不等于授权下载；
- 配置成功不等于自动发起生成；
- 草稿正文、媒体和声音样本不得进入 ACPF Session 或共享 Client pending storage；
- Mini-App 更新导致 requirements 变化时必须重新 probe，不得沿用失效的 ready 结论。

## 12. 非内置 Mini-App 扩展流程

非内置 Mini-App 的标准第一阶段是 In-Package 本地源码开发：在
`packages/<package>/` 中维护普通 `ai2apps.json`、`app.yaml.mini_apps`、独立 WebUI、共享资源和
测试，由 `AI2Apps-App-Dev` 或通用 Dev App 直接发现并挂载。它必须走真实 Studio Registry、
AppInstance、mount、sandbox 和 Capability Broker；独立打开 HTML 或制作只在 Coder Preview
中工作的页面，不能替代这项验收。

标准顺序为：

1. 建立 App Package 源码树并通过 manifest/resource 校验；
2. 在所有声明的 Studio placement 中完成 source-mounted discovery 和真实 mount；
3. 刷新验证 UI 资源热修改，重新读取目录验证 `app.yaml` 热加载；
4. 验证源码态没有正式安装记录，生产标记缺失时不加载；
5. 完成 Asset drop、ACPF probe、草稿恢复、Run/Artifact 和 Capability Broker 测试；
6. 通过标准 builder 生成并验证签名 Package；
7. 在干净开发实例安装签名候选，重复安装态发现/mount/能力与生命周期回归；
8. 按 Package Publication Runbook 正式发布。

源码挂载是正式路径的开发覆盖层，不是可信安装身份。详细目录、刷新规则、安全边界和门禁以
[Studio Mini-App Package Contract v1](ai2apps-studio-mini-app-package-contract-v1.md#standard-local-development-workflow-for-non-built-in-mini-apps)
为准。

### 12.1 Coder 辅助流程

Studio 左栏和 Mini-App 详情应提供“在 Coder 中创建/编辑 Mini-App”入口。Coder 应提供
按输入输出和生命周期区分的模板，而不是把 Mini-App 绑死到单一 Studio domain。例如：

- 媒体转换 Mini-App；
- 项目型 Mini-App；
- ComfyUI-backed Mini-App；
- Live Session Mini-App；
- 跨 Studio Mini-App。

Coder 接入后应承载模板、编辑和自动验证，但不得另建一套与本地 Package 源码挂载不兼容的
Preview 身份。建议流程：

1. Coder 创建或打开位于标准 Package 源码树中的多个 Mini-App manifest、UI、placement、共享 Pipeline/Service 和测试；
2. Validate 校验 manifest、Component Graph、Capability 版本、资源索引、CSP、Bridge、requirements 和 output contract；
3. Run 可以提供隔离 WebUI Preview，但“在 Studio 中预览”必须转入 Development source mount；
4. TestFlight identity 仅用于提交后的私有安装态验收，不作为日常源码热修改路径；
5. 测试 Asset drop、ACPF probe、草稿恢复、Run 进度和 Artifact 输出；
6. Build 生成 development Project Bundle；
7. Submit to TestFlight 后仅当前开发环境可见；
8. 正式发布仍遵守签名 Package 发布流程。

私人 Mini-App 也必须经过 validator、隔离执行和权限检查。Coder 的可编辑源码身份不得在
运行时冒充已签名正式 Mini-App。

## 13. 各 Studio 的映射

### 13.1 Video Studio

推荐 Mini-App：

- 文生视频：提示词与分镜批量生成；
- 图生视频：首帧或首尾关键帧驱动生成；
- 参考素材视频：图片、视频与声音参考驱动生成；
- 动画制作：角色、风格、分镜、连续性、配音和合成；
- 直播制作：主播、场景、实时脚本、字幕、切场、推流和录制；
- 数字人口播；
- 商品广告、MV、短剧、视频扩展和修复。

右栏主要 Preview 类型为 video/live，Run 可以包含脚本、图像、语音、视频和合成 Step。

### 13.2 Voice Studio

推荐 Mini-App：

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
五个内置 Mini-App；播客制作和实时伴读只展示为规划项。前三者请求
`audio.speech_generation`；音色设计和训练角色请求 `audio.voice_clone`；训练角色仅在用户
主动转写时额外请求 `audio.speech_recognition`，手工输入逐字稿时不要求安装 ASR。所有能力
均通过 ACPF `configure_only` 配置。训练录音先作为当前用户的私有 Gallery Asset 持久化，
Voice Profile 只保存其 `referenceAssetId`、逐字稿和权利确认；配置完成后不自动训练或合成。
Studio 页面文案使用 App Shell 的 `en`/`zh` locale，同一次 Shell 语言切换会随顶层重载同步。

### 13.3 Image/Drawing Studio

推荐 Mini-App：

- 快速绘图；
- 商品海报；
- 角色设定表；
- 局部重绘与扩图；
- 风格迁移；
- 批量变体；
- 漫画/分镜项目。

中栏可以是提示词表单、画布、蒙版、图层、参考板或版式编辑器。右栏统一展示当前图像、
版本比较、放大结果、中间 Artifact 和导出历史。

### 13.4 跨 Studio 示例

| Mini-App | 主要输入 | 主要输出 | 建议 placement |
| --- | --- | --- | --- |
| 视频语音替换 | 视频、音色/声音参考 | 新视频、可选音轨 | Voice Studio、Video Studio |
| 视频拆帧 | 视频 | 图片序列 | Imagine Studio、Video Studio |
| 图片生成视频 | 图片、提示词 | 视频 | Imagine Studio、Video Studio |
| 音频驱动头像 | 图片、音频 | 视频 | Voice Studio、Imagine Studio、Video Studio |

同一 Mini-App 在不同 Studio 中可有不同分类、入口文案和默认结果去向，但必须保留同一
canonical ID、Package 版本、权限身份和核心状态模型。

## 14. 状态与恢复

Studio Shell 必须分别保存：

- 当前用户和 AppInstance 的左栏模式、宽度和折叠状态；
- 当前 Mini-App ID、版本、Studio placement 和最近使用顺序；
- 当前 Mini-App mount identity 和宿主上下文；
- 当前 Project/Draft/Live Session；
- 当前选中的 Run、Step 和 Artifact；
- Gallery Mini-Entry 的独立持久状态引用。

职责边界：

- 布局偏好可以是设备本地状态；
- Mini-App 草稿和项目必须由 Mini-App/平台后端持久化；
- Run、Step、Task 和 Artifact 必须由平台后端持久化；
- ACPF pending storage 只保存 Session ID、App ID 和 opaque resume token；
- 敏感素材、声音样本和 Prompt 不得为了跨 App 恢复而写入共享 Shell storage。

## 15. 安全、权限与信任

1. Mini-App UI、Executor/Pipeline 引用、Package 和输出都必须绑定 canonical 安装身份和版本；
2. Studio Shell 不信任 iframe、drag payload 或页面自报的 App/Mini-App/Studio ID；
3. Mini-App 的 Gallery 访问必须按 Asset/Resource Handle 授权；
4. ACPF 配置不能隐式授予模型调用、文件、网络、麦克风、摄像头或推流权限；
5. Live Session Mini-App 的摄像头、麦克风、屏幕捕获和外部推流必须逐项声明并获得用户授权；
6. 第三方 Mini-App 不得伪装平台安装、许可、账户或安全 UI；
7. Output Artifact 必须记录来源 Mini-App、placement、Pipeline/Executor、模型 revision 和 Run；
8. 禁用或卸载 Mini-App 后，历史 Run 和 Artifact 仍应可读；重新执行需要重新满足依赖和权限；
9. Mini-App iframe/CSP、Package 资源索引和 TestFlight 隔离遵循 App/Coder 现有规范；
10. 同一 Mini-App 在多个 Studio 中挂载不会自动扩大权限；每次 mount 只能获得当前宿主明确交付的上下文和 Resource Handle。

## 16. 可访问性与交互一致性

**`aria-label` / 可访问名称是 UI 自动化测试的基础合同，属于开发必验项。**
所有 Studio Shell、内置 Mini-App、Package Mini-App 和共享动态 UI 生成器必须遵守
[App 控件命名与自动化测试规范](ai2apps-app-development-guide.md#控件命名与自动化测试规范必选)。
纯图标/符号按钮和无可见标签输入框必须提供明确、本地化的 `aria-label` 或有效
`aria-labelledby`；已有可见按钮文字或关联 `<label>` 时无需机械重复标注。
不得仅靠 `title`、`placeholder` 或 `data-testid`。动态操作名称与展开/选中/运行状态必须同步。
验收应在真实 mount 的 iframe 内按 role + accessible name 检查，覆盖动态生成、重挂载和
中文/英文状态；同时验证键盘可用性。源码属性计数不能替代渲染后的名称验收。

- 三列均必须支持键盘导航和可见焦点；
- Mini-Apps/Assets 切换、折叠状态和 Run 状态必须具有可访问名称；
- 拖放必须提供“选择并插入”的键盘等价操作；
- 不得只靠颜色表示 Ready、Running、Failed 或选中状态；
- Preview 播放器使用宿主支持的标准媒体控制，并提供字幕/文本等价物；
- 长时间 Run 必须持续显示阶段、进度或可解释的等待状态；
- Mini-App 切换、配置完成和任务失败必须有明确反馈，但不得使用阻塞式重复弹窗；
- Studio Shell 统一提供错误、空状态、离线、未配置和恢复中的基础视觉语言。

## 17. 实施顺序

### Phase 1：Studio Shell 基线

- 实现三列布局、折叠和响应式降级；
- 左栏 Mini-Apps/Assets 双视图；
- 挂载 Gallery Mini-Entry；
- 右栏标准 Run/Artifact Workspace；
- 将现有 Video Studio 三种模式迁移为三个独立的内置 Mini-App。

验收：迁移后现有文生、图生、参考素材、队列、下载、合并和 ACPF 功能不回退；窗口缩放和
App 切换不丢失状态。

Video Studio 首轮落地状态（更新于 2026-09-04）：

- 已建立三列 Studio Shell，文生视频、图生视频和参考素材视频作为三个内置 Mini-App 入口；
  Phase 1.1 中三个入口仍共享第一方 WebUI，但各自保存独立的切换草稿；独立 UI Entry、mount
  identity 和版本生命周期仍属于 Phase 2；
- 左栏已统一使用 Mini-App 术语，支持 Mini-Apps/Assets 逻辑并挂载 Gallery Mini-Entry；
- 左右栏支持显式折叠；窄窗口中以抽屉呈现，避免继续压缩中栏创作区域；Shell 的当前
  Mini-App、左栏视图、折叠状态和所选 Run 作为展示偏好恢复；
- Gallery 图片、视频和音频可通过标准 drag payload 路由到对应 Mini-App 和素材槽位；
- 右栏保留现有预览、任务队列、下载和片段合并行为，并增加当前 Run 摘要、单步状态、
  Run 历史与服务端冻结输入 Retry；
- 现有 `video.generation`、`video.reference_generation`、草稿恢复和 ACPF configure-only
  流程保持不变；
- Mini-App Registry、已安装 Package placements 与可信 WebUI mount 基础已经落地；第三方
  Run/Artifact/Capability Bridge、Coder 模板以及直播/动画专用执行器仍属于后续 Phase，
  不在本轮用临时私有协议提前固化。

### Phase 2：Mini-App Registry、Placements 与 Bridge

- 扩展并验证 `ai2apps.mini-app/v1` Studio 契约；
- 建立可信 Registry、placement 解析、Mini-App Mount 和版本身份；
- 扩展 Project/Package Component Graph 以支持无 UI `pipeline` Component；
- 实现 `provides`/`requirements`、Capability visibility、Resolver 和 Host Broker；
- 实现多组件 Package 的原子验证、安装、升级与卸载；
- 实现 Asset drop、Run、Artifact、ACPF 和 Coder Bridge；
- 建立 Mini-App 草稿与 Run/Step 数据模型。

验收：两个结构明显不同的 Mini-App 可以共享左右栏，同时提供不同中栏 WebUI；
同一 Mini-App 只安装一次即可在两个 Studio 中运行；同一 Package 的三个 Mini-App 可通过
Capability Broker 共享一个“视频提取音频”Pipeline，且没有 Mini-App 之间的 UI 调用。

### Phase 3：跨 Studio 验证

- Video Studio：文生/图生/参考素材内置 Mini-App + 动画项目；
- Voice Studio：快速朗读 + 多角色有声书；
- Image Studio：快速绘图 + 局部重绘/画布；
- 校验 image/audio/video/project Preview adapter。

验收：三个 Studio 不复制 Mini-App Registry、Gallery、Run、Artifact 和 ACPF UI 逻辑；
视频语音替换可同时从 Voice/Video Studio 打开，视频拆帧可同时从 Imagine/Video Studio 打开。

### Phase 4：Coder 与第三方扩展

- Mini-App Project 模板；
- Validate、Preview、TestFlight 和 Studio deep-link；
- 私人 Mini-App 安装与版本更新；
- ComfyUI workflow validator 和高级编辑入口。

验收：用户可以在 Coder 中创建最小 Mini-App，在所有已声明 Studio placement 中预览，通过 ACPF 配置已声明
能力，生成标准 Artifact，并在 Gallery 中复用。

### Phase 5：Live Session

- 标准 Live Session 状态和控制协议；
- 直播监看、延迟、降级、录制和推流状态；
- 摄像头、麦克风、屏幕和外部目标授权；
- 中断恢复和安全停止。

验收：Live Session Mini-App 不依赖伪造的长任务，可以在右栏准确恢复和结束会话。

## 18. 开发验收清单

- [ ] Mini-App 列表右侧遵循第 5.2.1 节：深灰下载图标、浅灰/深灰收藏星标、不可用标记；
- [ ] 收藏点击不切换 Mini-App 或触发下载，刷新后恢复，依赖状态变化不丢失收藏；
- [ ] 图标与字体满足第 5.2.2 节，卡片尺寸保持基线，长文字不挤压状态控件。

新增或升级 Studio/Mini-App 时至少检查：

- [ ] 新增/修改控件已按第 16 节验证可访问名称、状态与键盘操作，图标按钮和无标签字段无漏标；
- [ ] 真实 Mini-App mount 内的自动化定位支持 role + accessible name / label，覆盖动态 UI 和中英文；
- [ ] 顶层按创作目标选择 Mini-App，而不是继续增加输入模式 Tab；
- [ ] 左栏可在 Mini-Apps 与 Gallery Mini-Entry 间切换；
- [ ] 中栏是隔离、独立且可恢复的 Mini-App WebUI；
- [ ] Mini-App 至少有一个显式 Studio placement，且 input/output 契约兼容；
- [ ] 非内置 Mini-App 已从标准 App Package 源码树被 Development Bundle 发现并真实挂载；
- [ ] HTML/CSS/JavaScript 与 `app.yaml` 热修改分别完成刷新/重新挂载验证；
- [ ] 源码挂载未创建正式 Package Store 安装记录，非 Development Runtime 不发现该源码；
- [ ] 跨 Studio Mini-App 只安装一次，不复制 Package、版本、权限或业务实现；
- [ ] 多 Mini-App Package 具有可验证的 Component Graph 和原子安装/升级语义；
- [ ] 共享业务能力使用版本化 `provides`/`requirements`，不通过 Mini-App 互调或私有代码导入；
- [ ] `private`/`package`/`public` 可见性和跨 Package 信任边界通过校验；
- [ ] Capability 调用经 Host Broker，并记录调用方、Provider、Package 版本、Studio/mount 和 Artifact；
- [ ] 右栏复用标准 Run/Step/Artifact Workspace；
- [ ] Mini-App 打开时只 probe，不自动下载大型依赖；
- [ ] 缺失能力通过 ACPF ensure，Mini-App 不自行安装；
- [ ] ACPF 默认 configure-only，配置完成后不自动生成；
- [ ] 草稿通过 opaque token 恢复，不进入共享 pending storage；
- [ ] Gallery 交付 Asset/Resource Handle，不暴露根路径；
- [ ] 拖放存在权限校验和键盘等价操作；
- [ ] Run/Step/Artifact 可在刷新、App 切换和 Desktop 重启后恢复；
- [ ] 下载使用 Artifact 原生 URL，不在前端缓存大型 Blob；
- [ ] Mini-App 可声明 ComfyUI executor，但专用 WebUI 不被 ComfyUI 强制替代；
- [ ] Coder Preview/TestFlight 与正式签名身份隔离；
- [ ] 已构建签名候选并在干净实例重复安装态发现、mount 和能力回归；
- [ ] Desktop、普通浏览器、窄窗口和至少一个移动布局完成验证；
- [ ] 权限、许可、安装、失败、降级和不可用状态有明确且不可伪造的 UI。

## 19. 非目标

本规范不试图：

- 定义所有媒体模型的底层推理协议；
- 用一个通用节点系统替代所有专用 Mini-App UI；
- 让 Studio Shell 直接执行第三方代码；
- 让 ACPF 替代权限、Discover、Package Manager、Model Worker 或默认模型路由；
- 要求所有 Studio 在视觉细节上完全相同。

一致性要求针对信息架构、职责边界、状态与安全契约。每个 Studio 和 Mini-App 可以在这些
边界内形成适合其媒体和创作任务的独特体验。
