# Bot → Todo 执行与审批回接 v1

Bot 间单层立即委派与协作等待见 [C2 实施说明](bot-delegation-c2-implementation.md) 和 [总体设计](bot-communication-and-collaboration-v1.md)。子任务使用实际接收 Bot 的 Todo/Task-Session、沿分支继承的访问权限与原交互审批；等待协作通过结束当前执行回合、保留逻辑任务并在成功后排队新回合实现，不建立第二套执行器，权限规则见 [任务树内的 App Access](aaat-declaration-context-v1.md#任务树内的-app-access)。现有等待用户输入/审批仍占 Bot 的执行槽位。

2026-11-03，实施完成，Dev / App-Dev 已激活并验收，尚未发布。此协议复用 Todo 原任务/执行状态、AgentRuntime 原 Run/Interaction 与 AppChat 授权，不建立第二套任务执行器。首批任务只能使用已经开放的 App 只读能力；写入、发送、付款等能力没有因本协议自动开放。

## 用户路径

普通问题直接回答。实质工作或执行计划由 Bot 调用 `messager.task.propose` 准备任务，补齐标题、完整指令、日程与通知选择。模型来自该次对话，不能在提案参数中换执行器或权限。提案只保存待审阅意图，不创建 Todo、不启动推理任务。模型声明及返回结果明确禁止把提案称为已启动任务。

对话中展示宿主持有的提案卡：任务内容、模型、立即/定时单次/周期计划、时区、冻结的后台读取范围以及结束通知选择。用户在 Local desktop 同源宿主确认后才在 Todo 收件箱创建托管任务，并启动或保存日程；过期权限/接口、跨用户、不同 Bot、改动后的审阅摘要不能被批准。未完成的确认可以取消；若已有执行回执，则先恢复真实任务状态，再停止原执行，不假称尚未创建。

任务与日常对话使用独立 Session。任务等待输入时仍占 Bot 的串行通道，用户可以继续聊天询问实际进度。对话内的任务卡展示原 Run 的原待输入/审批；用户提交后唤醒同一 Run。本次执行结束后，宿主按实际 Todo Run 终态写回原对话。Todo 项目的验收/完成状态沿用原有规则，不把 Run completed 自动当作项目已验收；面板明确标为“本次执行完成”。选择安静时不报告成功，但失败/取消仍有真实回执。尚未扩展微信或其他外部通知渠道。

## 可信边界

- Messager 拥有提案、Bot 归属、任务身份、审阅规则和对话展示。Todo 拥有 Task/Run、队列、计划、取消和恢复。General Agent 不认识 Bot、Task 名或业务 Tool 名。
- TaskInput 的 `managed` 是失去绑定时拒绝执行的标记，不是授权。真正执行绑定在 Todo 私有表，创建任务时与串行 lane 在同一事务写入；用户/model 参数不能填写该绑定。只有已注册的可信 owner adapter 可以启动此类任务，不存在退回全权限 GeneralAgent 的分支。旧执行器也不能把 managed 当作 internal 执行。
- 执行绑定固定 Bot ID、提案 ID、批准时的后台权限 revision/Provider/version、任务执行字段摘要及通知选择。启动、恢复模型执行、Tool 调用和回复等待项均复核当前权限。修改执行字段、撤回或重新授权都不能复活旧绑定。模型职责、消息、提案正文和回答不提供授权。
- 手工关联的旧 Todo 保持原 Todo 执行权限，不能被伪装成新 Bot 托管任务；新托管任务不能解除/改绑 lane 绕过串行约束。界面明确区分两者。
- 本机制的 adapter 注册是内置可信代码接口，不向第三方 Package 提供任意后台代码入口。

## 幂等与恢复

提案以原 Tool invocation 为幂等键。用户确认通过固定 creation key 创建唯一 Todo；任务、私有绑定、lane 与创建回执原子保存。启动通过固定 request key 保存唯一 Run/启动回执，重复点击或网络丢失只返回原回执。

AppChatOwner 的通用 `admit_run` 钩子在 admission 中检查 owner 规定的固定请求 ID、原指令与模型；任务 Session 不能被另一个请求绕过 Todo 队列重新启动。`execution_origin='task'` 是宿主审计标签，不提供权限。

若进程在 AppChat 已创建 Run、Todo 尚未写回 agent_run_id 的窗口中断，owner restore 从原 Task scope、Session 与 turn 回执恢复原 Run。找不到原执行证据时不自动重新执行。已完成结果通过稳定消息键去重；重启恢复或重复轮询不会重复写入回执。

备份只携带需要 owner 审阅的标记，不导出可执行授权。跨库导入的托管任务保存为 `owner-review-required`，停用自动计划并拒绝执行；保留或恢复的托管任务也不能因缺少私有绑定而转成普通执行器。

## 等待与审批

待处理项直接读取原 AgentRun Interaction，包括请求、版本/审阅摘要和响应 schema。回应绑定 actor、Bot、Todo Run、Agent Run、Interaction 与 response_id；重放同一个响应只返回原结果。更改请求、过期、撤回、终态或其他 Bot 的等待项均拒绝。

审批入口限制为本次操作和当前资源，不允许在 Bot 回接中升级为 session/agent/app 范围。表单、App handoff 与 Local-owned BiDi 操作仍通过所属 App 完成；不会用普通 JSON 或模型回答伪造其业务完成。拒绝沿用原 Interaction 的失败规则，不改用另一个 Tool 自动重试。

当前只读 App profile 不包含支付或发送权限。审批协议夹具可验证原 Run 的拒绝及范围限制，不等于已经接入真实付款、购物车或其他敏感操作 owner。

## 日期与验证范围

定时单次使用带时区偏移的明确时间，服务端归一化为 UTC；面板按提案时区展示。默认时区 Asia/Shanghai，不能取执行主机的时区猜测用户意图。立即单次明确使用 frequency=off（省略计划），指定时间单次才使用 once；真实模型验收曾暴露歧义，已通过 owner 声明/参数说明明确区分。单次触发后 next_due 为空，周期执行复用现有 Todo 的 catch-up、DST 和原子计划认领。

专项覆盖真实 SQLite、API、Todo 调度及 AgentRuntime，模型/敏感请求使用明确夹具；原生开发实例与真实模型验收另行记录。详细完成记录见下节；本文件不代表生产发布。


## 完成验收

完整 AaAT 门禁 882 项通过（450.13 秒），补充审批 6 项通过。Dev 使用当前配置的 DeepSeek 模型，实际完成对话提案、原生确认、Todo 启动、原 Task 等待输入、并行普通对话询问状态、原生回复后同一 Run 完成及唯一结果回写。该任务未读取 App 数据，未扩大后台授权，未发送外部消息。Dev / App-Dev 的 App 与 Helper 源码根、运行模块路径及服务资源均核对为当前 checkout；重载后原回执保留，两个实例数据独立。

定时、撤回、重启恢复及敏感审批范围限制由专项夹具验证，不等于真实付款等操作验收。收据见 [执行链路验收](acceptance/messager-todo-execution-20261103/receipt.json)。本阶段尚未完成整个 Messager v2 的记忆管理、删除/清理和更多 App 写权限。


2026-11-03 后续实现：对话提案现在同时冻结用户维护的长期记忆，宿主审阅卡可展开查看。记忆是数据参考，不增加执行权限；单条后续修改不改变已经批准的任务。全部清理或删除会提升授权版本、取消旧执行并停止队列/计划，历史 Run 仍能结算唯一审计回执。具体见 [记忆与生命周期阶段](messager-ui-and-bot-task-v2.md)。
