# Messager 三栏界面与 Bot 任务协作 v2

2026-11-02，实施中。用户本轮要求的范围包括 UI、默认 Bot、头像、任务调度、后台授权、人机确认与分页，不应仅以 CSS 调整视为完成。

Bot 之间的咨询、子任务委派、资料共享、交接与结果回接见 [Bot 通信与任务协作设计 v1](bot-communication-and-collaboration-v1.md)。2026-11-04 的 [C2](bot-delegation-c2-implementation.md) 实现单层立即子任务与“等待协作”的回合结束/恢复；本文已有等待用户输入/审批仍占位的行为保持不变。长期/多层协作不由此自动开放。

2026-11-04 后续开发计划：[Bot 记忆与任务历史 v1](bot-memory-and-history-plan-v1.md)。包含跨近期窗口的任务/产物检索、结构化记忆、问答触发的自动记录、低 Token 开销、去重/合并/替代，以及信息流中的记忆提示、查看和有版本保护的撤销。M1 历史查询与 M2 结构化记忆核心已实现，见 [M1/M2 核心落地记录](bot-memory-history-m12-implementation.md)。记忆维护 Task、明确来源自动候选和一次有界召回已实现，见 [自动记忆 v1](bot-memory-automatic-v1.md)；自动记忆开放前必须先具备来源、版本、撤销与防止已遗忘内容自动复活的能力。

记忆处理调度补充：对话只产生候选并持久入队，加入/合并由独立记忆 Task 在原 Bot lane 执行。当前执行不被抢占或改写，记忆 Task 可优先于普通待执行任务；聊天不等待。候选等待、实际保存和失败分开反馈，详见上述计划第 3.1 节。该调度为待实施设计。

2026-11-05 已讨论 Flash-Bot、ASC-Bot，以及 Outlet-Bot、Mirror-Bot；见本文末尾两节。B0 类型定义与 B1 首批 Flash 计算器已落地；创建菜单开放标准与 Flash，ASC/Outlet/Mirror 继续灰显。状态脚本、外部代理、跨实例映射及发票工作流仍待实施。实施顺序和边界见 [非标准 Bot 开发计划 v1](bot-types-development-plan-v1.md)。

## 界面

顶部保留小尺寸 Messager 图标与名称，删除技术副标题；右侧依次提供左右栏开关、身份密钥轮换、刷新，均为带 accessible label 与 Hover-Tip 的图标按钮。轮换仍保留原确认流程。

三栏与 Chat/Imagine Studio 共用尺寸、折叠、滚动与移动端约定。左侧依次 Bot、Friends、Inbox；好友申请是 Friends 内入口，中栏显示申请列表。Bot 选中后中栏使用 Chat 消息组件，移除顶部模型选择，模型配置归 Bot 右栏。不可通过隐藏 CSS 改变执行权限。

右栏展示身份、头像、职责、运行任务及排队任务、长期记忆、授权与维护操作。头像包含平台 SVG 预设/颜色和用户上传、拖拽、Gallery 选取，图片通过现有有归属校验的 Artifact/Asset 流程保存，不接受任意 URL 或路径。默认 AI2Apps Bot 按用户幂等创建，不能借名字判断默认身份。默认 Bot 的删除/重建须有明确产品语义，避免用户改名后重复创建。

## 会话与任务

Bot 的日常对话 Session 与 Todo Agent-Task 执行 Session 分离。日常对话可以只回答，也可以提出并通过 Todo owner 创建任务；不能把任意长回答都自动包装为 Task。任务支持立即单次、定时单次、周期执行，复用 Todo 的模型、执行、进度、取消、恢复和调度。

每个 Bot 一条持久串行执行通道，等待用户确认也占据当前槽位。不同 Bot 可并行；同 Bot 后续任务排队。数据库原子认领，并跨重启恢复。前台对话独立于该槽位，因此可在执行时询问状态、补充信息或处理确认。状态回答读取实际 Todo/Run 快照，不由模型猜测进度。

Bot 与 Todo task/run 之间建立 owner 校验的稳定关联。不得在 GeneralAgent 内按 Messager、Bot 名或业务工具名添加分支。Todo 的现有 todo.create 只创建待办，不意味着启动 Agent-Task；需要由 Todo owner 提供明确的创建/调度执行契约。

## 决策与确认

Bot 可在用户已授权范围内，根据可信 AaAT 声明准备和补全参数。参数不明确时通过对话询问；强制用户确认、购物车/付款、敏感信息和敏感操作继续遵循 owner 的声明与实际业务入口检查，Bot 的模型文本不构成用户同意。

持久交互要关联原 task/run、Provider 版本、参数摘要与审批用户；对话中说明正在做什么、具体将发生的效果、为何需要确认。用户拒绝或取消后，不可换 Tool 自动重试。完成通知依据真实任务终态、Bot 的通知偏好与已授权通知渠道生成；去重，不把未确认结果当作成功。

## 记忆与历史

长期记忆展示用户可读的条目、来源和更新时间，支持审阅/修正/清理；与运行上下文、历史消息和日志分别处理。清理对话不能暗示清理了长期记忆，清理记忆不能暗示取消了在运行任务。删除 Bot 应先处理当前任务、队列、调度及 Hook 授权；破坏性操作有独立确认。

首次消息加载最近 50 条；使用服务端稳定游标向上分页，保持滚动锚点。轮询/事件只增量合并，不重新下载整段历史，不漏掉用户确认卡片和任务回执。分页显示窗口与 Agent Context 裁剪独立。

## 已核对的现状与实施顺序

1. messager/bots.py 当前仅有身份与只读 Intelligence 工具，App Chat snapshot 固定取最新 200 条；尚无 Bot 长期记忆管理、头像和权限编辑。
2. 当前 Bot 使用 chat-mini iframe，含模型选择且与执行共用忙碌状态；需要明确的 Chat 宿主展示适配与独立对话通道。
3. Todo 已有执行、排队、取消、恢复和调度；复用 owner 服务，补 Bot 归属及每 Bot 串行认领，不能另建任务状态库。
4. 先落实三栏与 Bot 身份/头像/默认项及消息游标；再接 Todo 执行通道、运行中对话、持久确认和完成通知；最后联合验收，包括两个 Bot 并行、同 Bot 串行、重启、拒绝/取消、权限撤回及分页滚动。

每阶段需独立记录夹具与真实 Dev 验收。尚未交付的功能不得显示为已可用。


## 首批实现进度

已写入三栏骨架、紧凑Header与图标提示、左右栏开关、Bot/Friends/Inbox导航、Friends内申请入口及中栏申请列表、右栏Bot名称/职责编辑。默认Bot使用独立actor→bot_id映射幂等创建，改名不重复创建，编辑校验owner。尚待完整回归及Dev激活；头像、完整Chat信息流、分页、记忆、权限管理与Todo任务协作未完成。


## 2026-11-03 消息视图实施

新增Bot独立消息视图，复用Chat用户气泡CSS和安全Markdown渲染，移除嵌套Mini-Chat的重复标题/职责和顶部模型选择，模型设置移到右栏。App Chat提供仅状态读取、最近50条、向前/向后sequence游标；旧快照接口保持原行为。滚动向上加载保持锚点，新消息仅增量合并；切换Bot后过期请求不能覆盖当前视图。前台独立任务通道尚未接入，因此当前仍保留单会话活跃Run互斥，不能当作“后台执行时可并行聊天”已完成。


## 2026-11-03 头像实施

Bot头像支持四套固定SVG图形与颜色、PNG/JPEG/WebP图片上传/拖拽及Gallery选择。图片保存为有归属校验的素材引用，最大5MiB；API不接受任意URL、路径、其他用户素材或SVG上传。头像与Bot名称/职责分开存储，改变头像不会改变其工具授权。已有默认和自建Bot均可恢复头像；任务队列、长期记忆与App访问授权管理仍未交付。


消息视图/头像阶段验收：完整AaAT门禁846项通过（404秒），最终分页/头像5项与头像前端2项通过。固定Dev/App-Dev空闲后通过标准Helper重载，App/Helper源码根、运行App Chat导入与已服务资源逐字节核验；Dev原生界面确认头像、右栏模型和原有历史恢复。125条翻页和私有图片隔离为临时数据夹具；原生未发送新消息/调用模型或更改用户头像。收据：[消息视图与头像](acceptance/messager-bot-stream-20261103/receipt.json)。本阶段不包含Todo队列、执行期间独立聊天、长期记忆、Bot App授权与删除/清理。


## 2026-11-03 Todo 串行通道与关联阶段

Todo 原库新增 owner/task→execution lane 关联；只有受信任 owner adapter 可以配置，不进入 TaskInput 或模型参数。Messager 用稳定 Bot ID 派生 lane，绑定前验证 Bot 与 Todo task 均属于当前用户。关联和解除不会创建 Run、启动执行或授予权限。活跃/排队时禁止改绑，其他 Bot 不可覆盖或解除既有绑定。

Todo launch 在原写事务冻结 lane。队列在同一写事务读取已认领 Run 并认领下一项；同 owner/lane 最多一项，waiting_input/waiting_capability 继续占位，后续同 lane 排队但其他 lane 可越过继续。重启沿用原 Run 和 watch_internal，不重复创建执行。无 lane 的旧任务保持原全局并发规则。新机制不识别 Bot/App 名，也不改变 General Agent 工具权限或确认规则。

右栏可关联已有 Todo，显示原 task/latest run 的有界实时状态、下次执行时间与进度文本，打开原 Todo 项目处理执行、调度、回复、审批与取消。最多50项，活跃/排队优先；关联候选最多100项，均仅当前用户，省略私有正文和执行输入/输出。Bot 对话上下文可读取这些真实快照，在 Todo 执行时仍可进行独立前台对话；任务文本不能充当授权或指令。

本阶段是任务协作基础。尚未接入对话自动创建/启动任务、定时单次、Bot冻结App授权、任务确认回接原对话、完成通知策略，也未交付长期记忆/删除。现有入口明确使用 Todo 的执行权限，不把“关联”称作 Bot 独立执行授权。下一阶段应先补 Todo owner 的审阅后创建/启动契约与冻结授权，再开放对话创建；不能把当前只读 Bot 直接升级为全权限 General Agent。


串行通道阶段验收：完整AaAT856项通过（432.81秒/退出0），最终Bot/通道11项通过，Todo核心95项及其他执行器/备份20项通过。串行、并行、重启、等待用户、取消和执行期间对话使用真实存储/Runtime及可控执行/模型夹具。Dev/App-Dev空闲后由标准Helper重载，核对App/Helper源码根、运行Todo/Bot模块来源、服务资源及新表；Dev原生展开候选后取消，App-Dev确认中文任务栏与正确原生标题。真实用户任务未关联、启动或审批，未发送消息或调用付费模型。收据：[Todo串行通道](acceptance/messager-todo-lanes-20261103/receipt.json)。本阶段的后续限制以上节为准。

## 2026-11-03 Bot App 访问授权阶段

Messager owner 提供两个明确适配的只读 profile：已保存情报、Todo 项目。范围为当前用户在该 App 拥有的数据，前台对话与已批准后台工作分别选择；不根据无 effects、名称前缀或模型判断自动收录新 Tool。实现仅从明确名单取匹配 App/Provider/version 且无声明副作用的接口。未适配的写入、发送、敏感操作不显示为可授权能力；这些仍需所属 owner 的确认契约。

已有情报前台读取保留并固定当前接口版本，不默认授予 Todo、后台或其他 App 权限。按 Bot 保存单调递增授权 revision 与 Provider/version；明确保存才更新版本。接口升级不会静默扩权。权限审阅包含当前profile/Provider/version摘要；读取面板后接口若发生变化，保存被拒绝，必须重新审阅。仅 Local desktop 同源宿主可以修改授权，非 desktop、opaque Origin、跨用户、过期 revision 和未知 profile 拒绝；模型没有修改授权的 Tool。

AppChatOwner 新增成对的 capture_authorization/validate_authorization：submit 在原 admission 写事务中捕获 owner 授权并写入宿主私有 Run 关联表，普通 Run input 不能伪造或覆盖；每次模型执行与 Tool 调用前重新复核。Scope、消息、UI snapshot 和职责不提供授权。授权变更与 submit 共用同一服务锁，在事务中找出旧活动 Run，提交后取消；每次调用仍独立检查 revision，撤回再授权不能复活旧 Run。此通用机制不识别 Bot/App/Tool 名；未采用该机制的 owner 保持原行为。General Agent 为 Run 拥有的发现、参数预检/确认上下文补齐 trace_id，避免缺少实际执行身份时放宽检查。

右栏提供 App 只读访问的审阅、保存和撤回。后台读取选择只限定既有已批准后台工作的能力上限，不创建 Hook/定时任务，不取代独立 Hook 授权。已有手工关联 Todo 的任务状态属于明确关联的 Bot 工作台投影，不等于读取所有 Todo 详情。手工 Todo 执行继续使用 Todo 原权限；本阶段尚未让其继承 Bot 权限，也未开放对话自动创建/启动任务。下一阶段需先将新 Todo 执行 Session 绑定冻结的 Bot 授权，再加入创建/启动 owner 契约及单次/定时/重复调度。

Hook 身份摘要改为仅名称/职责；动态 Todo 状态继续只作为对话 context，不再导致已批准 Hook 因任务进度变化被误判为 Bot 身份变化。


访问授权阶段验收：最终完整AaAT863项通过（424.19秒/退出0）；最终审阅/通用执行11项通过，私有授权防伪3项通过，Hook兼容批次30项通过。真实SQLite/Runtime/Tool链使用可控模型夹具验证；Dev/App-Dev空闲后由标准Helper加载，App/Helper源码根、运行AppChat/General/权限模块、私有表和已服务资源核验通过。原生Dev英文/App-Dev中文面板确认默认值，未保存新的用户授权、未执行用户任务或调用付费模型。收据：[Bot访问授权](acceptance/messager-bot-access-20261103/receipt.json)。对话创建/启动任务及冻结Todo执行权限属于下一阶段，不能视为已完成。

## 2026-11-03 Todo 执行接通阶段

已实现对话提出任务、宿主确认后创建/启动、定时单次/周期执行、冻结后台读取权限、原 Run 等待/审批回接和终态对话回执。新任务使用独立 managed 执行与 Session；手工关联旧任务继续使用 Todo 原权限。具体边界、恢复及尚未开放的敏感能力见 [Bot → Todo 执行协议](messager-todo-execution-v1.md)。已通过完整 AaAT 882 项回归（450.13 秒）及补充审批 6 项测试；Dev/App-Dev 已激活并核对当前源码与资源。Dev 真实模型跑通提案、原生确认、启动、等待期间并行聊天、原 Run 回复续跑和唯一完成回执；敏感审批仅以夹具验证。验收见 [收据](acceptance/messager-todo-execution-20261103/receipt.json)。尚未发布，记忆管理、删除/清理与更多 App 写能力仍属于后续阶段。

## 2026-11-03 Chat 风格输入区

Bot 输入区增加附件、语音输入和图标发送按钮，附件支持文件选择、拖入、预览及移除。
语音复用 Chat 保存的 STT 选择（存在时），转写使用 `/v1/audio/transcriptions`；结果只进入
可编辑草稿，不自动发送。缺少已准备的识别模型时指引到 Chat 的语音设置。
附件保存到当前 Bot 会话，由服务端核验归属并冻结到原 Run；文档每份最多前 20 个块/
8000 字符并明确标记有界摘录，图片进入多模态输入（模型仍需支持图片）。最多 8 个附件，
文档 25 MiB/份，图片 8 MiB/份且合计 16 MiB。尚不将附件自动转移到 Todo 后台任务，
相关提案会明确要求用户另行提供独立任务指令。不会因上传材料扩大 Bot App 权限。


## 2026-11-03 长期记忆与生命周期阶段

身份职责、长期记忆、近期对话是三类独立数据。职责仍在身份设置中编辑；长期记忆由用户在右栏明确保存，可编辑、移除和恢复，显示来源（用户保存）及更新时间。每条带乐观版本，拒绝覆盖另一窗口的新修改；同一用户不同 Bot 的记忆隔离。最多 50 条有效记忆、共 8000 字，每条最多 2000 字；可恢复档案最多 200 条，满后复用已有条目，不自动丢弃旧内容。当前不自动从对话抽取事实，也不声称用户说过“记住”就已保存。

记忆通过 Messager owner context 作为不可信业务数据进入新对话回合，不写入共享 General 的全局提示，也不授予工具或 App 权限。新提案冻结当时的记忆快照，任务审阅卡可展开查看；后续单条编辑不悄悄改写已确认任务。移除不是不可恢复的安全擦除：旧消息、已确认任务快照和审计仍保留。清除全部记忆采用下面的清理流程，停止旧执行及计划，使旧上下文不能继续产生新操作。

清除对话只归档当前会话，下一次打开创建独立 Session；长期记忆保留。“恢复上一份对话”交换当前会话和最近归档会话，保留原消息、Run 和任务回执。归档的 Session 无已注册执行 owner，不能通过旧挂载继续读取或提交；Bot 删除使用可恢复归档，列表隐藏且全部 Bot 业务入口拒绝访问。已删除 Bot 列表可恢复身份，历史对话另行恢复；默认 AI2Apps Bot 不允许删除，提供重置（身份职责、头像、对话与有效记忆）。

清理均需 Local desktop 同源宿主审阅本次影响摘要及哈希。执行先提升权限版本并撤回 App 授权，取消当前 Bot 前台/任务 Run，拒绝待确认提案，暂停关联 Hook 和计划，再做内容变更。Bot 托管队列取消、运行中任务请求原执行器停止，原最终状态和收据仍由 Todo/AgentRuntime 结算；界面不把请求取消当作已经停止。Hook 的原 System Task 收到取消请求，原校验拦截后续动作，已发生的效果不撤销。关联外部/手工任务仍活动时，清理在变更前拒绝，要求先到所属 App 停止，避免绕过其他执行器。恢复不恢复 App 授权、Hook、计划或旧执行。

专项覆盖真实 SQLite/API/Run、Todo 排队/重复计划、Hook 暂停、冻结记忆快照和恢复后不复权。模型为可控夹具；App-Dev 原生界面另行核验保存、移除/恢复、来源时间、审阅、删除、恢复以及默认 Bot 自动切换。本轮发现并修复设置表单销毁后对话挂载引用失效，新增 JS 回归。收据保存在 acceptance/messager-memory-lifecycle-20261103/。

输入区验收完成：Dev/App-Dev 原生按钮及已配置 STT 选择核验通过；Dev 通过原生文件选择、上传、发送，实际模型正确返回合成附件标记，无工具调用；最终消息只展示正文与附件名卡片。语音录制/转写链路使用夹具验证，未录制现场声音。专项 22 项、输入区交互 3 项、完整 AaAT 893 项通过（487.01 秒）。[验收记录](acceptance/messager-composer-20261103/receipt.json)。尚未发布。

本阶段完成验收：完整 AaAT 893 项通过（487.53 秒/退出 0），Bot owner 专项 21 项通过，JS 挂载与选中保持回归 1 项通过。App-Dev 原生创建专用测试 Bot，保存/移除/恢复记忆；现有 Cloud DeepSeek 模型在零 App 授权、零 Tool 调用下正确读出合成记忆标记。清除对话后记忆保留，恢复原会话及模型结果成功，恢复后权限仍为空。Dev / App-Dev 来源及资源核验通过；Dev 原有上传面板保留，原生修改验收在独立 App-Dev 进行。详见 [验收收据](acceptance/messager-memory-lifecycle-20261103/receipt.json)。本阶段已激活，尚未发布。

## 2026-11-03 Bot 对话模型目录与默认值

Bot 不再直接列出完整 `/v1/models` 或沿用 Mini-App 的 work_standard 选择。改为使用 Chat 相同的模型目录来源与 `AI2AppsConversationModelPolicy`：合并受管 Cloud/Fusion 元数据、统一 Gateway 别名，排除非 LLM/VLM、隐藏、Helper、hf_cache、未就绪或失败项。能力声明用于 Agent 候选排序，未声明不会抹去用户已明确选择的有效对话模型。

新 Bot 没有专属手动选择时，按 Chat Agent 的 work_agent → 工作能力/账户 API 默认回退规则选取。账户 API 默认使用 `cloud/ai2apps/` 路由；无可用默认时显示明确选择入口，不取目录第一项。已有 Bot 的有效手动选择保留；过期或非对话模型选择回退到当前 Agent 默认。模型能力说明折叠展示，默认不可用时直接提示。音频输入仍使用独立 STT 目录。

验证：前端策略/输入区 21 项通过，Python 默认模型/Agent 选择 8 项通过；Dev 原生模型菜单确认为 8 个对话模型，实时目录原有 44 项。无 Bot 手动选择时与实际 Chat Agent 默认相同。HTML/JS 变更仅刷新页面，未启动模型、未改动全局默认或用户授权。收据：acceptance/messager-agent-model-20261103/receipt.json。


## 2026-11-03 对话配置闭环

新增 Messager owner 能力 `messager.bot.configure`，仅前台用户对话可见且由私有 Run 授权固定版本。支持三类明确请求：修改当前 Bot 名称/职责、添加用户指定长期记忆、停用原 Bot 托管 Todo 的后续执行计划。普通讨论不触发设置写入；任务执行和后台 Hook 不可用此能力。附件不能授权配置变更，需单独发送明确文本。共享 General/路由没有新增 Bot 特例。

能力只保存 24 小时有效的提案。宿主卡展示身份职责前后对照、记忆正文/来源、或原计划标题/时间/时区及影响。用户在 Local desktop 同源宿主确认后才写入；拒绝不修改设置。每次确认复核 actor/Bot/Session、审阅哈希、冻结授权版本、当前设置/记忆版本或任务 revision。变化后拒绝陈旧确认，要求重新提案。每个 Tool invocation 幂等；应用后的重复确认返回原回执。实际保存结果用稳定消息键写回原对话，丢失的消息投影可恢复，不重复副作用。右栏名称职责、记忆和任务列表同步刷新。

身份/记忆应用复用原 BotDirectory 和 BotMemory 业务入口，通过可信同库事务同时提交变更和提案回执；不接受模型或 API 指定事务对象。角色变更只影响后续对话，原批准任务保留身份/记忆快照；既有 Hook 的身份守卫要求重新审阅。

新建立即/定时单次/重复任务继续使用 `messager.task.propose`，不建立另一个调度器。owner context 提供当前 Bot 托管计划的有界目录（最多 50 条及 has_more），包含实际 task_id、标题、日程、revision 和 next_due。名称有歧义时询问用户；停用必须给出原 task_id，不能通过创建新任务代替。手工关联或其他 Bot 的任务拒绝通过此入口修改。

TodoStore 新增通用 `disable_schedule` 事务及 owner/request_key 回执：确认将原 schedule 改为 off、next_due 置空并提升任务 revision；原已入队或运行的 Run 不取消。原任务定义和日程仍在提案/执行审计快照中。恢复计划需要新的用户审阅，不复活旧授权。调度 admission 在写事务内复核当前 schedule，拦截 tick 已认领但用户刚停用的槽位。通用层不识别 Bot 名称或领域。

跨 platform / Todo 数据库采用 applying + Todo 原回执：若 Todo 已提交而平台回链未完成，再次确认只读取原回执并结算原提案，不能从任务“看起来关闭”推断本操作成功，也不重复写入。若无 Todo 回执，原存储事务证明尚未提交，用户仍可取消。内容清理拒绝待确认的配置；已经进入 applying 的记录保留原操作核对路径，不伪造为未发生。

暂不开放对话自动扩大 App 权限、无确认记忆抽取、任意 Todo 编辑或旧计划自动恢复。本轮验证与开发实例证据保存在 acceptance/messager-conversation-config-20261103/，模型夹具与真实模型分别记录。

确认写入同时在实际写事务内复核原身份，防止右栏在校验与提交之间保存新职责时被旧卡覆盖。接口注册对象与冻结版本亦在确认时复核；版本变更要求重新提案。专项注入并发 UI 保存，验证旧卡拒绝且新职责保留。

本阶段验收完成：最终完整 AaAT 903 项通过（500.82 秒/退出0），最终 owner/原 Todo 专项31项通过（43.51秒），JS回归1项通过。App-Dev 真实 Cloud DeepSeek 四轮对话通过原生审阅卡完成职责修改、记忆保存、每日06:00（Asia/Shanghai）计划创建及原计划停用；确认三份配置回执各一份、只创建一个 Todo、无任务 Run、后台 App 读取范围为空、无外部消息。最终 Dev/App-Dev 重载后来源及服务资源核验通过，原内容与停用状态保留。收据：[对话配置闭环](acceptance/messager-conversation-config-20261103/receipt.json)。开发实例已激活，尚未生产发布。

## 2026-11-03 Bot / Gallery 右侧栏

右侧栏提供 Bot 和 Gallery 两个 Tab。Bot 按 Task、Profile、App 访问权限、记忆、对话记录分组；Task 第一组默认展开，其余组默认折叠。Profile 包含名字、头像、职责、对话模型及删除/默认 Bot 重置；记忆清除归记忆组，对话清理/恢复归历史组。清理仍使用原有影响范围审阅、撤权及停止机制。

Gallery 复用系统 Gallery Mini-Entry 与 Shell 标准挂载，独立页面沿用第一方 mini 路径。来自 Gallery 的拖拽只信任素材 ID；读取实际拥有者授权的元数据和内容，按既有限额复制到拖入时的 Bot 会话，切换 Bot 后不注入新会话。整个对话区域可接收附件，不局限输入框。

会话附件通过 `application/x-ai2apps-session-attachment`，Workspace 生成文件通过现有 `application/x-ai2apps-session-artifact` 拖入 Gallery。正文里的受管附件/生成文件/Gallery 引用保留同一身份；不接受本地路径或任意第三方 URL 作为受信任文件。Gallery 服务端再次检查 Session/actor/collection 权限，读取实际源文件并按内容去重；不把拖拽载荷里的名称、路径或声明当授权。HTML 以下载链接呈现，不在 Bot 主页面执行。音视频使用媒体预览；不支持直接解析的会话材料只携带明确的未读取元数据，不假称已转写或分析，不扩展 Bot App 权限。

生成文件展示最近50项，不改变消息最近50条的游标加载规则。附件仍受现有 8 项、图片8 MiB/合计16 MiB、其他文件25 MiB限制；未增加大视频传输或自动语音/视频分析。

验收：Python 专项30项、前端14项通过；完整 AaAT903项通过（503.78秒，退出0）。Dev 原生界面确认 Tab、分组和生成素材卡片，Gallery Mini-Entry 可索引新素材；真实接口完成专用图片/HTML的生成文件→Gallery→会话附件→Gallery去重往返，内容一致，无模型调用、无外部消息。原生自动化拖拽手势没有触发导入，不能视为手势实机验收通过；拖拽载荷与接收行为以事件夹具验证。收据见 acceptance/messager-sidebar-gallery-20261103/receipt.json。

## 2026-11-03 可调整的左侧栏

左边界与中间对话区之间提供可聚焦的竖向分隔条，支持鼠标/触控笔拖动、方向键（每次16px）、Home/End及双击恢复默认。默认260px，最小88px、最大480px；实际最大值还会为中栏保留360px，并计入右栏宽度。小屏维持原侧栏浮层且不提供拖动条。Pointer capture、取消与卸载清理防止跨 iframe 时丢失拖动状态。

宽度低于168px时，Bot/好友卡片隐藏名称、职责和进度文字，只保留头像与数据源实际提供的未读角标；名称保留为提示与可访问标签。不会根据任务完成状态、失败状态或列表顺序编造未读。现有卡片接口没有未读字段时不显示角标，本次未新增 Cloud 或 Bot 的未读消息追踪机制。窄栏三个 Tab 仍在一行，以图标显示；新建、请求和搜索入口可恢复展开宽度。

偏好保存在当前实例浏览器本地。窗口临时缩小可限宽，但不会覆盖偏好；宽度更充裕时恢复。原生 App-Dev 验证真实鼠标拖宽、最小值、头像模式、刷新记忆以及双击重置。仅前端资源变更，无 Python/运行时重启，不打断 Dev 已有工作。

## 2026-11-03 固定高度 Bot 卡片

左栏 Bot 卡片固定64px高，只显示头像、单行名字和已有未读状态，移除职责及任务状态副标题。名字过长省略，并保留完整名称提示；窄栏继续隐藏名字，固定高度保持一致。

未读改为卡片左上角45度绶带：浅蓝底与蓝色数字，只有布尔未读信息时用蓝色圆点；99以上显示99+。无真实未读数据不显示，不根据任务状态生成未读。仅修改 Bot 卡片，好友和 Inbox 的状态语义不变。现有前端5项回归通过，App-Dev 原生确认简化卡片布局；本次没有制造测试未读或改变任何用户读状态。

## 2026-11-03 浮层提示与列表底栏

错误/成功提示由顶部下滑浮层呈现，不再占用主布局空间。固定6秒收起，可手动关闭；相同可见消息不会因重复报错延长计时，新消息替换时取消旧定时器，旧回调不能关闭新提示，页面卸载清理。支持减少动态效果设置。提示关闭后身份密钥轮换的未完成二次确认也取消，不保留不可见确认状态。原有错误仍照常显示，本次不改变服务错误语义或权限。

新建机器人和已删除Bot入口改为带名称提示的图标按钮，固定在Bot列表底部同一行。列表在独立区域滚动，按钮不随列表移走；窄栏88px下仍同排。新建入口展开并聚焦原表单，保留未提交草稿；归档入口切换索引/空状态，继续使用原恢复路径，不自动恢复任何Bot。

前端14项回归通过，App-Dev原生验证真实NotFound浮层、不挤占工作区、手动关闭/超时、底部新建及归档入口、88px底栏同排；最终恢复260px。仅HTML/CSS/JS刷新，未重启Local、未创建Bot/任务或调用模型。验收记录：acceptance/messager-notice-footer-20261103/receipt.json。


## 2026-11-03 首批写入授权与任务提醒（场景验收由用户进行）

App 访问权限新增两个默认关闭的授权项，前台对话与已确认后台任务分别选择，并复用原同源宿主审阅、权限 revision 和接口版本冻结。原有只读授权不扩大。

- Todo 所有的 `todo.inbox.create` 仅接受 title、description、priority，使用原 TodoStore 与 creation_key 原子回执，在当前用户收件箱创建普通待办。不能指定目录/父项目、执行器、模型、计划、收件人，也不修改、删除或启动项目；成功返回实际 task_id 与 execution_started=false。
- Messager 所有的 `messager.notice.create` 仅接受 title、body，在本机保存当前用户的站内提醒。目标从原 Bot/Task Session 解析，不接受模型提供收件人、URL 或任务引用。saved/receipt_id 代表本机保存，不等于 Cloud 或外部消息已经送达；muted 表示通知被策略静默。

权限目录精确匹配 App、capability、Provider 版本与已声明 effects。新增写入项要求 workspace.write，原只读项仍要求无 effects；接口或效果变化不能静默扩大权限。实际写入时在 AppChat admission 锁内重新复核冻结权限，撤权后旧调用与旧任务不能继续写入。后台写入授权不扩大 Hook 的原只读详情委托；Hook 自身的动作授权、预算及循环保护保持独立。

Bot 右栏新增“任务与提醒策略”，分别控制成功、失败/取消、等待回复/确认和已授权主动提醒的通知。成功还遵循每次任务提案的 notify 选择；失败和等待依照当前 Bot 策略。此处控制提醒，不删除原任务审计与对话回执，也不授予 Bot 主动创建提醒的能力。任务卡展示冻结的后台允许操作及提醒说明。清除/归档后的原会话、失效 Bot 或已处理的等待项不再作为有效提醒目标。

提醒在 Messager Inbox 显示，包含未读状态；Inbox/Dock 和 Bot 列表复用现有徽标协议。点击先在服务端核对 actor、原 Bot 会话、原 Todo Run 及必要时的原 Interaction/deadline/cancel 状态，再打开 Bot、显示对应任务并定位等待卡；不会自动回复、确认、批准、重启或创建新任务。长历史下的有效活动任务优先进入有界 work 投影。

底层使用本机持久提醒对象及既有 NotificationProducer 发件箱与受控 app_route。提醒正文、模型结果和输入提示不上传为系统预览；传输仅包含固定通用文案、opaque notice 引用和分组。创建、入队和消息目标有稳定幂等键；发送/重试及点击时再次授权。Cloud 未连接或未协商支持 custom app_route 时，本机 Inbox 继续可用，不改走任意 URL 或其他发送工具。移动端 Bot 控制仍遵守既有客户端边界，首批在桌面 Dev/App-Dev 开放。

TodoExecutionAdapter 增加可选 observe 回调，由 Todo 原 watch_internal 在持久 Run 更新后调用，仅投影原状态；异常不会改变执行结果或启动另一执行器。Bot 从原待输入/审批创建一次提醒，从原终态创建一次结果提醒；基线之前的历史结果不补发。重启恢复复用原 Todo/Agent Run、Interaction 与通知回执。原 NotificationProducer 增加通用 cancel_pending：可信 owner 可在本机撤回其精确待发送事件，支持离线及调用方事务。策略关闭或已读会撤回尚未发送的提醒；已经送达的事件不能靠本机取消操作撤回。

新 API：GET /messager/notices，POST /messager/notices/{id}/open，POST /messager/notices/read-all，GET/PUT /messager/bots/{id}/notification-policy。变更入口要求同源桌面宿主；公开参数不能指定 actor、目标或执行绑定。

本阶段只做模型/网络夹具下的自动化验证与开发实例只读加载检查，不运行真实模型场景、不创建用户验收任务、不替用户启用新授权或更改提醒设置。人工验收入口：Bot 右栏的“App 访问权限”“任务与提醒策略”，以及左栏 Inbox。证据保存到 acceptance/messager-write-notifications-20261103/；尚未发布生产版本。

本阶段自动化检查完成：完整 AaAT 964 项通过（500.52 秒/退出0），界面回归12项通过；补充集成84项、owner专项20项通过。Dev/App-Dev 空闲后通过各自标准 Helper 加载，App/Helper 源码根、实际模块路径与已服务资源内容核对通过。未运行真实模型场景、未创建用户验收任务、未代为启用写入授权或更改提醒策略。人工场景验收由用户进行，未发布生产版本。详见 [首批写入与任务提醒收据](acceptance/messager-write-notifications-20261103/receipt.json)。

底部图标的提示改为显式 Hover-Tip（2026-11-03）：悬停或键盘焦点时向上显示；新建提示随表单状态更新为取消新建，已删除Bot提示保持清晰名称。使用 aria-describedby，取消重复原生 title；左右分别朝栏内定位，窄栏可换行。App-Dev原生核对两项焦点提示与位置，前端7项回归通过。

### 右侧栏宽度（2026-11-03）

Bot/Gallery 共用可拖拽右边栏，分隔条向左拖动增宽。沿用现有响应式宽度作为最小值（常规300px、1050px及以下250px）；最大720px，并按左栏与对话区至少360px约束。移动端保留原覆盖栏布局，不显示拖拽条。宽度独立保存于浏览器；临时窗口限宽不覆盖偏好。支持左右方向键每次16px、Home/End和双击恢复最小值，沿用 pointer capture 与卸载清理。

### 清除对话确认与即时清空（2026-11-03）

修复右栏底部点击清除后，确认区出现在滚动区域顶部而不可见的问题。清理操作统一使用根节点上的原生模态确认框，展示 Bot 名称、清理范围与执行/计划/Hook/权限影响；默认焦点在取消，可用 Escape 退出。读取范围期间防止重复点击，提交期间禁止重复提交及取消，切换 Bot 后旧确认失效。

仅在服务端成功后使旧控制器与轮询失效，立即移除旧消息、附件和会话材料节点，再以同一 Bot 打开新的空白 Session。失败时保留原消息，不假装清空。沿用现有生命周期的可恢复副本、独立长期记忆、Gallery 原文件与原任务审计；此次没有更改后端清理策略。

前端7项、owner/Python13项自动回归通过。Dev 原生已刷新并检查模态可见、取消默认焦点和 Escape 关闭，实际用户对话未清理，留给用户验收。Dev/App-Dev 的 App/Helper 源码绑定、实际模块路径与提供的 JS/CSS 核对一致。见 acceptance/messager-clear-dialogue-20261103/receipt.json。

### 消息操作（2026-11-03）

Bot 用户气泡与 AI 回复下方均提供复制、朗读/停止按钮，复用 Chat 消息操作组件；复制原始消息正文（Markdown保留源格式），附件标签不混入复制内容。朗读使用现有 Desktop TTS 模型选择与分段播放，排除代码块；切换 Bot、卸载或页面进入后台时停止并清理音频。更早消息加载也使用同一操作栏，不改消息游标或任务执行。

### 消息图标及状态提示（2026-11-03）

消息复制/朗读操作使用图标按钮，Hover或键盘聚焦显示Tip。复制成功切换绿色勾号并显示“已复制”约1.8秒后还原；失败显示失败Tip和可访问错误说明。朗读按钮空闲为音量图标，生成音频时为加载图标与“正在生成语音，点击停止”，播放时为停止图标与“正在朗读，点击停止”；点击可取消生成或停止播放，结束/切换Bot/后台恢复空闲。复用Chat Tip反馈，现有Mini-Chat文本操作栏保持其原有外观。

### 普通朗读的 TTS 能力匹配修复（2026-11-03）

普通朗读合并 `/v1/models` 与 Chat 使用的 `/admin/api/models` 完整能力/权重就绪信息，默认选择不需要参考音频或必填声音描述的可用模型。可兼容的 Chat 已选TTS模型优先；音色遵循对应模型的Chat偏好并校验预设列表，必要时通过 `/v1/audio/voices` 发现音色。不修改用户保存的Chat设置，不为参考音频模型虚构参考素材，不在合成失败后跨模型重试。服务错误保留HTTP状态和返回的具体说明。

### Bot 按需能力发现与原 Run 授权（2026-11-03）

AppChatOwner 可由可信宿主显式声明 allow_tool_approval，且必须同时提供 capture_authorization/validate_authorization。默认关闭，原受限 App Chat 保持原界面范围与免逐次审批语义。打开后，owner 验证回调返回 False 表示范围可被发现但本次调用没有预授权；AppChatService 将调用交给原 CapabilityPolicyEngine/GrantLease，不以目录展示充当授权。其他返回值保留旧预授权语义。范围验证失败仍直接拒绝。

Bot owner 在用户前台 Run 准入时冻结可发现 Tool revision、Provider identity/version 与原 Bot 权限 revision。读取受信任声明并按需加载 schema，缺参使用原 parameter_form，App 交接使用原 handoff。原 AgentRuntime 保持唯一执行权、交互身份、未知副作用、取消与重启恢复协议。控制交互在创建前经过相同范围验证，参数表单每次宿主访问也重新检查当前 Run/owner/provider 范围。

额外调用遵循 Agent-Chat 的原策略与明确拒绝；没有自动授予 Bot 持久权限。新审批限定 once/run（本次调用/本次请求），避免跨 Run Provider 升级沿用旧授权，不能创建共享 AppChat Agent 或 App 级授权；前端不默认同意、不自动提交审批。已授予的 Bot 前台接口继续原策略；后台 Hook/Todo 不带发现快照，仍仅可用其冻结的后台授权。按需批准只对当前原 Run 生效，不授予其他 Bot、后续新 Run 或 Session；长期权限仍在 Bot 的 App 访问设置中单独管理。

AppChat 状态投影包含原 Interaction 的 kind、response_schema、ui_hints、request 与 deadline_at。Bot UI 复用 AI2AppsParameterForms，而非另造素材、模型、安装与参数提交协议；审批回接与参数提交均继续原 Run 和 Session。Gallery 产物沿现有会话附件/输出投影。没有按画图、音频或某个 Mini-App 名称修改共享 General 的业务逻辑。

本阶段自动化与开发实例加载结果见 acceptance/messager-capability-discovery-20261103/receipt.json；真实画图由用户自行验收。

按需调用还要求通用 app-chat.invoke 权限，由原 CapabilityPolicyEngine/GrantLease 审批。它补足只靠旧 App Chat 范围守卫、required_capabilities 为空的接口；不把 effects 或名称猜成业务授权。Gateway 与 Router/owner 的实际调用复查必须同时验证额外权限，目录和参数准备不授予它。Todo 所属适配器仅在其自身 Todo Chat 中应用 directory_id/UI 脏编辑限制，Bot 等其他已授权调用仍走 Todo 的自有数据访问校验。

本阶段验证完成：完整 AaAT970项通过（575.21秒，退出0），Bot/写入/配置/Todo/架构专项59项、零 capability与隔离7项、直接 Router守卫1项、前端24项通过。Dev与App-Dev经标准空闲检查和Helper重启加载，源码根、实际导入路径、新资源与图像/发现接口注册核对通过。原用户对话保留，未做真实图像生成或代为授予权限；用户自行重试验收，尚未发布。
### 每个 Bot 的语音设置（2026-11-03）

右侧 Bot Tab 的“语音”折叠组提供：使用 Chat 默认、语音工坊角色、模型与预设音色。新 Bot 默认跟随 Chat 模型与音色设置；独立设置持久保存在本机，按用户和 Bot 隔离，不写 Chat 设置。完整选择后自动保存，下次朗读生效；版本冲突返回 409 并重新读取。归档恢复保留设置，重置 Bot 清除覆盖值。

GET/PUT `/v1/platform/messager/bots/{id}/voice` 校验 App 使用能力与 Bot 归属。模型模式要求已就绪 TTS 和匹配的预设音色；角色模式要求当前用户拥有的已就绪工坊角色及可用模型。角色被删或模型不可用时，优先回退到该 Bot 上一次成功合成的可用设置，再使用默认朗读设置，并显示回退提示。

独立模型复用现有 speech API；角色复用工坊 quick-read 合成与归属检查，生成音频进入工坊共享输出，不建 Bot 输出历史。共用消息组件只接收通用朗读回调。角色路径通过模拟接口与归属测试；真实合成验证覆盖独立模型模式。

语音选项无需保存按钮。模式切换尚未选完整个角色或模型/音色时继续使用已生效设置；完整选择自动提交，提交中禁用选择，冲突重新读取。上次可用配置仅在成功合成后记录，带当前设置版本校验，不能由旧请求覆盖新选择。播放前验证当前和历史配置；明确不可用的响应（400/404/409/422/503）允许转用后续候选。取消、网络异常和结果不明确的其他服务错误不自动重试。回退不改写用户选择，并在消息下方说明实际使用的配置。

模型下拉的“安装模型…”调用标准 ACPF `audio.speech_generation`、`configure_only`、`installMore` 引导。Messager 的声明位于 `provisioning/profiles/messager.yaml`，复用已验证的 CustomVoice Runtime/Package/Checkpoint 方案。完成后刷新目录；取消保留原选择，不下载，不自动安装或开始朗读。


### Bot 按 App 授权 Read/Write（2026-11-03）

本节替代上一阶段普通 Bot 调用的逐次批准入口。可信宿主从实际 pending Interaction 的原 Run/Session/Tool/Provider 推导 App 身份，不接受前端指定 App、Tool 或模型自报授权。申请卡显示 App 的 Launcher 图标/名称，Read/Write 初始均选中；Write 依赖 Read，取消 Read 同时取消 Write。用户点 Allow this bot 后保存到当前 Bot 的 App Access。设置页按 App 列出相同开关；默认仅展示保存状态，不自动批准新授权。

App Read/Write 覆盖该 App/Mini-App 的普通 AaAT；effect 由所属 Tool 声明，空 effects/读取效果为 Read，普通写入/产物效果为 Write。未知效果、计费、敏感/破坏性效果，以及 owner 的 access_policy=confirm，不因 App 授权获得免确认。CapabilityProvider 可声明 access_policy=read/write/confirm；它只能细化/收紧权限，不能用 read 覆盖实际写入或计费效果。默认 General/Chat 授权不改变，也不加入业务身份分支。

### 已加入的 App 与独立 Mini-App 权限（2026-11-03）

右侧仅显示当前 Bot 已加入的权限目标，分为 App 和 Mini-App 两组，各有添加图标。添加弹窗提供两个分类和名称搜索；单击项目后授予只读并加入列表，写入须另开且依赖读取。开关直接应用。删除按钮先展示目标名称和撤权影响，确认后移除该目标的全部权限，调用既有撤权路径使旧授权执行失效，保留原任务回执；取消不提交。

新 Bot 默认加入 Gallery、Messager、Todo（读写）和 AI Browser（只读）。默认项由 Bot owner 配置，不改变通用 Agent 的安全策略。已有明确授权、关闭、清理或撤销的状态保留，不因刷新、升级、恢复而重新授予。仅历史未修改的自动 Intelligence 接口授权被新默认策略替代，并推进权限 epoch；明确保存过的 Intelligence 授权保留。

权限目标由可信 provider 的 App owner 与可选 mini_app_id 共同确定。Package 是安装来源，不是把多个 Mini-App 合并授权的单位；父 App 权限不隐式开放其 Mini-App，某个 Mini-App 的权限不扩展到同 Package 的其它组件。Mini-App 名称、图标和宿主工作室来自实际声明。API 继续保留历史 app_id 字段作为权限目标键，owner_app_id/mini_app_id/kind 明确真实归属；客户端不得从 Package 名称推导权限。

旧 Package 范围授权只迁移到当时已注册的组件，之后新增的兄弟组件不继承。已卸载组件保留可识别的撤权条目，不能继续获得执行权限。目录声明和权限 revision 共同防止陈旧提交，添加、撤销及特殊动作审批继续走原 owner 与原 Run/Interaction，不建立新执行器或绕过付费/敏感确认。

验收：完整 AaAT 门禁 981 项通过，最终目标专项 6 项和界面 11 项通过。原生 App-Dev 核验默认值、App/Mini-App 目录、取消和撤权确认；真实账号未执行新增或删除授权测试，写入与撤权在隔离夹具中验证。Dev 与 App-Dev 均在空闲后通过标准 Helper 重载，运行模块和服务资源来自当前 checkout。收据：`acceptance/messager-access-targets-20261103/receipt.json`。

### 消息流内的授权卡片（2026-11-03）

Bot 的权限请求、参数表单和 App 交接均挂载在消息流内；授权卡片紧随当前消息，显示目标 App/Mini-App 图标、实际名称及宿主，操作详情默认折叠。移除输入框上方重复的通用工具审批提示。访问授权主按钮为 `Allow this bot`，写入请求默认提供所需 Read/Write，读取请求不默认勾选 Write；确认后仍通过原 Bot/Run/Interaction 的 request_hash 审阅接口保存权限并继续原调用。

访问授权不等于付费调用许可。声明计费、敏感或特殊操作的调用在访问授权后仍显示带相同应用身份的单次确认卡片，不自动执行。已获得普通访问权的审批仍使用 Allow this bot；已获得访问权但需要特殊确认的调用使用明确的单次确认按钮。无法唯一解析身份时显示重试/拒绝，不伪造应用或持久授权。

内置组件可由原生 owner 提供匹配 mini_app_id 的 component_identity 显示信息；Package 仍要求真实 manifest。卡片不采用模型传入的名称或 URL，不改变工具路由、授权范围、版本防护与计费策略。切换 Bot/交互后，旧异步查询不能覆盖新卡片；提交后禁用旧按钮，避免重复提交。模拟接口与隔离 Run 验证，不批准真实待授权的绘图请求。

普通 pending 调用保存授权后批准原 Interaction 一次并唤醒原 Run；只授予 Read 而当前需要 Write 时不执行。计费/特殊调用先保存 App 授权，再展示独立的本次操作确认；允许 Bot 访问 App 不等于批准付款或计费。原 owner 的参数表单、invocation_policy、用户/资源归属与明确 deny 继续生效。

App 授权归属于 actor+Bot，不影响其他 Bot。新增授权供后续对话和新审阅任务捕获；已准入后台任务不扩大其冻结的 Provider/version 快照。撤权先使旧执行 epoch 失效并取消旧执行，再写入新权限；原任务/回执保留。原部分接口授权保留并标明 limited，不默认为整个 App 的 Read；用户保存新 App 设置时可明确替换/撤销旧授权。清除/重置生命周期同时失效这些 App 授权。

宿主新 API：GET/PUT /messager/bots/{bot_id}/app-access；GET/POST /app-access/requests/{run_id}/{interaction_id}。批准入口要求同源 Desktop、精确 Bot/actor/原 pending Run、当前声明与 request_hash。Provider/Tool 变更、取消和失效请求不能保存授权并启动原操作。旧 /access 接口保留为受限兼容路径。没有自动安装 Package、替用户启用开关或执行真实生成。

本阶段自动验证完成：完整 AaAT975项（618.33秒，退出0）、前端31项、旧功能38项、集成14项和最终 App 授权/迁移6项通过。当前 Dev 原生已核对 App 图标分组、Read/Write 与 Write 禁用状态；未保存实际授权或进行付费生成。原等待绘图请求经用户明确同意后取消。App-Dev 已标准加载最终版本；Dev 主体已加载，最终旧授权迁移修正等待新启动的浏览器/采集任务结束后再标准重启，不强行取消新任务。证据：acceptance/messager-app-read-write-20261103/receipt.json。

最终 Dev 加载补记（2026-11-03）：用户同意取消新批次后，操作前精确复核已无活动采集节点或等待 Run，未再取消任何额外任务。标准空闲检查通过，经 Helper 重启完成最后迁移修正。最终 Dev PID37161/63548、App-Dev PID35894/61969；App/Helper 源码根、实际导入路径和提供的界面资源均与当前 checkout 核对一致。旧“等待加载”状态已解除；证据见 acceptance/messager-app-read-write-20261103/activation-final.json。未代为授予真实 App 权限或进行付费生成。

### Bot 规划目录性能与权限即时性（2026-11-03）

实际 Dev Run 从准入到等待 image.generate 授权约58.16秒，两次模型步骤合计约4.35秒。逐 Tool 校验反复 capture/export 整个权限目录，逐 Provider 可见性检查再次重建全部 exports，而 App 导出又在未授权目标上查询 manifest，多层调用放大了目录/权限查询。

Bot owner 改为只验证当前调用的准入路由、冻结 Provider/version 与当前授权，未选 Provider 时覆盖所有准入候选，不能因同名能力的一个 Provider 获准就放行另一个。App Access 先筛选已授予目标，在单次 export 中按目标复用身份读取。复用只在当前调用局部，不缓存跨请求授权或撤权结果。

AppChatOwner 新增可选受信任 provider_visibility(scope,provider) 点查询；共享宿主先验证 Session 的 Provider/version pin 与当前注册对象，再交由 owner 判断可见性。默认 owner 仍执行原 exports membership。回调不授予 Tool 执行权，不替代 validate_authorization、GrantLease、付费或参数确认。Bot 注册组合层提供点查询；共享执行器不按业务 App 名分支。

新增 test_bot_planning_cost.py：125 Tool目录检查约0.03秒，首次 ModelCallAction 准备约0.05秒（无模型/网络/业务执行）；断言一次目录扫描、零递归 capture、零逐 Provider 全 exports 重建，当场撤权仍拒绝。两组不同 owner/capability 验证显式关闭、当前注册对象和升级 pin 拒绝，原 owner 保持旧规则。时间是夹具测量，不等于真实用户完整绘图耗时。

- 完成证据：后端 AaAT 门禁 987 项通过，规划成本夹具 5 项通过，Bot 前端单元检查 33 项通过。前端收到 `/state` 后先更新授权/运行状态，再读取 `/work`；任务列表慢不会继续遮住授权提示。Dev 与 App-Dev 已通过标准 Helper 加载并核验导入路径/资源，Dev 原生界面恢复输入；未执行真实绘图或替用户授权。详见 `docs/acceptance/messager-planning-cost-20261103/receipt.json`。性能数字仅为无真实模型的夹具。


### TTS/ASR 失败后的 ACPF 引导（2026-11-03）

Messager 朗读缺少模型或合成接口失败时，在消息旁显示“配置语音能力”，错误详情折叠展示。语音识别无模型或接口失败时显示同样入口。配置由现有 ACPF 完成 Runtime/模型/依赖 Package 的设备兼容、下载和用户确认流程，使用 configure_only；不执行 pip 命令、不替用户安装或批准。限流/权限/网络/麦克风与播放器错误不冒充缺模型。

TTS 原文保留，配置后用户重新点朗读。ASR 失败的录音仅在当前挂载内保留，明确点“重试这段录音”才再次识别；结果追加到可编辑草稿，不自动发消息。关闭页面/重启会释放该临时录音，不持久保存私密音频。过期的配置完成回调不能修改新录音或已离开的 Bot。共享消息控件只提供可选的 onSpeechError UI 回调；Messager 所有者决定 ACPF 请求，不改 AaAT/General/授权执行。

验证：15 项 Node 夹具通过，包括原消息不丢失、TTS 500 失败回调、429 不安装、缺 ASR 模型、录音显式重试、配置后不自动提交、离开后不回写。未实际安装 Package 或运行真实语音模型。仅静态脚本更新，打开/刷新 Messager 生效。

默认朗读修正：Bot 未配置专属声音时，使用 ACPF probe 当前 ready Provider 的精确 modelId，再选择该模型声明的默认预设音色；不继承 Chat 的旧模型/音色偏好。故障修复入口 ensure 不启用 installMore，已有就绪能力直接返回；用户主动安装更多声音仍保留多选安装。17 项 Node 检查通过，Dev 对原熊猫消息点击朗读后 Worker 返回 HTTP200、控件恢复空闲且未再提示安装。证据见 acceptance/messager-speech-acpf-20261103/default-model.json。

朗读播放修正：Messager 使用 Chat 同一 StreamingTextSegmenter（8/24/56 字阈值）分句，单路合成与顺序播放重叠，最多预缓存两段；首段就绪即播放，不等整条消息完成。不挂载原生 audio 控件，朗读图标切换准备/播放/停止。Bot 专属声音、ACPF 修复和取消/离开释放继续生效。共享消息控件通过 compactSpeech 显式启用；其他 App 默认保持旧行为。21 项 Node 回归通过，另有 3 项原 Chat 分句检查通过；多段重叠、缓存上限和停止为无真实模型夹具验证。


### AI 服务用量与交易付款的确认边界（2026-11-03）

- `ai.usage` 表示已配置 AI 模型/API 的正常推理用量，包括 Token、绘图、语音等。Bot 已获目标 App/Mini-App 的读写权限时，它本身不构成逐次人工确认理由；仍遵循既有模型配置、账户限额和执行预算。本次不新增或扩大预算，也不购买额度、开通订阅或自动充值。
- `purchase` / `payment` 表示购买商品、预订酒店/机票、外卖下单、支付等交易，必须单次明确确认。费用对应 AI 产品的充值、订阅购买也属于交易付款，不能标成正常推理用量。
- 旧的 `billing` 语义不明确，继续保守要求确认；新接入必须区分上述类型。不能把所有 billing 视为允许，也不能让模型或不受信任参数自行降级确认要求。
- Owner 声明实际副作用；原生文生图/编辑及其 Mini-App 改为 `ai.usage`，保留 network、workspace.write、artifact.create。Bot 将 ai.usage 归为写权限，未授权、只读、撤权和冻结权限校验照常生效；显式 confirm、敏感、删除、未知副作用仍单独确认。
- ai.usage 不等于只读或无副作用；网络故障/不确定结果不因此自动重试，避免重复生成及重复消耗。声明与 Provider 版本仍按原契约复核；历史待审批不会由页面自动批准，新声明也不自动恢复旧任务。


### Bot 短回合与独立 Agent-Chat 任务（2026-11-03，当前前台交互）

本节替代前台 Bot 一条 App Chat Run 占用输入直到执行结束的行为。原 App Chat/AaAT 执行器仍是工具执行权威；Messager 新增 owner 所有的短回合协调器，不在 General 添加 Bot 分支。

用户消息先持久保存，以 Session+request_id 幂等准入一个无 Tool 的短回合。模型只返回结构化 reply/task 决策：能依据当前对话、记忆与有界任务状态直接回答的简单交流立即回复；需要复杂推理、媒体生成、App/工具或多步执行的请求交给独立 Bot-Agent-Chat-Task。无 Tool 短回合不会调用 AaAT，也不接受模型自报的执行结果或授权。输入区仅在消息提交/附件录音等本地操作时短暂锁定，执行任务及其审批不锁住新消息。

每项执行工作是 Todo 的 managed Task，执行 lane 为既有 messager-bot:<bot_id>，与该 Bot 的已管理一次/定时任务共用串行槽位。原始即时请求本身构成创建本次执行任务的用户意图，不增加一张重复的“是否创建任务”审批；定时计划仍走原有显式计划审阅。排队不是运行成功，模型说明和界面状态不能代替真实 Todo/Agent 回执。

任务使用独立、不可任意复用的 App Chat Session；只有对应 Todo owner adapter 能准入原始请求和模型。其作用域绑定 actor、Bot、job_id，保存原始请求、Bot 身份/记忆及前台权限/可发现目录版本快照。排队不自动扩大旧任务的权限。实际调用继续复核当前权限、Provider 版本和声明。需要新的 App 访问时，原任务的 Interaction 在主 Bot 信息流出现现有 App 图标及 Read/Write 授权卡；付费、敏感或特殊操作仍须独立确认。新聊天消息不被偷偷当作另一个任务的批准。

原 AgentRuntime 执行模型和工具，Todo 调度执行、恢复和取消；协调器不创建第二套模型/工具循环。停止任务通过 Todo 取消原 Run，队列槽位等待真实终止后释放。重启只恢复已保存的 worker Session/Run，不重放已完成的外部调用；尚未提交执行的中断保持失败/中断回执，不能自动换 Tool 重试。撤权、清除对话和归档继续失效已准入执行的 epoch；清除/恢复只针对主对话，不把执行 Session 误当成可恢复主对话。

任务结果和媒体通过真实回执回写主对话，按消息展示。媒体只使用标准 artifacts 元数据和当前 Workspace 的实际名称、MIME、身份；不解析自然语言里的 art ID 来猜图、不显示固定“Conversation materials”区域。主对话到执行任务只传递原请求之前的有界历史与明确选中的附件；标准输出素材在同一 actor/应用作用域内按内容与来源验证导入，并重写精确引用。执行产物再导入主对话，消息分页和向上加载保留对应图片/视频/音频位置。错误、排队、授权、结果分别来自其原始状态记录。

接口：POST /messager/bots/{bot_id}/dialogue/turns（session_id/request_id/text/model/attachments）；GET /dialogue/state?session_id=；POST /dialogue/jobs/{job_id}/cancel。写入口要求同源 Desktop 和精确拥有的主 Bot Session。旧 App Chat 原语供可信 owner/Hook 与执行任务复用，不向模型提供新的任意委托工具。

验证使用真实 Runtime、SQLite、Todo lane、原 CapabilityPolicy/Interaction，模型与外部业务操作为夹具；覆盖等待审批时直接回复、第二任务排队、原 App 授权回接、撤权阻断、幂等、恢复原 worker、worker Session 防伪/防复用、同源 API，以及消息媒体归属/规范化/重复导入。真实付费图像生成不属于代码验收。

本轮完成：完整 AaAT 门禁 1001 项通过，最终 Bot 对话/任务用例 7 项通过，相关执行/授权用例 25 项通过，Bot 前端 42 项通过。App-Dev 真实问候 run_459ef59a55694e369befc81b7899571d 返回 kind=reply，无 Tool 步骤、无任务创建。Dev 两张历史图片已分别在各自结果消息中显示。Dev/App-Dev 标准 Helper 加载及 App/Helper source-root、实际导入路径、所提供资源均核验。排队与 App 授权回接为真实 Runtime+Todo/Policy 的夹具 E2E，未重复真实付费绘图。源快照之外，排队任务还接收同一主对话中较早任务的因果结果；附件仅先验证身份，耗时解析在获得执行槽位后进行。完整证据：acceptance/messager-dialogue-jobs-20261103/receipt.json。

### Bot切换加载（2026-11-03）

切换时同步呈现读取状态；打开会话与模型目录并行，获得会话后立即挂载完整输入框，模型目录与历史消息独立加载，消息不等待模型目录。目录尚未就绪时可编辑草稿，发送、附件和录音暂不可用；模型就绪后只更新模型选项，不重新创建输入框或丢弃草稿。任务状态异步补齐，不阻塞首屏完成。沿用Bot切换generation校验，旧会话响应不写入新会话；消息与滚动位置采用下节的五会话显示缓存；权限和审批仍实时读取。


### Task-Session 续接、计划版本与反馈协议（2026-11-03，实施规范）

Bot 对话、Task-Session、计划版本和执行 Run 是独立记录。短回合决定 reply / 新建 task / continue / plan_update / clarify；关联判断只使用当前主对话下最近 20 个 Task-Session 的摘要、已选任务和真实状态，不加载所有任务全文。歧义时询问；Session 保留有助于上下文复用，但不承诺 Provider/KV-Cache 命中。

尚未准入执行的排队任务可以追加用户要求与附件；追加内容独立持久保存、幂等去重，实际执行时复核原权限 epoch，再构造最终输入。已开始、等待参数/审批或已提交操作的 Run 均不原地改参数、指令或审批；补充要求排为同 Task-Session 的下一轮执行。完成任务复用其执行 Session 启动新 Run。被取消、失败或结果不确定的 Task-Session 不自动恢复/重放，应澄清或创建新的任务分支。用户停止一个 Task-Session 时，同时停止该会话的待执行续接，不能在停止后自动接着跑。

同 Task-Session 的 Run 串行；仍共享 Todo 的 Bot lane。Task-Session 保留原模型对话和真实产物，后续 Run 使用新请求的权限快照，不跨权限 epoch 沿用旧批准。任务归属优先于缓存。近期索引默认 20 项，固定项优先；退出索引/归档不删除历史、图片或审计回执。提供按需详情、固定/取消固定和归档入口。

修改定时任务创建可审阅的新计划版本，保存原目标、补充要求、原 Todo revision、当前背景授权与新执行绑定。确认后原 Todo task_id 保持不变，从下一次尚未准入的执行生效；已启动/已入队 Run 使用旧版本快照。拒绝、冲突、过期和权限变化不修改原计划。扩展删除、付费或敏感操作仍受新授权审阅和实际 owner 的特殊操作确认约束。

每次决策以宿主实际状态生成持久反馈：新建及排队、排队任务已合并、运行中补充已追加等待、完成后继续、停止后需澄清、计划变更待确认/已应用/已拒绝。反馈带 Task-Session/Run/计划版本身份，幂等去重。收到/正在准备不能冒充已执行；新聊天不能冒充批准。执行开始、取消及结果同样产生实际状态回执。

### 最近五个Bot的对话缓存（2026-11-03）

Messager挂载点内使用LRU内存缓存最近点击的5个Bot（包含当前Bot）。缓存保存只读界面快照、已经加载的消息/更早分页、滚动像素位置与文字草稿；不落盘，页面刷新/销毁失效。第6个Bot进入时淘汰最久未访问者。切回先同步显示缓存，随后后台重新验证Session并读取模型目录和最新消息；已上翻的更早记录保留，切出时及缓存显示期间的滚动位置在替换后恢复。

缓存不是执行器或授权缓存。快照的发送/工具按钮禁用，输入框临时只读，审批卡片、任务状态不复用；最新会话就绪后挂载真实控件并查询实时审批。停止原视图的轮询、语音播放/录音及监听，附件上传状态不保存为新会话授权。会话校验失败立即移除缓存，Session变化、空或截断历史丢弃过期消息。清空对话、归档显式失效对应缓存；销毁时清理全部。快速切换的晚响应不得替换新视图或覆盖新快照。该缓存仅用于显示，后端的Actor、Session、Run、版本和撤权检查保持原样。


### Task multimodal projection correction (2026-11-03)

Completed Task content may be text or standard multimodal blocks. Preserve lists as `openai_content`; never persist Python `str(list)` as user-visible text. Summaries extract text blocks only. Verified artifact identities remain bound to the current Session; media already embedded in Markdown must not gain a duplicate preview card. Exact legacy owner projections can be repaired from their canonical completed Run, retaining message identity/order, artifacts and execution audit without replaying model or effect calls.

### 对话模型安装入口（2026-11-03）

Profile对话模型菜单末尾提供“安装模型…”。入口通过Messager所有的text.chat.local请求打开标准ACPF，installMore允许选择其它模型，completionPolicy为configure_only；当前选择立即还原，不把入口值写为模型。取消不改模型；ready后重新读取目录，保留仍有效的当前选择。引导不提交对话/任务，不因安装而重试失败任务；用户切换Bot后不向旧Bot视图写回。Chat与Messager共用conversation-models.yaml中的设备/Runtime/Package/Checkpoint配置，原有Chat音频与Bot语音配置独立保留。

### 信息流素材与Chat对齐（2026-11-03）

图片以Chat风格缩略图呈现，点击或键盘Enter/空格放大，提供共用的“保存图片/加入素材库”按钮与成功/失败提示，不再显示原始stjob文件名下载行。音频、视频、PDF和文档等使用Chat共用artifact卡片，按格式提供受控预览、下载与加入Gallery；HTML等格式只下载/本机打开，不直接执行。已有正文内的同一图片不重复显示。

Gallery导入使用原Session artifact/attachment身份与Messager来源标识，继续由后端验证Actor和资源归属；不因渲染而授予Bot权限。导入后通知右栏Gallery刷新。拖拽保留标准资源引用。Bot退出/切换释放音视频、临时Blob与图片对话框；缓存展示期间不恢复可执行操作。下载/导入在隔离浏览器验证，实际用户素材未作为测试写入Gallery或下载。


### Bot 用户反馈、运行上下文与任务聚合（2026-11-03）

- 共享 Agent 将受管产物引用与助手正文分离：模型请求的独立 Runtime resource context 传递标准资源身份和用途边界，原助手文字保持干净。该上下文只用于后续定位，不授予权限，也不作为用户答复。旧平台固定提示仅可按已验证产物身份精确兼容清理；不对用户普通文字做模式删除。
- 每轮执行记录独立 step_label，由当前用户要求形成；宿主决定实际 queued/merged/waiting/continued/started 状态，简短反馈用动作描述解释接下来做什么，不冒称成功。无需为状态提示新增模型调用。
- Worker 以事实和标准产物向 Bot 交付，不独立邀请用户发起下一项工作。Bot 发布中间成果时读取同一 Task-Session 的实际后续队列；有后续工作时使用阶段完成/下一步说明及标准成果块，最终轮展示完整结果。失败/停止不宣告成功，审批继续说明原因并等待原交互。首次投影保存持久 presentation 回执，恢复后不因队列变化改写当时反馈或重复发布。完整 Worker 原始输出/执行审计保留。
- 右侧默认按 Task-Session 身份显示一张卡，展开各轮动作、状态和原 Todo 执行链接。执行中状态优先于排队状态；同名独立会话不合并。受管临时执行的 Todo 条目从旧平铺列表中排除，定时计划和用户手工关联任务仍保留原入口及下次执行信息。底层 Todo/Run 身份和历史不迁移。
- 图片呈现沿用另一会话维护的 bot_materials/Chat image card 预览、保存、Gallery 和拖拽实现，本次不改图片显示 JS/CSS 或渲染调用。


### Bot 自主补齐执行参数（2026-11-03）

Bot 优先按明确用户要求、已观察上下文和所选 AaAT 可信声明组织参数；未指定的可选参数使用已配置/声明的默认值。参数完整或可由默认值补齐时直接调用能力，不主动用 app.collect_parameters 再要求用户确认普通参数。图像 owner 明确声明模型、尺寸、质量和格式的默认规则；不能跨 owner 在 General 写图像特例。

必须询问的情况包括：缺少必要素材或私有事实、资源身份有歧义、所需模型/配置不可用、用户明确要求挑选参数、owner 声明强制确认。不得臆造用户照片、替换明确模型、降低明确尺寸或额外提升预算/质量范围。参数补齐与 App 读写权限、交易/敏感操作确认、安装和原审批分开，不能把“参数已确定”当作执行授权。


### 询问必须带任务上下文与明确待补项（2026-11-03）

每个 Bot 询问应说明任务、当前步骤、具体缺少/拿不准的参数及原因、用户需要回答的内容/可选项，以及回复后将继续什么。Bot 可信指令明确要求这一表达；前台 Task 的宿主快照还绑定实际 Task-Session、step_label 和原用户要求，作为参数表单/审批/普通问题的可见说明。说明是只读展示数据，不改变原 Run/interaction 或审批语义。

参数表单继续使用共享组件的当前 owner 声明、动态 missing/invalid 字段和字段标签列出真实待补项，已确定值保留预填；Bot 的任务说明放在独立外层，表单重绘不能清掉它。无缺项的显式参数审阅不谎称缺参数。计划/后台任务也展示原任务目的；其参数表单仍挂载到原 Run、原 interaction 并经同一 API 校验/提交，其他 App 交接保留原流程。权限、交易和敏感操作确认独立，不把任务说明作为授权。

### Descriptor inspection and access lookup failure (2026-11-03)

A foreground Bot may read capability.describe for a Provider in its frozen discovery inventory without an execution approval. The descriptor Tool must be effect-free and require no execution capabilities; current Tool revision and selected Provider identity/version are checked. This supplies parameter information only and grants no business execution, App Read/Write access, background authority or special-operation confirmation.

An access lookup returning a deterministic unresolved target displays that the operation has not executed and offers cancellation, without Retry or Allow. Transport/loading failures offer explicitly labelled Reload access information plus cancellation; this reload only repeats the read-only lookup and never repeats business execution. Existing pending approvals are not automatically approved or replayed when loading a fix.

### 上传附件缩略图与用户气泡（2026-11-03）

消息展示从同一 Session 的附件记录读取实际媒体类型和大小，补齐历史消息中仅有 ID/文件名的附件引用。图片沿用 Chat 风格缩略图、放大预览、保存图片和加入素材库操作；不按扩展名猜测类型，不改变原 Run 输入或访问权限。用户文字气泡按内容收缩，附件独立右对齐，较宽附件不会撑大短 Prompt。

验收：后端 23 项、浏览器 15 项通过；Dev/App-Dev 来源及实际服务资源核验完成，App-Dev 实机确认原上传 PNG 缩略图、打开/关闭预览和短气泡。下载与 Gallery 写入仅在隔离夹具验证，未修改实际素材。记录见 `acceptance/messager-upload-thumbnails-20261103/receipt.json`。

### 左侧 Bot 工作状态（2026-11-04）

Bot 卡片用蓝色单环表示生成回复，紫色双环表示执行 Task，无常驻文字；悬停说明具体状态。两种状态独立、可同时显示，紧凑侧栏也保留。任务排队或等待确认/回复时暂停双环，完成后移除；减少动态效果偏好下禁用旋转。

目录按用户隔离读取真实活动对话 Run 与独立 Task/已关联 Todo lane，不以最后一次已完成消息推断工作状态；当前 Bot 跟随对话状态更新，Bot 列表每5秒刷新。状态展示不授予权限或启动任务。后端15项、侧栏6项及隔离浏览器窄栏双圈布局检查通过；App-Dev真实API字段和服务资源核验完成，Dev/App-Dev经标准Helper空闲重载。未调用真实模型制造任务。

### 对话未读与已读位置（2026-11-04）

Bot 卡片绶带只统计主对话中已读位置之后、状态为 completed 的 assistant 消息；后台 Task 的内部工作 Session（`dialogue_job`）及归档 Session 不参与列表计数，也不能作为对话已读接口的目标。列表与对话页遵循同一可见会话范围，避免轮询时互相覆盖而闪现绶带。用户、工具和系统消息不计数。站内提醒继续属于消息箱，独立统计，不再叠加到 Bot 对话未读数。每个用户/Bot/Session 保存单调推进的已读序号；会话归属、Bot 和归档状态在服务端校验，不能跨用户/会话写入或提交超过消息末尾的位置。

首次启用以现有主对话末尾作为一次性基线，不追溯旧历史。新消息从基线之后计算；服务重启不重置游标。切换到有未读的 Bot 时优先加载第一条未读开始的窗口，显示“以下是未读消息”分隔线，超过50条可继续向后获取；无未读时沿用最近5个Bot缓存及滚动位置。只有当前挂载且可见的对话滚动到底部，才将已加载的末尾序号确认为已读。停留在历史位置、后台或离开对话不会清除；新回复继续累计。

验收：10项Python和9项Node/浏览器检查通过，覆盖游标单调性、并发新消息不被旧确认清除、归属隔离、归档、首次迁移、首条未读超出最近50条、后台不清除和缓存位置恢复。Dev/App-Dev由标准Helper空闲重载，App/Helper来源约束、运行模块路径及实际服务资源核验通过。App-Dev实机确认正常历史展示，原临时预览提醒已按精确ID静默清理；新增回复/滚动行为使用隔离夹具，未调用真实模型制造消息。见 `acceptance/messager-read-cursor-20261104/receipt.json`。

### 消息流直达末尾（2026-11-04）

Bot消息流底部居中显示悬浮向下箭头圆形按钮，Hover-Tip为“滚动到消息末尾”。下方还有超过32px内容时显示，点击立即到达已加载消息末尾，到底隐藏；不占消息布局。滚动、消息/素材高度变化和窗口/侧栏调整自动更新。沿用可见到底的已读规则；3项浏览器检查通过，App-Dev真实对话验证按钮出现、点击及隐藏，实际服务JS/CSS与checkout一致。

### 内容清理与持久权限分离（2026-11-04）

清除对话、恢复上一份对话、清除长期记忆保留用户已授予的 App/Mini-App Read/Write 和旧版权限配置。操作仍推进权限 epoch，使旧上下文的 Run、审批和提案失效，停止相关执行并暂停关联计划与 Hook；新对话按当前保留权限重新准入。默认只有删除/归档和重置 Bot 清空持久权限；清除对话时也可通过明确勾选撤销权限。恢复对话内容不恢复历史授权或自动重启任务；旧版本已经丢失的权限不能猜测重建。确认弹窗按这两类操作说明实际影响。


### 清除对话的组合选择（2026-11-04）

清除对话的模态确认框包含两个独立且默认不勾选的选项：“同时清除长期记忆”“同时撤销 App / Mini-App 访问权限”。打开/取消/完成后清空选择，其他清理入口不能继承这些选项；提交期间禁用选择及重复提交。动态说明和按钮反映所选范围，取消为初始焦点。恢复对话不恢复已清除的记忆、已撤销权限或调度。

API 一次提交 clear_dialogue 与严格布尔选项 clear_memory / revoke_access，省略均为 false；非 clear_dialogue 动作拒绝额外的 true 选项。清理审阅摘要包含当前权限版本，确认后权限或内容变化会要求重新审阅。先使旧上下文的执行/审批失效并暂停关联调度，再在一个 SQLite 事务中归档对话、清理所选记忆及撤销所选持久权限；事务失败不部分提交这些所选持久变更，但已停止工作不自动恢复。授权撤销仍由 Bot 权限 owner 执行，不依赖客户端自行连续调用多个清理接口。

### Dev Mobile Bot 测试入口（2026-11-04）

Dev 的 Messager 已接入可信 host Mobile Gateway，实际目录验证 enabled=true、supported=true、requiresCloudUpgrade=false。手机刷新该设备的 App 列表后打开“消息 / Messager”。只开启 Dev 的设备策略，不复制到 App-Dev 或生产。

专用手机页面提供Bot列表/详情、真实未读和分页、默认Agent模型与手动选择、持久化对话、上传附件、受管图片/音视频预览与下载、任务状态/停止/续接及站内提醒。共享原 Bot/App Chat/任务服务与同一Session；不注入桌面身份或放宽Bot权限。管理、好友、语音、Gallery及审批/参数补全继续由桌面处理，等待时手机显示明确提示并可继续聊天。

定向Python24项、390px手机浏览器网关链路1项通过，覆盖真实服务权限隔离、上传/读取、稳定请求去重、模型安全投影、头像归属、发送/图片去重、输入区可视高度变化。完整AaAT门禁结果见 `acceptance/messager-mobile-dev-20261104/receipt.json`。真实iPhone联调由用户测试确认；未执行真实模型验收请求。通用协议沿用原Cloud通道，无Cloud代码改动。

### 等待用户协助的列表状态（2026-11-04）

Bot 存在 `waiting_input` / `waiting_capability` 的活动对话或任务时，列表返回 `needs_user_assistance`，桌面及手机以右上角橙色白色 `!` 绶带显示。该状态不等同于未读；左上角蓝色未读计数可同时存在。进入对话或标为已读不会清除协助状态，只有原等待工作恢复或结束才清除。等待项不显示工作转圈，同 Bot 的其他实际回复/任务可继续显示各自转圈。展示投影不改变权限批准、参数表单、取消或恢复协议。

### Mobile Bot Profile 与专注对话（2026-11-04）

Bot 的对话模型保存在 Local 的 actor/Bot 专属 Profile 中，使用 revision 防止桌面与手机相互覆盖。桌面首次读取时将有效的旧浏览器选择迁入 Profile；已有 Profile 始终优先。旧 Bot 没有持久设置时，兼容最近一次真实前台主对话模型，再使用系统 Agent 默认路由，不能取其他 Bot 或 Task worker 的模型。此迁移不合并 Dev/App-Dev 数据。

手机对话页不显示模型选择，也不把模型目录加载作为发送前提。发送接口使用服务端的 Profile 模型，忽略旧客户端提交的临时模型值；当前请求仍由原 Bot 对话服务冻结、去重与执行。尚未配置任何可用默认模型的新 Bot，可从右上角详情进入 Profile 设置。

进入 Bot 对话后，通过现有带 mountToken/instanceId 的受信任 Shell 消息隐藏 App 页头与底部 Dock；返回列表恢复，在重新激活缓存 App 时重新同步。未添加 Cloud 或浏览器控制协议。

右上角详情按钮打开手机全屏面板：Profile 可编辑名字、职责和对话模型；任务会话可查看和选择继续，权限、记忆、语音等显示现有设置。权限授权/审批、记忆与语音策略修改等仍在桌面处理，此入口不扩大执行权限。

### Mobile 页面滑入与返回（2026-11-05）

Bot 列表 → 信息流 → Bot 详情使用同一组保留 DOM 的页面栈，参照情报中心以 240ms ease-out 从右侧滑入；返回时当前页向右滑出。Bot 详情不再使用带 Close 的弹窗，左上角返回按钮回到原信息流。

信息流和详情均支持单指向右滑动返回上一级（水平位移超过 72px，且大于纵向位移的 1.5 倍）。输入框、选择器、按钮、链接、代码横向区域、媒体控件以及打开的图片预览不触发返回；多指、纵向滚动和取消手势不返回。减少动态效果设置下直接切换。详情页期间继续读取任务状态，但不改变原消息流滚动位置，也不因隐藏消息流的尺寸为零而误标已读；返回保留草稿和滚动位置。此变更仅涉及 Mobile HTML/CSS/JS。

### 原生边缘返回与防闪动修正（2026-11-05）

仅监听内容 touch 手势不能覆盖 iPhone 原生边缘返回：Bot 的列表/信息流/详情必须向 Mobile 宿主登记两层 UI 历史，不能让浏览器直接弹出整个 App。当前通过通用 `ai2apps.shell.navigation.push/back/history` 完成，宿主校验 active trusted frame 的 origin、mountToken、instanceId 和连续有界 depth（≤20），拒绝 sandbox/后台 mount。原列表历史项先登记 depth=0；信息流/详情分别 push 1/2。

参照情报中心的区别处理：按钮及页面内返回先请求宿主 `history.back()`，宿主 pop 后回传 `animate=true`，只播放一次页面动画；浏览器/系统原生 pop 回传 `animate=false`，保留同一 iframe，直接恢复已保存 DOM/UI。取消未完成的 WAAPI 动画，强制布局并跨两个 rAF 暂时禁用过渡，避免重复动画、App 重挂载及加载闪动。缓存记录支持 Forward，不重复创建会话；打开尚未完成即返回的情况，Forward 只恢复原 Bot 的读取流程。

宿主模式下最左侧 24px 留给系统手势，不由内容 swipe 再触发一次返回。手机必须刷新整个工作区网页加载新宿主脚本，仅退出/进入缓存的 Bot iframe 不会升级宿主。


## 快捷 Bot 类型设计：Flash-Bot 与 ASC-Bot（2026-11-05）

状态：B0 及 Flash 固定计算器首批已实施，详见 [B1 计算器](flash-bot-b1-calculator-v1.md)；ASC 和发票工作流待实施。下列脚本与 owner 接口仍为拟议契约；当前实施范围和阶段顺序以 [非标准 Bot 开发计划 v1](bot-types-development-plan-v1.md) 为准。

### 类型与共用基础

| 类型 | 入口 | 决策与执行 | Task 创建时机 |
| --- | --- | --- | --- |
| 普通 Bot（拟议 execution_mode=agent） | 对话、既有计划/Event Hook | 对话判断直接回答或创建 Agent Task，按需发现 AaAT | 实际需要执行时 |
| Flash-Bot（execution_mode=flash） | 明确的输入类型与 pattern，可为结构化表单/上传区 | 代码校验、固定代码工作流；不经过通用 Agent 规划 | 输入验证通过后 |
| ASC-Bot（execution_mode=app_shortcut） | 点击列表条目/快捷入口 | 打开目标 App/Mini-App，恢复预设，再由目标 UI 接收输入 | 目标 App 实际提交工作时 |

共用 Bot 稳定身份、actor 归属、名字、头像、可见性、版本及既有授权机制。App/Mini-App 仍是单一 enabled 访问开关；Bot 使用授权、协作计划和特殊操作确认独立。类型通过显式字段识别，不靠名字、头像、职责文本或模型猜测。列表可统一展示，但以图标/类型提示区分点击行为；ASC 不伪造聊天会话，Flash 不伪装成通用对话助手。

类型配置与实际 App 状态分开存储，并有 revision。修改仅影响后续启动，已准入 Task 保留原 workflow/config、Provider/version、输入及权限快照。改变执行模式不直接改写在运行或排队的工作；配置变更需先处理受影响任务。删除入口不删除既有产物、任务审计或 App 数据。普通 Bot 的长期记忆/自主激活不能未经显式设计直接套到快捷类型。

### Flash-Bot：固定输入与代码工作流

入口链路：接收输入 → owner 代码校验 → 持久创建一次 Task → 执行固定工作流 → 投影真实结果。输入不合格时给出拒绝原因、支持的格式和示例；不创建 Task，不自动转交普通 Agent 猜测，不静默修正成另一种任务。

输入契约须声明 schema/version、文本 pattern/语法、文件 MIME/大小/数量、必填参数、错误文案与资源上限。正则也需要长度/复杂度界限；不能用危险 eval 解析表达式。文件除扩展名外仍由业务 owner 检查实际格式和解码限制。身份、源资源归属、输入不可变引用由宿主绑定，不由输入文本自报。

工作流引用已注册的可信实现及版本，不把用户输入当代码，不让模型临时生成脚本执行。步骤、分支、重试条件、输出契约由代码决定。工作流可以使用模型：例如发票识别使用视觉模型，但识别后字段校验、人工补充、去重与归档仍由 owner 控制。模型输出是待校验业务数据，不是执行授权，也不能增加工作流步骤。

复用 Todo/既有 owner Task adapter 与原任务生命周期，不建立第二套执行器、任务状态或审批库。每次合格提交用稳定 request_id 去重，配置和输入版本在准入时冻结；首期复用 Bot 串行 lane，后续并发必须由工作流明确声明。聊天/输入界面不等待工作槽位。明确显示验证失败、已入队、运行、待用户、完成/失败/取消，进度取真实执行状态。

取消、重启和未知效果不自动重做已执行的业务步骤；效果提交复用业务 owner 的幂等/检查点。必要参数和敏感操作继续通过原持久 Interaction 说明“什么任务、正在做什么、哪项信息不确定及为什么需要用户”。代码工作流同样不能绕过 App/Mini-App 访问、资源、预算和特殊确认。

初期例子：

- 表达式计算：安全解析器与受限数值运算，限制长度、计算复杂度、数值范围；不需要模型或工具规划。
- 发票识别归档：图片验证 → 固定识别能力 → 字段/业务校验 → 重复检测 → 受控归档 → 结果回执。识别不确定或重复可能时按业务策略询问，不因再次上传或超时重试重复归档。

每份输入默认是独立执行。诸如“再给它戴帽子”的任意对话续接不在固定输入契约时应拒绝并解释；允许续接的工作流需要显式声明稳定对象/版本参数。Flash 的低延迟来自省去通用规划，不承诺模型识别或外部服务必然即时完成。

### ASC-Bot：App 解读的跨端状态脚本

用户在 App/Mini-App 调整好配置后，选择“保存为快捷 Bot”。目标 owner 通过受控 export 导出可移植状态，用户预览目标、参数、所需输入及是否输入后自动提交，再保存名称/头像/配置版本。不能通过录屏、DOM、鼠标步骤或完整浏览器快照代替状态导出。

“脚本”采用有版本、可验证的声明式指令；不执行任意 JavaScript、Shell、模型生成代码、任意 URL 或文件路径。宿主解析打开目标的指令；App 选择自己的组件，Mini-App 解释自己的参数。仅注册的 owner 能定义操作和配置 schema，不能把业务含义放进 General Agent 或通用 Shell。

拟议脚本骨架如下，所有尖括号内容为占位符，不是现有 ID，不可直接执行：

```json
{
  "schema": "ai2apps.app-shortcut/v1",
  "steps": [
    {"op": "open_app", "app_id": "<Imagine Studio 稳定 ID>"},
    {"op": "select_mini_app", "mini_app_id": "<风格转换稳定 ID>"},
    {
      "op": "apply_state",
      "state_schema": "<目标组件配置 schema/version>",
      "state": {
        "style_id": "<吉卜力风格稳定 ID>",
        "model_ref": "<Image 2.5 Flare 稳定模型引用>",
        "width": 1536,
        "height": 1024,
        "quality": "high"
      }
    },
    {"op": "await_input", "slot": "source_image", "submit_when_ready": true}
  ]
}
```

示例分辨率仅演示字段形式；实际参数名、比例/分辨率组合、质量和风格选项由组件声明、验证和规范化。名称只用于展示；App/Mini-App/模型使用稳定 ID/引用，不能通过可见名称、平台坐标或临时目录定位。资源不使用创建机器上的绝对路径。

恢复前先验证整个脚本、目标可用性和状态 schema，再向目标 owner 一次性应用完整配置，避免逐字段设置触发刷新而覆盖前项。拟议 owner 契约包括 export、validate、apply、能力/平台兼容声明；复用既有受信任 mount/instance 和业务服务，不增加任意 iframe 发消息即可执行的旁路。旧配置只有 owner 提供明确版本转换时才转换；失效配置提示具体字段并允许重新保存，不猜测参数含义。

默认保存配置而非上次输入材料、账号状态或运行进度。凭据、Cookie、Token、原 mount/session、审批结果、任务 request_id、安装路径及运行句柄都不进入脚本。显式绑定 Gallery 等固定素材需保存受控资源引用，并在每次打开/执行时检查当前访问与可用版本；不能因快捷入口保存过就自动获得读取权。

已有目标页面存在未保存编辑时，不静默覆盖；由目标 App 在独立实例/草稿中应用，或明确提示用户选择。重复点击和重连不重复创建实例/提交任务；执行关联启动 request_id，输入就绪后的提交仍走目标 App 原业务入口。

“拖入图片即生成”是显式保存的输入就绪行为，不是脚本直接调用任意 AaAT。目标组件必须声明支持，且在实际图片校验、参数验证、模型/Runtime 可用性和当前权限通过后，只提交一次。拒绝、取消、必需的敏感确认和任务未知结果不被该行为绕过。输出继续归目标 Studio/App 原有输出与素材机制，不另建 ASC 输出历史或下载实现。

### Desktop/Mobile 可见性与执行位置

脚本可移植不等于定义已经同步，也不等于两端已经具备目标能力。分别判断：

1. 可见性：Bot 定义是否在当前 Mobile 所连接的 Local/账号范围内，由原 Bot 目录与访问权限决定。同一 Local 的 Desktop/Mobile 应读取同一份定义；独立安装间同步、Cloud 存储或中继另立需求，不假定现已具备。
2. 可打开：目标 App/Mini-App 是否有该端受支持的 UI 与脚本解释器。Mobile 的上传/拍照控件可与 Desktop 拖拽不同，但使用同一输入契约。
3. 可执行：云模型、本地 Runtime、模型配置、执行宿主、资源访问、配额与预算是否满足。模型/组件缺失可走 ACPF 配置，配置完重新验证并恢复原快捷入口，不替用户静默更换模型。

| 情况 | 拟议行为 |
| --- | --- |
| 当前端支持 UI，所选执行宿主与能力可用 | 恢复预设，等待输入，按保存策略提交 |
| UI 支持但需要 Desktop/Local Runtime | 显示执行位置，经既有授权入口交由该宿主运行 |
| 缺少可安装组件/模型 | ACPF 配置后继续原入口 |
| 当前端不支持组件或宿主离线 | 显示具体原因及可选执行入口，不假装可用 |
| 参数、模型引用或 schema 失效 | 标出失效项，请用户修正并重新保存，不静默替换 |

云模型本身不需要 Desktop GPU，但当前 Mobile Messager 通过连接 Local 的 Gateway 工作。不能据此承诺 Desktop/Local 离线后仍可独立运行云模型；独立云执行宿主属于另项能力。未来如增加定义同步或独立云执行，按仓库 Cloud 边界提交需求，不从本仓库直接改 Cloud 代码。

脚本和预设不携带授权。Mobile 的身份、资源范围、目标宿主与敏感确认仍按实际接入契约校验；Desktop 已批准一次操作不能变成 Mobile 或另一个安装的通用批准。

### 建议实施顺序与验收

按 [非标准 Bot 开发计划 v1](bot-types-development-plan-v1.md) 的 B0 → Flash → 通用 App-State → ASC → Outlet → Mirror 推进。Flash 先计算器、后发票；不再把发票扩展排在 ASC 之后。App-State 先统一 export/validate/apply 与版本合同，再分阶段接入 App/Mini-App。
验收须覆盖：无效输入不建 Task；重复提交只执行一次；工作流配置更新不改旧任务；无模型的计算器和需模型的发票流程分别计量；脚本整体校验/单次应用；不包含机器路径/凭据/审批；Mobile 不支持或 Local 离线的明确反馈；组件/模型失效；取消及 ACPF 回接；有未保存草稿不覆盖；拖入图片仅生成一次；特殊确认仍有效；输出归原 App；不修改普通 Bot、记忆维护与 Event/Hook 执行。

### Mobile 自动刷新频率（2026-11-05）

移除 Bot 列表和对话页头的手动刷新按钮。列表页可见时，每 5 秒刷新当前标签（Bot 列表或消息箱）；对话打开时，消息流仍每 2 秒增量读取。进入列表、切换标签、页面重新可见及已读状态变化仍会即时读取对应数据。页面隐藏时暂停轮询，离开页面时清理两个计时器。


## 外部代理与跨实例映射：Outlet-Bot、Mirror-Bot 技术草稿（2026-11-05）

状态：已纳入后续开发计划，技术草稿待细化，未实现、未开放外部入口或跨实例授权。本节补充前述快捷 Bot，不将现有同 Local、同用户的 Bot 通信误写为已支持外部人员或跨实例。关注/收集/知识/审阅等属于用途或模板，不再据此增加独立执行类型。

### 分类维度与身份

拟议配置使用三个正交维度，不建立 agent/flash/shortcut/outlet/mirror 五选一的互斥枚举：

| 维度 | 拟议字段/选项 | 所属职责 |
| --- | --- | --- |
| 执行方式 | execution_mode：agent / flash / app_shortcut | 源 Bot 如何处理输入 |
| 交互对象 | audience：owner / outlet | 是否接收外部参与者消息及对外代理规则 |
| 身份位置 | location：local / mirror | 真实 Bot 与执行权所在实例 |

Outlet 可采用普通 Agent 或 Flash 固定工作流；Mirror 是源 Bot 的映射，不再选择一套本地执行逻辑覆盖源 Bot。对于远端 ASC 的 UI 交接、远端 Outlet 的外部通道操作，必须分别声明支持；不能因维度可组合就默认所有组合都已可用。

本地 Bot ID、外部通道身份及远端 Bot 引用分别建模。远端稳定引用至少包含来源 namespace/installation/instance、source_bot_id 及当前导出契约版本；命名空间来自经验证的连接，不接受模型自报。名字仅展示，允许本地别名，不能用同名推断同一个人/Bot。外部发送者身份不映射成 owner principal。

### Outlet-Bot：外部与内部之间的代理

Outlet 面向非主人参与者，例如微信群替身：接收群内 @ 与外部私聊，在允许的范围内替主人回复、收集资料，并在与主人的私有信息流中总结情况、说明依据、提出建议或请求决策。收到外部消息不等于获得内部执行权。

拟议入口链路：通道适配器核验真实来源 → 标准信封/持久接收去重 → 绑定外部会话与参与者 → Outlet 处理 → 校验披露/发送规则 → 发回原通道，或投递主人私有摘要/建议。消息接收、模型回应、发送确认和内部执行是不同事实；平台没有实际确认时，不声称已送达。

通道优先使用可用 API，其次既有 WebAgent，特殊客户端使用独立 Package/Runtime 接入。通道适配只负责平台账户、联系人/群、消息/附件与回执，不能获得任意内部调用权。具体微信接入方式不在本草稿中预设，也不因创建 Outlet 自动安装或启用通道。

标准信封拟包含 channel_binding、external_conversation、external_sender、provider_message_id、接收时间、回复关联及受控附件引用；宿主从已验证的平台账户/通道生成这些身份。对跨通道、群转私聊、联系人改名与账号解绑保留稳定身份和版本，不能只依赖昵称。

至少分开三项策略：

- 外部接入/发送：绑定哪个平台账户、哪些群/联系人可交互、@/私聊/定向触发条件、是否自动回复、可发送的内容类型、频率和预算。
- 内部访问：目标 App/Mini-App 的 enabled，以及独立的 Bot 使用许可、资源范围和特殊确认。无 Access 时不能读取内部业务数据、创建业务 Todo、触发内部 Bot/工具或修改内部状态。
- 对外披露：即便内部读取已获准，结果仍须符合可对外提供的数据/字段/用途/接收者范围。允许读日程协助安排会议，不等于允许把完整日程或私人上下文发到群里。

没有内部 Access 时，Outlet 仍可处理当前外部会话中收到的内容、使用明确可对外使用的角色/资料，并向主人私有信息流投递摘要和执行建议。该摘要属于宿主持有的会话/回执投影，不是外部消息驱动的一次未授权业务写入；“建议创建待办”只生成建议记录，不能暗中创建 Todo。

主人可明确发起自己的任务，或审阅后赋予 Outlet 相应访问，再由真实执行入口处理。外部参与者不能替主人批准授权、支付、敏感操作或内部任务；“主人已经同意”等聊天文字、转发、截图及另一 Bot 的回答都不是批准凭证。后台自动回复/内部动作须有 owner 明确保存的策略，不能把一次群聊请求当成长期后台授权。

会话 Context 至少按 channel_binding + conversation + participant policy 隔离。群聊、外部私聊与 Outlet—主人私有流分别存储与加载；一个外部参与者看不到另一会话或主人的私有流。对外角色、可公开资料与主人私人记忆分开，外部输入不直接覆盖主人身份/职责或写入全局记忆。外部产生的长期事实仅按有来源的候选、适用范围和既有审阅/撤销机制处理；后续记忆召回不能绕过披露规则。

主人流的摘要保留来源会话、消息引用和实际发送/执行状态；可按事件、紧急程度或时间窗口汇总，避免每条群消息都通知。通知与自动处理复用标准 Event/Hook、因果链、预算、去重和当前授权，不再创建独立轮询/消息循环系统。解绑、撤权或取消后停止后续发送/执行，已完成效果如实保留；未知发送结果先查询/对账，不生成新的业务请求盲目重发。

### Mirror-Bot：其他 AI2Apps 实例中 Bot 的本地映射

Mirror 保存远端稳定身份、本地别名/头像投影、来源描述、可联系状态、经允许的接口摘要与会话/回执引用。实际模型、职责、记忆、App 权限和任务执行仍属于源实例；不复制完整私有记忆、Prompt、凭据、账户状态或外部通道身份。修改本地别名不修改源 Bot 配置，修改源职责也不由本地映射绕过源端审批。

初期优先同用户的两个已明确绑定的 AI2Apps 实例。跨用户/组织的身份映射、分享/租户边界、保留与删除策略另立阶段；不会因为名字、同一 Cloud 账号标识或一个可访问 URL 就默认建立信任。

权限由多个边界共同约束，而非复制源端权限：

1. 本地调用方是否允许使用这个 Mirror、是否允许发出该种咨询/任务与资料。
2. 源端是否公开可发现、是否明确允许这个经验证的对端身份/实例调用其导出接口，以及导出范围、期限和预算。
3. 源 Bot 在源端是否具备执行所需 App/Mini-App/资源权限；特殊操作在真正执行处继续确认。
4. 结果与附件是否允许返回该接收方、本地实例及最终外部通道。源端允许读取不等于允许复制到本地或再发给群友。

Public 仅表示可发现，不代表已授权执行。两端范围取共同允许的导出操作/数据范围；不是把不同实例的 Provider ID 列表直接拼接成联合权限。本地允许访问 Mirror 不授予源端 App 权限，源 Bot 权限也不会变成本地 App 权限。Outlet 调用 Mirror 时，继续保留原外部来源与披露约束，不能把它洗成主人直接请求。

传输凭据由宿主连接管理持有，不进入模型、Bot 配置或 ASC 状态脚本。每次请求绑定经验证的源/目标实例与 Bot、调用方、request_id、契约版本、有效期及因果关联；接口和字段由源端声明，使用可信 owner 适配器，不在 General Agent 按远端 Bot 或业务名称加入分支。具体传输/配对协议在实施前盘点既有 Gateway/Remote 能力，本文不虚构已存在的 RPC API。

本地持久保存发送记录，源端保存去重/准入记录，并关联本地请求与源 Task/Run。状态区分未发送、已接收、已接受/排队、执行、待确认、完成、失败、取消及结果未知；HTTP/网络发送成功不等于任务完成。重连优先查询原请求，不靠重建任务恢复。取消只请求源端停止，收到源端终态前不能声称已经取消；已发生的效果不回滚。

源实例对实际执行、检查点、结果和审批持有唯一执行权。本地可以协调和显示进度，但不能再建立一个竞争执行相同业务的 Task。需要用户确认时转发原交互的可信引用，由源端验证审批者及本次参数/版本；本地 Mirror 不能伪造确认结果。对端离线、解绑、撤权、契约更新或失效均应明确显示，并拒绝新准入；重连不恢复已取消/失效工作或静默获得新权限。

附件通过明确共享范围与有效期的受控资源传递，验证 MIME、大小、来源、完整性和接收范围；不向模型暴露任意内部路径、下载凭据或 bearer URL。业务数据和候选记忆仍保留原来源；Mirror 不默认同步记忆，任何回传须复核跨实例共享许可后才能接入既有候选机制。

跨实例委派保留原因果/root、参与者和去重关联；每个执行端都施加本地上限，换实例、Mirror 链或重启不重置授权与预算。防环应解析到真实来源身份与任务等待关系，不能只看本地 Mirror ID。首期仅接受直接映射真实源 Bot，不开放任意多级 Mirror 转发；跨实例预算协调与恢复必须另行验证，不能把当前同实例防环称作已经解决。

### 后续开发阶段与验收

以下阶段是已登记待办，不代表本轮授权实现或部署，也不强制抢在 Flash/ASC 之前：

| 阶段 | 计划范围 | 验收重点 |
| --- | --- | --- |
| TYPE-1 共用建模 | 明确执行方式/交互对象/身份位置；独立配置、稳定引用、UI 标识和版本 | 普通 Bot 不变；不靠名字识别；不支持组合明确提示 |
| OUT-1 接入骨架 | 单通道适配器、真实发件身份、持久信封、会话隔离、去重及 owner 绑定策略 | 无 Access 不执行内部功能；群/私聊/主人流不串 Context；重复消息不重复发送 |
| OUT-2 代理与主人流 | 普通回复或 Flash 工作流、可对外资料、披露规则、私有摘要/建议、原审批回接 | 外部文字不构成主人授权；内部读取不等于允许外发；摘要/建议不偷建业务任务 |
| MIR-1 直接文本映射 | 同用户两个已绑定实例、直接映射普通源 Bot、导出/导入许可、原请求状态与文本回接 | 单边授权不能执行；离线与 Public 不冒充可用/获准；重连去重及解绑撤权 |
| MIR-2 任务与资源 | 源 Task/Interaction/取消的可信回接、Flash 结构化入口、受控附件和因果/预算关联 | 未知结果不重放；源执行权唯一；附件不越权；跨实例循环与恢复故障注入 |
| OUT/MIR 后续 | 多通道、多实例、远端 ASC UI 交接、跨用户/组织分享 | 分别评审身份、披露、租户和 UI mount 边界，不由前期自动开放 |

设计细化先完成类型/主体/信封/导出授权契约和目标传输能力盘点，再选择一个通道及两个测试实例。接入验证分为适配器与模型夹具、隔离实例联调、真实外部账户效果；真实发送、授权或付费按具体任务取得明确授权，不因草稿已登记就执行。

共同必验：非 owner 外部身份冒充、群消息注入、附件归属、跨会话/私有记忆泄漏、允许内部访问但禁止外发、同名 Bot/实例混淆、仅一端授权、离线/乱序/重复回执、请求被取消后迟到完成、重启/中断/未知效果、源端特殊审批、解绑/撤权、跨实例等待环、回声触发、预算不刷新，以及 Outlet→Mirror 组合不提升身份或披露范围。

若同步、配对、中继或远端执行需要改变 Cloud API/行为，先在本仓库编写 Cloud 需求交接文档，由 Cloud 项目实施部署；本草稿不直接改动 Cloud，不把当前同 Local 的 Mobile Gateway 描述成跨实例 Bot 协议。

## 延时/重复计划 Access 预检（2026-11-05）

创建和修改计划接入声明预检、现在固定或范围内自动获取两种选择。权限绑定计划，不扩大 Bot 长期 Access，特殊操作仍回到原 Run 单次确认。技术方案、范围、版本与撤销语义见 [Bot 计划 Access 预检 v1](bot-plan-access-preflight-v1.md)。

## Bot 创建 UX 与初始配置（2026-11-05）

新建按钮先打开 Bot 类型菜单：标准 Bot 与 Flash-Bot 可选，ASC-Bot、Outlet-Bot 和 Mirror-Bot 灰显并标注暂未开放。Flash 当前仅提供固定计算器；不开放尚未实现的流程。

选择标准 Bot 后，桌面整个左侧栏替换为创建页；取消恢复原列表和正在查看的对话。Mobile 复用同一创建表单，作为列表的下一层页面，接入已有宿主历史、返回手势和防闪动机制，不使用对话框。表单内容滚动，底部固定“创建 Bot / 取消创建”。

创建前可配置名字、职责、预设头像/颜色、对话模型，以及 App/Mini-App Access。Access 使用当前单一 enabled 开关与受信任目录，不恢复旧 Read/Write 模式；初始勾选沿用现有标准 Bot 默认 App，用户可取消或添加其他项目。Provider/Tool 版本变化后必须重新读取目录并复核选择，特殊操作确认继续由原业务/Interaction 控制。

草稿只存在当前 UI，打开菜单、读取目录和取消均不产生 Bot。`messager/creation.py` 为 owner 提供配置创建入口：桌面 `GET /messager/bot-creation/options`、`POST /messager/bot-creation`；Mobile 通过自己的受限 owner adapter `/messager-mobile/creation/options`、`/messager-mobile/creation` 接入。同一个数据库事务保存身份、空的旧授权记录、当前 Access、头像、可选模型和创建回执；中途错误全部回滚，不留下半配置 Bot。此流程不提交 Task、发消息或执行 Tool。

每个草稿有稳定 request_id，按 actor 隔离并校验配置摘要：相同请求返回原 Bot，改参重用请求键被拒绝。网络或 5xx 导致结果未知时，界面冻结原输入并提供“重试确认”，复用原请求，避免重复创建。未提交的取消直接丢弃草稿；实际提交期间取消按钮暂停，浏览器离开并不回滚已经提交的创建。模型与权限仅在成功创建后生效，实例间不复制设置。

### 固定 Test 验收入口（2026-11-05）

经用户授权，Messager 在 Helper 管理的固定 `test` 实例开放，与 Dev/App-Dev 共同用于验收。Test 仍从签名 App 内加载完整源码快照，不启用 Development 热挂载；数据、Cookie、模型和权限不从开发实例复制。生产/default/main 实例继续显示开发中，未随本次验收开放。


### 2026-11-05 修正：系统任务与 Bot 权限

Bot 的定时计划进入 Todo 的系统任务目录，由系统时钟统一触发；Todo 队列与原 Run/审批不变。预检批准的普通 App 权限保存到 Bot，Task 只冻结执行上限。删除 Bot 软删除自有后台 Task，恢复记录保持停用；清除对话增加独立的后台 Task 删除选项，默认关闭。详见 [当前方案修订 2](bot-plan-access-preflight-v1.md)。

### 托管 Cloud 结构化决策（2026-11-05）

Bot 无工具短回合经通用 Gateway 协商并提交 JSON object 格式；只有 Cloud 成功终态和格式标记验证通过后，才由 Bot owner 校验 kind/text/任务字段，并进入原权限和准入流程。普通文本不猜成 Task，失败不自动换模型或重放；有实际 usage 的格式失败保留结算信息，不代表免费。协议、边界及实机验收见 [Local 结构化输出](managed-cloud-structured-output-local-v1.md)。


### Bot 参数确认操作样式补齐（2026-11-05）

Desktop/Mobile 的 Bot 参数表单不依赖 Chat 页面内的按钮基础样式。任务卡与授权卡内的确认使用深色主按钮，取消及取消自动提交使用带边框的次按钮，支持换行、键盘聚焦和提交禁用。确认/取消不能退化为无边框文本；隐藏的倒计时取消按钮保持隐藏。此修复只改变外观，不更改参数补全、审批次数或执行授权逻辑。

### 清除对话与后台 Task 的完整收尾（2026-11-06）

用户在防呆面板确认的清理选项由系统完成。勾选删除后台 Task 时，原取消/调度退休流程完成后，必须核对 Task 已标记删除且 next_due 为空，再撤销其关联的任务执行授权；失败返回错误，不显示清理成功。Bot 的普通 App Access 仍由其独立 checkbox 控制。恢复任务或对话不会重新授予任务执行授权。

已有删除任务因跨库清理中断留下的授权，由原 Task 恢复检查自动收尾，不要求用户再点一次停用。授权管理不再渲染到对话消息流，保留 Task 的管理入口在 Desktop 右侧任务栏；这是供日后主动停用的管理功能，不是完成清理所需的额外操作。清理后轮换出的新会话消息页为空；历史回执保留在原记录，不伪装成新消息。

定向验证覆盖删除/保留 Task、归档恢复保持停用、关联授权撤销、旧残留自动收尾、空新会话和空消息流渲染。未执行真实用户清理，也未启动业务任务。本轮按用户要求不做完整 App 回归。


## 2026-11-07：分组、Poke 与用量统计

左栏底部加号菜单提供「新建分组」。每个用户有固定的「快捷Bot / Quick Bots」分组，不能删除；Flash 与 ASC 默认归入其中。标准 Bot 默认无分组。分组可折叠，分组、成员、折叠状态和 Bot 顺序保存在 Local 数据库，跨页面刷新和 Local 端口变化保留。桌面直接拖动卡片进入分组，手机长按卡片后拖入分组。删除自建分组需要二次确认，默认聚焦取消；只解除成员分组，不删除 Bot、对话或权限。显式移出快捷分组的 Bot 不会在后续刷新时自动归回。

标准 Bot 输入区在附件、语音旁提供 Poke 图标。一次点击作为可见的「👋 Poke」消息进入同一持久对话决策通道，使用已配置的 Role、当前工作状态和权限；空闲且 Role 有明确工作时可提出正常任务，否则打招呼询问。正在执行时报告实际状态，等待输入或权限时提醒缺少的内容。Poke 不等于批准，也不自动重启失败、取消或结果未知的操作。请求 ID 支持网络失败后的幂等重试；点击不提交或清空输入中的草稿和附件。Flash 仍要求明确工作流输入，不提供 Poke；ASC 仍为打开 App 的快捷入口，不引入聊天执行。

右栏「统计与用量」展示本 Bot 的任务数、执行次数和完成/进行中/失败/取消次数，以及已记录模型调用的输入与输出 Token、Cloud 已结算 Points。统计范围是归属此 Bot 的主对话和 worker Session，不包含被委派的其它 Bot；未上报的工具/生成服务费用也不计入。Points 按 requestId 去重，不能当作货币费用。BYOK 货币费用只有在服务商明确报告金额和币种时才展示，当前未取得此记录时显示「未报告」，不推测单价、汇率或免费。缺少 Token 记录时总量标为下限。统计不会触发模型调用，详情打开时读取，后台最多每 30 秒更新一次。

验证记录见 `acceptance/bot-groups-poke-statistics-20261107/receipt.json`；夹具测试、App-Dev 真机操作和手机实机验收分别记录。


### 2026-11-07 后续：连续 Poke 与统计口径

分组标题采用 20px 独立 SVG 箭头，自建分组始终显示垃圾桶操作，默认快捷分组显示锁标记并说明不可删除。删除仍需确认，不删除 Bot 或对话。

Poke 决策在内部请求中将过去可见回复作为引用的历史数据，不再作为普通 assistant 消息中的非 JSON 输出示例。可见消息仍为「👋 Poke」。这项修正不改变角色、权限、任务决策或失败后的重试规则；Cloud 拒绝格式的失败仍保持失败，不自动重放。App-Dev 旧失败证据：结构化输出校验未通过，stopReason 为 stop，输出 20 tokens，已结算 1 Point，并非触及 1200 token 上限。

Bot 用量默认选择今日；可选过去 7 天、过去 30 天、全部历史。今日从浏览器时区的当天 00:00 起，7/30 天为该时区当前时间往前的相应天数，统计范围中显示起止时间及当前时区。模型用量按步骤开始时间归入窗口，执行次数按开始时间（尚未开始时按入队时间）归入窗口；任务数为窗口内有执行的不同任务数，状态为读取时的实际状态。历史调用没有时间记录时只计入全部历史。切换范围有请求版本保护，旧响应不覆盖新选择。

Task 详情展示整个逻辑任务所有步骤的累计统计，包含对应的规划和 worker 调用；关联 Todo 则只按此 Bot 通道内的精确 Todo ID 汇总其执行。Task 统计不受 Bot 面板的时间选择影响。所有查询校验 actor、Bot、任务归属，不能用任意 Task/Run ID 获取他人的统计。

有实际 usage/结算记录的失败模型调用也计入 Token 和 Points，包括结构化格式校验失败。未报告的工具费用与 BYOK 货币单价仍不猜测，不能把「未报告」理解为免费。

Task 详情分列任务自身（模型执行、规划与 AI 审核）、自身 AaAT、委派 Bot（所有下游子任务的模型与 AaAT）及总计。只沿该 Task 的持久委派记录追溯同一用户的子任务，不包含其它对话或未参与任务的 Bot。读取 Tool 调用日志的结构化用量和结算回执；同一结算请求 ID 只记一次，工具读回和委派回传不会重复记账。Token 与 Points 独立标为「未知」，有部分记录时显示已知部分；明确报告的零仍为零。历史没有保留回执的调用不会补估。Bot 面板仍保留原有统计口径，父 Task 的归因不会改变实际执行 Bot 的账单。

### Group order (2026-11-08)

Drag a Desktop group heading to reorder groups; on Mobile, long-press the heading then drag. Quick Bots participates in ordering while remaining undeletable. Ungrouped stays first. Order is actor-owned and persisted on Local, independent of Bot membership/order and collapse state. Newly created groups append; deleted groups are omitted. Both owner routes reject duplicate or stale/foreign group sets atomically. No extra drag handle is shown.
