# App/Mini-App Chat：持久执行契约 v2

2026-10-27。已接入通用服务、Todo 与 Imagine/Video/Voice Studio 的标准内置 Chat。Package 必须有所属宿主明确导出的 AaAT，不能隐式继承全部能力。
本契约补充 AaAT 声明与 App/Mini-App 集成契约；v1 仅统一显示，旧入口继续兼容。

## 固定接口和所有权

受信任宿主注册 `AppChatOwner`：App、可选 Mini-App、注册版本、明确的 AaAT
能力集合、作用域规范化/校验、逐次业务资源校验、UI 操作 JSON Schema、所属指令。
前端与模型不能注册 handler、提供可执行代码、选择授权集合或提供任意模块路径。
App 内 Chat 范围由注册确定；Mini-App 不自动继承整 App，宿主共享能力必须明确导出。

HTTP 统一位于 `/v1/platform/app-chat`：

- `POST /sessions`：以 registration、业务 scope、UI 数据创建/恢复自有持久 Session。
- `GET /sessions/{id}`：消息、Run、关联系统 Task、待处理 UI 请求和能力列表。
- `PUT /sessions/{id}/ui`：mount、语义 UI 快照及版本；这不是业务授权。
- `POST /sessions/{id}/turns`：request_id、text、model；立即返回后台 Run。
- `POST /sessions/{id}/ui/{command}`：绑定 mount/revision 的实际 UI 应用结果。
- Run 的取消、预算续行与交互回复沿用既有 `/agent-runs` API。

JS `AI2AppsAppChat.create` 复用 `AI2AppsMiniAppChat.createController` 与同一消息
surface。它只传输快照、提交和展示，不在页面运行模型/工具循环。功能调用是已有
AaAT Provider；UI 操作也经标准 Tool/Gateway，由所属 adapter 接入统一 UI 请求协议。
UI 的 read 操作返回最近快照及观察时间，不把关闭页面后留存的快照说成实时页面。

## 生命周期与范围

每个用户/注册/规范化业务 scope 恢复同一持久 App Session。Session 与可编辑 metadata
分开保存范围和 Provider 版本，不通过模型 input、工具 names 或 UI 数据授予权限。
每轮请求幂等、同会话串行，由现有 AgentRuntime 执行。系统 Task 只观察这个 Run，
不再启动一个模型循环。任务取消委托原 Run；已有业务任务保持各自执行权。

发现和实际 Gateway/Provider 派发分别检查范围，禁止跨目录/对象、外部 Provider，
不使用名字前缀推断归属。Provider 更新/撤销后旧范围不能自动采用新版或其他 owner；
需要重新核验接入。用户进入此对话并提交目标，表示授权范围内 Tool 调用，不逐次弹
普通批准或参数审阅；业务必填校验、许可及不可逆操作确认仍由 owner 保留。
第一批 Todo 仅导出查询、创建、字段 patch 与展示操作，不在新入口导出启动外部执行器、
删除、调度配置。旧列表/详情按钮不变；原 Mini-Chat run_project/schedule 还未迁入。

UI 请求绑定原 mount 与快照 revision。客户端应用前核对当前状态、脏草稿和请求状态，
仅执行声明操作；ack 重复提交不会重放 UI。新页面不会执行旧 mount 请求。应用后 ack
未知时不自动重放。关闭页面不取消功能任务；离开页面后需要 UI 的操作等待，超出原
Run/Tool 时限仍受预算限制。返回后恢复实际消息/任务结果，不重新调用模型补历史。
Local/模型服务必须仍运行；本功能不声称关闭 Desktop/电脑休眠后还能执行。

## Todo owner

`todo/app_chat.py` 决定目录范围和可操作字段，`todo/aaat.py` 与页面复用 TodoStore。
`todo.update` 以 task_id、revision、patch 修改；未给出的字段保留。当前脏表单阻止写。
`todo.ui` 声明读取快照、选择项目、展开项目、搜索与筛选；它不修改任务业务数据。
切换目录不会改变已运行任务的固定范围；首次迁移按会话绑定目录，不等价于旧页内
隐式扩大范围。跨目录/聚合视图的新会话需要明确选择源目录。

## 验证要求

任意 Provider 身份测试必须覆盖发现/执行双重限制、原资源归属、Provider 版本变化、
伪造 metadata、幂等请求、UI mount/revision 失效、重复 ack。持久 Run 验证不依赖页面
订阅。App-Dev 验收单列真实模型和夹具，包含查询/修改/UI 与关闭页面后返回恢复。
新注册接入不得另建前端模型循环或自己的 Tool 执行授权通道。

## Studio owner（2026-10-27）

三座 Studio 共用 `studio_app_chat.js`，各自登记独立 App/当前 Mini-App 的固定 scope。
原页面的描述接口只提供有界 UI 数据，旧前端模型循环和 run_current 不再参与新 Chat。
`studio.ui` 读取当前快照、修改声明草稿字段、选择已有共享输出；模型只能发声明操作，
不能注入 JavaScript、原生路径或跨 Mini-App 执行。更新模型只能使用当前 UI 所列模型。

Owner 的 `exports` 必须返回注册表内的同一 Provider 对象，明确选择当前 Mini-App 功能
和宿主共享 UI；通用机制只核验对象所有权、固定版本和声明范围。Video 的宿主基础处理
仅在提取音轨/合成器中导出，并按当前 Mini-App 限定 extract/trim/join；不扩展到其他应用。
功能执行复用原 AaAT 与现有队列。补充原生文生视频、已审阅有声书/演播项目渲染的队列
适配；缺少 AaAT 的 Mini-App 只能读取/修改 UI，不通过点击旧运行按钮伪装成迁移完成。
图生视频、完整合成器时间线、声音设计/训练等尚未补齐原生功能 AaAT 的入口不声称功能等价。

输出仍归原 Studio：Imagine artifacts、Video 原任务/Run、Voice 唯一 host-owned Quick Read
共享输出。不会另建每个 Mini-App 的播放、下载和历史；输出选择只能引用已观察到的 ID。
关闭页面后功能任务由 Local 继续；UI 操作须在原 mount 应答，关闭后不自动在新页面重放。
模型未就绪仍由原有配置流程处理，失败消息同样持久恢复；本次不把模型下载成功当成生成成功。
