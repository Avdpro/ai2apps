# Messager 托管 Cloud 结构化输出兼容需求

## 当前进度

Cloud 已于 2026-11-05 部署结构化输出 v1。Local 对接实现及最终验收见 [Local 实现说明](../managed-cloud-structured-output-local-v1.md)，以下保留原始问题与交接需求，不代表 Cloud 尚未交付。

## 背景与边界

2026-11-05，在固定 Test 实例将 AI2Apps Bot 的 Profile 从本地 Qwen3.8 27B NVFP4 切换为 `(Cloud) DeepSeek · DeepSeek V4.1 Flash`。保存值为 `cloud/deepseek/deepseek-v4-flash`，revision 2。本次没有复制其它实例的凭据或切换系统默认模型。

这是交给 Cloud 项目的协议确认/变更需求，不在此仓库修改或部署 Cloud 服务。应先确认既有 `/v1/ai/responses` 是否已有可用结构化输出协议；如已有，Local 按已公布契约接入；如没有，Cloud 项目先实现并部署，再由 Local 接入。

## 已确认的证据

- Bot 的持久化 model step 输入包含 `response_format: {"type":"json_object"}`，system 明确要求带 `kind` 和 `text` 等字段的对象。
- `ai2apps/model_invocation.py::invoke_agent_cloud_json` 经 `ChatCompletionRequest` 调用现有 Cloud Gateway。
- `ai2apps/cloud_gateway.py::_ai2apps_request_body` 将 system、input、tools、maxOutputTokens 等转成托管 Cloud body，目前没有投影 `response_format`。
- Test 日志确认三次请求实际发送至 `coder.ai2apps.com /v1/ai/responses`。没有读取或导出 Cloud Token。
- 两个算术请求的模型内容分别是裸 `42` 与 `44`；只读任务请求返回自然语言“好，我已经重新排队……”。三次完成原始请求分别约 1.49、1.38、1.56 秒，但 Bot 决策解析均失败，没有执行新 Task。
- 当前 Bot 失败提示同时暴露底层解析错误。不能把这些失败请求的耗时当作完整任务完成时间。

因此，已证实结构化要求在当前 Local 托管协议转换中未传递，以及实际响应不符合 Bot 契约；尚未独立证明 DeepSeek 原生接口不支持结构化输出，也不据此断言 Cloud 服务内部如何处理 system。

## Cloud 项目需要明确/提供的契约

1. 对 `/v1/ai/responses` 正式声明结构化输出字段、可用模型能力及版本。字段命名由 Cloud 已有规范决定，不能由 Local 臆造。
2. 支持 JSON 对象；如支持 JSON Schema，同时声明支持范围、模型限制及拒绝行为。透传或映射到提供方的实际结构化输出参数。
3. 保留可信 system/developer 指令和原用户输入的角色/优先级，不用强制“普通聊天回复”替换调用方的结构化决策任务。
4. 不支持的模型或格式应在调用前明确返回可识别错误/能力限制，不能静默忽略格式要求后返回普通文本并宣称兼容。
5. 返回内容、finish reason、拒绝/截断和 usage 语义保持清晰。无论流式与否，不能把裸数值、字符串或数组当作满足 JSON object 的结果。
6. 不改变身份绑定、预算/计费、权限或效果确认规则。格式适配不授权业务 Task，也不能把失败任务重放成一次新的效果调用。

## 随后的 Local 接入与验收

- Gateway 按确认后的 Cloud 协议转发结构化意图，并补任意不同提供方的通用覆盖；不按 DeepSeek 名称增加业务分支。
- Bot owner 检查决策必须为合法对象，错误信息应可理解，保留明确失败终态；不把普通自然语言猜成已执行的任务或自动授权。
- 使用固定 Test 的真实模型重测：直接问答、独立只读 Task、运行期间聊天、缺参澄清、权限等待/拒绝。
- 对比同一模型请求的端到端耗时与 Tool 执行耗时。用户可见成功、Task 实际创建/终态、输出证据及模型记录同时成立，才算通过。
- 不通过自动切换模型、复制其它实例凭据或取消确认来绕过失败。

本次证据与原始本地模型对照见 `../acceptance/messager-default-entry-test-20261105/deepseek-comparison.json`。
