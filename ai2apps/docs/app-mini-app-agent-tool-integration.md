# App 和 Mini-App 的 Agent 与 Tool 对接指南

本文面向已有 App 的维护者、Mini-App 和 Package 开发者，以及 Agent、Harness 和 Shell 集成者。目标是让同一份业务能力既可在 App 界面使用，也可被 Agent 组合调用；需要用户参与时，能够打开正确的工作区、持久等待，再把可信结果交回原任务。

## 0 当前规范与架构边界（2026-10-20）

所有接入和修复必须先遵守 [AaAT 声明与 Context 契约](aaat-declaration-context-v1.md) 的所有权、标准执行流程与开发评审准入，以及 [开发约束](../AGENTS.md)。本文的历史验收和特定 App 示例用于说明接入，不要求在 AS 增加相应业务分支；如与当前契约冲突，以当前契约为准。

App/Mini-App 提供业务语义、支持范围、实体定位、统计、输入校验、交互规则和结果证据。General Agent 和共享 AS 只消费通用声明与控制协议，管理调用、授权、进度、等待/恢复、预算和结果策略分发。不得为了接入某个 Tool 修改 General 的全局提示、添加业务 Tool/App 名或前缀判断、导入业务校验器，或按业务特有结果字段处理成功/失败。

标准链路为：发现候选摘要 → 选择能力 → 加载/复核所选声明及 Provider 版本 → 按声明组织参数 → Tool 执行与持久交互 → 返回实际结果/Context/证据 → AS 整理答复或规划下一步。新接入优先使用 `agent_context`、Provider `describe/prepare`、`invocation_policy`、`aaat_context`、能力作用域化的 `AgentResultPolicy` 及可见性注册。需要核心新抽象时，必须说明其通用性并增加不同/任意 Provider 的验证，不能把 App 特例换个文件存放。

`app.describe` 无筛选时发现摘要，定向 capability 时返回完整声明，也覆盖无参数表单 Provider。共享 AS 从注册表加载所选可信声明，而不是把 Tool 返回正文当作系统指令。`tool_declaration_required` 表示调用尚未执行，需要模型读过声明重新规划；具体边界、兼容性和失败替代语义均见上述契约。

修改共享 AS 或 AaAT 契约/交互/结果策略时必须运行 [架构与行为回归门禁](aaat-boundary-regression.md)：`python ai2apps/tests/run_aaat_boundaries.py`（Git 根目录）。CI 同步执行；若失败应修正所有权或通用抽象，不得增加业务豁免来通过。

本文以当前仓库实现为准。文中的“必须”是新接入的工程约束；标明“示意”的代码需要补齐业务实现。“已支持”不代表全部 App 已自动注册能力。工作区交接适配为 `intelligence.create_channel`；Chat 参数表单首个适配是 App/Mini-App 音频转写，见第 15 节。其他能力的宿主挂载、业务接口和结果适配仍需逐个实现。

## 1 选择正确的能力形式

### 普通 Chat 的后台回合（2026-10-23）

普通文本/多模态对话使用 Chat 所有的 `chat/turns.py` 专用执行器，复用现有
AgentRun 调度、模型步骤、取消与恢复机制。它不调用 General Agent、不注入工具
说明、不发现或执行 Tool。后台运行与使用 Agent 模式是两个独立概念。

Desktop/Mobile 先持久保存用户消息，再 POST `/chat/threads/{id}/turns`，携带
稳定 `request_id`、`expected_revision` 和冻结的模型参数/上下文。服务端在同一
写事务内检查线程归属、版本、活动回合并创建 Run；重复键改参拒绝。客户端只轮询
turn 状态/有界流式预览，GET 恢复不创建或重放任务。失联、关闭 WebView、切换
页面不等于取消；取消必须调用该线程下的 turn cancel 接口。

模型输出先保存为持久 model step；最终 assistant 消息、稳定消息 ID、Session
revision 和 Run completed/output 在同一事务提交，取消与提交通过数据库写锁
串行化。已保存模型步骤的恢复不会再次调用模型；推理中 Local 进程停止可能需要
重新计算未完成步骤，不能保证在断电时保留 GPU 上的未提交输出。Local 保持运行时，
前端离线不会影响执行。两小时 Run deadline、真实模型错误与明确取消仍然有效。

重连读取原线程的消息和活动 turn，继续观察或在已保存结果后发送下一轮。
正在生成时拒绝整段历史覆盖；完成提交提升 revision，旧快照拒绝覆盖；后续正常
保存保留后台消息的 ID/幂等键。现有 Desktop、Owner Mobile、签名 Mobile 的
actor/client-scope 隔离继续生效，本机制没有把各端列表合并或把正文上传 Cloud。
Owner Mobile 的普通 Chat turn API 不授予 Agent 或任意 Run 的操作权限。
Chat 内 AaAT 的待输入/审批 Interaction 也通过同一系统通知 outbox 提醒，按交互 ID 去重。
发送前与点击时再次检查 pending、期限、取消及当前会话归属；仅恢复/展示原表单，不提交或批准。
参见 [等待交互通知](chat-reply-notifications.md)。业务 prompt/草稿不能成为通知正文。
Terminal 专属 Mini-Chat 和图像生成工作流保持其各自入口，不在本次普通模型
回合迁移范围内。Chat 完成通知现已从已保存的根 Run 终态接入；参见
[Chat 回复完成通知](chat-reply-notifications.md)，保持 Owner 和 client-scope 隔离。

共享仓储新增可加入调用方事务的 Run 创建/终态接口，以及相同 completed/output
的幂等终态重放；这是不识别业务身份的事务能力，Chat 规则留在所属执行器。
验收使用真实 SQLite/API/Run 调度器与可控模型夹具，覆盖观察者断开、结果恢复、
继续下一轮、重复/并发提交、取消、空输出、版本冲突、Owner 路由与跨范围拒绝。
Chrome 页面测试验证关闭/重开与恢复零重复提交；不等同于本轮真实付费模型验收。

本次真实 App-Dev 另行完成 Cloud 模型验收：会话
`ses_8abd4bb6afdd43b2897b05a054d7588f` 保留三个普通 Chat 回合；长回复
`run_e463127218d04d8daee9fc9b1b84ea27` 的 App 关闭事件时间为
2026-10-22T17:42:25.230459Z，回复与 completed 在 17:42:28.017417Z
提交，内容1192字。重新挂载 Chat 后可见完整回复和验收结束标记。前两轮亦能
恢复并在同一 Session 继续。该记录不等同于 iPhone 真机或本地 Worker 实测。

执行进度须遵守 [任务状态与 AaAT 观察契约](aaat-declaration-context-v1.md)。
已有 System Task 的工作只用 `TaskContext.report` 上报一次；handler 的 `progress_view`
统一投影业务阶段、计数，任务中心/App/AaAT 共用 `progress_snapshot`。AaAT 通过
`SystemTaskService.follow` 观察现有任务，不重新提交任务或另建业务轮询器。
Browser Task/Studio Job 等已有执行器保留唯一执行权，提供同一格式的任务快照。
仅简单同步 Tool 直接使用 `report_progress`。`content.task_progress` 是对话传输投影，
不是第二份执行状态或独立 App 接口，也不能发起授权或覆盖真实任务终态。

App 是用户界面和业务的入口，Tool 是可验证的单项操作，Agent 是可持续执行的工作流程。一个 App 可以同时提供三种入口，不需要把整个 App 包装成一个大 Tool。

内部执行器应声明 `discoverable: false`。Session 的对话任务历史只展示可发现的根 Agent Run；执行层的根 Run 不必然是一轮用户对话。内部 Run 仍保留原记录、归属检查和详情/状态读取，主任务沿既有进度和交互协议展示必要信息，客户端不按执行器名称隐藏卡片。

| 形式 | 适用情况 | 当前接入路径 | 完成方式 |
| --- | --- | --- | --- |
| 直接 Tool | 参数足够、无需打开界面，如读取素材元数据 | ServiceRepository.ensure_tool 和 ServiceRegistry.bind_tool | 返回符合 Schema 的结构化结果 |
| 可委托 Agent | 多步推理、多个 Tool、后台任务和持续状态 | 注册 Agent definition 和 executor；通过 agent.delegate 委托 | 子 Run 完成，将结果交回父 Run |
| 交互式能力 | 需要选择、编辑、预览、确认或使用专属 App 界面 | 注册 InteractionCapability，经 app.interact 发起 | 原 Run 等待，目标 App 后端提交结果后恢复 |

推荐按业务动词拆分，例如 `media.inspect`、`media.export`、`media.edit_interactively`。名称只是设计示例，不是现有注册项。读取和写入分开；一次调用避免同时承担搜索、删除、导出和用户确认。

不要通过模拟点击来代替一个已有稳定业务 API。UI 与 Tool 应复用同一业务服务、权限和存储层。必须由用户完成的操作保留在交互式路径中。

## 2 参数由谁决定

开发者定义输入 Schema、字段含义、约束和默认策略；模型根据用户请求生成候选参数；服务器验证参数、身份和资源权限；用户在交互界面修正或补齐业务字段。最终结果以服务器保存的业务数据为准。

| 数据 | 权威来源 | 禁止的做法 |
| --- | --- | --- |
| capability、参数结构和版本 | 可信能力注册表 | 让模型发明未注册 capability |
| 用户需求、频道名称等业务输入 | 用户请求及模型提议；交互时允许用户修改 | 把预填值当成最终授权 |
| actor、owner、Session、Run、origin App instance | 登录会话、ToolCallContext 和数据库关系 | 从模型参数或隐藏表单决定资源所有者 |
| 目标 App 和 Mini-App | 注册的 app_id、mini_app_id | 接受模型提供的 URL、脚本或 mount 凭证 |
| 结果与资源 ID | 后端业务存储和当前交接关系 | 直接接受前端声称“已完成”的 JSON |
| Token、步数、超时和访问范围 | Runtime 与委托预算、能力策略 | 用模型参数扩权或逃逸父任务约束 |

Schema 应明确类型、长度、枚举、必填字段，通常设置 `additionalProperties: false`。资源使用稳定 ID；大量文件、音频或正文使用受控 artifact 引用，不塞入 Tool 参数或聊天正文。默认值必须可解释，不能缺少目的地就默认发布、缺少 ID 就操作“最近一个”资源。

业务数据中的文字、网页内容和文章摘要均是不可信数据，不能成为授权指令。

## 3 直接 Tool 的接入

现有接口位于 [ServiceRepository](../services/repository.py)、[ServiceRegistry](../services/registry.py) 和 [适配器示例](../services/adapters.py)。安装流程需创建或定位 Service 和运行中的 Service instance，再注册描述和实际 handler。

下面示例假设已经获得可信的 `service` 和 `instance`；`media_store` 是需要开发者提供的业务服务，不是平台内置接口。

```python
services.ensure_tool(
    service_id=service.id,
    qualified_name="media.inspect",
    display_name="Inspect media",
    description="Read metadata for an existing media asset accessible to the caller.",
    input_schema={
        "type": "object",
        "properties": {"asset_id": {"type": "string", "minLength": 1}},
        "required": ["asset_id"],
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {
            "asset_id": {"type": "string"},
            "mime_type": {"type": "string"},
        },
        "required": ["asset_id", "mime_type"],
        "additionalProperties": False,
    },
    effects=(),
    timeout_ms=10_000,
)

async def inspect_asset(arguments, context):
    # 示意：业务服务必须根据实际调用上下文验证资源访问权限。
    asset = await media_store.read_authorized(arguments["asset_id"], context)
    return {"asset_id": asset.id, "mime_type": asset.mime_type}

registry.bind_tool(
    "media.inspect", provider_key=instance.provider_key, handler=inspect_asset,
)
```

副作用操作必须按项目既有策略声明 `effects`、`required_capabilities` 或 `capability_rules`，并在业务层执行权限检查。不要为方便测试把真实写入声明为 `effects=()`。注册描述、描述可见、handler 可调用、业务获准是不同环节，需要分别验证。

`ensure_tool` 支持 `retry_policy`，默认不自动重复副作用。重试必须依赖幂等键和确定的业务事务；请求超时不等于写入未发生。长任务应保存 job/run 状态，提供查询和取消接口，不把分钟级等待藏进短时 Tool RPC。

## 4 可委托 Agent 的接入

参考 [委托服务](../agents/delegation.py)、[General Agent](../agents/general.py) 和 [Runtime](../agents/runtime.py)。需要注册 definition、绑定 executor，并定义任务输入、结果结构、工具范围和预算。注册 App 或 Mini-App 不会自动生成这些内容。

当前通用委托工具是 `agent.delegate`。以下调用中的 agent key 必须替换为已注册且调用者可用的 Agent：

```json
{
  "agent": "example.research-agent",
  "task": "根据提供的文章生成中文简报",
  "request_key": "briefing-1",
  "parameters": {"channel_id": "existing-channel-id"},
  "context": "仅使用给定频道的文章，保留来源链接",
  "budget": {"max_steps": 12, "max_model_tokens": 30000, "timeout_seconds": 600}
}
```

`request_key` 用于同一父 Run 内识别同一委托，重复请求应恢复已存在子任务。`parameters` 的具体语义由目标 executor 校验，不能因为顶层接受 object 就认为所有字段合法。父任务的权限与预算不能被子任务放大。

App 能力可以由 Agent 调用多个 Tool 完成；需要用户编辑时再进入交互式能力。不要将 `agent.delegate`、某个专用执行系统里的 `agent.call` 和 `app.interact` 当成可互换接口。

## 5 交互式调用的完整链路

实际链路为：用户提出任务 → General Agent 生成 `app.interact` 调用 → executor 创建 Interaction → Run 进入 `waiting_input` → 用户打开目标 App → App 后端验证并完成业务 → 后端提交 Interaction → 原 Run 恢复 → 原工具调用读取结果 → Agent 继续。

有两个独立动作：**完成业务并恢复执行**由后端负责；**切回原界面**由 Shell 负责。切换页面不能代表完成，完成后的页面跳转失败也不应导致再次创建资源。

### 5.1 注册能力

当前注册入口是 [app_interactions.py](../agents/app_interactions.py) 的 `register_capability`。它是可信 Python 适配器入口，应在安装 Tool catalog 之前执行，不是向任意 Package 暴露的公共注册 API。

```python
from ai2apps.agents.app_interactions import InteractionCapability, register_capability

register_capability(InteractionCapability(
    key="example.review_asset",
    app_id="example.media-host",
    mini_app_id="example.crop-editor",  # 普通 App 不填此字段
    version=1,
    parameter_schema={
        "type": "object",
        "properties": {"asset_id": {"type": "string", "minLength": 1}},
        "required": ["asset_id"],
        "additionalProperties": False,
    },
    prompt="请在编辑器确认裁切结果，然后返回原任务。",
))
```

这是接入示例，不表示对应 App 已存在。注册函数拒绝重复 key、非法 Schema 和包含斜杠的目标标识，但这些校验本身不能证明 Package 已安装或可信；安装与挂载层必须继续检查真实身份、可用状态和权限。

当前 `CAPABILITIES` 是进程内注册表，尚无通用 Package manifest 自动导入、运行时卸载或能力版本迁移协议。核心 `app.interact` 使用通用说明；新能力的业务说明和约束必须由所属 `InteractionCapability.agent_context` 与参数 Schema 提供，并通过 `app.describe` 发现。不得为新 App 修改核心工具说明或添加业务能力枚举。

### 5.2 模型调用参数

现有已实现的调用：

```json
{
  "request_id": "create-channel-1",
  "capability": "intelligence.create_channel",
  "parameters": {
    "name": "人工智能资讯",
    "interests": "人工智能研究和开源发布",
    "excluded": "营销软文"
  }
}
```

`request_id` 长度为 1–128，作用域为当前 Run，内部 request key 为 `app:` 加该值。同一请求重放必须保留参数；用同一 ID 改参数会被拒绝。新业务请求用新 ID。

`parameters` 必须存在，但当前频道能力三个字段均为可选，分别限制为 80、3000、1000 字符。字段用于界面预填。`version`、目标 App、原 Session 等由服务器补齐，不在模型输入中。

### 5.3 自定义 Agent 和 Harness

General Agent 已在解析模型工具调用时识别 `app.interact` 并生成 `InteractionAction`。直接经 Tool 网关调用 `app.interact` 只会尝试读取已经提交的交接结果，不会创建交接或自动打开页面。

自定义 executor 的核心顺序如下，属于执行流程示意：

```python
from ai2apps.agents.app_interactions import interaction_action
from ai2apps.agents import ToolCallAction

def execute(context):
    arguments = load_persisted_arguments(context)  # 业务方实现，不能重放时随机生成
    action = interaction_action(context, arguments)
    if action is not None:
        return action
    if context.step("read-app-result") is None:
        return ToolCallAction("read-app-result", "app.interact", arguments)
    result = context.step("read-app-result").output
    # completed 与 cancelled 必须分支处理，再继续自己的状态机。
    return continue_workflow(context, result)
```

Harness 若没有接入 Agent 的等待、恢复和 Interaction UI，不能只把名字加入工具表就宣称支持。应选择复用 AgentRuntime，或者明确实现持久等待、取消、恢复和结果读取。纯后台、无 UI 的运行方式必须在发起交接前定义用户从哪里处理待办，或明确报告不支持该能力，不能永远阻塞。

## 6 App 前端怎样接收和返回

Shell 通过现有 Bridge 传递导航提示，API 位于 [base.html](../web/templates/base.html)，宿主处理位于 [shell.js](../web/static/js/shell.js)。

```javascript
// 原 Agent 卡片打开目标 App。
await window.ai2appsShell.openHandoff(runId, interactionId, false);

// 目标 App 返回原界面；这一步本身不会提交完成结果。
await window.ai2appsShell.openHandoff(runId, interactionId, true);
```

目标 App 监听 `ai2apps:host-context`，读取 `event.detail.appInteraction`：

| 字段 | 用途 |
| --- | --- |
| runId、interactionId | 查询服务器上的交接记录 |
| returning | 是否回到原工作区 |
| sessionId | 返回时由服务器 origin 决定的原 Session |
| miniAppId | 目标是 Mini-App 时由注册表决定的入口 |

提示不是授权。目标前端必须先 GET `/v1/platform/agent-runs/{run_id}/interactions/{interaction_id}/handoff`，检查返回的 `target.app_id`、`target.mini_app_id` 和 `status`。返回结构含 `origin`、`parameters`、`response`。原 App 恢复时也从这个接口确认 Session，不信任模型或页面自带的返回 URL。

目标 App 应提供三个清楚的行为：

- 完成并返回：先调用目标后端完成接口，成功后 `openHandoff(..., true)`。
- 暂时返回：只导航，保留 pending 任务和业务草稿。
- 取消交接：明确提交取消。关闭页面、刷新、切换 App 不应等同取消。

原 App 加载原 Session、重新观察原 Run 后，调用 `acknowledgeHandoff(interactionId)` 清除单次返回提示，避免以后打开 App 时又跳回旧会话。普通业务完成事件不得自动抢走用户当前焦点。

Shell 导航意图使用 sessionStorage；真正任务状态在后端。整页刷新已有覆盖，不应把“浏览器存储永远保留”当成恢复条件。新窗口或存储丢失后，应能从原 Agent 的 pending 交接卡片再次打开目标。

前端异步回调要保存本次交接引用，并在更新 UI 前检查其仍是当前交接。不要让旧请求覆盖用户后来打开的另一个任务；按钮应防重复点击，但服务器仍必须幂等。

## 7 后端完成适配必须做什么

后端是业务完成的唯一可信边界。新能力至少需要“读取当前进度”“按交接创建或更新业务资源”“完成交接”三个行为，可复用现有 API，不要求统一的新 URL。

处理顺序：

1. 通过当前 principal 验证 Run 访问权限。
2. 调用 `require_handoff` 并限定自己的 capability。
3. 验证注册版本、目标标识、pending 状态、期限和原 Run 仍在等待。
4. 读取该 owner 与该交接关联的业务资源，不能仅凭客户端传入 resource ID。
5. 检查业务完成条件，从存储生成有界的结果快照。
6. 调用 `respond_interaction`，传可信服务端 `app_interaction_capability`。
7. 唤醒 `agent_runtime`，返回已持久化结果。

创建过程存在模型规划等长等待时，等待前后都要复核交接；用户可能已取消任务。业务写入与完成提交不能跨数据库原子提交时，用持久幂等关联恢复：重试先查业务结果，再补交接，不重新创建。

当前通用结果外壳为：

```json
{"status": "completed", "result": {"resource_id": "server-verified-id"}}
```

`resource_id` 是说明性字段，各能力可定义自己的结果。平台当前只约束 `result` 为 object，**没有每能力专用 result_schema 自动注册机制**；新增能力必须在完成适配器里明确验证并记录结果结构。不可把未来设计字段误写进现有 descriptor。

取消使用精确外壳：

```json
{"status": "cancelled", "result": {}}
```

通用 `/interactions/{interaction_id}/respond` 对 App 交接只允许这一取消结果；成功完成必须走可信目标适配器。不要为了复用接口开放前端任意提交成功结果。

完成后重复点击必须返回已保存快照，不能用最新内容覆盖旧结果。取消、超时、原 Run 停止或能力版本不匹配时，不能恢复任务或声称成功。取消交接不代表自动删除此前创建的业务资源；清理策略必须在产品中明确。

## 8 情报中心参考实现

参考 [intelligence.py](../api/intelligence.py)、[intelligence.js](../web/static/js/intelligence.js) 和 [Store](../intelligence/store.py)。实际路由在 `/v1/platform/intelligence` 下。

| 接口 | 行为 |
| --- | --- |
| POST /channels?handoff_run=…&handoff_id=… | 带交接创建频道，普通创建仍可不带参数 |
| GET /handoffs/{run_id}/{interaction_id} | 找回已创建频道，支持刷新后恢复 |
| POST /handoffs/{run_id}/{interaction_id}/complete | 从服务器读取频道和文章快照，提交并唤醒原 Run |

频道 ID 根据 owner 和 interaction ID 的 SHA-256 前 32 位确定；Store 在事务中复用已存在记录。该策略是频道实现细节，其他 App 可以用独立关联表，不应盲目复用同一 ID 算法。

完成结果为 `channel`、`articles`、`article_count` 和 `note`。最多回传 30 篇，每篇标题最多 300 字符、摘要最多 2000 字符、最多 10 个来源记录。`article_count` 是频道实际文章总数，可能大于本次返回数组长度，Agent 不能宣称已总结全部文章。

创建频道后就可以返回；当前不会强制等待采集完成。数组为空时 Agent 必须如实说明。用户要求“采集后生成简报”的完整流程，应在采集完成后点击返回；需要更严格完成门槛的新增能力，应由后端检查 job 状态，而不是仅禁用按钮。

原 Run 继续时会把已提交结果放入原 Tool 调用链，然后生成简报。2026-10-17 实机验证了创建、真实采集 10 篇、临时返回、刷新恢复和回到原 Run。后来同一 Session 的后续 Run 验证了输出预算修复：请求 8192 tokens、输出 1357、finish_reason=stop、10 个来源链接均匹配原结果。两次 Run 的验证范围不同，不能描述成一次重新执行全部链路。

## 9 Mini-App 的额外对接工作

Mini-App 使用 `app_id` 指定宿主，`mini_app_id` 指定宿主内入口。Shell 负责打开宿主并传递身份，**不会自动为任意 Mini-App 建立可用的交互工作区**。

宿主必须实现以下步骤：

1. 校验服务器返回的目标确实属于自己，Mini-App 当前已安装、启用且可信。
2. 用已有认证 mount broker 打开该入口；不得从参数拼 iframe URL 或把平台凭证交给子 frame。
3. 把必要业务参数和有界交接上下文通过现有受控 Bridge 传给目标入口。
4. 由宿主或可信后端校验结果。Mini-App 发出的“完成”消息只作为候选通知。
5. 用 mount、实例和交接身份验证消息来源，拒绝同源兄弟 frame 或旧 mount 冒充。
6. 持久化草稿与交接关联；恢复时重新取得授权 mount，不能复用过期凭证。
7. 统一处理完成、暂返、取消和错误；入口不可用时清楚提示，禁止默默落到宿主默认 Mini-App。

Package 隔离、opaque frame、Profile 和资源授权规则保持有效。不能用这套机制授予第三方 Package 注册可信 Python handler、访问任意 Session 或控制其他 App 的权限。

Studio 开发必须同时遵守 [Studio Mini-App Package 合同](../../docs/ai2apps-studio-mini-app-package-contract-v1.md)。Voice Studio 仍使用宿主统一的 Preview & Output，Mini-App 不应新增自己的播放、下载和历史系统；交接结果引用宿主输出资源，不能把 Line 私有缓存或参考材料当成可删除的输出历史。

浏览器能力遵守 [浏览器控制架构](../../docs/ai2apps-browser-control-architecture.md)：使用认证、绑定身份的 BiDi Gateway，提取和稳定性助手放在客户端 SDK；不得暴露原始调试端口、bearer 凭证或新增平行浏览器控制协议。

## 10 失败恢复与版本管理

| 场景 | 预期行为 |
| --- | --- |
| 刷新目标 App | 从交接进度找回资源，不能重复创建 |
| 暂时返回原 Agent | Run 仍等待，用户能再次进入目标 |
| 提交完成后跳转失败 | 已完成结果保留；可重新返回原会话 |
| 完成请求网络超时 | 查询交接状态并重试幂等完成，不假定失败 |
| 原任务被取消或期限到达 | 拒绝新完成，不复活 Run |
| 两个窗口同时完成 | 一个结果被持久化，两端读取同一结果 |
| 能力卸载或版本改变 | 明确不可用；不能按新语义执行旧请求 |
| 用户或 App 身份不匹配 | 拒绝读写，不泄露对方资源 |
| 模型输出被截断 | 保留内容并标记不完整，不展示普通成功提示 |

`InteractionCapability.version` 与保存的请求版本必须相同。当前没有自动迁移等待中交接的实现。升级不兼容能力前应保留旧适配器兼容路径或明确结束旧任务，不能只修改版本然后宣称无缝恢复。

当前 General Agent 在无本地 tokenizer meter 且未显式设置上限时使用 8192 tokens；显式 max_tokens/max_completion_tokens 和本地 meter 预算仍保留。8192 不是无限输出保障，应继续限制结果体积、检查 finish_reason，并对长报告采用分页或 artifact。

## 11 升级已有 App 的实施清单

按以下顺序改造，每步保留原手工使用流程：

1. 盘点业务操作，标记只读、写入、长任务、必须交互和已有权限边界。
2. 抽出 UI 与自动化共享的业务服务；消除只在前端存在的关键校验。
3. 为适合后台的操作补 Tool 描述、输入输出 Schema、handler、权限、超时和幂等。
4. 需要多步自治时注册 Agent，接入预算、持久状态和取消；不要把所有操作都升级成 Agent。
5. 为必须交互的部分注册 capability、实现后端资源关联与完成适配。
6. 普通 App 接 host-context；Mini-App 同时补宿主 mount、消息验证和结果所有权。
7. 补前端入口、返回行为、空结果与错误提示；原有直接打开 App 的流程不能要求交接 ID。
8. 执行下面的自动化和真实验收，保存证据并更新 Desktop release ledger。

新 App/Mini-App 从第一版就应交付一份能力清单：稳定 key、形态、Schema、结果结构、权限、副作用、幂等策略、超时、版本兼容、是否支持无界面运行、宿主和支持的调用入口。能力文档与代码一起评审。

## 12 验收标准与命令

新增能力至少覆盖以下行为：合法参数、非法参数、缺失资源、跨用户拒绝、原 Session 保留、重复创建、重复完成、并发完成、取消、过期、原 Run 停止、能力版本变化、刷新恢复、普通非交接入口、结果过大和空结果。

Mini-App 增加：宿主匹配、入口卸载、旧 mount 消息拒绝、兄弟 frame 冒充、共享输出选择和返回原会话。宿主只传 miniAppId 的单元测试不能代替实际 mount 验收。

当前相关测试从 Git checkout 根目录执行，避免在 ai2apps/ 中运行 Python 导致本地 secrets 包遮蔽标准库：

```bash
.venv/bin/python -m pytest ai2apps/tests/test_app_interactions.py ai2apps/tests/test_agent_output_budget.py -q
node --test ai2apps/tests/app_handoff.test.cjs
```

真实验收必须记录：发起会话、原 Run 与 Interaction、目标业务资源、完成结果、恢复后的 Run/Session、模型 finish_reason、来源或 artifact。验证完整链路，而不只看 HTTP 200 或 Completed 标签。不要在验收文件保存令牌、Cookie、密码或 mount 凭证。

App-Dev 的静态资源刷新生效，Python 变更按标准 Helper 重启流程激活；涉及 Runtime、Swift 或 AceFox 时按固定 builder 重建。激活必须核验 App/Helper source-root、运行时导入路径和实际 served asset；不能复制到旧 snapshot。参见 [App-Dev 环境](../../docs/ai2apps-app-dev-environment.md)。

本次现有证据：

- [真实交接与最初截断记录](app-composition-20261017/live-handoff-evidence.json)
- [8192 输出预算真实复验](app-composition-20261017/live-output-budget-retest.json)
- [交接后端回归](../tests/test_app_interactions.py)
- [Shell 和 Chat 回归](../tests/app_handoff.test.cjs)
- [输出预算回归](../tests/test_agent_output_budget.py)

## 13 开发评审时必须明确的边界

当前支持可信注册能力、General Agent 持久交接、目标 App 验证完成、返回原 Session、Mini-App 目标身份携带，以及新闻频道的完整业务适配。

当前尚不提供任意 App 自动转 Tool、任意 Package 自动注册可信能力、所有 Mini-App 的通用挂载完成适配、每能力自动 result_schema、能力热卸载迁移或所有 Harness 的通用交互 UI。需要这些能力时，先设计对应平台扩展与兼容策略，再让 App 依赖它们。

交付一个接入时，应能回答：模型看见什么能力、参数怎样校验、谁拥有结果、用户在哪一步参与、页面关闭后任务在哪里、如何回到同一个任务、重复请求会不会重复写入、升级后旧交接怎么办。所有答案都应落实为代码和测试。

## 15 Chat 内的参数表单（音频转写首个适配）

`app.collect_parameters` 用于不需要离开 Chat 的参数收集，和打开业务工作区的 `app.interact` 并行存在。当前注册了 App 能力 `voice.transcribe` 与 Mini-App 能力 `voice-design.transcribe`（宿主 `ai2apps.readaloud`，Mini-App `ai2apps.audio.voice-design`）。它们复用同一个 Host 音频转写适配器，并不加载 Mini-App frame。

模型可以发出：

```json
{
  "request_id": "transcribe-1",
  "capability": "voice-design.transcribe",
  "initial_values": {"language": "auto"}
}
```

模型只能选择可信注册的 capability 和预填业务值，不能生成任意脚本、URL、权限或安装计划。真正的参数描述来自 `agents/parameter_forms.py` 中的 `ParameterForm`，由服务器交给 Chat。一个简化的字段描述如下（完整 Schema 仍由服务器验证）：

```json
{
  "fields": [
    {"key":"audio","type":"asset","label":"音频素材","accept":"audio/*","sources":["file","gallery","microphone"]},
    {"key":"language","type":"select","label":"语言","default":"auto","options":[{"value":"auto","label":"自动"},{"value":"zh","label":"中文"},{"value":"en","label":"English"}]},
    {"key":"model","type":"model","label":"转写模型","capability":"audio.speech_recognition"}
  ]
}
```

字段默认值先应用，模型的合法预填值覆盖默认值；已保存的用户草稿拥有最高优先级。用户可以修改预填值。`text/number/boolean/select` 是基础渲染类型，`asset/model` 是高级类型。现有高级适配仅实现单个音频素材、语音识别模型，不能将它当作已支持任意文件、图像、视频、多素材槽或任意模型任务的接口。

### 生命周期与安全边界

1. General Agent 识别控制工具，创建 `control=parameter_form` 的持久 Interaction，Run 进入 `waiting_input`。
2. Chat 通过 `/v1/platform/agent-runs/{run}/interactions/{interaction}/parameters` 读取描述与草稿。父 Run 和 delegated child 都能渲染。
3. 每次编辑通过 PUT 保存 `{revision,values}`。并发旧版本收到 409，不能静默覆盖。刷新或 Local 重启后读取同一草稿。
4. Finder 文件选择/拖拽、素材库拖拽和录音都保存到 Host 私有 VoiceMaterials，参数只保留素材 ID。素材库导入验证所有者；不把用户输入加入 Voice Studio 的生成输出历史。
5. 模型候选来自当前已安装、checkpoint ready 的 audio_stt 声明。最终提交时服务器再次验证候选和素材权限，不能用手填模型 ID 绕过检查。
6. 点击提交时调用可信后端适配器。音频先解码为 16kHz WAV，最多 600 秒，上传最多 64 MiB，再通过 ModelInvocation 执行实际转写。
7. 适配器再次检查 Interaction 与草稿未变更，保存完成响应并唤醒原 Run。模型收到 `{status:"completed",result:{parameters,text,note}}`；转写文本是不可信内容，不是新的系统指令。通用 `/respond` 不能伪造成功结果。
8. 取消使用明确的 `cancelled` 响应。重试已提交的请求返回原响应；进程内并发提交被串行化。若在推理中重启 Local，推理可能重新执行，但持久 Interaction 只恢复原任务一次。

### 模型安装与返回

音频首个适配从服务器提供 Chat 的 `audio.speech_recognition` 安装意图：`actionId=parameter-form:{interactionId}`，`resumeToken=interactionId`，`completionPolicy=configure_only`。安装前等待草稿保存。安装后重新读取模型列表，确认 ready 后 acknowledge；不自动执行转写，用户仍需明确提交。

普通 Chat 语音设置和参数表单必须按各自 actionId 恢复 ACPF，不能仅按 capability 恢复，否则普通语音设置会提前接管表单的安装会话。Runtime 升级及重启继续安装仍由原 ACPF orchestrator 与 durable session 负责，表单不能清理或替换其记录，也不能把 Local 已重启当作能力安装成功。

SenseVoice 除识别权重外，还要求标点恢复模型。其可信安装计划采用已有组件栈，按 Runtime、两个 Provider、两个 Checkpoint、验证的顺序运行，避免主模型已下载但整体一直无法 ready。

### 新 App/Mini-App 如何接入

当前是进程内可信注册表，不是任意 Package 自动加载参数 JSON 的扩展点。新增能力必须同时增加：

- 明确 app_id、可选 mini_app_id、稳定 capability、version、严格 JSON Schema 与字段描述。
- 与该能力匹配的 Host 业务完成适配器及模型/素材候选验证。当前 `/submit` 只接受两项音频转写能力；仅注册一个新描述不会自动获得业务执行能力。
- 可信安装配置。不能让模型或未受信 Mini-App frame 指定 Package 地址或任意安装计划。
- 默认值、用户覆盖、跨用户拒绝、并发 revision、取消、重复提交、刷新/重启、安装返回的测试。

需要复杂编辑或 App 专属界面时继续使用 `app.interact`；简单问答可以使用现有 `agent.ask_user`。不要为了表单统一而把所有业务 UI 搬进 Chat。

## Capability 多提供者路由（2026-10-18）

`image.generate` / `image.edit` 是 Agent 调用的能力入口；具体 App/Mini-App 是
provider。内置 Imagine Mini-App 的声明位于 `images/capabilities.py`，同一声明同时
驱动 Studio catalog 的 `agentCapabilities` 和启动时的可信 adapter 注册。声明能力
不等于获得执行权限；仍经过 Tool schema、授权与 Mini-App 所属 App 的访问检查。
Package 自报 JSON 不能注册任意 Python handler；第三方 Package 动态注册尚未接入。

当前提供者：

| 能力 | Provider | 实现 |
| --- | --- | --- |
| image.generate | ai2apps.images.generate | 既有 App 图像 Tool |
| image.generate | ai2apps.imagine.text-to-image | 文生图 Mini-App，Studio durable job |
| image.edit | ai2apps.imagine.image-edit | 修图 Mini-App，Studio durable job |

宿主以 `CapabilityProvider(id, capability, app_id, handler, mini_app_id, priority,
version)` 注册可信实现。能力入口统一校验参数，同一能力的所有 provider 必须接受相同
语义，且不得扩大入口声明的权限/副作用。修图必须提供当前 Session 的 `artifact_id`；
不可用重新文生图替代修图。Mini-App 结果同时保留 Studio 输出，并将真实 artifact
导入调用方 Session，Agent 展示返回的 artifact URL。

路由状态持久化在 `capability_provider_health`，按 actor、installation、capability、
provider、version 隔离。先选择最近成功且不在冷却期的 provider，其次按 priority。
默认冷却 300 秒；重启不清除成功偏好，adapter 版本改变不会继承旧版本健康记录。
结果的 `provider` 与 `provider_attempts` 可用于诊断实际选择和切换。

只有 adapter 明确抛出 `ProviderUnavailable`，保证**尚未提交业务操作**，才会记录
临时不可用并尝试下一 provider。参数错误、用户拒绝、超时、未知失败和已提交的任务失败
不自动重做，以免重复计费或绕过用户决定。持久任务使用 Tool invocation ID 作为幂等键；
轮询超时不会取消或重新提交已有 Studio job。原调用重试应复用 invocation ID。
所有 provider 都不可用时返回失败，不能声称已生成图片。

验证：`tests/test_capability_routing.py` 覆盖冷却、成功偏好、重建路由后的持久化、
actor/installation 隔离和禁止不安全切换；`tests/test_image_capability_providers.py`
运行真实 Runtime/Studio 队列、输出存储及会话导入，但推理响应为测试 PNG，故不代表
真实 Cloud 出图验收。后者还验证 Mini-App 修图传递原图及禁止访问另一 Session 的原图。


### 真实 AaAT 验收（2026-10-18）

本轮从 App-Dev Agent Chat 发起，非直接调用图像推理接口：

- 修图 Run `run_dd1c02b11c454f28aa4e00fdea4d3654`：`image.edit` 路由到
  `ai2apps.imagine.image-edit`，Studio Job `stjob_81d74845e3e74ce39a590058157d2042`
  成功，将原会话红杯图片改为蓝杯，产物 `art_c99ace339fd441fb838b64548af3d74d`
  回到原 Agent。详见同目录 `app-composition-20261018/run_dd1c02b11c454f28aa4e00fdea4d3654.json`。
- 故障切换 Run `run_0ba80de5e203492daba2a958eafe3582`：仅对指定 App-Dev 验收
  会话临时注入旧 App provider 的 `ProviderUnavailable`，位置在任何请求提交之前。
  实际 attempts 为 `ai2apps.images.generate: unavailable` →
  `ai2apps.imagine.text-to-image: succeeded`。后者执行真实 Cloud 推理及 Studio
  Job `stjob_45a6a16e5e784453b7151c3abd6e8c83`，输出绿色杯子图片
  `art_09e453fb26704746b0689734aaabc84a`，795642 bytes。故障是可控注入，成功图片
  不是 mock；不可将其表述为自然 Cloud 服务故障。注入已从源码删除。
- 上述结果均包含 `mini_app_id`、`studio_run_id`、`studio_job_id` 和 Chat artifact，
  是 Mini-App 的 AaAT 路径；此前 `ai2apps.images.generate` 直接出图只算旧 App Tool。

- 成功偏好复验 Run `run_8d4a5aa2bdbb4f5b8b8a54a117aad35a`：已移除临时故障并标准重建、重启 App-Dev，旧 App 冷却于 19:29:01 UTC 到期；19:29:10 UTC 发出下一次请求。只有 `ai2apps.imagine.text-to-image: succeeded` 一次 attempt，真实生成黄色杯子 `art_5d9a2aed4a144a9fb94dce13da344350`（705599 bytes）。证明成功偏好跨进程保存，且不是依赖旧提供者仍在冷却。三个真实 Run 的完整 Tool 输出保存在 `app-composition-20261018/`。
- 当前验收：32 项 Python 回归、2 项 Shell 启动请求超时测试通过。干净 App-Dev 的签名、标准 verifier、App/Helper 源码根、运行中模块路径和 served Chat 资源均已核对，原生 Shell 正常进入 Home。上述验收只覆盖内建文生图/修图 Mini-App，不等同于第三方 Package 的任意声明可自动执行。

### Provider 参数协商契约 v1（2026-10-18）

本节更新 AaAT 参数归属：Capability 定义业务意图与公共输入/结果；每个 Provider
拥有自己的参数描述与提交前校验。不能把某个实现的固定尺寸枚举作为整个 Capability
的上限。路由提供者的注册增加两个可选、可信代码回调：

- `describe(principal, model=None)`：返回 `version`、通用 `schema`、模型列表、
  当前 `model`、`effective_schema`、`constraints`、`warnings`。
- `prepare(arguments, context)`：重新解析最新模型约束，校验并补齐未给出的默认值，
  返回执行参数。此阶段不得创建任务、推理、计费或产生业务副作用。

App 和 Mini-App 使用相同接口，通过 `app_id`、`mini_app_id` 标识归属。
参数描述来自可信宿主适配器；第三方 Package 不能仅靠声明任意 Python/JS 回调
获得执行权，仍须经过现有安装、信任与适配器注册机制。

`image.generate` / `image.edit` 公共入口保留 prompt、artifact_id、size、quality、format
以兼容旧调用，新增 `provider`、`model` 和 Provider 扩展参数容器 `parameters`。
扩展容器不能覆盖同一次请求中已出现的公共参数，也不能嵌套覆盖路由控制字段。
Provider 的有效 Schema 决定哪些扩展字段可接受；未知字段不能被静默丢弃。

模型枚举不是分辨率并集。图像适配器使用已安装 Model Package 的 image_capabilities、
现有 BYOK 图像目录规则及当前用户 Cloud imageOptions，按模型构造有效 Schema。
固定尺寸使用 enum，自定义尺寸同时检查宽高上下限、步长、总像素、长宽比和输出格式。
未安装模型可以展示，但 prepare 会拒绝执行。Cloud 目录不可用时兼容模式会注明限制，
不能以未获取的元数据宣称支持更多分辨率。当前图像适配器开放模型、尺寸、质量、格式、
提示词与会话原图引用；更多模型特有字段须由可信适配器明确声明并传给实际执行器。

Agent 可调用 `capability.describe({provider, model?})` 发现有效参数。
管理界面每个 Provider 的“Provider 参数与模型”使用同一描述器，选择模型仅预览，
不修改用户默认模型。检查接口受 System Manage 权限保护。

需要用户填写时，调用 `app.collect_parameters`，capability 使用 Provider ID：
`ai2apps.images.generate`、`ai2apps.imagine.text-to-image` 或 `ai2apps.imagine.image-edit`。
initial_values 可传已有参数。Chat 显示动态模型/参数表单，切换模型后保留用户输入，
将不受支持的枚举值标为需要重选；服务端提交仍重新校验所有几何约束。
表单完成只返回 `{capability, provider, arguments, configure_only:true}`，不创建图片。
原 Agent 再通过普通 image Tool 调用执行，继续走原权限、计费与会话原图所有权检查。
表单草稿使用原 Interaction 的版本化持久化与幂等响应机制；取消不等于执行成功。

兼容性与失败必须区分：`ProviderIncompatible` 仅允许从 prepare 抛出，路由记录
`incompatible`，不写健康冷却，再尝试满足同一原始请求的候选。`ProviderUnavailable`
保留原来的提交前故障/冷却语义。用户指定 provider 时不切换 Provider；指定 model、
尺寸等条件不得静默改写。执行提交后的失败仍禁止自动切换，以避免重复任务和计费。

音频表单的上传/录音和 ACPF 安装返回协议保持原逻辑。新增图像配置表单本轮不提供
安装按钮，也不消费 ACPF 的恢复记录；未安装模型先在原 App 完成安装后再刷新选择。
这不等同于已经完成“所有 Provider 的通用安装表单”或所有第三方 Package 自动接入。

本轮验证：Provider 参数、路由、图像适配器与音频表单共 17 项 Python 测试通过，
另有原 image Tool 兼容测试通过；能力树与 Chat 表单 12 项 JavaScript 测试通过。
App-Dev 真实 Run `run_619073920d374bde998c1c979f3322d7` 从 Agent 调起配置表单，
Cloud GPT Image 模型切换到本地 FLUX.2 Klein，`17x17` 被后端拒绝且草稿保留，
改为 `1024x1024` 后提交，原 Agent 收到 `configure_only` 及 Provider/模型/参数并结束。
该 Run 仅调用 `app.collect_parameters`，没有调用图像生成；完整返回见
`app-composition-20261018/provider-parameters-live.json`。

## 2026-10-18：动态能力字符串与声明驱动交互

`app.collect_parameters` 和 `app.interact` 的 capability 均为字符串，不再将业务能力枚举写入核心 Tool Schema。调用 `app.describe` 可发现当前注册的 Provider、表单和跳转能力；未知能力明确失败，不把字符串当 URL、代码或任意可执行入口。完整声明与选择后复核遵守第0节链接的当前契约。

```json
{"request_id":"unique-request","capability":"image.generate","provider":"ai2apps.imagine.text-to-image","values":{"prompt":"一只猫"}}
```

provider 可省略。表单选择遵循当前 actor/installation 的最近成功记录、优先级和冷却状态；选择结果持久化在 interaction.ui_hints.provider，后续恢复不重新选提供者。旧调用的 initial_values 以及已存在 Provider ID 形式 capability 保留兼容，但新接入使用功能 capability + provider。values 和 initial_values 不可同时提供。

### App / Mini-App 接入

- 路由 `CapabilityProvider` 提供 describe 时，自动获得共享 Chat 表单接入，不需要向核心添加业务 ID。describe 返回 effective_schema，可选 fields、models、constraints、warnings；prepare 在提交时进行最终校验。此桥接只返回参数，不调用业务 handler。
- 非路由能力通过 `register_form(ParameterForm(...))` 注册：key 为唯一提供者 ID，capability 为功能名称，app_id 为可信宿主，mini_app_id 可选。静态 schema/fields 或异步 describe(runtime, principal, form, values, item) 提供动态 schema/fields/models/install。字段可用 text/number/boolean/select/json/asset/model；音频 asset 当前使用共享上传、素材库和录音通道，其他素材传输适配仍需宿主实现，不能只声明类型就假定已支持。
- mode=configure 默认仅返回已校验参数。mode=execute 必须提供 complete 回调，由所属 App 完成业务；validate 可做素材所有权等额外检查。调用方必须处理 cancelled，不得当作成功。
- `register_capability(InteractionCapability(...))` 注册进入 App 操作的声明。目标 app_id/mini_app_id 必须来自可信注册，模型不提供跳转 URL。目标 App 仍需实现经过授权的完成适配器，不能仅注册名称就声称支持业务。
- 可信宿主/Package 生命周期负责注册与撤销；本次没有新增任意第三方 manifest 自动执行器。平台注册不能由用户表单或模型 JSON 注入。

### 参数解析与恢复

表单 GET 返回 descriptor、values、missing、invalid。missing 从有效 Schema 的 required 计算；invalid 来自服务端 JSON Schema 校验。保留无效的已有值供用户修正，不因初始参数不完整拒绝打开表单。默认值只补缺失字段，不能覆盖 false、0 或用户显式选择。动态 Provider 根据当前模型返回有效约束；前端编辑后重新加载配置表单，提交再次校验。

原 request、版本、App/Mini-App、选定 Provider、草稿 revision 与原 Run 绑定。旧持久化请求不改写；Provider 版本不一致的新交互拒绝继续而不静默改用其他提供者。转写适配器迁移至 readaloud/parameter_form.py，新闻声明迁移至 intelligence/agent_interaction.py。ACPF 的 actionId、resumeToken、configure_only 安装完成策略保持原值；恢复安装只更新模型列表，不能自动提交或重复执行业务。

静态声明示例（可信宿主启动时注册；不改核心枚举）：

```python
from ai2apps.agents.parameter_forms import ParameterForm, register_form
register_form(ParameterForm(
    key='example.slides.compose', capability='presentation.compose',
    app_id='example.studio', mini_app_id='example.slides',
    schema={
        'type': 'object',
        'properties': {
            'title': {'type': 'string', 'minLength': 1},
            'pages': {'type': 'integer', 'minimum': 1, 'default': 3},
        },
        'required': ['title', 'pages'], 'additionalProperties': False,
    },
))
```

省略 fields 时从 Schema 自动生成字段；通过 fields 可声明音频素材槽或模型控件。表单提交结果包含 `user_confirmed: true`，表示用户已提交参数，不是再次请求相同参数确认；它不替代随后业务 Tool 的正常授权检查。此次真实绘图验收曾出现聊天模型重复询问，已补充上述返回标记及 Tool 说明，但模型仍可能偏离指令，不能承诺仅凭描述消除所有重复询问。

### Imagine Studio 参考图能力（2026-10-18）

| Mini-App Provider | Capability | 业务参数 |
| --- | --- | --- |
| ai2apps.imagine.group-photo | image.group_photo | person_artifact_ids（2–3 个不同人物图），background_artifact_id 或 background；可选 atmosphere、pose、prompt |
| ai2apps.imagine.style-transfer | image.style_transfer | artifact_id、style；可选 prompt |
| ai2apps.imagine.reference-creation | image.reference_creation | artifact_ids（1–4 张）、prompt |

均支持 Provider 的 model/size/quality/format 动态约束与 app.collect_parameters。引用必须是当前 Session 中实际存在的 PNG/JPEG/WebP artifact ID；后端逐个校验所有权、类型与大小，不接受任意路径或 URL。合影人物引用在前，背景引用在后，不能复用同一素材作为人物与背景。三者分别创建对应 Mini-App 的 Studio Run/Job，返回 Studio IDs 与导入当前 Session 的产物。

本版在 Chat 表单中用 artifact ID（多图为 JSON 数组）表示图片引用；尚未将音频素材槽的上传/拖拽控件扩展成图片选择器。适合已有 Session 图片的组合任务，不能把这称为已支持完整图片拖拽体验。合影与参考创作需要支持多参考图的模型，模型后端仍会执行自身输入限制；提交后的模型失败不会自动改用另一提供者。

Agent 的最终输出按 Tool 返回 artifact.media_type 识别图片产物，不再只识别固定的 image.generate/image.edit 名称。

2026-10-20 补充：Imagine Providers 通过所属 `agent_context` 提供素材复用与主体角色语义。用户指向已有生成/上传图片时，模型必须把真实 ID 带入参考字段；表单可以先保留少于 minItems 的已知素材，继续收集缺失照片，最终提交仍完整校验。文字中提及图片不等于已附加素材，不能在通用 AS 中增加合影或熊猫分支。诊断与验证见 [素材预填修复](imagine-reference-prefill-20261020.md)。

实机验收（App-Dev，2026-10-18）：Chat 使用真实文生图 Mini-App 生成两张虚构人物肖像，`app.collect_parameters(image.group_photo)` 带入两张 Session artifact、模型及公园背景；用户提交表单后 Agent 调用合影 Tool，得到 `mini_app_id=ai2apps.imagine.group-photo`、`studio_job_id=stjob_44800e7421f446a2b6d9ffc92484e483`、`artifact_id=art_1f359ada14b64796abe254e6a916fe3e`。Agent Run 为 `run_3dbe438b1686497581942c26ee7c3eb5`。首次尝试遇到模型将云端模型服务商误填为 AaAT Provider，以及 Cloud 504；纠正 Provider 并显式重试后成功。AaAT Provider ID 与 model 的服务商前缀不可混用。

同一 Session 的后续真实调用也成功：`run_381cab8ffc1c49e6b677d7a554bd2ced` 分别调用风格迁移（产物 `art_787cf7ec339946eaa15651e0712b4d0d`）与参考创作（产物 `art_69bad80f57074f96b62233b8ffd3ed27`）。已查看实际图片，分别为公园合影水彩版和两位人物在花园喝茶。多图消息的列表 key 改为完整图片 URL，避免同 Session 的 artifact 下载 URL 前缀相同导致渲染冲突。

### Agent 上传图片与素材引用

General Agent 将用户消息内的 PNG/JPEG/WebP data URL 原图导入当前 Session 的 artifact 存储（按内容与稳定名称幂等），模型上下文得到真实 artifact ID 和受控预览。每张原图限制 20 MiB；预览为最长边不超过 512 的 JPEG、最多 24 KiB，每个请求最多八张预览，超出时明确告知预览省略但保留素材引用。原始消息和原图字节不改写，模型不应将预览当作生成输入。合影等 Mini-App 使用 artifact ID 解析完整原图并检查 Session 所有权。该路径不抓取任意远程 URL，也不提高整体 Agent 请求字节限制。

### Tool 参数预检与自动纠正

General Agent 调用任何已注册 Tool 前，按该 Tool 的实际 input_schema 校验。按 Schema 校验结果自动删除 additionalProperties:false 明确禁止的任意多余字段，不设置字段名白名单。支持嵌套对象、数组中的对象和引用 Schema；properties、patternProperties 接受的字段及开放对象字段保留。无法确定 oneOf/anyOf 分支时不猜测，交给模型纠正。原始模型 Tool Call 与实际执行参数分别保留在 RunSteps，可追溯变更。

其余参数错误作为未执行的 Tool 错误反馈给模型，使用现有最多三次的纠正预算，不直接结束第一轮失败。不会改写已声明参数的值、猜测素材 ID、降低分辨率或改换指定模型。网关依然执行完整校验和授权；已经提交或副作用不确定的调用不通过该机制重放。

### 默认模型与显式选择（2026-10-18）

Provider 参数描述可以返回 `selection_required: true`，并提供无默认值、必填的 `model` 字段及可选模型。General Agent 在任何生成调用之前打开持久化 Chat 参数表单；提交后使用用户选择继续原调用，取消则停止。表单草稿和恢复沿用现有交互机制，不改变 ACPF/Runtime 安装恢复。

图片 Provider 不得因默认模型不在当前操作的候选列表中而选择第一个本地或云端模型。默认模型不可用、不支持当前操作或目录不可用时必须请求选择。旧 `cloud/<provider>/<model>` 仅在网关同样会使用账户 Cloud 路由（该 BYOK Provider 未配置）时匹配 `cloud/ai2apps/<provider>/<model>`；不得跨模型或跨已配置 BYOK 路由替换。GPT Image 的参考图编辑能力可由模型族补足，但显式的否定能力声明优先。

### Provider 启用状态

“设置 → 能力与工具”的 Provider 卡片提供启用开关。状态按账户及 Installation 保存，重启及 Provider 重新注册后保留；关闭不移除能力映射和历史成功记录，但该 Provider 没有路由排名，自动路由和显式指定均不可调用，参数表单选择及待提交表单也必须遵守关闭状态。重新启用恢复参与路由，仍需通过权限和依赖检查。已经提交的任务不会因此取消。

### 错误后的 Agent 决策与安全恢复（2026-10-19）

App/Mini-App Provider 应明确区分 `prepare`（尚未提交业务操作）与 `execute`。
参数不兼容用 `ProviderIncompatible`，确保未提交任务、未生成、未计费；只有明确未提交的暂时不可用才能用 `ProviderUnavailable`。
Host 保留结构化错误、Provider 尝试、所有者和调用参数，将安全错误作为 Tool result 交回 Agent，重新分析原因并选择修正参数、换可用 Provider、读取状态，或通过 `agent.ask_user` / 参数表单收集缺失信息。恢复最多 3 次，仍受 Run 步数与时间预算限制；每次是新的模型决策，不自动重放原调用。

对可能已经产生副作用的执行失败（例如生成中连接断开、超时、返回格式损坏），模型可以继续分析并使用只读查询工具，但错误标记 `outcome_uncertain`，同一 Run 禁止再次执行有副作用的操作，防止重复生成、重复计费或重复写入。没有可用状态恢复工具或不能确认结果时，应告知不确定性并询问用户。当前不能仅凭普通文字状态输出自动解除该保护；用户确认后可从新一轮请求继续。权限拒绝、取消、身份错误不会被转换为自动重试。App 应提供与原 job/request ID 绑定的状态/结果查询能力来支持后续自动恢复；这不表示 Host 已具备所有外部服务的补取接口。

Agentic Chat 与使用同一 General Agent/Runtime 的 Harness 共用以上策略；自定义 executor 的 ToolCallAction 需显式启用 recover_tool_errors，Runtime 仍会阻止未确认结果后的副作用重放。

### 参数表单的素材槽声明与调用身份（2026-10-19）

素材字段由 Provider 的 JSON Schema 声明，而不是按字段名猜测。单素材使用 string；多素材使用 array of string，并设置 minItems/maxItems/uniqueItems。素材项声明 `"x-ai2apps-asset":{"storage":"artifact","accept":"image/png,image/jpeg,image/webp"}`；数组将该声明放在 items。Host 的 schema_fields 生成 type=asset、multiple 和数量/媒体约束。旧 VoiceMaterials 音频槽及录音流程继续使用原接口，不改变 ACPF intent/resume 归属。

表单显示 Tool capability、Agent、App、Mini-App 身份，App/Mini-App 图标从可信注册声明读取。Artifact 素材槽支持 Finder 文件、Gallery 单/多素材拖放、Gallery picker 和本 Session 已有素材；显示图片/音视频预览、删除与数组顺序调整。单素材值为 artifact ID，数组值为有序 ID 列表；不要求用户编辑 ID 或 JSON。文件和 Gallery 素材先导入当前授权 Session，再保存 draft，重启后按 draft 引用恢复。新增导入接口按 Run ownership 和声明字段验证，Gallery 只读当前 actor 的素材；图片上传限制 20 MiB、支持 PNG/JPEG/WebP 并验证格式，最多 25M 像素。

App/Mini-App 应提供明确区分用途的能力说明，尤其是相邻能力（合影、修图、参考图创作）。Agent 收集缺失参数时应携带已知提示词和素材 ID；Host 不通过全局硬编码把任意请求强行改派到固定 Mini-App。表单展示的调用身份以已绑定的 Provider 为准，不静默篡改已有交互归属。

### 表单中的替代能力与 App 内继续（2026-10-19）

`CapabilityProvider` / `ParameterForm` 新增声明：

- `related_capabilities`：该 Provider 提供者认为可替代当前目标的功能能力字符串；同能力其他可用 Provider 默认可选。不同能力必须显式声明，不靠 Host 硬编码词义。比如合影与参考图创作互为相关能力。
- `switch_values(runtime, run, source_form, target_form, values)`：Provider 所有者负责迁移不同能力间的字段；Host 只保留目标 schema 已声明的字段。各 Provider 草稿独立持久化，切回原选项恢复其已有填写内容。数量超限等保留为待用户解决的约束，不静默丢素材。
- `display_name` / `summary`：可本地化的用户可读名称与用途说明。
- `continuation`：可信 App continuation adapter 的注册键。未实现 adapter 的 App 不显示可用的“在 App 中继续”按钮，不通过猜测 URL 或伪造完成结果代替对接。

Host 在填写参数时提供候选项说明、身份和 Mini-App 图标；禁用/冷却 Provider 不列为可选。选择候选项以 draft revision 做并发校验，保存新目标的 App/Mini-App/version 绑定。原始 Agent interaction 请求保持不可变，结果明确标识实际选择的 capability/provider。

App continuation adapter 注册在 `agents.form_continuation.ADAPTERS`，实现同步的 `begin`、`link`、`complete` 回调。Host 存储交接快照和目标任务绑定。`begin` 只准备参数和素材，不提交生成、不计费；Shell 仍使用标准 openHandoff 通道，目标从服务器读取。App 在 ai2apps:host-context 中接收 runId/interactionId，读取已验证的 handoff，选择指定 Mini-App，并将参数及素材填入其正常创作界面。当前 Imagine Studio 的五种 AaAT 图像 Mini-App 已接入；其他 App、Package Mini-App 需实现对应 adapter 与 host-context 消费端后再声明。

接口位于参数 interaction 下：`POST /parameters/switch`、`POST /parameters/handoff`、`POST /parameters/handoff/link`、`POST /parameters/handoff/complete`。GET 原标准 `/handoff` 可读取 origin/target，供 Shell 前往目标或返回原对话。交接期间 Chat 显示“等待 App 完成”，可以回到 App 或点击“已完成，取回结果”。交接后禁用表单本地编辑/换 Provider，避免冻结参数与 App 参数分叉；App 内草稿可继续正常编辑。

Imagine Studio 新建任务时记录 parameterHandoffInteractionId 并绑定新 Studio Run；完成检查 actor、installation、App instance、Studio、Mini-App、创建时间、成功状态和持久化素材，拒绝旧任务、其他 Mini-App 或未成功任务。返回真实产物并导入原 Agent Session，幂等提交 interaction，Shell 返回原 Session。若该表单来自一次正在等待模型选择的 Tool 调用，Runtime 以可信 App 完成记录结算该 Tool step，继续模型循环，绝不再提交一次相同生成。返回数据中的 executed_in_app 与 app_parameters 标识实际执行位置和参数。

选择、草稿、交接绑定均在 SQLite 中保留。Imagine 草稿包含 workspace 素材 ID 和交接 ID，重新打开不会重复覆盖已编辑参数。沿用既有 ACPF intent、精确 actionId/resumeToken 和 Runtime 重启继续安装机制；此交接不消费或伪造安装完成回执。App 仍必须经正常模型/权限流程由用户发起生成。

交接模型必须按实际 ID 在目标 Mini-App 的兼容模型中精确匹配；不可用时要求用户选择，不静默换供应商。指定画幅随草稿保留，不能被参考图的自动画幅匹配覆盖，包括重启恢复阶段。用户选择相关能力后，原 Agent 按实际目标 capability 和 Provider 接收结果与继续调用。

### WebAgent Mini-App 接入示例：Search All / Web Reader（2026-10-19）

`web.search` 与 `web.fetch` 是系统能力门面，分别由 `ai2apps.search-all.search` 和 `ai2apps.web-reader.fetch` 提供 Mini-App 实现。App 身份为 AI 浏览器，Mini-App 身份、提供 Package、源任务 ID 和来源 URL 随结果返回。`app.describe` / `capability.describe` 可以发现它们，Provider 可独立开关与选择。

这类 Mini-App 不要求打开前台页面才能执行。可信服务解析当前安装的声明，经过 actor/Installation/Session/Profile 校验，调用现有 WebAgent Broker 与共享任务队列。Schema、站点范围和程序来自 Package，模型只传业务参数。网页阅读器的实际调用范围进一步缩小到已经校验的公开 origin。不能为 AaAT 新建另一套浏览器控制或页面轮询执行器。

后台 `waiting_input` 必须结合 `requires_user` 判断：`browser_bidi_action` 是执行器正常等待浏览器响应，不能当成人工协助。用户协助与确认保留原任务标识，使用 AI 浏览器现有入口。只读网络工具声明 `external_read` 与 `network` 时，普通失败不会污染为“可能扣费/写入”的未知结果；带 billing、写入、发送或未知副作用的工具仍保留保守规则。

搜索合并结果保留各来源和失败列表；空结果不能冒充成功。研究 Agent 应在搜索后调用正文读取，最终引用依据正文，不以搜索摘要替代阅读。

### 展示元数据与 continuation 守卫补充（2026-10-19）

Provider 的 `display_name` / `summary` 支持字符串或本地化字典，沿共享表单桥接传递。
`app.describe` 的 forms、Provider catalog/inspect、参数表单 descriptor 均保留这两个字段；
候选列表将 summary 作为 description 返回。Search All / Web Reader 也声明中英文用途说明。

Imagine continuation 的任务归属检查包含 actor、installation、App instance、Studio、Mini-App
和交接创建时间。重复 link 同一任务允许幂等；替换任务只允许原任务处于明确终态
（succeeded/failed/cancelled/expired）。draft、queued、running、waiting_input 均不得被改绑。
回归覆盖竞争 link、complete 与 link、重复 complete 只执行一次结果适配，以及绑定前、
绑定后、成功待取回、已提交四阶段的 Runtime 重启。这里的并发保证范围为同一 Local
路由实例；未宣称多进程或导入产物与提交 interaction 之间崩溃窗口的事务性 exactly-once。

Parameter forms should distinguish missing input from confirmation of a fully
prefilled call. The host introduces the declared App/Mini-App and lists fields that
need attention; owners supply labels, defaults and validation rather than adding a
business-specific prompt to General Agent. For configure-only completion, return the
exact confirmed arguments. Shared AS reuses same-Run/version/exact-value confirmation
once through a durable interaction-to-invocation claim; changes require a fresh form.
Custom invocation policies retain ownership of their specialized confirmation rules.
See the confirmed parameter reuse section of `aaat-declaration-context-v1.md`.

## 动态发现与 Package 安装能力

该机制同样适用于 Package 中的 Tool、Agent、App 和 Mini-App：注册的 Provider
可提供静态声明，以及按当前用户返回的动态资源摘要。AS 使用相同的发现、选择、
声明复核和确认机制，不识别内置/Package 的业务身份。参考 `CapabilityProvider`
的 `discovery_context`，不要把频道或其他用户资源写入全局静态声明。

Package 接入时必须由安装器/运行适配器将已验证的能力导出映射为 Provider：
`requirements.capabilities` 表示依赖，不表示该 Package 提供了能力。动态发现须
通过现有隔离运行实例的只读协议执行，绑定 installation、actor、Session、Package
ID/版本和已授予的访问范围；不可把第三方 Python 放进宿主，不接受任意 URL、脚本、
命令或回调路径。返回资源名、摘要等仍是不可信数据。安装只注册已授权导出；升级
替换版本，禁用/卸载撤销 Provider，更新运行实例时不保留跨版本/跨用户观测缓存。
权限拒绝、超时或运行实例不可用应报告 unavailable，不能扩权或改用其他用户状态。

当前通用 Provider 钩子已实现并以任意 Package 风格身份做隔离回归；现有
`PackageRuntimeBinder` 仍只自动注册已有 Service Tool manifest，不会仅因新增一段
JSON 就自动获得 AaAT 导出、App UI 或发现 RPC。后续 Package 自动接入应在安装/
生命周期适配层补齐上述映射，不在 General Agent 添加 Package/App 特例。

### App-Chat Mini-Entry（2026-10-20）

需要嵌入业务会话、按钮 hook 或所属执行适配器时，使用统一的 [Mini-Chat 会话与按钮扩展 v1.1](app-chat-mini-entry-v1.md)。旧 Mini-App Chat v1 接口与工具控制路径继续兼容。新 UI 契约不授予执行权限，所有业务入口继续校验身份、对象、版本、确认和幂等。

Shopping Pro 的补货、日历分档和购物车确认流程见 [Shopping owner 工作流](shopping-aaat-workflow.md)。其声明、结果解释和确认守卫由 Shopping Pro 提供，共享 AS 无业务分支。

图文结果接入：在可信Provider handler返回可选 `aaat_view`，遵循[AaAT图文契约](aaat-declaration-context-v1.md)。App提供table/cards布局、纯文本列/条目、已观察的图片与原始链接。共享AS只验证、投影和持久化；Chat统一渲染。继续通过原任务机制更新进度，历史恢复不得重新提交工具。


### Mobile 客户端准备层

Mobile 复用桌面参数表单（可注入受限 transport）和 AaAT 图文视图。App 无需编写 AS 特例；图片、字段、确认约束仍由 Owner 提供。专属 App handoff 只能走原有 Owner adapter 完成回执，不允许 Mobile 直接用通用回应伪造成功。当前新 Mobile transport 未注册且默认拒绝，App 授权需等 Cloud/iOS 协议联调。参见 [准备层验收](mobile-agent-client-acceptance-20261021.md)。

### 会话图像和 Studio 归档（2026-10-21）

完整Runtime中image.generate默认走Imagine Studio文生图Mini-App；旧内置图像Provider
兼容入口复用同一Studio执行器，不再绕过任务归档。库模式无Runtime时保留原直接生成。
Imagine Studio可在明确刷新时通过所属recover-session-results接口归档旧会话图片，
校验原Run/Session所有权、完成状态、真实产物绑定和图像格式；复制为Studio拥有的逻辑
artifact，保留Chat原图，幂等恢复中断归档，已删除的归档不重建。没有新增AS业务分支。
Mobile通过通用的Run输出图片签名路由读取实际已记录artifact，原Session下载接口再次
执行权限校验；不开放任意路径/URL代理。终态任务卡片不显示未定进度条。

### WebAgent 执行核验策略

Agent Source 的 execution_policy 和 web_agent/各 capability 的
minimum_execution_policy 见 [视觉与回读契约](webagent-visual-control-recovery.md)。
可信 Local 调用方可通过 WebAgentInvocation.submit(execution_policy=...)
或 Mini-App Broker 同名参数提出 Task 策略，不能从页面文字或模型业务参数读取。
策略随编译程序保存、随嵌套调用单调继承；最低核验要求不会因调用方关闭视觉而降低。
源 Package 与内置能力使用同一声明链和执行器，无需 AS 增加业务路由。

### 近期任务与缓存恢复

App/Package 的 discovery_context 应提供当前身份授权的近期 Task 引用、用户可识别
的目标、状态、Profile、可复用结果来源及必要输入。重试不应要求用户抄写 ID。
Owner 负责缓存选择和业务复用规则；AS 负责比较当前用户意图、声明和观测，歧义才
询问任务目标。传回引用不能替代写操作确认，也不能解除结果未知的重放禁止。

Shopping Pro 的 AaAT 历史入口仅暴露 history_mode=incremental（默认）或 cache；
自动选择同一 Mini-App 实例、actor、授权 Session、Profile 的有效历史。增量读取
遇到已知订单不重读详情（即便历史价格未知）；cache 不访问订单页。完整重读只在
Shopping Pro 内进行。补货日期和建议可根据当天重新计算，不等于重新抓取订单。
明确缺货在输入之前记为 unavailable，继续处理其他商品，最终返回 partial、已核实
商品和 skipped 原因。页面布局不明、登录、渠道/数量冲突和输入结果未知仍须暂停。


### Browser Task 页面默认回收

App/Mini-App 使用现有 retain_pages 显式请求保留；默认 false。不要把某个业务动作
硬编码为永久保留页面。Shopping Pro AaAT 的购物车操作遵循默认回收；最终商品、
数量与渠道证据保存在结果里，关闭 Tab 不会清空购物车。人工协助期间任务仍在等待，
页面应保留；完成、失败或取消后通过既有 Browser Task 清理链路回收。

表单草稿也使用通用 Tool 参数清理：所属 adapter 先完成别名迁移，再按实际动态
Schema 去除未声明字段。额外字段被清理不意味着无效业务值被接受；必填、类型、
范围和 owner 校验继续执行。前端应使用服务器返回的 canonical values/revision。

### 对话内 Browser Task 人工协助

Chat 按既有 task_progress.requires_user 和 browser_task_id 显示通用任务控制，
从原 Browser Task/Agent Run 重新读取当前协助请求。打开页面通过原生受保护 BiDi
激活已记录且 Profile 匹配的 context；继续通过原 interaction/respond；取消通过
原 Task cancel。UI 不复制执行状态、不开新任务、不把 continued 当作业务成功，
也不自动批准 agent_confirmation。页面刷新后从持久任务和 interaction 恢复。

Shopping Pro 的补齐数量路径优先使用所属 DOM reader 定位的独立 increment 控件，
滚动可见并重新读取目标行后交给通用 red-box review；只有缺少确定控件时才请求
视觉选择。数量菜单（包括带 Add to Cart 文案的 quantity trigger）不能作为加一
候选。仍逐次点击并核验实际增加一件，未知副作用不能重放。

已有数量高于最低目标时，视觉核验提示必须说明实际观察数量及最低目标，不能要求
截图显示恰好等于最低目标。购物车行提供 quantity_control/row_rect 作为只读滚动锚点，
即使没有独立 increment 坐标也要先把目标数量滚动到可见区域；不改变原数量规则。


### 推荐：参数表单的语言与紧凑布局（2026-10-22）

推荐 App/Mini-App 在所属声明中提供中英文展示文案，但这不是注册或执行门禁；旧字符串声明继续兼容，不要求一次性迁移。共享表单支持字段 `label`、records 列 `label`、选项 `label` 和 `submit_label` 使用 `{"zh":"数量","en":"Quantity"}`；中文界面（含 zh-CN/zh-TW）选择 zh，其他界面语言选择 en，中文缺失时回退 en。旧字符串按原文显示。不要依赖运行时模型翻译；参数 key、选项 value、商品名称和用户内容不随界面翻译。业务错误建议由 owner 提供相应语言，当前原始服务端错误仍可能保留原文，不承诺自动翻译。JSON Schema 的 title 仍须使用标准字符串；多语言展示请通过 fields 声明。

字段可选 `width: "compact" | "medium" | "full"` 展示提示；不声明时数字和布尔字段紧凑、普通文本与选择项中等、JSON/records/素材/多选独占一行。共享渲染器按表单实际宽度换行，窄屏优先保持可读和触控空间。records 的数值列收窄、内容列保留主要空间，操作按钮独立；提交/取消位于底部动作区。宽度仅影响展示，不改变字段顺序、参数值、草稿版本、校验、确认或执行权限。此次不自动隐藏技术字段，也不引入业务名称判断。

第一方表单语言接入（2026-10-22）：Shopping Pro、Todo、Intelligence、Gallery、Knowledge、Voice、Imagine、Search All/Web Reader 已补充所属字段和选项展示文案；推荐新 App 直接声明 zh/en map。服务注册的 `field_labels`、`option_labels`、`form_name`、`form_summary` 为注册时 owner 提供的展示元数据，不参与共享执行选择或权限判断。自定义 describe 应返回带翻译映射的 fields；表单标题通过 prompt map 显示。保持 JSON Schema title 为标准字符串，保持参数 key/value 稳定。不要拼接中英标签、运行时让模型翻译参数或按业务字段名在共享渲染器中添加字典。

社交账号查看 owner（2026-10-22）：AI Browser 通过单一 social.account AaAT 提供 X、小红书、微博的平台参数及解析/确认/读取阶段。解析候选返回 handle/name/bio/url/avatar；选择项可提供 description/url/image 供共享表单显示身份预览，仅接受无凭据的 HTTPS URL，DOM 使用 textContent。确认凭据绑定真实候选、Session、分身、参数与声明版本；结果含原始帖子 URL、发布时间、日期时区、读取窗口及 partial 覆盖，不把置顶旧帖当今日动态，不执行关注/点赞/转发/回复。登录缺失在当前分身请求人工协助，不通过独立浏览器规避。

Social account forms can restore an omitted internal resolution reference from
completed observations in the same Session and Profile matching the requested
handle. The owner supplies the field default and observed identity choices; the
host's normal form draft/confirmation flow remains unchanged. A previous read
reference may follow only its persisted resolution evidence. Neither mechanism
is authority to skip account confirmation or reuse another Run's receipt.

统一社交账号入口：`social.account` 的平台参数为 x/xiaohongshu/weibo，阶段由 owner 声明解析、账号确认和读取流程。对 Agent 不再暴露按平台分拆的 Tool；旧内置 adapter 入口由通用 service 注册集合清理其可发现状态。平台、Session、Profile、实际候选、当前确认凭据共同约束读取，不互相借用账号记录。

动态读取按帖子稳定 ID 合并滚动窗口。仅同账号非置顶、非转发且可解析并按时间排列的页面末端进入日期范围之前，才确认观测到日期边界；置顶独立返回，不触发提前终止。加载停滞、未知日期、乱序、滚动/时间上限或结果截断保留 partial/stop_reason，不声称平台完整档案。小红书可在时间预算内对日期缺失笔记作限量详情回读；没有日期的条目单独返回，不推测为今日。

Social owner adapters with alternate authenticated sites must observe each home in the existing Profile and bind confirmed reading to the persisted selected origin. Never infer shared authentication from a brand name or a feed author link.

### 行程安排 AaAT（2026-10-22）

Trip Planner 分别导出 `travel.flights`、`travel.hotels`、`travel.guide`、`travel.refine`，由可信 owner adapter 注册；实际执行仍走既有 Browser Task / Mini-App 模型配置与隐私路由。航班默认仅查询去程；明确选择去返两向或仅返程时才要求返回日期，酒店无需出发城市，攻略读取观光来源后总结。优化只处理当前 Session/Profile 的已完成观察，重查提案不自动执行。共享 AS 不添加旅行分支；所有能力仅查询与建议，不预订或付款。参见 [owner 契约与验收范围](trip-planner-aaat.md)。

### 本地大附件引用与模型配置交接（2026-10-23）

Desktop 原生选择器提供的原文件路径只交给受保护的 Local 登记端点；
Agent、表单草稿与对话只持有 Session 所有的附件 ID 和公开元数据。
登记不得读取、哈希或复制文件内容；使用前及长任务结束后核验来源指纹，
文件移动、替换或修改后要求重新选择。手机本地路径不能用于 Desktop：
支持引用的素材槽可流式上传一次，再登记为 Desktop 管理的引用。
小图片现有视觉输入和旧上传 API 继续兼容，不能将它们宣称为原路径引用。

素材槽通过 `x-ai2apps-asset.references: true` 显式声明支持引用。
owner 必须在自己的服务中解析 Session 附件并按需打开源文件；不能把引用
自动展开成 Base64，不能假定任意旧 Mini-App 都已支持。当前详细转写与
原生视频媒体任务接入原文件处理。普通 Chat 只为小型受支持文档按需提取
有界预览；大附件保留引用，交给兼容 App。

表单 owner 可声明 `install`（所属 App、能力、操作）以及
`configuration_required`。共享层只验证可信声明、owner、Session、版本与
待处理交互，保存草稿后通过 Shell 打开所属 App 的现有 ACPF。
Desktop 返回原对话后仅重新检查，不提交业务任务；Mobile 保留草稿并
提示去 Desktop 配置。安装、许可确认和业务执行仍是独立动作。
AS 不识别具体 App、模型名或业务字段，也不自动换模型或重试任务。

### Mobile 大附件与视频字幕（2026-10-23）

Mobile Chat 默认将附件分块上传到素材库，完成后保留 Session 引用和 Gallery ID。
共享表单的 references 素材槽可只读展示已选的自有 Gallery 素材，或把用户明确选择
的 Gallery 素材登记成 Session 引用；不得因预览读取而复制大文件。owner 负责接受
对应资源 ID、核验类型和处理前的有效性。详细转写与视频字幕 owner 都支持该约定。

Video Studio 的 `video.subtitles` AaAT 复用已安装字幕 Mini-App、持久 Studio Job、
转写与翻译及导出服务。默认导出字幕 ZIP，可选双语和烧录，不把流程移入 General
Agent。源视频最多 8 GiB 上传，现有转写处理时长上限为一小时；用户需要配置模型
时保留表单与素材，Mobile 只提示去 Desktop 配置。见
[实现与验收记录](mobile-chat-video-subtitles-20261023.md)。

通用 Mobile 文件结果为已完成 Tool output 的 `files` 列表，元素携带 artifact_id、
filename、media_type 和同 Run Session 的下载 URL。客户端只显示显式下载动作；
服务器再次验证 Run、Session、成功 Tool 记录与精确产物绑定，不能代理任意 URL。

### Chat 内配置与 Discover 推荐（2026-10-23）

owner install 声明可在 Desktop 参数交互中内嵌原 ACPF；会话由服务端绑定原 interaction
与 Provider version，刷新恢复，配置完成只重查，不提交业务。Mobile 仅观察和 Desktop
配置提示。Discover owner 的 discover.packages 只读查询现有目录，Agent 支持未知时明确
unverified，实际安装仍在 Discover；不得从 requirements 推导导出能力。当前范围与恢复
边界见 [Chat ACPF 实现记录](chat-acpf-and-discover-20261023.md)。

Cloud 1.77 接入：Discover 现在协商能力目录、验证签名 capabilityCatalog、固定安装版本与
双摘要，并在安装后观察真实注册状态。目录声明不能注册 handler；Package 隔离 AaAT
执行适配与生命周期自动注册仍未实现。见 [接入范围与验证](discover-capability-client-integration-20261023.md)。

后续实现（2026-10-23）：签名 App 定义可用 `ai2apps.app-service-exports/v1` 将目录导出绑定到明确的隔离 Service Tool；生命周期对账注册/撤销 Provider，Discover 的持久安装交接保留原 Chat Run。旧包不能仅凭目录 JSON 调用。协议、版本/权限守卫和真实/夹具验收范围见 [Package 生命周期与安装续接](package-aaat-lifecycle-20261023.md)。

Discover 双语检索（2026-10-23）：discover.packages 由 owner 使用当前对话模型生成中英文短词，分别检索并按精确 release/component 合并，保留来源与原始核验状态，分页读取身份绑定的持久快照。AS 不包含关键词或业务词典。范围、边界与验收见 [Discover 双语检索](discover-bilingual-20261023.md)。

Voice Studio 音频处理 AaAT（2026-10-23）：voice.separate 复用分离 Mini-App，
voice.replace_speaker 以 analyze/replace 两阶段复用指定角色换声 Mini-App。
实际角色、样例及源文件指纹由 owner 保存核验，换声使用权必须明确确认。
大文件与参考音频均沿用 Session/Gallery 原路径引用；结果发布至唯一共享输出，
并可将已发布 WAV 的 Session Artifact 引用交给下一步兼容能力。
详见 [接入顺序与本轮验收](aaat-expansion-roadmap-20261023.md)。

Video Studio 基础处理 AaAT（2026-10-23）：video.process 复用音频提取器与Composer
完成提取、截取、按序拼接；video.upscale 复用原有超分辨率服务及实际模型声明。
输入为有归属的原路径引用，产物为共享Output及同Session Artifact，可继续交给兼容App。
精确参数/源指纹绑定原任务，取消或未知失败不能改走另一入口重放。
限制与真实/fixture验收范围见 [接入记录](aaat-expansion-roadmap-20261023.md)。

Video Studio 视频本地化 AaAT（2026-10-23）：`video.dub` 对接现有配音翻译
Mini-App 与 Broker，单旁白语义必须显式确认，不承诺多角色保真；用户从实际就绪的
自有语音角色或临时原声克隆模型中选择，确认视频处理及声音使用权后执行。模型能力
来自声明和就绪探测，不从名字推断。翻译及缩写采用 Owner 的可信 policy，台词作为
不可信数据。AS 不承载单旁白、语言、音色或角色业务判断。

`video.replace_speaker` 先分析视频说话人并返回 JSON、观察编号及短样例，再选择
目标编号和参考音频。分析凭据绑定 actor/Installation/Session/原视频 stat 指纹与
视频工作流；音频换声记录不能用于视频。处理和发布前复核原视频、参考声音引用，
变更时明确失败。后台队列、取消、任务恢复和视频宿主共享 Output 复用原实现；
原文件不复制，仅必要解码与生成结果进入处理内存和输出。缺模型通过原参数表单
ACPF 交接保留草稿；Mobile 到 Desktop 配置。参见
[接入进度及实测证据](aaat-expansion-roadmap-20261023.md)。

视频角色换声后续验证（2026-10-23）：视频提取和分离入口保留双声道PCM，输出仍由
原混音/封装器发布；过响的新声音只调整目标轨，不能全局归一化而改变未选中角色。
codec的显式声道选项默认保持旧mono行为，AS不参与声道或混音决策。
[真实模型与保留性验收](video-speaker-preservation-20261023.md)区分像素级画面一致、
音频波形/背景指标、台词ASR一致和未评测的主观音色质量。


### Todo 状态/进度查询（2026-10-26）

Todo owner 的 `todo.search` v2 在列表实体中返回任务自身 `progress`（0–100），并支持
`progress_gt`/`progress_lt` 严格边界与 `progress_gte`/`progress_lte` 包含边界。
例如“进行中且进度超过 10%”对应 `status=in_progress, progress_gt=10`；不再为取得进度逐个读取 `todo.get`。
可组合目录、关键词、状态及进度条件；筛选在分页前执行，`total` 是所有匹配项数量，
`offset`/`next_offset` 和覆盖字段明确分页范围。进度不是子任务完成度聚合。
声明与筛选实现归 Todo owner，General Agent 和共享执行器不包含 Todo 特例。


情报新闻 AaAT 卡片的“来源”使用实际原始 URL 的 hostname（多个域名去重），不得用文章标题冒充来源；无 URL 时只回退显式来源名/平台，否则标未知。共享卡片元数据最多显示两行并省略，悬停保留全文。历史展示缓存由情报 owner 幂等修正，不改写 Run/Tool 原始证据。

新闻卡片的来源/日期列可声明空 label：共享渲染器不输出空标签，将该列值跨满元数据行并右对齐；这条规则不识别字段业务名。情报 owner 输出日期到日（YYYY-MM-DD），保留记录中的日期口径，原始时间戳仍保存在业务证据中。

参数确认标题由共享表单组件统一渲染为单个标题（15px 粗体，字段名 13px）。Desktop 展开参数表单时隐藏外层重复的状态标题及交互 prompt，折叠时仍显示状态标题；Mobile 隐藏重复的参数状态文案。普通授权、预算及 App handoff 提示继续使用原交互标题，不改变确认权限、草稿或提交行为。


参数表单必填提示与倒计时（2026-10-27）：共享表单始终为当前必填字段展示红色星号，空值输入框使用浅红背景（深色主题为暗红），输入后即时恢复。服务端按当前值解析顶层 allOf/if/dependent 条件必填并随草稿保存返回；表单显示不替代原 JSON Schema 与 owner 校验。数字 0、布尔 false 是已填值。

初次显示即完整且校验通过的 configure-only 表单可显示 60 秒自动提交倒计时及取消按钮；普通编辑/聚焦、表单按钮/素材操作、隐藏页面、离开、卸载、错误或配置交接立即取消。首次未填全的表单后来填好不自动启动，同一 tab 的同一交互刷新不重新启动；不持久化后台倒计时，不在页面关闭时提交。到时仍使用原 save/revision/submit 路径，保持所有权、声明版本、业务确认与幂等校验。

所属 descriptor 可设置 `auto_submit_allowed: false` 禁用计时。execute-mode、Search 工作流、等待 App/安装配置、schema 指定必须肯定确认（必填 const=true 或 enum=[true]）不自动提交。自动填写参数不代表安装、授权、同意许可或业务副作用确认；这些步骤仍走原交互。

普通 Tool/AaAT 运行批准倒计时（2026-10-27）：能力批准的可信 Runtime 根据显式 effects 生成可选 `ui_hints.auto_approve_seconds=60`。仅声明读取或本地产物的常规操作进入倒计时；未知影响、凭据/特权、进程执行、对外发送/发布/上传、删除和付款等保持手动。页面内容、模型参数不能开启该标记。Browser 的 `agent_confirmation`、预算继续和安装/许可确认不自动同意。

Desktop（含子 Agent）与 Mobile 共用批准计时组件。仅在当前可见且未过期的 pending 批准上显示“60 秒后仅允许这一次”和取消按钮。到时调用原决定接口，固定 approve + once，不选择“记住工具”或扩大资源/应用范围。操作控件、取消、页面隐藏/离开、组件卸载和运行状态变化终止计时；当前 tab 刷新不重新计时。重复快照不重建计时，错误不自动重试；服务端仍复核原交互、能力、状态、租约及幂等。

### App 内对话接入标准 v2

新 App/Mini-App 对话接入使用 [持久 App Chat 契约](app-chat-durable-v2.md)：
注册受信任 owner 的显式能力/对象范围和 UI 语义操作，使用统一 Session/Turn/快照接口。
功能 Tool 复用已有 AaAT；禁止在页面新增模型/工具执行循环。普通 scoped 调用免逐次
批准，不替代所属业务许可/确认。UI 模块不拥有后台 Run 的取消权，页面离开不取消任务。
Todo 与三座 Studio 已按此接口接入；Package 接入细则如下。

### Package Mini-App 对接（2026-10-27）

8 个第一方 Package 的 15 个 Mini-App 使用同一宿主持久 App Chat v2。Package 的
`chat` 声明仍为 v1 数据接口，提供闭合的 `update_current_draft` schema 与帮助资源。
两个版本分别描述执行生命周期与 UI 数据，不是两套执行循环。
canonical `package_mini_chat.js` 只读取声明字段/选项及有界元数据，修改前校验整个
patch，完成后调用原 draft 保存接口；拒绝函数运行、许可确认、凭据字段与任意代码。
宿主负责标准 Session、Run、system Task、固定当前 Mini-App scope 与原始共享 Output。
AI Browser Package 复用同一宿主适配器；切换 Mini-App 不扩大原 Run 的能力范围。

慢启动时仅 context 只读请求在 15 秒内重发同一 ID；invoke 不自动重发。Provider
版本或 mount 改变后重新建立桥接，不复用旧页面命令。开发源码 Mini-App 索引从
`app.yaml` 经标准构建器同一投影派生，不能维护第二份不同索引。

素材使用可核验的 Gallery/Session 引用。浏览器 File 的名称、大小和类型不是可执行
引用，必须标为 `referenceAvailable:false`，不能编造 ID 或把字节放入模型上下文。
数字人和静止时间保留当前 Gallery 拖入项 ID，owner 执行前再次核验归属。其他素材
沿用原 App 选择/引用流程；本次不把任意浏览器 File 自动转换为持久素材。

音乐、音效、歌曲、照片说话、静止时间功能导出复用原队列/模型服务。未知准入不能
自动重放。固定时长音频只接受 worker v1 字段；歌曲只接受 v2 自动时长/规划字段。
跨 Studio placement 必须显式登记所属宿主 Provider，不因同属 Package 继承其他能力。
签名 capabilityCatalog 仅供发现，不能替代宿主注册、版本与权限检查；发布 Package
也不能替代对应 Desktop 宿主升级。
