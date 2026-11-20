# AaAT 架构与行为回归门禁

当前入口：在 Git 仓库根目录、已安装项目测试依赖的 Python 3.11+ 环境执行：

```bash
python ai2apps/tests/run_aaat_boundaries.py
```

现有 `.github/workflows/ci.yml` 的 Python 3.11/3.12/3.13 矩阵执行同一入口。它显式收集 AaAT 用例，不依赖默认 `testpaths=tests` 能否发现 `ai2apps/tests`。该步骤在前面的普通单测失败后仍执行，取消工作流则停止。工作流接线本身也由结构化 YAML 检查覆盖。修改当前工作区不表示已经在 GitHub 执行或设置分支保护；合入后按现有 CI 触发范围运行。

## 三层检查

### 1. 正向分层依赖图

`tests/architecture/aaat_guard.py` 解析实际源代码 AST，不导入应用或执行模型。`tests/architecture/aaat_policy.json` 记录共享平台依赖的架构分类和理由，不是业务关键词黑名单。

- 所有通用 `agents/` 模块默认是受保护根，新模块自动纳入；共享 AaAT/路由/网关/能力清单是额外根。
- 沿直接和传递导入追踪依赖，包括函数内、相对和别名导入，以及可静态解析的动态导入。把业务依赖搬进另一个 helper 仍会显示完整越界链。
- 未分类的本地模块、业务所有者模块或装配/专用执行器不能成为共享 AS 的依赖。不可解析的动态导入与动态执行在被检查的共享闭包中失败，不执行它们来“试试看”。
- 专用 Browser Builder、组合入口和两个兼容导出有明确分类。兼容文件必须保持纯重导出，共享 AS 不能通过兼容文件进入业务代码。
- App/Package 注册组合层和业务 HTTP 适配器可以知道其所有者；它们不是通用 AS 执行根，但若被共享核心反向导入，依赖图会拦截。不是把整个 `ai2apps/` 都禁止导入业务模块。

只验证源代码依赖时可单独执行 `python -m pytest ai2apps/tests/test_aaat_architecture.py`；需要 pytest 和 PyYAML，不要求运行 App、GPU、模型或联网。

### 2. 结构化身份分派检查

AST 检查在共享 Agent/Service 代码中识别 Tool/App/Mini-App/capability 身份的字面量比较、前后缀、match 和固定映射分派，跟踪简单别名、常量拼接和大小写归一化。它判断的是“身份参与业务分派”的代码结构，而不是代码里是否出现 Todo、Search All 等单词。

平台保留的发现、参数收集、交接和结果读取协议在 policy 中明确列出；身份之间的动态比较、非法标识分隔符校验和正文中出现业务名称不构成业务分派。测试会确认这些正常行为不被误报。

检查器的正反例主动构造错误依赖和内联特例，要求它们失败；新增业务名称不需要加入黑名单。

### 3. 更换身份后的实际执行轨迹

`tests/test_aaat_boundary_behavior.py` 对五组不同 Tool/App/Mini-App 身份运行同一契约和同一 General 调度流程。包含随机生成的新能力名，以及先前出现过前缀特判的命名空间。断言以下行为一致：

- 首轮不全量注入 App 声明；选定后复核，未复核不执行。
- 只加载选中所有者的声明与 Provider 版本；不加载未选择的 App 规则。
- 只运行所属 invocation/result/preview 策略；准备复核不会激活执行后策略。
- 大正文保留 partial/coverage/Provider 来源；业务正文或伪造的 agent_context 不进入系统指令。
- 业务特有的结果字段不成为通用控制协议；next_actions 不自动执行写操作。
- 每组轨迹均为：模型选择 → 未提交的声明复核 → 模型重规划 → 实际 Tool 执行一次 → 模型整理并经所属结果策略验证。

统一入口还运行声明、完整执行流、路由、表单、App 交互、continuation 和通用错误恢复回归，覆盖编辑提交、取消/重复提交、等待中重启、提交前替代方案与未知副作用结果阻止再次执行。

这些行为测试使用真实 General executor、Runtime、SQLite、Gateway、Router 和交互 API；模型决定、所有者业务和外部发布是测试夹具。不调用真实搜索、发帖、付费模型或重启开发 App。

## 变更规则与限制

2026-11-21 Desktop release preflight separates the Image transport owner into
`images/cloud_gateway.py`. Image APIs and Studio jobs import that adapter directly;
the shared `cloud_gateway.py` retains Chat/Responses protocol transport. Image
background and BYOK capability rules remain under the Image owner, with unchanged
validation and provider requests. No shared-policy classification or exemption is
added. This removes the transitive dependency through shared model invocation.

新增共享模块必须在正向分类中说明平台职责，不能简单放宽到整个 `ai2apps` 或给业务模块加“临时豁免”。新增业务应在所有者注册契约和策略；修改门禁策略与保留控制协议必须与代码一起评审。现有 [AaAT 契约](aaat-declaration-context-v1.md) 的所有权要求继续生效。

这是可执行的架构回归，不是 Python 安全沙箱、完整数据流证明或自然语言语义判定器。任意反射、隐蔽数据流、未采样身份，以及全局提示里一段新增业务指导的语义，仍可能需要人工评审；不得据此宣称自动证明所有未来代码都符合边界。依赖链、结构化分派、身份不变性和所有者策略隔离互为补充，不能删除行为测试后只保留字符串/源码扫描。

## 本次验证

2026-10-20 在本地 Python3.13 通过统一入口：106项通过，50.70秒，退出码0。包含27项依赖/结构/检查器正反例/CI接线检查、5组身份变换行为检查，以及74项已有执行与交互回归。测试结束后存在既有 Metal 设备不可用的 atexit 警告；本轮没有 GPU 推理或真实外部业务验收。CI 已修改接线，尚未宣称远端三个 Python 版本已经执行。


后续素材复用修复为统一入口增加了 Imagine Provider 声明/部分素材预填及 Provider 参数集成回归，并加入任意 Provider 在声明更新期间取消交互不重开的测试。最新组合128项通过；详见 [素材预填修复验收](imagine-reference-prefill-20261020.md)。通用架构分类没有添加图像 App 豁免。

### Cloud/OpenAI 协议适配归属（2026-10-20）

Chat/Responses 的请求、工具调用、流事件与 token usage 转换属于现有共享
`ai2apps.fusion` 推理传输层，实现在 `fusion/openai_responses.py`。
它只保留和转换协议字段，不解释 Tool 名、App 身份或业务结果。
`cloud_gateway` 负责提供者解析与显式协议不兼容时的端点选择；适配器不反向依赖
Gateway。两个端点共用 `fusion/provider_errors.py` 的有界凭据脱敏。
此修正不修改架构 policy、豁免、检查器、业务证据要求或失败重试条件。

本次验证：完整 AaAT 门禁 131 项通过（68.42 秒），协议/Cloud Gateway 定向回归 27 项通过。
模型与 HTTP 为夹具，未调用真实付费 API；测试退出码为 0，退出时有既有无 Metal 设备警告。

2026-10-21 增加 Mobile Agent/Desktop App 能力范围身份不变性回归：任意两个未暴露
Mobile UI 的Provider仍复用Desktop目录与调用；显式禁用Provider仍拒绝。检查包含实际
注册表/网关行为，不以App名称关键词作为通过条件。

### E3 Hook execution guards

Gateway 和 CapabilityRouter 接受宿主注入的通用 execution_guards（visible、authorize、scope），不导入 Hook/业务 owner。此抽象补齐后台 Run 在工具发现、直接路由、真正调用及异步因果传播阶段的统一约束；持久授权和业务语义属于 Hook 及 owner adapters。AppChatOwner.context 提供动态业务资料，host-only admission 在创建 Run 同一事务登记执行来源；它们不从模型 JSON 或公开 HTTP 接收。`test_event_hook_execution.py` 用独立发布者/读取者/消费者名称、真实 Gateway/Task/Run 和 A→B→A 验证，不以业务白名单放宽架构门禁。

### E4 deterministic effect plans and monitoring

Hook actions are trusted owner adapters, not model-visible Tool grants. The Bot owner freezes explicit action registrations/versions/arguments at preview; the generic Hook runner accepts only that plan and records each step. Todo and local-notification owners reuse their existing access checks and storage; source/model text cannot select a recipient or executable handler. GeneralAgent and shared Gateway/Router gain no business branches. Per-rule serialization and unknown-result blocking preserve order across deliveries. `test_hook_actions_monitoring.py` covers actual owner writes, idempotent crash recovery, conditional evidence, partial success, pause/revocation and an unrelated unknown external-effect fixture. Read-only monitoring never claims, resumes or retries work.


### Package Hook consent

Package 签名声明只限定申请上限，宿主事务 admission 生成独立 grant；通用 ConsumerType 接受宿主 authorize/needs_details/background_capabilities 声明，执行层不判断业务名称。Package 固定处理器的元数据模式不自动获得详情 Tool。前台详情始终绑定原 event_id 与既定 AaAT Provider/version，并复用源权限检查。`test_package_hook_consent.py` 使用真实临时签名归档安装、真实 SQLite/Task/Gateway 和独立事件/详情夹具覆盖授权隔离、升级及撤销；不将夹具结果当作线上业务验收。


Package Hook 收尾回归发现参数交接中的既有 SQLite 快照升级冲突。Provider 切换、handoff 受理与绑定写入使用已有 `transaction(write=True)`，在读取当前版本之前预留写事务，保留全部版本/状态/确认检查；不重试副作用。`test_handoff_claim_reserves_writer_before_rechecking_parameters` 用真实并发写入验证事务保留，既有交接与参数表单回归继续覆盖取消、竞争绑定和恢复。


### App Chat display history cursors (2026-11-03)

App Chat adds owner-authenticated sequence cursors for display-only history (maximum50/page), incremental reads, and a state projection that omits message bodies. Existing snapshot clients retain their200-message response. Paging does not alter Agent context, execution, confirmation or Tool grants. The Bot view consumes this generic interface with stable message IDs; Todo-owned tests cover latest/older/incremental windows and foreign-session denial, alongside existing Bot and durable App Chat tests.


### Todo 串行通道（2026-11-03）

Todo 的受信任 owner adapter 可持久绑定不携带授权的 execution lane；launch 在原事务冻结，dispatch 对同 actor/lane 串行认领，等待交互占位。此为 Todo 调度能力，不在 General Agent 或 AaAT Router 添加业务分支。Messager 只在其 adapter 校验 Bot ID 并配置 lane，前台 context 只读真实任务状态。门禁增加任意 Provider lane、不同用户、重启/第二dispatcher、改绑保护与 Bot 归属/前台并行夹具；创建/启动和审批的现有确认机制保持。

### App Chat 执行级 owner 授权（2026-11-03）

会话固定接口不足以表达可撤回的执行授权。通用 owner 可成对提供 admission capture 与运行中 validate；授权快照保存在宿主私有 Run 关联表，与 Run/turn 原子写入；模型/UI/普通 Run 输入不可提供或覆盖该值。模型执行及实际调用前验证，不能因撤回后重新授予而恢复旧快照。General 的 Run-owned discovery、parameter-form 与 parameter-contract 上下文传递真实 trace_id；不添加业务身份分支。任意 Knowledge/Gallery fixture Provider 验证真实模型→工具→路由链的 Run 身份及旧快照失效，Bot owner 单独验证 profile、安全默认值、前后台分离、版本与用户隔离。旧 AppChat owner 回归保持原流程。Bot 的只读 profile 组合和字段验证留在 Messager，通用层不认识这些 App 名或业务 Tool。

### Todo 托管 owner 与固定 admission（2026-11-03）

Todo 的可信 execution adapter 将业务拥有的执行策略与通用队列分开。TaskInput `managed` 只有拒绝回退的含义；真正绑定保存在私有表，在创建事务中固定。通用 restore/finished/recover 回调只恢复原执行证据与终态，不根据业务名分派。启动回执与 Run 原子写入，备份导入不携带授权且不能退回普通执行器。

AppChatOwner 可提供 admit_run 来校验固定请求/输入，execution_origin 描述 user/task 来源；普通 UI 不能传入这些 owner 策略。任意 Knowledge/Gallery fixture provider 验证新请求被拒绝、原 request 幂等与 task 来源标签，不依赖 Bot 身份。Bot owner 验证真实提案→同源审阅→Todo→受限 AppChat→原 Interaction 的链路、权限撤回、重启写回空窗和审批 once/current 范围。现有 Todo/其他 App owner 保持原流程。

### 2026-11-03 Scoped Chat selected materials

AppChat owners may explicitly opt in to user-selected attachment IDs. The shared admission
resolves only records in the authorized Session, before its write transaction (document
parsing can write its own blocks), and freezes bounded text or image content in the original
Run. IDs do not grant document Tools or App access. The default and task execution owners
remain closed. Retry signatures include ordered material IDs and return the original Run
without re-reading mutable material. Cross-provider tests use Knowledge and Gallery owners
with empty exports; cross-Session, opt-in, bounded excerpt, image and retry checks live in
`tests/test_app_chat_durable.py`. Bot attachments do not silently flow into Todo proposals.


2026-11-03 Bot 对话配置：新增 owner provider 和宿主审阅入口；身份/记忆复用所属业务服务，未在共享 Agentic 增加领域分支。Todo 的 disable_schedule 是任意 owner 可用的事务/幂等回执，调度 admission 只检查普通任务日程与 revision，新增任意 owner 名称的用例验证停用后槽位不能执行。专项覆盖原始调用、同源确认、冻结权限、拒绝/陈旧提案、跨 Bot 拒绝及跨库提交窗口恢复，纳入完整门禁。

### 2026-11-03 Opaque selected media and Gallery transfers

Selected material that has no supported text parser is carried as bounded, explicitly unread
metadata, never as invented transcription or extra App authority. Gallery owns the new
Session attachment import route and reuses the existing Session authorization, owner-bound
Gallery collection checks, source validation and content deduplication. Workspace artifact
transfer retains the existing protocol. `test_bot_gallery_materials.py` exercises real SQLite,
HTTP authorization and deduplication, including foreign actor and mismatched Session guards;
it is part of this boundary gate. Native gesture evidence is distinguished from event fixtures
and actual API integration in the acceptance receipt.


2026-11-03 Bot 首批写入与提醒：Todo 收件箱创建和 Messager 本机提醒均由所属 App 声明、验证并返回原存储回执，Bot scope 按精确 App/effects/版本冻结授权；未在 General/共享路由添加领域分支。通用 Todo owner observe 只观察已保存 Run，使用任意 owner 的正常/失败回调测试证明不会改变或启动执行。通用通知 cancel_pending 仅撤回指定 owner 的本机待发送事件，使用异 owner 不可取消、静默策略、已有通知发件箱/Chat 通知回归验证。新增 owner 测试覆盖 BG/FG 隔离、撤权、严格输入、普通 Todo 不执行、原等待项被动点击、终态静默、进程重建恢复、Hook 委托不扩大、隐私预览与既有队列重试，纳入完整门禁。用户自行进行真实场景验收。

### App Chat 可选按需审批（2026-11-03）

缺失的通用抽象是“可发现但未预授权的 owner 接口”：旧 App Chat 仅支持白名单内免逐次批准。新增显式 opt-in，与 owner 的冻结授权回调配对，允许 False 表示进入原权限策略，异常仍拒绝；不增加业务名称分支、共享依赖或第二执行器。原控制交互创建与参数宿主访问复核执行范围；审批范围由执行宿主限定为 once/run，防止共享 Agent/App grant 扩散。

新增 test_bot_capability_discovery.py，以 fixture.paint 和 different.compose 两组不同 App 身份跑实际 General/Runtime/Gateway/Router/SQLite/审批链：调用前0次效果，用户一次授权后原 Run 执行1次，其他 Bot 仍需授权，后台权限未扩大。另测原参数表单提交、拒绝、撤权、伪造 input、无 Run 直接调用和 Provider 版本变化。模型、图片/文本产物和业务效果均是夹具，未运行真实生成或安装。原有受限 App Chat 和后台执行回归保留。

按需调用还要求通用 app-chat.invoke 权限，由原 CapabilityPolicyEngine/GrantLease 审批。它补足只靠旧 App Chat 范围守卫、required_capabilities 为空的接口；不把 effects 或名称猜成业务授权。Gateway 与 Router/owner 的实际调用复查必须同时验证额外权限，目录和参数准备不授予它。Todo 所属适配器仅在其自身 Todo Chat 中应用 directory_id/UI 脏编辑限制，Bot 等其他已授权调用仍走 Todo 的自有数据访问校验。

Bot App 授权补充（2026-11-03）：access_policy 是受信任 Provider 的读/写/独立确认声明，由 Bot owner 解释；共享 General、Router 执行流程与原权限引擎不识别业务 App 名。所有 App 身份从原调用 Provider 解析，后台继续冻结原授权。test_bot_app_access.py 以任意 fixture Provider 验证 Read/Write 依赖、Bot/actor 隔离、原 Run 回接、计费/特殊操作不随 App 授权执行、版本变化拒绝和后续调用复用；模型与效果为夹具。新增 App 卡前端测试覆盖初始开关、Read 依赖、明确提交和特殊操作第二次确认。

### Bot 规划目录性能与权限即时性（2026-11-03）

实际 Dev Run 从准入到等待 image.generate 授权约58.16秒，两次模型步骤合计约4.35秒。逐 Tool 校验反复 capture/export 整个权限目录，逐 Provider 可见性检查再次重建全部 exports，而 App 导出又在未授权目标上查询 manifest，多层调用放大了目录/权限查询。

Bot owner 改为只验证当前调用的准入路由、冻结 Provider/version 与当前授权，未选 Provider 时覆盖所有准入候选，不能因同名能力的一个 Provider 获准就放行另一个。App Access 先筛选已授予目标，在单次 export 中按目标复用身份读取。复用只在当前调用局部，不缓存跨请求授权或撤权结果。

AppChatOwner 新增可选受信任 provider_visibility(scope,provider) 点查询；共享宿主先验证 Session 的 Provider/version pin 与当前注册对象，再交由 owner 判断可见性。默认 owner 仍执行原 exports membership。回调不授予 Tool 执行权，不替代 validate_authorization、GrantLease、付费或参数确认。Bot 注册组合层提供点查询；共享执行器不按业务 App 名分支。

新增 test_bot_planning_cost.py：125 Tool目录检查约0.03秒，首次 ModelCallAction 准备约0.05秒（无模型/网络/业务执行）；断言一次目录扫描、零递归 capture、零逐 Provider 全 exports 重建，当场撤权仍拒绝。两组不同 owner/capability 验证显式关闭、当前注册对象和升级 pin 拒绝，原 owner 保持旧规则。时间是夹具测量，不等于真实用户完整绘图耗时。

- 完成证据：后端 AaAT 门禁 987 项通过，规划成本夹具 5 项通过，Bot 前端单元检查 33 项通过。前端收到 `/state` 后先更新授权/运行状态，再读取 `/work`；任务列表慢不会继续遮住授权提示。Dev 与 App-Dev 已通过标准 Helper 加载并核验导入路径/资源，Dev 原生界面恢复输入；未执行真实绘图或替用户授权。详见 `docs/acceptance/messager-planning-cost-20261103/receipt.json`。性能数字仅为无真实模型的夹具。

### Managed Cloud structured-output v1 classification（2026-11-05）

`ai2apps.cloud_structured_output` is an exact shared platform module: it negotiates an authenticated model capability and checks bounded JSON objects and terminal markers. It does not interpret Bot kind/text, App IDs, Tool names, business parameters or authorization. Its transitive imports remain subject to the same positive boundary check; no namespace exception is added. A mutation test verifies that moving Bot decision parsing into this helper is still rejected. The Bot business envelope remains in `messager/decision.py`; generic provider error metadata preservation is tested with an unrelated provider error contract.
