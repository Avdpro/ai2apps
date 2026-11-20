# Local 托管 Cloud 结构化输出 v1

2026-11-05；Cloud 协议交接：[Local 对接文档](/Users/avdpropang/sdk/ai2apps-cloud/docs/structured-output-client-handoff-2026-11-05.md)。本实现不改 Cloud 服务、账号、默认模型、预算或业务权限。

## 通用 Gateway

调用方继续使用 OpenAI 兼容 `response_format`；托管 Gateway 投影为 `responseFormat`，只接受 `text` / `json_object` 和唯一字段 `type`。请求模型不再静默擦掉额外格式字段。JSON Schema、额外字段、JSON 与非空 tools、需要独立 developer 优先级的组合明确拒绝。普通未指定格式/显式 text 的行为保持原有文本路径。

JSON 模式使用相同认证读取 `/v1/ai/models`，只按精确所选模型的 `capabilities.structuredOutput` 协商：contract=`ai2apps.structured-output.v1`、modes 包含 json_object、buffered=true、有效且不超过 1 MiB 的 maxOutputBytes。字段缺失/撤回/目录失败均不提交模型请求，不以模型/提供方名字推断支持，不删工具或换模型绕过限制。

非流式响应要求成功 HTTP、responseFormat、structuredOutput.valid=true/type、stop 终态，以及合法且有界的顶层 JSON 对象；拒绝工具输出、数组、null、裸数字、代码围栏和坏 JSON。Cloud 回滚导致成功标记缺失同样失败。

SSE 的 JSON 内容在 Local 再次有界缓冲；未收到并校验 response.completed 不投影内容。无终态、失败、截断、意外工具输出、超限和断连均不交付待执行内容，发送明确失败，不自动重试。普通流式增量不改变。

## Bot 所有的业务校验

合法 JSON 对象不等于合法 Bot 决策。`messager/decision.py` 验证允许字段、kind/text、可选身份/标题、memory/requirements 容器、受限 schedule 字段与类型；无效决策在记忆写入、计划审阅或 Task 准入之前失败，显示可理解的信息，不泄露 Python 解析异常。实际实体归属、版本、参数、记忆来源及权限继续由原 owner 服务复核；任何格式声明均不授予 Task/App 权限。

## 失败及计费

原 Cloud HTTP error.code/message/retryable/details 保留到持久 model step 和 Run。格式失败中的 schemaVersion、usage、points.charged、billingStatus=settled 等不被当成未扣费/全额退款。没有结算事实时不制造结算状态。非流式成功仍保留 ai2apps_cloud 的 points/usage、格式标记及 requestId；SSE failed 元数据沿原错误路径投影。

失败不使用新幂等键自动重试、不重放旧失败任务、不自动授权或切换模型。只读查询与恢复保留原身份、Run/Session、幂等及权限守卫。

## 所有权与回归

新增通用机制只知道平台格式/能力/终态协议，不知道 Bot 或业务 App/Tool 身份；模型决策业务 schema 放在 Messager owner。跨任意/不同提供方 ID 的协商、普通文本兼容、JSON/SSE、安全失败、结算信息和 owner 准入分别覆盖；不增加共享 Agent 的业务分支。完整 AaAT 门禁必须通过，实机结果与 fixture 结果分开记录。

最终验收与限制见 `acceptance/managed-cloud-structured-output-local-20261105/`。

## 当前实机结论

固定 Test 的 DeepSeek 算术、Gallery 只读 Task、授权等待/拒绝和澄清已有真实成功证据；另两次独立问答由 Cloud 格式守卫拒绝，实际扣费各1点，Local 保留 settled 事实且不重试。总体仍有格式稳定性问题，详见验收目录。完整门禁结果另记收据；SSE 是隔离夹具覆盖，Bot 实机路径为非流式，不夸大为全部真实供应商流式验收。
