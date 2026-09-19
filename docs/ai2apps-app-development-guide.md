# AI2Apps App 开发指南

本文档定义 AI2Apps App 的通用开发约定。新 App 和现有 System App 都应遵循这些约定，避免把 Desktop、普通浏览器和移动端的宿主差异重复实现到每个 App 中。

架构对象、Entry/Mini-Entry、AppInstance 和安全边界的完整定义见 [AI2Apps Platform Architecture](ai2apps-platform-architecture.md#10-app-architecture)。能力首次配置、按设备推荐 Runtime/Package/Checkpoint 的流程见 [AI2Apps Capability Provisioning Framework（ACPF）](ai2apps-capability-provisioning-framework-v1.md)。

Video Studio、Voice Studio、Imagine/Image Studio 以及其它以 Mini-App、素材、
生成任务和媒体产物为核心的 Studio 类 App，必须同时遵循
[AI2Apps Studio App 与 Mini-App 设计规范 v1](ai2apps-studio-app-ui-design-standard-v1.md)。该规范定义
统一三列布局、自带 UI 且可跨 Studio 挂载的 Mini-App、Gallery Mini-Entry、Render Workspace、
ACPF 和 Coder 扩展边界。Pipeline 仅指 Mini-App 或 Agent Tool 可复用的无 UI 执行层。
一个 Package 可以包含多个 Mini-App 以及共享 Pipeline/Service；Mini-App 应通过版本化 Capability
契约和 Host Broker 共享能力，不得互相调用 UI 或导入对方私有实现。

非内置 Mini-App 的标准开发入口是
[Studio Mini-App Package Contract v1：Standard local development workflow](ai2apps-studio-mini-app-package-contract-v1.md#standard-local-development-workflow-for-non-built-in-mini-apps)。
开发阶段必须把 Mini-App 放入普通 App Package 源码树，通过 Development Bundle 直接挂载到
真实 Studio；不得把“反复构建并安装 `.ai2app`”当作日常 UI 调试循环，也不得用脱离
AppInstance、mount、sandbox 和 Host Broker 的独立网页冒充 Studio 集成测试。固定环境、刷新与
重建边界见 [AI2Apps App-Shell App 开发环境](ai2apps-app-dev-environment.md)。

**控件可访问名称是开发验收要求，也是未来 UI 自动化测试的基础。** Shell、App、Mini-Entry 和
Mini-App（含 Package 动态生成 UI）必须遵循本文的[控件命名与自动化测试规范](#控件命名与自动化测试规范必选)，
不能仅凭页面视觉正常或存在 `data-testid` 判定通过。

## 1. 宿主环境

同一个 App Entry 可以运行在以下宿主中：

- `desktop`：AI2Apps Desktop，由 AceFox 承载；
- `browser`：Chrome、Safari、Firefox 等普通浏览器；
- `mobile`：AI2Apps 移动端入口或移动 Web 宿主。

宿主类型必须由 AI2Apps Shell/服务端提供，App 不得依赖 User-Agent、窗口尺寸或浏览器私有特征进行猜测。当前同源 System App 会在 Entry 根节点收到 `data-client-environment`；sandbox/schema App 后续应从 App View Bridge 接收同一语义的只读环境字段。

宿主字段只用于表现层适配，不是授权依据。文件、设备、模型和系统操作仍必须经过相应的 Session、Capability 和 Host Broker 检查。

### App Launcher 可用状态

尚未达到用户可用标准、但需要保留产品预告位置的 App，应在 manifest 中声明：

```yaml
navigation:
  status: development
```

此状态下 App 仍显示在 Desktop App Launcher 中，但卡片置灰并显示“正在开发”，不能启动、
Pin 到 Dock、进入移动端可启动目录或出现在 App 建议中；Host 和 Runtime 也必须拒绝绕过 UI
的直接启动。功能完成并通过发布验收后删除该字段，或显式改为 `active`。完全不应出现在
Launcher 中的纯 Mini-App Provider 应使用 `navigation.launcher: false`，两者语义不可混用。

## 2. 模型调用与 Worker 透明边界

App 只面向平台模型调用契约，不面向 Model Worker。Chat、绘图、音频、Video、Voice Studio、
Knowledge/RAG 以及后续 App 都必须通过 Host-owned Model Invocation Service 发起模型操作。
Worker 的调度和生命周期变化不得要求 App 改造。

App 可以：

- 按模型 ID 或 Capability 选择模型；
- 读取公开的模型能力描述，例如输入类型、分辨率、音色和上下文限制；
- 提交请求和业务幂等键；
- 订阅平台提供的任务状态、进度和取消结果；
- 管理自己的 Project、Session、Artifact 和可恢复业务任务。

App、Agent 和业务 Service 不得：

- 导入或调用 `WorkerJobScheduler`、`WorkerResourceManager`、`WorkloadClass`；
- 创建或持有 QueueTicket、RequestLease、MemoryReservation；
- 估算 Worker resident/transient memory，或决定驱逐、Pin、Drain、Idle Exit；
- 启动、重启、停止 Worker，或读取/拼接 Worker Endpoint；
- 获取 Worker 内部认证 Header、直接从浏览器访问 Worker；
- 根据 Worker 当前 cold/warm/running 状态实现业务分支；
- 在 App 内复制模型下载、ACPF、P2P 路由或资源调度逻辑。

交互、前台、后台只是平台调用意图，不是 App 可操纵的调度优先级。Host 负责把意图映射为
权威 Workload Class，并统一完成排队、资源准入、惰性启动、路由、进度、取消和 Lease 清理。
长任务应先建立 App 自己的 durable task，再把单个有界模型工作单元提交给平台调用服务。

ACPF 只负责 Capability、Package、Checkpoint 和 Service 生命周期配置。Ready、健康和协议验证
不应伪装成推理任务；若确实需要 Smoke Inference，也必须通过统一模型调用服务执行。

代码审查与 Release Gate：业务目录中出现 `worker_scheduler`、`scheduler.acquire`、
`WorkloadClass`、`ensure_package_model_ready`、Worker Endpoint 或 Supervisor 生命周期调用，应默认
视为架构违规；只有平台调用层、Worker 管理 API/Dashboard、资源管理器、Supervisor 和 Worker
协议适配代码可以持有这些依赖。

### 模型选择器与安装入口（必选）

所有 App、Mini-Entry 和 Mini-App 的模型选择器（包括对话、语音识别、语音合成及其它
专用能力）必须采用同一机制：

- 普通选项只列出当前能力真正可用的模型；Package 已注册不等于 Checkpoint 已安装。
  不因模型尚未驻留内存而排除可由平台惰性启动的模型。
- 在**下拉菜单内部的最后一项**提供本地化的“安装更多模型”；不得以菜单下方的文字
  按钮替代。自定义模型菜单也应在末尾提供同等动作。没有可用模型时仍保留安装入口。
- 该项是操作，不是模型 ID。选中后立即恢复原模型显示，再启动共享 ACPF；不得写入
  会话、偏好、默认模型或推理请求，取消/失败不得改变原选择。
- ACPF 展示该能力下全部受信任安装配置，不只展示推荐项；已安装项标注“已安装”并
  置灰、禁选，不兼容项显示原因。全部已安装时仍可查看，安装继续按钮禁用。
- 即使已有可用模型，“安装更多模型”也必须打开选择界面，不能被普通 ensure 的
  already-ready 快速返回跳过。复用 ACPF 确认、许可证、下载、恢复和完成回调，不另建下载流程。
- 安装完成后刷新可用目录，保留仍有效的用户选择；异步刷新一次发布完整目录，并在选项
  渲染完成后同步选中值，避免误显首项。加载期间的新手动选择不得被旧请求覆盖。
- 验收覆盖菜单末项位置、无模型、有已安装模型、全部已安装、取消/失败、安装完成、
  切出切回刷新，以及操作值不进入持久化或推理请求；区分单元测试与 App-Dev 实机验收。

### 模型思考策略（必选）

App 和 Mini-Entry 必须使用模型目录公开的签名 `reasoning` 契约，不得按模型名称、Provider、
family 或输出中是否偶然出现 `<think>` 推断。`required` 模型必须显示为强制思考并禁用 Off；
`optional` 模型才允许 Auto/On/Off；`none` 模型不提供 Thinking 控件。所有界面发送的是用户
意图，最终约束由 Model Package 与 Runtime 强制执行；前端标签解析只能兼容旧响应，不能代替
协议级 `reasoning_content`/`content` 分流。完整 Package 规则见
[Model Worker Package 开发手册](model-worker-package-manual.md#对话模型的-reasoning-契约必选)。

## 3. Artifact 下载 UE

下载是跨宿主差异最明显的基础动作，统一遵循下面的行为：

| 宿主 | 点击后的用户体验 | 所有者 |
| --- | --- | --- |
| AI2Apps Desktop | 立即打开系统原生“另存为”对话框，由用户选择文件名和位置 | Desktop Shell / AceFox |
| 普通浏览器 | 使用浏览器标准下载流程，并提示“下载已开始，请在浏览器下载列表中查看” | 浏览器 |
| 移动端 | 使用宿主支持的浏览器下载/分享流程，并给出开始提示 | Mobile Shell / 浏览器 |

App 必须使用平台返回的 Artifact `download_url`，保留原生链接导航和 `download` 语义：

```html
<a :href="artifact.download_url"
   download
   @click="downloadArtifact($event, artifact.download_url)">
  下载
</a>
```

处理函数只负责校验和反馈，不应把大型 Artifact 先 `fetch()` 到 JavaScript 内存再构造 Blob：

```javascript
downloadArtifact(event, url) {
    if (!url) {
        event.preventDefault();
        this.showError('下载地址不可用，请刷新后重试。');
        return;
    }
    if (this.clientEnvironment !== 'desktop') {
        this.showSuccess('下载已开始，请在浏览器下载列表中查看。');
    }
}
```

平台下载响应负责：

- 返回正确的 `Content-Type`；
- 通过 `Content-Disposition` 提供安全、可读的默认文件名；
- 对不存在、无权限或已过期的 Artifact 返回明确的 HTTP 错误；
- 支持大文件流式传输，避免 App WebUI 占用一份完整文件内存。

Desktop 的“另存为”策略属于 Shell，不应由 App 调用 macOS 私有 API，也不应让每个 App 各自维护下载目录偏好。普通浏览器则必须保留其自身的下载设置：用户若配置为自动保存，App 不应强制弹窗；若配置为每次询问，浏览器会显示自己的保存对话框。

## 4. 非内置 Mini-App 的标准开发阶段

非内置 Mini-App 必须依次经过：Package 源码合同校验、Development source mount、真实 Studio
发现与挂载、热修改验证、签名制品构建、干净实例安装态回归和正式发布。源码态允许快速迭代，
但不代表已签名、已安装或可发布；安装态回归也不得改回另一套 manifest 或 UI 实现。

开发 Package 的 canonical App ID、Mini-App ID、placement、Entry 和 capability requirements
必须从源码态一直保持到正式制品。HTML/CSS/JavaScript 修改刷新或重新打开 Mini-App 即可；
`app.yaml` 修改重新读取 Studio 目录，Entry 改变后重新挂载；Host Python 修改重启 Local；
Runtime、依赖层、Swift 或 AceFox 修改才重建 Development App。

Development source mount 会对 sandbox Entry 启用仅限当前 Local origin 的开发策略：允许
same-origin 子资源和 mount-scoped Host Capability Broker 请求，以便 CSS/JavaScript 热修改和
真实工作流调试。该例外必须同时满足“Entry 来自 `development` definition”和显式
`AI2APPS_ALLOW_DEVELOPMENT_RUNTIME=1`，已安装 Package 与生产 Bundle 不会继承。发布验收必须
重新在严格 opaque-origin sandbox 下完成，不得把开发策略当成正式 Package 的运行依赖。

Studio 中的依赖状态必须使用共享 Mini-App mount Capability Probe，不能用“已发现”“已挂载”或
“页面加载成功”代替。`Setup required` 必须是按钮：点击后由共享 Studio Mini-App Client 使用
当前 Studio AppInstance 启动 ACPF。Mini-App 只声明语义 Capability；具体 Runtime、Package、
Checkpoint、版本和验证目标来自 Host 内置的受信任 ACPF Profile。新增非内置 Mini-App 时，必须
同时验证 Readiness Probe、Setup 按钮、ACPF Profile 选择界面和配置完成后的重新 Probe；多个
Studio 共用同一工作流时，应复用 multi-App Profile，而不是复制前端安装逻辑。
重启恢复也是强制验收项：Runtime 安装触发 Local 重启后，Studio 必须先恢复共享
`setup-mini-app` ACPF Session、回到发起配置的 Package Mini-App，再继续 Provider/Checkpoint
安装并重新 Probe；只回到 Studio 默认入口不算完成。

## 5. 实现检查表

开发或升级包含 Artifact 下载的 App 时，至少检查：

- 无下载地址时按钮不可用，或点击后显示明确错误；
- Desktop 点击后出现原生“另存为”对话框；
- 普通浏览器点击后开始标准下载并出现页面内反馈；
- 文件名、扩展名和 MIME 类型正确；
- 大文件不经过前端 Blob 缓冲；
- App 没有通过 User-Agent 猜测宿主；
- 下载行为不绕过 Artifact 权限和审计边界。

自动化测试应覆盖模板保留原生下载链接、环境字段由可信宿主注入、Desktop 下载偏好启用 Save As，以及普通浏览器反馈文案。发布前还应分别在 AI2Apps Desktop 和至少一个普通浏览器执行一次人工 smoke test。

## 6. Video Studio 参考实现

Video Studio 是当前参考实现：服务端验证 Desktop Shell 的 HttpOnly 会话后注入宿主环境；WebUI 始终使用 Artifact 原生下载链接；Desktop 由 AceFox 打开 macOS“另存为”，普通浏览器显示下载开始提示并交给浏览器下载管理器。

相关实现：

- `ai2apps/api/client.py`：可信 Desktop Shell 环境识别；
- `omlx/admin/routes.py`：System App Entry 环境注入；
- `ai2apps/web/templates/system_apps/video_studio.html`：原生 Artifact 下载链接；
- `ai2apps/web/static/js/video_studio.js`：跨宿主反馈。

## 控件命名与自动化测试规范（必选）

每个面向用户的交互控件必须暴露正确的语义角色和非空、明确的可访问名称。
这是 Shell、System App、App Entry、Mini-Entry、内置及 Package Mini-App 的共同开发合同；
新增和修改控件必须在本次开发中验收，不能留到编写自动化测试时再补。

### 名称来源与 aria-label

- 优先使用原生 `button`、`a`、`input`、`select`、`textarea`。文本按钮可以直接使用可见文字
  作为名称；表单优先使用 `<label for="唯一ID">` 或包裹控件的 `<label>`。
- 已有可见标题时可以用 `aria-labelledby` 引用它；引用目标必须存在，ID 在当前文档中唯一。
- **纯图标、符号、无文字按钮，以及没有可见标签的输入框必须提供有意义的 `aria-label`
  或有效的 `aria-labelledby`。** 名称描述操作目的，例如“关闭通知”“移除第 2 张参考图”，
  不得用 `x`、`plus`、图标名、CSS 类名或内部 ID 充当名称。
- 不必给已有正确可见名称的每个控件重复添加 `aria-label`；它会覆盖原来的名称。
  若确需添加，名称必须包含可见标签文字，避免用户看到的文字与测试使用的名称不一致。
- `placeholder` 是填写提示，`title` 是补充提示，都不能作为本项目唯一的标注方案。
  部分浏览器会将其作为回退名称，但不视为通过本项目验收。`name`、`id`、`data-testid`
  和 `data-action` 也不等于可访问名称。
- 标签必须随 UI 语言本地化，不能显示翻译 key。重复行中的操作需通过带名称的行/区域限定，
  或在名称中加入对象上下文；不要把变化的进度、时间戳、随机 ID 当作操作名称。
- 装饰性 SVG/图标使用 `aria-hidden="true"`，装饰图片使用 `alt=""`；不要把交互控件本身隐藏。

```html
<label for="project-title">项目名称</label>
<input id="project-title" name="title" autocomplete="off">
<button type="button" aria-label="关闭通知">
  <svg aria-hidden="true" focusable="false"><!-- close icon --></svg>
</button>
<button type="submit">保存项目</button>
```

以上为中文示例；真实模板使用项目的 `t(...)` / `tr(...)` 本地化机制。

### 动态 UI、状态与隔离挂载

- Alpine `x-for`/`x-if`、`innerHTML` 和 `createElement` 生成的控件遵循同样规则，必须检查
  渲染后的 DOM 与可访问树，不能只统计源码中的 `aria-label` 数量。
- 切换“播放/暂停”“开始/停止”等动作时同步更新名称；折叠按钮同步 `aria-expanded`，
  开关按钮按语义设置 `aria-pressed`，Tab 同步 `aria-selected`。仅有名称不代表键盘操作已完成。
- iframe 必须有描述当前 App/Mini-App 的 `title`；iframe 的名称不能替代内部控件的名称。
  在真实 Studio placement、AppInstance 和 mount 中检查 Mini-App，包括重挂载及多实例时的 ID。
- 自定义控件必须实现相应的键盘与焦点行为；优先改用原生控件。上传/拖放需有可聚焦的
  文件选择入口，隐藏的 file input 不计为可见入口的替代方案。

### 自动化测试与提交验收

- 优先按 **role + accessible name** 或关联 label 定位；列表先限定当前对象，Mini-App 先定位
  正确的 iframe/browsing context。测试应固定语言，或按测试语言读取预期名称。
- 对确需跨语言稳定定位的目标，可补充稳定的 `data-testid`，但仍需独立断言语义角色、名称
  和状态。避免依赖 DOM 层级、CSS 外观类、坐标或无语义的第 N 个按钮。
- 浏览器测试继续通过平台 WebDriver BiDi 及授权 Gateway 执行；此处的定位约定不引入另一套
  浏览器控制协议或绕过 mount 的权限边界。
- [ ] 新增/修改的可见交互控件均有正确 role 和非空、有意义的名称；图标/符号按钮无漏标。
- [ ] 表单标签关联有效；没有仅靠 placeholder/title 的字段；同一作用域内目标能明确定位。
- [ ] 初始、加载、错误、展开/折叠、运行/停止、动态添加/删除后，名称和状态均正确。
- [ ] 至少检查中文、英文和键盘 Tab/Enter/Space 操作；隐藏面板不残留可聚焦的操作入口。
- [ ] 在固定 App-Dev 中完成实际 App/Mini-App 挂载的渲染检查；报告区分静态检查与实机验收。

当前源码的已确认缺口见 [2026-09-09 可访问名称审查](ai2apps-accessible-name-audit-2026-09-09.md)。
