# AI2Apps Harness 与 DeepSeek Harness 源码对照审查

日期：2026-10-04。结论：保留 AI2Apps 的服务端执行与权限边界，优先借鉴上下文预算、可追溯压缩和可恢复工具错误；暂不引入 Cordis 或替换整个执行循环。

## 后续实施更新

用户要求继续优化后，已开始落实本报告建议：

- 最近历史查询以当前输入为截止点；自动生成输入按 idempotency key 定位；委派子任务记录父输入锚点。
- 启动恢复清理硬中断遗留的 running 模型步骤，保留 cancelled 尝试及原因，不自动重放 uncertain 工具。
- 引入独立 ContextPolicy 字节保护层，裁剪完整旧轮次，保护当前输入、system 与本 Run 工具链；记录请求 hash、策略版本和体积。它是保守的请求大小限制，尚不是模型 token 窗口计量。
- 对只读工具的 schema 拒绝允许最多三次模型纠正，错误仍按 FAILED 步骤记录并与 tool_call_id 配对；权限、效果型工具及 provider 异常维持原有路径。

这些是独立 Python 实现，未复制 DeepSeek 源码或引入其依赖。具体合同见 `docs/agent-task-runtime.md`，第一轮发布项为 `NXR-HARNESS-RELIABILITY-20261004`。下方问题描述保留为原始审查证据，P0 输入边界已修复；第二轮继续补充 JSON 大结果回读。精确 token 预算、多模态资源回读、事务摘要、程序式工具调用和安全并发仍未实现。

实施验证：`tests/test_ai2apps_harness_reliability.py` 最终 6 项通过，和 storage/services 合跑 43 项通过；原 Agent/stream 套件及初版新增测试合跑 43 项通过，两组共 81 个不同用例。存储套件沙箱运行曾因 MLX/Metal 初始化中止，已在本机环境重跑通过。代码尚未加载到运行中的 App-Dev Local，未做真实模型长任务效果比较。

## 第二轮对照与实施

继续阅读固定 DeepSeek 提交的 `packages/spill/spill-policy/src/{notice,retention}.ts`、`packages/compaction/compaction-tool-result-pruner/src/index.ts` 和 `packages/core/agent-loop/src/tool-calls.ts` 后，得到以下具体结论：

| 对照点 | DeepSeek 的实现 | AI2Apps 本轮处理 |
|---|---|---|
| 大结果 | 首尾保留、遗漏统计、可定位原文；prune 替换关联原始事件 | 用 RunStep 作为现有原文存储，新增当前 Run 内分页读取；模型看到首尾预览、sha256、step_id 和读取别名 |
| Unicode | 保留时避免切断代理对，区分字节与文本长度 | Python 按 Unicode code point 分页，分别记录 UTF-8 字节数和字符数，测试中文及 emoji |
| 可重放 | 替换事件保留来源和估计成本 | 原 RunStep.output 不变，发送给模型的预览保存在后续模型 RunStep.input 中，既有请求审计可定位 |
| 多模态 | 图片是不可拆分的独立内容块 | 本轮只实现已有 JSON Tool 输出的文本回读，不宣称能按语义回读图片；多模态需接 Resource Handle |
| 并行 | 有界池、独占屏障、取消后等待已启动调用结算，再按模型顺序提交 | 暂保持逐工具检查点。只加 asyncio.gather 会破坏恢复语义，因此不作快捷改造 |

额外修补了本地“连续相同工具”检测的盲区：A/B 等二至四步周期若输入和结果都重复三次，在下一轮前终止。此项是本地可靠性增强，不声称复制自 DeepSeek。

固定合成 JSON 示例（50000 个 x、`needle-你好😀`、50000 个 y）原文 100030 字节，引用预览 3605 字节，单个结果进入模型上下文的体积下降 96.4%。这是序列化体积测量，不是实际模型 TPS、token 成本或任务成功率基准。端到端 fake-provider 测试在 16000 字节请求预算内成功回读中部文字，原文仍完整保存在 SQLite。

后续顺序调整：先接模型路由的窗口/计量合同，再做有版本的摘要提交和恢复；大结果回读已提供基础，但不能把全文引用机制称为摘要。工具并发需要显式并发安全声明及逐调用取消/结算测试后再开启。

第二轮验证：`test_ai2apps_agent_result_references.py` 最终 7 passed；连同第一轮可靠性、Agent、Services、流式响应套件，共 65 个不同用例通过。首次合跑仅新增循环测试的等待时限不足（64 passed），增大测试等待预算后 7 项重跑通过；实现未放宽循环阈值。Ruff/scoped diff check 通过，未重启开发 App 或做真实模型性能验收。

## 第三轮：内置工具与能力（2026-10-04）

范围是 AI2Apps **General Agent 可发现/调用的工具**，不把 Coder 中外部 CLI 自带工具、App 内功能或本次审查所用 Codex 工具算作自己的 Harness。DeepSeek 参考固定提交的 `docs/tool-catalog.md` 与对应实现；目录是可组合插件的能力全集，不表示全部默认开启。Session Query 是 opt-in，Agent Teams 默认禁用且标记 experimental。

| 能力 | AI2Apps 证据与现状 | DeepSeek 对照 | 判断 |
|---|---|---|---|
| 文件读写/补丁 | `workspace/service.py`：list/stat/read/search/write/apply_patch；Session 工作区原子替换 | read/write/edit、str_replace_editor | 已有主体能力，不应重复实现另一套文件工具 |
| 文件发现/内容搜索 | `workspace/repository.py:search`：逐文件 UTF-8 读取、大小写不敏感子串匹配，结果有行号；工具 schema 无 glob/regex/include | glob、基于打包 ripgrep 的 grep，明确截断与完整结果位置 | P1 补文件 glob、模式/文件类型筛选、上下文行和有界扫描；全量结果可复用回读机制。不要照搬默认扫描隐藏/ignored 文件策略 |
| 进程/终端 | `processes/service.py` 有 start/write_stdin/status/logs/wait/cancel；`terminal/service.py` 只注册 Service/Instance，没有 ensure_tool | bash、persistent bash、PTY terminal_*、jobs | 不能说我们没有 shell；缺的是受控 PTY 的模型入口和统一后台任务完成通知。保留现有沙箱/工作区边界 |
| 结构化提问 | Runtime 已支持 InteractionAction、菜单/文本/文件/审批与等待恢复，GeneralAgentExecutor 不提供模型 ask-user tool | ask_user_question | P0 接到已有 Interaction，不新建聊天式轮询；用户选择与权限审批保持不同含义 |
| Run 内计划 | 有 Todo 产品、运行状态行、预算与 AgentRun；未发现 General Agent 原生的计划读写工具 | todo_write、goal | P0 增加 Run-owned plan/update 工具与持久 UI 投影，复用状态层。不要把内部计划更新自动变成用户 Todo 项目或其完成状态 |
| Skills | 当前内置 Agent 路径未发现 skill 加载器；Codex Todo 集成里的 SKILL.md 服务于外部 Codex | skill + 持久技能目录、按需读全文 | P1 引入受信任 Package 的技能索引、按需加载、版本/hash；技能不能扩大 Tool 权限。不要直接扫描整个用户主目录 |
| 运行/会话历史 | SQLite Run/Step/Event 和 API 已有，agent.read_tool_result 只读当前 Run 工具结果 | session_search、event_search/read/trace 等五工具 | P1 给模型可授权的历史检索入口，先当前 Session/项目；必须按 actor/App/Session 授权，不能照搬仅以 cwd 相同判断跨会话权限 |
| 子 Agent | agent.delegate 已有深度/预算/树/结果回收，调用方等待完成 | 可继续后台 child、list/send/interrupt、可选模型；实验 Teams | P2 补有界后台委派和控制入口；不急于复制完整团队任务板 |
| Web/浏览器 | web.search/fetch、browser service、受保护 BiDi Gateway、共享 SDK | web_search/fetch、实验 Stagehand 插件 | 基础能力已有。借鉴操作后验证/截图/结果质量；继续按权威 BiDi 架构实现共享 SDK，不能引入第二套语义浏览器协议 |
| 文档/知识/交付 | attachment.*、document.read/info/preview/search/create_pdf、knowledge.*、artifact.*、image.generate | read_image、present、workspace-dependencies | 我们已有面向业务的资产服务。可借鉴显式“交付本轮重要成果”的入口，复用 Artifact，不能新建输出历史或存储 |
| MCP | MCPServiceAdapter 已将工具投影到 Registry；此适配器未提供资源列举/模板/读取接口 | list_mcp_resources、list_mcp_resource_templates、read_mcp_resource | P2 补资源面能力，并沿用连接权限和资源大小限制；不重复建设 MCP 工具执行 |
| 代码语义 | 文件搜索和 Coder 可用；未发现 General Agent 原生 LSP Tool | lsp：definition/reference/implementation/hover | P2，适合加强内置 coding Agent 后做；语言服务进程、工作区范围和索引成本需要管理 |
| 调度 | AgentScheduleRunner 与 Todo Scheduler 已执行持久调度；未发现统一 General Agent 调度工具 | schedule_create/list/update/delete | 可补模型入口，复用现有调度器与用户授权，不另建第三套 scheduler |

建议先实施 **结构化提问 + Run 内计划 + 搜索增强**：它们能改善所有长任务，且大部分基础设施已经存在。第二批是 Skills 按需加载与历史检索；PTY/统一 jobs、可继续子 Agent、LSP 随内置编码能力目标推进。

跨领域共同借鉴点是工具的“模型使用合同”：输入单位清楚（字节/字符/行/页）、输出是否完整可见、原文可回读、等待超时不等于任务失败、缺少 provider 返回明确不可用、后台完成有持久状态和有界唤醒。这比只增加工具数量更有价值。

该轮只做源码对照与建议，没有注册新工具、改变浏览器协议或修改生产行为；不新增 Desktop 实现项。

## 审查基线与范围

- AI2Apps HEAD：`fa377dcb62875d5c82fc8177afd4277cd2357db9`。实际审查对象为当前工作区，包括已有未提交修改，尤其 `ai2apps/agents/runtime.py`；不能将本报告等同于该提交或生产版的审查。
- DeepSeek 官方仓库：<https://github.com/deepseek-ai/deepseek-harness>。
- 下载并阅读的固定提交：`5badb15009ae1756c3afe0ae0cef1faafc290ccc`；临时 checkout 位于 `/tmp/ai2apps-dsh-review-20261004`，没有运行其安装脚本或应用。
- 方法：静态阅读双方实现，检查本地既有测试并运行 Agent 定向回归。没有进行双方模型效果、性能或生产故障注入的比较。
- 本次仅新增审查文档，不修改运行时、Cloud 或 Desktop 制品，因此不新增 Desktop 待发布实现项。

## 能力对照

| 领域 | AI2Apps 当前实现 | DeepSeek 对照与判断 |
|---|---|---|
| 执行边界 | executor 返回 ModelCallAction / ToolCallAction 等动作，由 AgentRuntime 执行并落库 | agent loop 通过类型化事件组织阶段。我们已有可替换 executor，无须从零插件化 |
| 持久化 | SQLite AgentRun、RunStep、interaction、events；模型调用前保存 request，完成后保存 output | Session 日志投影成模型历史，记录请求路由与工具定义，冻结请求。值得补充来源、转换版本和最终调用边界的关联 |
| 恢复 | 已完成 action_key 去重；优雅停止可放弃安全步骤重试；不确定副作用要求显式处理 | 对中断请求和缺失工具结果有明确日志结算。应借鉴不变量及故障测试，不能据此宣称任何一方拥有 exactly-once 外部副作用 |
| 上下文 | 默认保留 200 条 Session 消息；本 Run 完成步骤追加到 transcript；累计 token 预算限制消费 | 按实际路由窗口测量压力，保留近期上下文、压缩旧区间，避免切断工具调用/结果配对。这是最明显的可借鉴点 |
| 工具 | ServiceRegistry / ToolGateway 已提供注册、schema、身份、授权、超时、调用记录和重试 | 有 pre/guard/around/post/result 阶段；普通工具失败可成为结果。借鉴错误分类和少量扩展点，不替换 Gateway |
| 子 Agent | agent.delegate 创建同 Session 子 Run，有 request_key、深度与预算约束，并等待结果 | SubagentProvider 区分本地/外部执行，支持可继续子会话。未来外部 Harness 接入可参考，暂不扩展完整团队协作 |
| 并发 | 通用 Agent 每次返回一个工具动作，依次检查点 | 工具调度有受限并发池、独占屏障、按模型顺序结算。值得后续评估，不能仅据 effects 为空就推定并发安全 |

本地依据：`ai2apps/agents/{models,general,runtime,repository,delegation}.py`、`ai2apps/services/registry.py`、`ai2apps/agents/model_stream.py`、`docs/agent-task-runtime.md`。

DeepSeek 固定源码入口：

- [请求构造与结算](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/agent-loop/src/agent.ts)
- [工具调度](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/agent-loop/src/tool-calls.ts)
- [工具注册和权限 guard](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/tools/src/index.ts)
- [上下文压缩触发](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/compaction/compaction-basic/src/index.ts)
- [压缩区间与事务](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/compaction/compaction-basic/src/region.ts)
- [可继续子 Agent 合同](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/subagent/subagent/src/types.ts)
- [被截断引用的完整快照](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/context/session-reference/src/spill.ts)

## 优先处理的具体问题

### P0：长 Session 读取边界

`GeneralAgentExecutor._messages_for_run()` 调用 `list_for_session(limit=1000)`；后者在 `ai2apps/storage/repositories/messages.py` 使用 `ORDER BY sequence LIMIT ?`，默认 after_sequence=0。因此拿到的是最早 1000 条，之后的 `eligible[-message_limit:]` 并不是整个 Session 的最近 200 条。

静态调用链表明：显式 message_id 位于第 1001 条以后时，单独 get 能取得 cutoff，但 records 不含该输入；直接 prompt 生成的 agent_input 若在范围外，也可能被误判为 missing_agent_input。此项尚未做 1001 条真实数据库复现，应作为首个回归用例。

建议新增“截至指定 sequence 的最近 N 条”仓储查询，按倒序限量后恢复正序；强制当前输入可见，排除该输入之后的消息。不要通过无限增大 limit 解决。验收覆盖 999/1000/1001 条、显式输入、自动生成输入、委派 cutoff 与 Session 所有权。

### P1：把窗口预算与累计消费预算分开

当前 `_total_model_tokens()` 管的是 Run 的累计消费；消息条数无法约束单条超大工具输出，也无法约束同一 Run 不断增长的 transcript。

建议增加宿主内部 ContextPolicy：按实际模型窗口预留输出空间，计入 system、工具 schema、消息与工具结果；模型窗口未知时显式采用可配置保守策略。先做可恢复的大结果引用和确定性裁剪，再引入摘要。不要照搬 DeepSeek 默认阈值到本地模型。

压缩记录应保存源消息/步骤范围、输入摘要 hash、策略版本、摘要调用和输出、原文资源句柄及提交状态。最近任务目标、用户约束、未完成工具配对不得被随意丢弃；摘要是派生数据，不能提升为授权依据。压缩失败、取消或期间上下文变化时不得提交过期摘要；原文须能回查。

验收：超大单工具结果、长工具循环、多模态输入、切换模型窗口、摘要失败、压缩中重启、工具配对完整性及跨用户引用隔离。

### P1：允许模型修正普通工具错误

当前 runtime 捕获 ToolGatewayError 后直接结算 FAILED 并终止 Run；general 对非法参数 JSON 也直接 FailAction。Gateway 自身已有有限重试，因此问题不是完全没有重试，而是失败后缺少让模型修正参数或选择替代工具的路径。

建议显式分类：参数格式错误、目标不存在等可恢复失败，持久化为与原 tool_call_id 配对的错误结果，再允许有限纠正；权限拒绝、身份失效、副作用未知、取消和预算耗尽保持宿主控制。不能把所有异常都转成普通文字继续执行，也不能自动重放可能已经产生副作用的动作。

验收：错误配对、纠正次数上限、重复失败终止、取消优先、授权不扩大、断点后不重复执行。

### P1：区分优雅停止与进程硬中断

`runtime.py` 的 CancelledError 路径会区分工具 effects，并对模型步骤调用 abandon_step_for_retry；`repository.recover_interrupted()` 的启动扫描则将所有 running 工具视为 uncertain，且该扫描没有对遗留 running 模型步骤做同样的 abandon 操作。现有测试包含优雅 stop/restart，不能等同于 SIGKILL 恢复证明。

建议先用持久库构造硬中断快照，核对模型步 action_key、遗留状态与重试轮次，再决定修复。保守暂停工具不是数据破坏，但文档中“只读工具可重试”的承诺应明确适用路径。把未结算步骤、请求取消、日志配对作为故障矩阵，优先于扩充插件数量。

## 可复用设计，而非整体迁移

1. **请求证据链**：保留现有 RunStep.input；增加实际路由、窗口、上下文策略版本、来源范围和请求 hash。核对 provider 是否转换消息，不能将调用前快照直接称为最终 wire 请求。公开诊断仅返回脱敏元数据，不增加凭据日志。
2. **少量受控扩展点**：先定义 context prepare、tool result transform、run observer；声明执行顺序和失败策略。审计观察者不能改变权限，转换结果必须记录。宿主最终权限校验只能收紧，不能被后续插件放宽；DeepSeek 的单调 guard 值得借鉴。
3. **外部执行器协议**：未来可为 dsh/Codex/Claude 统一 start、events、cancel、result、resume 能力声明，但要区分原生恢复和重新运行。现有 Todo 的 CLI 退出不等于业务成功，也不等于原生子会话恢复。
4. **受限并发**：只有明确标记可并发且互不依赖的工具可并行；效果型动作作为屏障，结果按调用顺序落库，取消要等待已启动动作结算。应先完成错误和恢复语义。

暂不采用：全面 Cordis 化、允许任意插件替换身份/审批、重写 SQLite 为 Session JSONL、完整 Agent Teams、程序式工具执行沙箱。它们增加的迁移成本与当前问题不匹配。

## 建议实施顺序与验收

| 批次 | 范围 | 验收门槛 |
|---|---|---|
| A | 最近消息查询修复 + 硬中断故障矩阵 | 当前输入不遗漏；安全恢复和 uncertain 语义有明确测试 |
| B | ContextPolicy、token/byte 预算、可回查大结果引用 | 请求有边界；工具配对不破坏；原文可追溯 |
| C | 事务化摘要压缩 + 有限工具纠错 | 长任务完成率提高；取消/重启/权限回归通过 |
| D | 固定请求证据链、观察接口、外部执行器合同 | 可诊断、可替换且不绕过宿主权限 |

效果比较应固定模型、任务集、工具实现和初始资源，记录完成率、模型输入 token、耗时、工具失败与恢复率、摘要开销。模型输出有随机性，不以单次演示声称收益；本次未测这些指标。

本地回归命令：`.venv/bin/python -m pytest tests/test_ai2apps_agents.py -q`。结果：**34 passed，60.26 秒，退出码 0**。退出时有 nanobind 的 No Metal device available 提示；本套测试不构成 GPU 推理验证。上游未安装依赖、未跑测试，因此以上是实现对照，不是上游运行认证。

## 首批三项落地（2026-10-04）

上表记录的是实施前差距。本轮已补齐：

1. `agent.ask_user`：模型提问转持久 Interaction，建议选项和自由回答并存，恢复后保持 tool-call 配对，答案不授予权限。
2. `agent.read_plan` / `agent.update_plan`：Run 内计划带版本号与稳定条目 ID，持久事件和父/子 Run 卡片展示，独立于 Todo。
3. `workspace.glob` / 增强 `workspace.search`：文件模式、逐行正则、大小写、上下文行、隐藏文件选项；工作区边界、无符号链接遍历、大小/条目/时间预算及不完整原因。

具体合同见 `docs/agent-task-runtime.md`。Skills 加载、历史检索、PTY/jobs、LSP 仍为后续候选，不属于本轮已实现能力。

## 第四轮：长任务上下文检查点

新增 `context-checkpoint/v1`：在字节压力下对较早的文本历史和完整工具轮次分批生成结构化摘要，保留当前输入、system 和最近两组原文。摘要走独立持久模型步骤，来源/锚点哈希校验后才投影到后续请求；支持中断后重做摘要，已完成工具不重放。新增当前 Run/Session 隔离的 `agent.read_context_checkpoint`，通过前一检查点 ID 回读来源链。

这缩小了“当前 Run 工具链只能持续增长”的差距，但仍不是与 DeepSeek 上下文管理等价：实际模型 token 窗口、语义摘要质量、多模态及真实长任务效果尚未闭环。历史中已被消息条数/字节策略排除的内容也不会自动恢复。实现合同及上限见 `docs/agent-task-runtime.md`。

## 第五轮：摘要信息保护 v2（2026-10-05）

重新核对固定 DeepSeek 提交：`packages/compaction/compaction-basic/src/summarizer.ts`
的模板要求保留约束、用户偏好、错误、待办及精确路径等信息；`region.ts` 实现来源区间稳定性检查、较小摘要校验和带来源事件的提交。
这些是源码可确认的借鉴点，不能据此声称它具备完整的“约束注册表 + 语义无遗漏证明”。

本地设计的 v2 在已加载上下文范围内，把被压缩的用户原文作为有来源坐标/哈希的独立证据保留，不让模型重写；覆盖检查验证这些原文记录的精确一致性。当前 Run 计划、工具状态、问答状态从持久记录重新投影，不从摘要推断。启用检查点时禁止字节预算回退丢弃历史，装不下明确报错。此版本仍未实现全 Session 约束注册表、Artifact 独立验证、最终验收检查或通用语义遗漏检测；不能把文本覆盖率称为重要信息完整率。
