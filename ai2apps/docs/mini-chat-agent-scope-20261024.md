# Mini-Chat 的 AI 展示及 Agent-Chat 开放讨论

2026-10-24。展示已实现；通用 Agent-Chat 开放尚未决定、未实施。

## 当前实际路径

| 路径 | 执行与范围 | 当前限制 |
| --- | --- | --- |
| 浏览器 Mini-Chat | `chat_mini.js` 前端持有模型流，附已绑定网页与 Knowledge 上下文 | 不是 General Agent，没有通用 AaAT 发现；不具备普通 Chat 后台回合持久恢复 |
| 旧 Mini-App Tools v1 | `mini_app_chat.js` 前端模型/工具循环，最多六轮；只使用宿主 describe 声明的 Tools/help，经原宿主 bridge invoke | 不是完整 AS；前端关闭不能保证完成，不能等同于有持久参数表单、审批、预算及恢复 |
| owner transport v1.1 | 共享 UI 只调用可信注册 send/action/cancel/reference hook，业务执行、持久历史及上下文由所属 App 提供 | 适配器可复用现有 Agent/Task，但只有实际接入才支持；注册会话 UI 不自动开放所有工具 |

“某 Mini-App 已能被完整版 Agent 通过 AaAT 调用”是该 App 的入站能力，
不意味着它的 Mini-Chat 已获准向外调用全部 AaAT。二者不能混为一谈。

## 本次展示边界

统一无气泡 AI 正文、Thinking 折叠、复制、Desktop TTS 和现有工具调用文本。
Thinking 只展示真实传入/流出的内容；owner 历史未保存该字段，不能凭 UI 恢复它。
现有引用、所属动作与简易表单保留。工具返回文本不作为成功证明。
没有构造假的 Agent Run 卡片、进度、预算或审批；没有把任意 owner 的普通 status
当成可以操作的 AS interaction，也没有自动执行新的 Tool。

## 建议讨论方案

建议暂不在全部 Mini-Chat 添加一个等同完整版的全局 Chat/Agent 开关。
先为明确需要执行能力的可信 owner 接入“当前 App 范围的 Agent”，底层复用现有
持久 Session/AgentRun 与声明、确认、参数表单、进度、结果视图、取消及恢复。
UI 显示实际 App/Agent 身份和范围，而不是把网页 Context 误认为工具授权。
范围必须由后端绑定/守卫，前端按钮不是权限边界；未接入能力保持现有问答。

跨 App 任务可提供明确的“在完整版 Chat 继续”，但要先实现已授权的原 Session/Run
交接和只读恢复；不能复制聊天文字后自动再执行，也不能用 URL 中的 ID 代替授权。
当前没有新增该交接按钮或隐藏扩权入口。

若决定在 Mini-Chat 开放完整 Agent，需要同时解决：

- 工具与资源范围：当前 App/对象限定，还是用户明确选择全局 Agent。
- 身份与隐私：actor/Installation/Session/Profile/对象版本及 Package 隔离不变。
- 真正的后台执行：迁离旧前端循环，关闭侧栏不取消 Run，恢复不重放。
- 完整交互展示：复用现有状态快照、AaAT 图文结果、参数/审批/预算表单及 App handoff；窄栏只改变布局，不省略确认。
- 历史和切换：保留原任务与消息 ID，切换网页/对象不改绑正在执行的请求。
- 真实验收：跨 owner 越权拒绝、前端离线、重启、取消、未知结果不重放及实际工具链。

待用户决定：是否采用“默认问答 + owner 显式接入的限定范围 Agent + 跨 App 转完整版”
作为第一阶段。此文是讨论，不是执行授权或已支持声明。

## 本轮验证

27 项 Node/Chrome 检查通过：Thinking 跨 chunk 分流、正文复制、Desktop TTS 请求/
停止/缺模型提示、owner 动作不在渲染时执行、用户气泡与原绑定/幂等边界。
8 项既有 Mini-Entry iframe、旧 Tools、情报对话浏览器测试在 Chrome 下通过；
本机 WebKit 缺失，因此不声称 WebKit 验收。297 项 AaAT gate 全通过（exit 0）。
音频/模型/业务调用为 fixture；真实 TTS 与实际任务交互未在本轮重跑。
App-Dev port56081 的两个 Mini-Chat JS 与共享 CSS 和 live checkout 字节一致。
刷新页面生效，不需要重启 Local、重构 App 或升级 Runtime。


## 2026-10-24 后续已授权实现

用户明确要求统一 Mini-Chat 并让文章 AI 决定使用 fast 搜索。本轮已统一旧 iframe 与 owner 内嵌 UI 到同一组件，保留原执行协议；增加模型/重置扩展。文章 owner 只声明一次受限 web.search，先持久保存模型选择再准备共享确认表单。仍未开放全局 General Agent、任意 AaAT 发现、自动费用授权或跨 App 工具执行；这不意味着所有 Mini-Chat 都具备新的通用 Agent 执行器。
