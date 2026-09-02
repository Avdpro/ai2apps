# AI2Apps App 开发指南

本文档定义 AI2Apps App 的通用开发约定。新 App 和现有 System App 都应遵循这些约定，避免把 Desktop、普通浏览器和移动端的宿主差异重复实现到每个 App 中。

架构对象、Entry/Mini-Entry、AppInstance 和安全边界的完整定义见 [AI2Apps Platform Architecture](ai2apps-platform-architecture.md#10-app-architecture)。能力首次配置、按设备推荐 Runtime/Package/Checkpoint 的流程见 [AI2Apps Capability Provisioning Framework（ACPF）](ai2apps-capability-provisioning-framework-v1.md)。

Video Studio、Read Aloud Studio、Image/Drawing Studio 以及其它以创作 Pipeline、素材、
生成任务和媒体产物为核心的 Studio 类 App，必须同时遵循
[AI2Apps Studio App UI 设计规范 v1](ai2apps-studio-app-ui-design-standard-v1.md)。该规范定义
统一三列布局、Pipeline 专用 WebUI、Gallery Mini-Entry、Render Workspace、ACPF 和
Coder 扩展边界。

## 1. 宿主环境

同一个 App Entry 可以运行在以下宿主中：

- `desktop`：AI2Apps Desktop，由 AceFox 承载；
- `browser`：Chrome、Safari、Firefox 等普通浏览器；
- `mobile`：AI2Apps 移动端入口或移动 Web 宿主。

宿主类型必须由 AI2Apps Shell/服务端提供，App 不得依赖 User-Agent、窗口尺寸或浏览器私有特征进行猜测。当前同源 System App 会在 Entry 根节点收到 `data-client-environment`；sandbox/schema App 后续应从 App View Bridge 接收同一语义的只读环境字段。

宿主字段只用于表现层适配，不是授权依据。文件、设备、模型和系统操作仍必须经过相应的 Session、Capability 和 Host Broker 检查。

## 2. 模型调用与 Worker 透明边界

App 只面向平台模型调用契约，不面向 Model Worker。Chat、绘图、音频、Video、Read Aloud、
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

## 4. 实现检查表

开发或升级包含 Artifact 下载的 App 时，至少检查：

- 无下载地址时按钮不可用，或点击后显示明确错误；
- Desktop 点击后出现原生“另存为”对话框；
- 普通浏览器点击后开始标准下载并出现页面内反馈；
- 文件名、扩展名和 MIME 类型正确；
- 大文件不经过前端 Blob 缓冲；
- App 没有通过 User-Agent 猜测宿主；
- 下载行为不绕过 Artifact 权限和审计边界。

自动化测试应覆盖模板保留原生下载链接、环境字段由可信宿主注入、Desktop 下载偏好启用 Save As，以及普通浏览器反馈文案。发布前还应分别在 AI2Apps Desktop 和至少一个普通浏览器执行一次人工 smoke test。

## 5. Video Studio 参考实现

Video Studio 是当前参考实现：服务端验证 Desktop Shell 的 HttpOnly 会话后注入宿主环境；WebUI 始终使用 Artifact 原生下载链接；Desktop 由 AceFox 打开 macOS“另存为”，普通浏览器显示下载开始提示并交给浏览器下载管理器。

相关实现：

- `ai2apps/api/client.py`：可信 Desktop Shell 环境识别；
- `omlx/admin/routes.py`：System App Entry 环境注入；
- `ai2apps/web/templates/system_apps/video_studio.html`：原生 Artifact 下载链接；
- `ai2apps/web/static/js/video_studio.js`：跨宿主反馈。
