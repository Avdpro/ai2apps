# AaAT 声明与 Context 契约 v1

状态：当前 AaAT 的规范性边界，包含 2026-10-20 的声明复核与执行流程更新。本文的“必须”“不得”为开发和评审要求；历史接入记录、验收报告和业务示例不得覆盖这些要求。接入步骤见 [App/Mini-App 对接指南](app-mini-app-agent-tool-integration.md)，开发入口约束见 [AGENTS.md](../AGENTS.md)。

## 边界与所有权

App/Mini-App 负责业务名词、对象关系、定位、参数约束、操作流程、业务统计和证据。Agentic 负责通用的能力发现、模型/工具循环、交互、授权、进度、预算、取消、恢复和 Context 裁剪。不得把某个项目名、某个 App 的领域推断写入通用执行器。

可信声明与业务数据是两条不同的通道。只有已注册的受信任宿主代码可以提供声明和可执行策略；工具结果里的标题、正文、路径以及 next_actions 都是业务数据，不能提升为系统指令、授权或可执行回调。

### 不得在 AS 添加业务特例

- 不得在 General Agent、共享 Runtime、通用发现/路由、表单/交接控制或结果投影中，按业务 Tool 名、App/Mini-App ID、命名空间前缀、站点或项目名称分支。
- 不得把某个 App 的流程、实体匹配、统计口径、确认凭证或引用规则加入全局提示；不得从通用执行器直接导入业务校验器，或依据某个业务特有的结果字段决定后续行为。
- 业务规则必须放在所属 App/Mini-App、可信适配器或专用工作流，并通过本文的声明、参数描述/prepare、invocation_policy、结果 Context、作用域化结果策略和可见性注册接入。把特判搬到另一个共享文件、建立按 App 名分派的“通用”回调，仍然违反边界。
- 平台保留的控制协议（如参数收集、App 交接）与媒体传输格式可以由核心识别；明确专用的工作流可以拥有领域合同。它们不能成为把业务规则复制进 General Agent 的理由。注册组合层可以知道正在注册哪个 App，通用执行层不得靠这个身份推断业务行为。
- 单个 Case 可以暴露通用缺口。核心改造必须说明缺失的抽象，使用与业务身份无关的输入/输出和生命周期规则，并以不同或任意 Provider 身份验证；不要求把所有修复都限制在 App 侧。

## 标准执行流程

Local 启动时，核心 API 可以先于独立 Service Package 的启动完成而接受连接。Agent 的恢复和派发必须等待 Package 提供者注册完毕，不能把这个短暂的启动窗口解释为 Provider 永久不可用，也不能在窗口内自动改走其他有副作用的能力。核心 API 的 bootstrap 成功只表示基础服务可访问，不表示所有 Package 已就绪；调用方仍以当前 Service/Provider 状态判断具体能力。

1. 用户提出任务，AS 根据可用 Tool/Capability 摘要发现候选。
2. AS 比较支持范围、参数条件、副作用和结果；必要时定向发现 Provider。候选实质目标有歧义时才询问用户。
3. 选定后从受信任注册表加载对应声明/Context。执行决策必须经过当前声明与 Provider 版本复核；不兼容则重新规划，不先执行再读声明。
4. AS 按声明组织参数；App 在实际业务入口再次校验支持范围、资源归属、权限和所需确认。
5. Tool 执行；参数表单或 App 内交互可以在提交前或执行中出现，使用持久等待、进度、取消和恢复协议。模型或前端自行声称完成不能作为业务成功依据。
6. Tool 返回实际结果及业务 Context/证据；大量正文按需读取，结构化状态和范围保留。
7. AS 依据所属声明解释成功、歧义、未找到、部分完成和覆盖范围，组织最终答复或重新规划；建议下一步不等于授权。失败替代规则见本文末节。

## 可信声明

CapabilityProvider.agent_context、ParameterForm.agent_context 和 InteractionCapability.agent_context 使用同一 schema：

```json
{
  "schema": "ai2apps.aaat-declaration/v1",
  "instructions": ["App 所有的业务语义与用法"],
  "entities": [{"type":"project", "id_field":"id", "label_field":"title", "parent_field":"parent_id"}],
  "workflows": [{"intent":"定位对象并统计", "capabilities":["example.resolve", "example.stats"]}],
  "result_semantics": {"counts":"完整数据范围内的后端统计，不能用分页预览数量代替"}
}
```

注册时按严格 JSON Schema 校验，拒绝未知字段和版本，深拷贝声明，UTF-8 总长不超过8 KiB。没有声明的旧 Provider 继续工作。声明版本不替代 Provider 版本和原有表单/continuation 版本守卫。

能力目录包含 App/Mini-App 归属。`app.describe` 无筛选时提供候选摘要、参数与可用状态，完整声明按 capability 筛选读取；无参数表单的 Provider 也能被发现。

通用 Agent 首轮不投影全部 App 的完整声明。模型选定能力、发现具体目标或表单切换目标后，宿主从当前受信任注册表加载对应声明，携带 Provider ID/版本，放入系统指令区。首次调用如果其决策模型请求尚未包含相同声明和 Provider 版本，宿主记录 `tool_declaration_required` 调用前复核，不执行工具、不打开有执行效果的交互，让模型读过声明后重新规划。这一准备步骤不消耗业务失败重试额度，但仍受 Run 总步数和预算限制。没有声明的旧 Provider 继续原路径。

路由候选同一 capability 的声明一起提供以便选择；后续结果整理继续保留本 Run 已选能力的语义。独立表单和 App handoff 采用同一机制。被工具白名单排除或被禁用的 Provider 不投影。不会从 Tool 返回正文中提取指令并提升为可信声明；声明不授予执行权限。

只有已实际投影的 Provider 才参与去重；仅开放参数收集/交接控制 Tool 时，也必须加载其合法目标的声明与 Provider 版本，不因目标直接 Tool 未暴露而丢失契约。读取已经提交的控制交互结果不提交新的业务工作：必须先消费真实取消/完成状态，不能因为等待期间声明发生更新而把已提交结果替换成一次新调用规划。原交互请求、归属和版本守卫仍由控制结果入口验证。

## 执行状态与进度传输 v1（2026-10-21）

### 复用任务状态源，不建立 AaAT 第二套执行协议

已经采用 System Task 的工作只调用既有 `TaskContext.report()` 更新状态、message、
progress 与 checkpoint；继续使用 `system.task.changed`、原有持久快照、排队/取消/
重试/恢复规则。任务所属 handler 可提供一次 `progress_view` 展示投影，供任务中心、
App 与 AaAT 共同读取。App 不再额外调用 AaAT 专属回调上报同一份进度。

AaAT 持有已验证的任务引用，订阅原有通知并读取最新任务快照；其 Agent status_line
仅为对话投影，不是另一个业务状态源。System Task 的 `follow` 是只读观察，不提交、
重试或取消任务，必须校验 owner、Session identity 和所属 App。状态与终态以原任务为准。观察器必须去重相同快照，避免自身状态通知触发重复转发。

已有 Browser Task、Studio Job 等专用执行器同样保持其唯一执行权，经任务观测接口
提供相同展示快照；不能为迁就 AaAT 再包一层竞争调度的任务。尚未上报状态的持久
后台工作应在其任务执行层补齐，所有消费者共用，而不是在 AaAT 内增加业务轮询器。
简单同步 Tool 可以直接使用现有 `report_progress`，不强制创建后台任务。

Tool/App/Mini-App 使用既有 `ToolCallContext.report_progress(text, phase=..., progress=...,
content=...)` 通道。新增标准快照置于 `content.task_progress`，schema 为
`ai2apps.task-progress/v1`：

```json
{"schema":"ai2apps.task-progress/v1","state":"running","stage":"reading",
 "task_id":"owner-task-id","requires_user":false,"wait_reason":"",
 "metrics":[{"label":"已读取订单","value":3,"total":9}]}
```

- `state` 为 queued/running/waiting/completed/partial/failed/cancelled；这是所属任务的观测状态，不能修改宿主 Run/Tool 的真实终态或声称业务成功。阶段 `stage` 与外层 `text` 的业务含义由 owner 定义，AS 不按 App 名解释。
- waiting 必须明确 `requires_user` 和可选 `wait_reason`。等待网络、浏览器响应和模型响应不等于需要用户；登录、验证、确认由 owner 经持久交互处理，进度数据不授予权限。
- `progress` 可为0至1的有限数或 null；未知总工作量不编造百分比。metrics 最多8项，包含纯文本 label、有限非负 value、可选 total；不得塞入网页正文、订单详情、凭据或可执行操作。单份标准快照至多8 KiB。
- 宿主根据实际调用绑定 Run/Session/actor/Installation/Provider，沿现有调用进度、状态行、通知通道持久化和转发。状态行 revision 为宿主单调序号；客户端读取当前快照并按 revision 更新，刷新后可恢复，过期或终态后的进度不得覆盖终态。
- App/Mini-App 适配器负责将业务进度映射为该结构，须保留阶段/计数/等待原因及所属任务引用。通用等待器不得猜测 Mini-App 身份或丢弃标准快照。Chat 仅以通用文本、计数和进度条展示，不识别业务字段。
- 旧 Tool 的 phase/text/progress/content 继续兼容；迁移时新增标准快照，不要求重建独立事件总线。Package 导出适用同一协议，通过已授权的隔离实例桥接，不能用状态消息替代确认、结果或权限检查。

## 业务结果 Context（结构）

App 可以返回 `aaat_context`：

```json
{
  "schema":"ai2apps.aaat-result-context/v1",
  "status":"resolved",
  "data_trust":"untrusted",
  "scope":{"project_id":"actual-id", "mode":"recursive"},
  "coverage":{"total":12, "returned":3, "truncated":true},
  "next_actions":[{"capability":"example.stats", "arguments":{"project_id":"actual-id"}}]
}
```

状态为 resolved、ambiguous、not_found、complete 或 partial。scope/coverage 具体业务字段由 App 在 result_semantics 中解释。总长不超过16 KiB，next_actions 不超过8项，且只能指向同一 App/Mini-App 已注册能力。建议不是自动执行命令；参数与权限仍须在实际调用时重新校验。Router 在结果中附加 capability、provider、provider_version，原始 Tool invocation 继续保存 Session、Run、actor 和结果来源。

## 通用挂接点

- `invocation_policy(arguments, ToolCallContext)`：可信 Provider 的 Agent 调用前决策。返回 true 表示此调用已由 App 验证所需确认，通用循环不重复收集；false 继续原有声明表单选择。可以返回明确的输入/确认错误。该钩子不代替业务入口的授权与确认校验；直接 Tool 调用仍由业务入口守卫。
- `AgentResultPolicy`：由所属组件注册 instruction/finalize/preview 回调，并声明 capability 范围。仅在本 Run 确实调用了范围内工具后启用，不能给不相关任务施加 App 约束。回调来自宿主代码，不接收模型指定的模块路径、脚本或函数。
- 结果裁剪调用所属策略的 preview，作为有大小上限的 app_context 数据保留；原始结果仍通过同 Run 的 agent.read_tool_result 按需读取。
- `ServiceRegistry.set_agent_visibility`：所属组件声明内部工具可供哪些执行器发现。通用循环只消费该表，不识别 App 命名空间。这是目录投影，不替代 Tool/Run/Session 的执行授权。

## Todo 实现

Todo 语义与业务操作位于 `todo/aaat.py`，中央 Service 只做注册组合。无 Video Studio 或其他具体项目名称规则。

- todo.resolve_project：忽略 Emoji/装饰、大小写、兼容字符与多余空白，按完整名称、前缀及包含关系解析项目；返回真实 ID、目录/项目路径、直接子项数、后代数和匹配依据。等强候选返回 ambiguous，不擅自选第一个。
- todo.project_stats：接受真实 project_id 或用户提到的 query。名称解析与完整层级统计由 Todo 一次完成。返回 direct/recursive 两套统计、所选 scope、优先级/状态分布、已完成数和明确口径。
- todo.children：带分页覆盖度的子项目/后代查询。标题不包含父项目名称的子项目仍通过 parent_id 归属。
- 默认统计包含所有完成状态，排除已删除/归档，不计父项目自身。统计在完整自有数据集计算，不受结果预览/分页 limit 影响。
- Todo HTTP API 的 projects/resolve、projects/{id}/stats 和 projects/{id}/children 使用同一业务函数，App 与 AaAT 统计没有第二套实现。

## 多候选与失败后重新规划

不同 capability 由 AS 对照用户目标、声明支持范围、输入条件、副作用和产物选择；同一 capability 的多个 Provider 保留当前成功偏好、优先级、启用/冷却和显式用户选择规则。不为每个候选执行一次来试错。只有存在用户需要决定的实质差别时才询问；模型仍可能选错，因此业务入口必须按参数 schema/prepare 再次校验支持范围。

Provider 明确在提交前报告 incompatible/unavailable，可在其声明范围与现有授权内换 Provider，或者由下一轮模型考虑其他 capability。权限拒绝、取消、登录和确认不能通过切换路径绕过。未知执行失败会返回 outcome_uncertain；通用执行器和 Runtime 拦截后续有副作用的调用，先以只读工具查状态或告知用户决定，不能把超时当成未发布。Web Use 是否能用于发帖取决于其实际声明、授权和执行约束，不是发布 Tool 失败后必然可用的后门。

表单/交接等待继续使用 Run/Session/actor 归属、版本、取消和重复完成守卫。configure_only 的返回参数用于下一次工具调用；executed_in_app 的完成结果不再重复执行。结果状态、scope、coverage 和 next_actions 作为数据返回模型；大正文分页时单独保留有界的 aaat_context 与 Provider 版本，不能把 partial/ambiguous 当成完整成功。业务统计、证据和结果校验继续由 App 提供；AS 不添加 Todo 或发布平台特例。

## 开发与评审准入

新增接入或修复执行行为时，变更说明和评审必须回答：

1. 规则由谁拥有？业务语义和验证在哪个 App/Mini-App/适配器实现？UI 与 Tool 是否复用同一业务服务？
2. 如果修改核心，缺少的通用抽象是什么？不认识任何业务名字时是否仍成立？不能用临时 Case 补丁代替声明或原有挂接点。
3. 发现摘要、选定声明/版本、参数与交互、结果 Context/证据是否齐全？是否正确处理表单改选目标、部分结果和已在 App 执行的结果？
4. 是否保留权限、actor/Installation/Session/Run、版本、确认、取消和幂等守卫？是否区分未提交与执行结果未知？
5. 通用机制是否有任意/不同 Provider 身份的测试，覆盖无关 App 不受影响、声明版本变化与禁止业务文本提升？受影响的交互/失败路径是否有定向回归和端到端记录？真实执行与模型/外部服务夹具必须分别说明。

不满足所有权边界的变更应修改设计后再合入，不以“先打补丁、以后抽象”作为默认接入路径。目录名或字符串搜索只能帮助审查，不能替代语义评审。

共享 Agentic、AaAT 路由/声明、交互或结果策略修改必须执行 [自动回归门禁](aaat-boundary-regression.md)：在 Git 根目录运行 `python ai2apps/tests/run_aaat_boundaries.py`，现有 CI 的 Python 矩阵执行相同入口。门禁以 AST 正向依赖图、身份分派结构检查、不同身份下的真实调度轨迹和所属策略隔离为依据，不靠业务关键词黑名单。新增共享依赖或平台保留协议必须说明架构理由并评审分类变更，不得通过业务豁免绕过失败。

自动门禁不是完整 Python 数据流证明或自然语言语义判定，仍需人工评审全局提示和通用性；不得宣称能自动证明所有未来改动符合架构。精确保护范围与局限见门禁文档。

现有通用验证入口包括 `tests/test_aaat_declaration_context.py`、`tests/test_aaat_execution_flow.py`、`tests/test_capability_routing.py`、`tests/test_parameter_forms.py`、`tests/test_app_interactions.py` 和 `tests/test_parameter_app_continuation.py`。按改动选择相关用例及所属 App 的业务回归；文档修改无需运行模型或重启 Local。

### Confirmed parameter reuse and form introduction

A submitted configure-only parameter form is a Run-owned confirmation, not a model
assertion of consent. Shared AS may reuse it for one invocation only when the
capability, selected Provider, pinned form/Provider versions and exact submitted
arguments match. Persist an atomic interaction-to-invocation claim using the
scheduler's original call key; do not replace that key or lose model/Tool result
association. Restart and replay retain the claim. A newer closed/cancelled form,
changed parameters, another Run or changed owner version cannot reuse the old
confirmation. Owner invocation policies and all normal access/effect guards remain
authoritative; this contract never grants permission or authorizes fallback retries.

The model should introduce the selected App/Mini-App and explain why user input is
needed before opening a form. The shared form also renders a deterministic summary
from trusted owner identity/schema: the target, missing/invalid fields or prefilled
parameters for review, and what confirmation/cancellation does. Default interaction
titles distinguish completing parameters from confirming them. Owner declarations
continue to define business defaults, validation and whether confirmation is needed.
Models must pass submitted arguments unchanged rather than adding optional fields.


### Conversation model defaults

Chat and Agent use independent `work_chat` and `work_agent` model routes. In the
normal profile, empty Chat and Agent routes both resolve to the current account
API default model. This is an explicit platform default, not a capability inference
from the model name. If that API model is unavailable, Agent requires a user choice
instead of silently substituting another model; Chat retains its legacy standard
route fallback only when no API default policy is available. Privacy remains isolated.
Without an API default, automatic Agent selection requires model catalog capability
flags `work_standard` or `work_complex`, together
with `tool_calling_reliable`. These declarations describe task capacity and verified
tool suitability, not reasoning effort, parameter count, provider or model name. They
are supplied by the model/Package catalog owner; missing declarations never qualify.
The configured Agent route is preferred if eligible, then eligible configured work
routes, then eligible available catalog candidates in stable catalog order. No eligible
candidate means explicit selection is required; no automatic lightweight fallback.

Explicit conversation selections remain unchanged across mode switches and are
persisted as selection provenance. Legacy saved selections are conservatively treated
as explicit. Explicit user selection may override the automatic threshold with a
notice; it does not alter permissions or Tool declaration requirements. New conversation
creation, first-send materialization, restored history and asynchronous user selection
must preserve this distinction. Model routing is platform policy, never an App-specific
branch in the General Agent. Normal and privacy default profiles remain independent.

## 动态发现 Context（2026-10-20）

`CapabilityProvider.discovery_context(ToolCallContext)` 为已注册的只读宿主适配器；
可同步或异步返回 JSON object。它与静态 `agent_context` 独立：固定声明说明业务
规则，动态观测说明当前用户可见的资源及新鲜度。General 首轮和后续规划从当前
Session 身份获取观测，只调用当前可用 Tool 对应且未禁用的 Provider；相同 owner/
回调去重。不得由模型、返回正文或 Package manifest 指定 Python callable/import 路径。

单个数据对象至多8 KiB，全部数据至多16 KiB；一轮最多8个适配器，单个至多1秒，
总等待至多2秒。异常或超限仅产生 unavailable，不反射异常内容；取消继续向上传播。
不跨用户缓存。每份观测附 Provider ID/版本、App 归属、observed_at 及 untrusted 标记。
业务内容作为标记为数据的观测消息进入模型请求，不写入可信系统声明；不能授予权限、
自动提交任务或绕过所选声明复核。真实调用必须再次校验资源、身份、版本和确认。

情报中心提供有数量上限的频道 ID、名称、主题、设置更新时间、最后采集尝试及最后
成功时间，并声明截断状态。首轮只含摘要，不含文章正文。`intelligence.news` 返回
所选频道的日期范围、本地设备时区及 UTC 偏移、已知发表时间与收录时间的区别；无已存文章不
等于全网无新闻。`intelligence.research` 经来源确认后创建一次性持久课题，复用既有
搜索准备、搜索、正文阅读及绑定引用的工作流；不创建长期频道、定时订阅或额外浏览
权限。确认须属于同一 Run/Session、Provider 版本和完整参数；较新取消覆盖旧确认。
检索词逐字保留确认值，不隐式拼接跨来源未定义的日期运算符。临时课题的回看天数
记录为请求范围；目前正文工作流不逐条核实发表日期，最终报告必须明确这一限制，
不能把请求范围冒充严格筛选结果。

## 通用图文结果视图 v1（2026-10-21）

Provider 可在成功结果中提供 `aaat_view`，schema 为 `ai2apps.aaat-view/v1`。
布局 `table` 或 `cards`，字段包括稳定 id、title、summary、columns（key/label）、
items（id/title/summary/image/url/fields）。所有文本均为不可信纯文本；不接受 HTML、
脚本、组件名或模型生成的模板。每视图最多30项、8列、64KiB；缺图显示占位，不编造图片。

App 负责业务字段、标题图/缩略图、原始链接、覆盖范围与状态说明。AS 仅验证结构并把实际
完成的 Provider 结果投影到最终消息的 `aaat_views`；记录 Provider/version/capability/step_id
作为来源。模型不能通过回答或工具参数指定视图。视图与文字结果共同持久化，历史恢复只读，
不得再次执行业务操作。旧结果无视图时继续显示文字。

视图里的链接限 HTTPS 或同源绝对路径，禁止凭据、脚本/文件/数据URL、协议相对URL。
图片由 App 绑定到已观察对象；既有授权图片接口及域名/来源限制不变。渲染器使用纯文本DOM、
无referrer图片和安全链接；图片失败只显示占位。v1只提供查看链接，不提供绕过确认的执行按钮。
后续有副作用的卡片操作必须再走已注册能力、原有权限、版本和用户确认。

进度仍使用既有 System Task/Browser Task 状态与事件；不向App增加第二套图文进度协议。
最终视图不是执行成功证明，App必须在标题/摘要/字段中准确保留partial、失败或未知事实。
购物用缩略图表格，新闻用标题图卡片属于各owner的投影选择，不能在通用AS按业务身份分支。

结构示例（业务字段来自owner，不是AS预置）：

```json
{"aaat_view":{"schema":"ai2apps.aaat-view/v1","id":"result","layout":"table","title":"结果","summary":"范围说明","columns":[{"key":"state","label":"状态"}],"items":[{"id":"observed-id","title":"实际标题","image":{"url":"/v1/platform/owner/observed-id/image","alt":"标题"},"url":"https://source.example/original","fields":{"state":"已核实"}}]}}
```

必填：schema/id/layout/title/items；table还必须有columns。可选：summary、条目的summary/url/image/fields。
列key及条目id不得重复，fields只能使用已声明列key，值是纯文本字符串。当前限制每行标题500字符、
摘要1500字符、单字段500字符、URL4096字符；错误视图必须拒绝展示并返回aaat_view_error诊断，保留已完成的业务结果和文字；不得把展示失败当作业务失败而重新执行。禁止自动
重复有副作用的工作。最终消息最多保留最近8个Provider/id视图，同一Provider/id采用最后完成的结果。

购物图片通过owner作用域的任务/商品接口读取，只接受同用户、已完成的Shopping观察任务与实际商品，
复用既有缩略图域名、大小及重定向限制；新闻普通封面使用同样文章所有权检查的专用thumbnail入口，仅取已保存封面；原微博图片接口保持原域名限制。没有增加通用任意URL代理。
源Package安装的能力使用相同返回契约和注册链，不需要AS补丁；Provider声明/版本、Session与权限检查
继续生效。历史消息有视图时按快照恢复，无视图时仍显示原文，不为补图重新调用Tool。


## Mobile 客户端适配（2026-10-21，待授权协议联调）

Mobile 展示复用同一参数表单与 `ai2apps.aaat-view/v1` 渲染器。客户端只解释平台交互种类与可信描述符，不按业务 Tool/App 名称分支。表单保存/提交保留 revision，通用回应保留 response_id；预算菜单必须等待用户选择。任务查询按已授权 Session 隔离；恢复只查询既有 Run、消息与草稿，不重建调用。

历史 App-only 授权提案已被下文 Desktop 批准的独立签名 Mobile Agent 连接替代。`web/mobile_agent_transport.py` 仍是未挂载、默认拒绝的准备模块；实际入口为 `web/mobile_agent_gateway.py`，Owner 网关仍拒绝 Agent 路径。query/Header/JS 标记不能授予权限；fixture 通过不代表生产真机验收完成。

App 专属交接仍由目标 App 完成；Mobile 不通过通用 respond 冒充 App 的完成回执。目标 App 未提供手机交接时，清楚提示在桌面完成并同步状态，不自动确认或替代执行。字段/上传使用已登记的 Owner 表单，未知交互保持等待，不放宽业务校验。


### Desktop 批准的 Mobile 连接

Mobile 授权当前采用 `desktop-mobile-agent-v1`，允许浏览器与原生 App；替代历史 App-only 提案。独立远程控制层验证 Desktop 确认、Cloud租约、代次、连接密钥及原始请求签名，再把真实 actor 注入隔离 Agent API。声明/Context 不授予此权限，AS 不判断 App 客户端类型或业务身份。旧 Owner Cookie 不扩权。实现与未完成的真机/Edge门禁见 [本地验收](desktop-approved-mobile-agent-20261021.md)。


### 一次扫码与 Desktop 能力范围（2026-10-21）

普通 App Cookie 与可选 Agent 签名授权可以在同一次扫码完成，但不得相互转换权限。
绑定 Owner/Device/Installation/connection 的 Cloud 交接与 Local 校验见
[一次扫码对接协议](desktop-mobile-one-scan-app-agent-handoff-v1.md)。Cloud 未协商时不声称
已启用组合交接。Agent 复用同一 Desktop 的完整 AaAT 注册与身份/Provider权限检查，
不按 Mobile UI 目录或 App 是否具有手机页面裁剪；Mobile UI 设备开关只控制普通 App
页面暴露，Desktop App/Provider 禁用、业务资源授权和执行确认仍生效。未注册 AaAT 的
App 不因普通 App 授权自动变成可调用 Tool，Package 仍遵守可信声明和安装注册合同。
共享 AS 不新增 App 名单、手机专用业务路由或 Owner 权限替代逻辑。

### Owner draft preparation and record fields

A trusted ParameterForm may provide prepare_values(runtime, principal, form, values, interaction).
It prepares the initial/restored draft for display before user review, for example migrating an
owner-defined legacy field alias. It must be deterministic, idempotent and read-only, return a JSON
object, preserve user intent and fail on ambiguous conflicts. It grants no authority, does not
submit a form, and cannot run after confirmation to change confirmed arguments. Generic form
submission still compares the reviewed canonical draft and revision exactly, validates the owner
schema including additionalProperties, and issues the ordinary run/provider-bound receipt.
Business alias interpretation belongs only in the owner callback.

A json field can declare presentation=records with columns of key/label/type and optional select
options or number bounds, plus maxItems. The shared Desktop/Mobile renderer edits an array of
records using those declarations. Labels/options come from the trusted owner descriptor; the
renderer uses textContent and no business field-name branches. JSON schema and owner validation
remain authoritative. Nested queued draft writes must snapshot values before later edits.

### Browser task assistance explanations

Browser execution owners may return `evidence.assistance_message` with `needs_user`.
It is bounded plain display text explaining the observed blocker, requested human
check, and completion condition. The durable browser interaction preserves the
internal `reason` separately for diagnostics; it does not present that code as an
instruction or guess authentication. A missing explanation receives a generic
request to inspect/report/cancel, without claiming a specific cause. This field
never grants authority, changes confirmation guards, or authorizes automatic retry.
UI and task progress share the existing durable interaction prompt. Owners must
avoid credentials or page bodies and distinguish uncertain effects from no effects.

Human assistance remains a waiting state in the shared Browser Task observer.
The observer forwards owner wait_reason/requires_user and continues following the
same task until its actual terminal state or original deadline/cancellation. It
must not turn a pending human interaction into a Tool failure, approve it, retry
the operation, or create another task. Completed historical Tool calls are not
retroactively rewritten when a previously detached task later finishes.

WebAgent视觉恢复遵循 [视觉控件恢复契约](webagent-visual-control-recovery.md)：
仅使用原任务模型Profile内明确声明图像输入的模型；模型选择已观察DOM引用，
红框复核后再次验证绑定并执行一次，操作后图像/DOM复核及owner业务回读缺一不可。
视觉判断不授予权限，不覆盖结果未知、不自动重放，也不替代业务确认。

WebAgent Agent/Task execution_policy 与 owner minimum_execution_policy 采用
[通用核验策略](webagent-visual-control-recovery.md)。最低要求单调合并并随嵌套调用继承；
调用方不能关闭 owner 要求的复检或结果回读。DOM/业务状态未知时可按策略用新截图
补充确认，明确业务冲突仍失败；声明不增加权限，不授权重试。此前“三阶段缺一不可”
适用于启用视觉复检的恢复路径；视觉关闭时仍保留真实结果回读。

### 提交前参数错误与 AI 纠错（2026-10-21）

通用 Capability 路由在 Provider prepare/handler 之前拒绝的重复公共/parameters
字段、parameters 类型错误及未知显式 Provider，返回 invalid_tool_arguments、
phase=prepare。Provider prepare 内的 JSON Schema ValidationError 同样表示未提交。
已有有界模型纠错把错误返回 AI，由 AI 重新生成调用；宿主不合并冲突字段、不替模型
重放，不选择另一个 Provider 来试错。重复值相同也须修正，确认与权限照常核验。

仅可信宿主报告的阶段和白名单错误码可证明未提交。handler 内抛出的同类校验错误、
超时、断线和普通 provider_error 均不享有此豁免；有副作用时仍锁定结果未知，禁止
自动重复或替代执行。历史未知结果记录不改写、不清除，新调用不得绕过未知守卫。
公共 App 适配器必须在 Provider prepare 中完成当前 effective_schema 的默认值填充与
校验；prepare 也供表单确认复用，仅校验参数与安装身份，不要求已有执行 Session；
业务 handler 保留原有 Session 要求及会话授权核验，然后执行已校验参数。不能仅因为 handler
抛出 ValidationError 就认定未执行；handler 的 Schema/回执/输出错误继续按实际执行
阶段处理。此分层也适用于源 Package 的能力声明，不按业务身份选择错误分类。

## 任务引用恢复与重试（2026-10-22）

用户说“再试一次”或改变条件时，不要求用户提供内部 Task/Run ID。所属 App 应通过
已有 discovery_context 返回有界、已授权的近期任务引用、可见目标、状态、Profile
及可复用输入/结果。AS 结合当前对话和所属声明选择；存在实质歧义时用可见任务目标
询问，不能取全局最新任务或跨 actor/Installation/App/Profile 猜测。缓存可在所属
App 授权的数据范围内跨 Session 复用；“继续哪个操作”的候选以当前 Session 为先。
引用是数据而非权限。重试采用新调用及原有确认，不能自动重放未知副作用、取消或
登录等待；原任务证据和状态保留。Package 安装的能力适用相同 Context 和所有权契约。

任务完成可以带 partial 展示状态：完成指工作流终止，并不代表所有业务项目成功。
原任务是唯一状态源；观察器保留 owner 对已完成任务的 partial 投影。执行失败、
取消、结果未知不能被 partial 掩盖。预算耗尽保留 max_steps_exceeded，并同时报告
最近有界的真实工具失败 code/message，明确这不代表最终业务结果；不得推测成功。


### Task 页面生命周期（2026-10-22）

Browser Task 默认不保留页面。所有终态（completed/failed/cancelled）回收自身和
已记录的后代弹出 Tab，根 Task 等待子任务终止和页面清理回执；复用页面只存活到
其所属 source Task 结束。保留必须通过现有可信调用参数明确声明目的，不能仅因
能力是购物车或结果可能供用户查看而自动开启；业务操作确认也不等于保留页面。
回收必须校验 Task 归属、Profile/userContext，不能采用 URL 扫描关闭用户页面。
重启后只按持久化 context ID 继续清理，不新建页面或重放业务动作。

### 表单与 Tool 参数清理一致性（2026-10-22）

参数表单复用 Tool 的 prepare_arguments，按选中 Provider 的实际 Schema 清理
additionalProperties=false 对象内未声明的字段；先运行 owner 的别名/草稿准备，
再解析动态 Schema，不能在未选定分支时猜测 oneOf/anyOf。类型、必填、范围仍严格
验证。清理后的草稿持久化并提升 revision，展示、保存和提交使用一致的确认值；
旧 revision 或未保存值仍拒绝提交。被去掉的 provider 业务内冗余值不能更换已绑定
Provider，也不能授予执行、跳过确认或自动重试未知副作用。


### 推荐：参数表单的语言与紧凑布局（2026-10-22）

推荐 App/Mini-App 在所属声明中提供中英文展示文案，但这不是注册或执行门禁；旧字符串声明继续兼容，不要求一次性迁移。共享表单支持字段 `label`、records 列 `label`、选项 `label` 和 `submit_label` 使用 `{"zh":"数量","en":"Quantity"}`；中文界面（含 zh-CN/zh-TW）选择 zh，其他界面语言选择 en，中文缺失时回退 en。旧字符串按原文显示。不要依赖运行时模型翻译；参数 key、选项 value、商品名称和用户内容不随界面翻译。业务错误建议由 owner 提供相应语言，当前原始服务端错误仍可能保留原文，不承诺自动翻译。JSON Schema 的 title 仍须使用标准字符串；多语言展示请通过 fields 声明。

字段可选 `width: "compact" | "medium" | "full"` 展示提示；不声明时数字和布尔字段紧凑、普通文本与选择项中等、JSON/records/素材/多选独占一行。共享渲染器按表单实际宽度换行，窄屏优先保持可读和触控空间。records 的数值列收窄、内容列保留主要空间，操作按钮独立；提交/取消位于底部动作区。宽度仅影响展示，不改变字段顺序、参数值、草稿版本、校验、确认或执行权限。此次不自动隐藏技术字段，也不引入业务名称判断。

2026-10-22：现有第一方 AaAT 参数表单已由各 owner 提供 zh/en 字段和业务枚举文案。`present_fields(fields, labels, option_labels)` 只复制展示元数据，不改变 key/value/schema/草稿。`ParameterForm.prompt` 与 App handoff 的 `InteractionCapability.prompt` 可为旧字符串或 zh/en map；持久交互的 prompt 保留英文兼容文本，`ui_hints.prompt_labels` 提供当前界面语言显示。Desktop/Mobile 共享语言选择规则，非中文回退英文。该能力不强制第三方提供翻译，也不把模型指令、用户内容、商品/模型名称或原始执行错误当作可翻译模板。

### AI Browser 社交账号能力（首个 X adapter，2026-10-22）

`social.account` 统一承载 X、小红书和微博，action=resolve_account 将显示名或账号 URL 解析为实际观察的候选；action=read_account 只接受同 owner/Session/Profile 的完成解析记录，并要求当前 provider/version 的持久参数表单确认。候选身份、日期窗口、原创/转发/置顶解释属于 AI Browser owner。General Agent 根据声明选择能力，不按 X、账号名或 Tool 前缀分支。跨源研究与账号时间线查看由各 owner 声明适用边界。

通用 WebAgent 的注册式 owner read adapter 只在 inspect 阶段按可信 caller_app_id 和 action 二元组派发，不执行模型传入的代码；业务脚本、站点作用域及结果解释由注册 owner 维护。与已有 BrowserTask 共用执行、Default 原生 userContext、人工协助、取消和终态 Tab 清理，不建立另一套浏览器控制协议。新增抽象由任意 alpha/beta owner 的精确派发与越权拒绝测试覆盖。

授权提示明确说明 scope 只保存到当前工具及资源范围，不把同一能力下的其他工具自动纳入授权。新账号查看流程无需走旧 browser.open/snapshot/read_article 工具链。错误结构保留在持久记录，用户摘要不再通过 str(dict) 逐层重复包装。

The registered read adapter also verifies the persisted BrowserTask owner, run ID
and registered caller before dispatch. Parameters alone cannot assert ownership.
A social retry may reference its completed read Task: the social owner follows
only that Task's persisted resolution reference in the same Session and Profile;
this supplies candidate evidence and never replaces fresh account confirmation.

统一社交账号入口：`social.account` 的平台参数为 x/xiaohongshu/weibo，阶段由 owner 声明解析、账号确认和读取流程。对 Agent 不再暴露按平台分拆的 Tool；旧内置 adapter 入口由通用 service 注册集合清理其可发现状态。平台、Session、Profile、实际候选、当前确认凭据共同约束读取，不互相借用账号记录。

动态读取按帖子稳定 ID 合并滚动窗口。仅同账号非置顶、非转发且可解析并按时间排列的页面末端进入日期范围之前，才确认观测到日期边界；置顶独立返回，不触发提前终止。加载停滞、未知日期、乱序、滚动/时间上限或结果截断保留 partial/stop_reason，不声称平台完整档案。小红书可在时间预算内对日期缺失笔记作限量详情回读；没有日期的条目单独返回，不推测为今日。

### Owner Mobile 统一授权接入（2026-10-22，待 Cloud）

`owner-mobile-unified-v1` 在 remote/web 所属访问适配层接入，默认 readiness 关闭；只有 Cloud 签名租约完整携带统一客户端绑定且目标 Local 开启后才允许精确 owner-agent 路由。旧 Owner Cookie 不扩权。复用同一 Agent router、actor、资源归属和 Tool 确认，不修改 General Agent 或声明权限。二维码确认可选择断开该 Desktop 其它客户端，Cloud 事务与撤销回执共同生效。协议及未完成联调见 [Cloud 对接需求](cloud-handoffs/owner-mobile-unified-v1.md)。

### Package 生命周期接入（2026-10-23）

Package owner 可将已签名 App-to-Service 导出绑定到实际隔离 Service Tool，注册与撤销只发生在安装/运行适配层。共享 Router 只提供按身份撤销、自有表单清理及提交前注册版本复核；共享 Service Registry 只通知受信任的绑定生命周期观察器。安装交接使用既有持久参数/App continuation，目录声明不提升为执行权限，恢复只提供安装回执与新鲜能力观测。原业务仍经过声明/版本/权限及参数确认。执行已提交后撤销不得标为 preflight unavailable 或切换 Provider。见 [协议与验收](package-aaat-lifecycle-20261023.md)。

### 显式工具授权范围（2026-10-24）

授权选择简化为仅本次、当前应用记住工具、拒绝。当前应用是发起 Session 的
App 实例，不是被调用工具所属 App 或整个 Desktop。记住工具显式提交
`resource_scope: tool`，允许该具体工具更换资源；不扩展到其他工具，策略拒绝、
Provider 版本失效及业务确认仍生效。省略该字段的历史回应继续绑定原资源，
不迁移或自动扩大旧授权。旧待审批请求不展示工具全范围选项。

### 浏览器子任务协助与确认凭据（2026-10-24）

Browser Task 可能使用所有者私有执行 Session，不能以它与 Chat Session 不同为由
丢弃协助入口，也不能因此开放任意子 Run。Chat 的 task control API 先验证原 Run
归属，再验证该 Run 的持久 Tool invocation progress 确实观察过所请求 Task、Task
actor 归属、当前待协助交互。Desktop/Mobile 只恢复原交互，不创建浏览器或新任务。
Mobile 的 owner metadata 从经授权的 Run 入口读取可信 App/Mini-App 注册信息，
不依赖另一个 Mobile App 目录连接；这些元数据不授予调用权限。

同一已确认参数调用若被持久记录为 `invalid_tool_arguments` 且 `phase=prepare`，
表示没有提交执行；原凭据可用于相同参数的纠正调用。凭据仍核验 Run、Provider
版本和参数精确匹配。执行失败、取消或副作用不确定不释放凭据。


### WebAgent Probe 与局部规则恢复

WebAgent owner SDK 的交互恢复先等待页面稳定并重新 Probe，再重试原定位；已观察到的屏外目标可在原上下文中滚动后重新绑定。原生标签和 Probe 发现的自定义 DIV/SPAN 控件同等参与生成。生成上下文携带控件覆盖摘要，显式 ref 必须属于当前所选窗口的 Probe，且未禁用、非敏感；输入另需可编辑。历史无 Probe 的 Source 保持兼容，不把陈旧 ref 作为授权。

原定位仍失败时，可由当前任务模型只选择一个允许的 Probe ref；操作、参数、站点和 owner 的候选范围不可改变。编译、fresh Probe 绑定与 native hit-test 通过后，依任务视觉策略进行标记图复核；执行一次后先回读并复核结果。视觉判断不得覆盖 owner 的明确反证。规则修正只作用于本步骤，不自动替换已发布规则。

命令回执丢失或执行后验证失败时，先尝试只读回读并记录具体失败原因，标记副作用不确定，禁止自动重放。进程恢复仅能观察原绑定上下文；原上下文不存在时明确记录不可回读，不创建新页面继续该未知操作。此机制属于 WebAgent owner/executor；General AS 不识别站点或商品语义。

### 验证后控件修正规则缓存

WebAgent owner SDK 可以持久保存已验证的定位修正提示；它不是操作结果缓存，也不是授权或动作重放凭据。缓存按 actor、浏览器分身、调用 owner、程序/步骤及精确 URL 隔离，并绑定 Source digest、generation、compiler/policy 版本、操作/参数/目标说明、站点范围和验证策略。缓存只保存结构及目标摘要；不保存跨文档 ref、坐标、页面正文或输入值。

优先发现已有缓存时，必须用新 Probe 校验完整的可交互结构和 owner 候选范围，唯一匹配当前目标，再重新编译并进行 fresh binding/native hit-test 及当前策略要求的视觉复核。规则/generation、结构、目标语义或允许范围变化即失效，之后按原定位→通用恢复流程处理。Probe 截断、缺少有界结构信息时不保存或复用。

仅操作正常返回且事后 owner/视觉验证支持成功时提交待保存提示；执行前复核本身不提交。视觉拒绝、明确回读反证或副作用不确定使相应缓存失效，禁止因此尝试第二次操作。原 action journal、Run/版本/权限/确认及取消守卫继续独立决定是否可以执行。缓存限2048条，旧条目可淘汰，不覆写原发布规则；AS 无业务例外。

### 普通只读访问与平台工具可用性

通用权限的内置兜底允许仅有 `external_read`/`network` 影响且仅请求
`network.outbound`/`browser.read` 的普通读取。明确的本地拒绝或审批策略仍优先；
写入、密钥、文件等能力不继承此默认值，访问地址与 Profile 绑定检查独立执行。
平台后端声明无法执行的传输工具应由所属服务从可用目录排除，不能依赖模型试错。
业务字段提取、原页面恢复与有界摘要由 owner 提供；AS 不识别站点或业务字段。


## 预算续额与持久等待（2026-10-26）

共享执行器在继续模型或工具调用前检查步骤与累计模型 Token 用量。达到额度时创建持久 `agent_budget` 菜单，显示实际累计用量与继续/结束选项，不以预算耗尽直接判定业务失败。继续从已使用量起授予新一轮步骤与 Token 额度；历史步骤、用量、完成结果与副作用记录不得清零或重放。结束保留已有结果。模型单次调用的 Token 于返回时结算，可能越过额度；下一次调用前必须等待用户。

预算续额不改变取消、执行超时、资源归属、工具授权及确认约束；不得依据响应中的任意数值提高额度。嵌套 owner 任务通过原有任务引用与交互守卫向 Chat 投影预算等待，不创建新业务任务或另一个浏览器。


General Agent 默认每轮步骤额度为 36（2026-10-26 起，原为 24）。显式 Run/委派额度继续作为更低上限；Token 默认额度与现有续额、权限、超时守卫不变。

### App/Mini-App 内持久 Chat v2（2026-10-27）

受信任 owner 注册显式 Tool/Provider 范围、对象校验与 UI 操作 Schema，服务端固定
Session 的注册/Provider 版本并在目录和实际派发处限制；可编辑 metadata、模型 input
与 UI 数据不能授予范围。已有 General 模型循环/AgentRuntime 执行，系统 Task 仅观察
同一 Run。范围内普通调用免逐次批准，显式 deny、业务校验和确认仍有效。
UI 操作绑定 mount/revision，待原页面应用回执，不重放未知结果。关闭页面不取消
功能任务，恢复读取原持久结果。Todo 首批迁移，其他入口不自动声称支持。
见 [统一接入标准](app-chat-durable-v2.md) 与
[420 项回归及 App-Dev 实际模型验收](acceptance/app-chat-durable-20261027/README.md)。

### Agent model declaration presentation (2026-10-28)

Conversation model projection and the account API Default alias retain the catalog's
`agent_capability_declaration.declarations`, including explicit false and unknown
values. A positive-only capability list cannot represent explicit unsupported claims.
UI distinguishes missing declarations from explicit unsupported requirements and names
the affected task-complexity or reliable-tool-calling requirement. Either standard or
complex tasks declared true satisfies task capacity; both false means unsupported;
otherwise absent/partial capacity remains unknown. This is presentation of catalog
evidence, never a model-name inference or a change to explicit selection authority.
The API defaults policy selects identity only; declarations come from that model's
catalog entry rather than the defaults-policy display name.

Missing declaration information is nonblocking metadata: Chat keeps it in an
initially collapsed, neutral model-settings disclosure. Only unavailable models
or explicit unsupported requirements appear as composer warnings in Agent mode.
Hiding this metadata from the composer does not change eligibility or evidence.

### Conversation Tool/App execution approval rules (2026-10-28)

A Core user may set a revisioned, owner-bound Session approval rule through the
explicit session rule API. Dedicated SQLite state is authoritative; imported
conversation metadata, Tool output and model arguments cannot set it. New Sessions
default to manual. Child Runs inherit the root conversation rule. Changes apply to
subsequent approval decisions; already displayed interactions retain their lifecycle.

Manual retains existing policy/leases/approval behavior. Always allows unresolved
execution-capability approvals per invocation; it does not create reusable grants,
override explicit deny or owner/license/payment/parameter guards, or authorize
uncertain-effect retries. AI reviews the sanitized proposed invocation and user goal
with the Run's chosen model, without Tools, and permits only necessary=true plus
risk=none/low. Unknown, malformed, error, stale-rule or missing-model review returns
to a manual interaction without an automatic approval countdown. Reviews are durable
internal steps keyed to exact Run/invocation/arguments/rule revision; usage counts
toward round and delegated budgets. They never enter business model transcripts.
After a new review the ordinary loop rechecks budgets before effectful dispatch.
Rule updates, review and automatic capability decisions are auditable. No owner name
or business Tool identity determines the rule.
