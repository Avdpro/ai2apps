# AI2Apps 编码子 Agent 技术开发方案

- 日期：2026-10-05
- 状态：已实现并完成独立、宿主和真实模型分阶段验收；固定 App-Dev 已启用。
- 目标：增强原生 Python Harness 对 AI2Apps App/Mini-App 的分析、开发和调试能力。
- 首期范围：专职子 Agent、异步委派、源码快照、证据结果、预算与任务树展示。
- 扩展范围：worker 独立修改与冲突检测合入，已纳入本次实现。

## 1. 目标与边界

采用“主 Agent 负责修改，子 Agent 分析、测试、审查”的协作方式。主 Agent 保持
对需求、草稿和最终结果的责任；子 Agent 承担明确且可验证的子任务。
用户继续通过 Coder 审阅并应用修改，子 Agent 不获得原项目写回权限。

面向小型 AI2Apps source Project，不以大型仓库全量并行修改为首期目标。
复用既有 General Agent、记忆、工具恢复、进程沙箱、源码校验和 Coder。
不增加外部 CLI 依赖，不修改 Cloud，不自动安装、发布 Package 或 Desktop。
静态预览不等于宿主 Bridge 验收；子 Agent 不得把未执行的视觉/移动端验收标为通过。
Voice Studio 输出仍遵循宿主 Quick Read Preview & Output 契约。

## 2. 已有基础与缺口

以下是本次检查时的代码事实，实施前应再次确认接口：

| 已有能力 | 当前代码位置 | 本方案处理方式 |
| --- | --- | --- |
| 持久化父子 Run、root_run_id、depth、delegation | `ai2apps/agents/models.py`、`repository.py` | 复用，不创建第二套任务系统 |
| 同 Session 委派、幂等 request_key、子任务截止时间不超过父任务 | `ai2apps/agents/delegation.py`、`repository.py` | 保留语义，新增非阻塞接口 |
| 通用深度上限 2、每父 Run 最多 4 个子 Run | `AgentRepository` | 编码场景收紧为一层，首期保持最多 4 个子 Run |
| delegate 创建子 Run 后等待终态 | `ai2apps/agents/delegation.py` | 保留旧接口兼容，不把它直接作为新编码协作入口 |
| 级联取消、暂停和恢复后代 Run | `ai2apps/agents/runtime.py` | 扩展到等待关系、快照、子进程清理 |
| definition 工具白名单、单 Run 步数/token 上限 | `general.py` | 角色白名单之外增加宿主权限校验和根任务总预算 |
| 分组并发与 Runtime 全局并发 | `repository.claim_next`、`runtime._dispatch_loop` | 增加可释放执行名额的持久化等待 |
| 独立源码草稿、观察 SHA、差异审阅与写回 | `ai2apps/app_development/core.py` | 主草稿机制保持不变，增加子任务快照 |
| appdev 工具只接受主编码 Agent 的 definition | `app_development/service.py::tool_context` | 增加宿主创建的角色/快照绑定，不能直接放宽为任意 Agent |

目前编码 definition 使用 `app-development` 分组、并发上限 1，且未开放委派工具。
现有 `waiting_subruns` 是进度 phase，不是 `AgentRunStatus`；仅修改展示或提高分组
并发，不能解决父任务占用全局名额等待子任务的问题。
当前 token 计量主要按单 Run 的模型 step 汇总，不等于父子任务共享总预算。

## 3. 首期协作模型

| 角色 | 工作内容 | 工具边界 | 交付 |
| --- | --- | --- | --- |
| 主开发 Agent | 分解需求、修改草稿、综合结果、最终验证 | 现有 appdev 工具和受限子任务工具 | 用户可审阅的最终草稿 |
| 分析 Agent | 找相关文件、调用关系、清单及平台契约 | 当前源码快照只读、受限上下文读取 | 文件定位、实现建议、待确认项 |
| 测试 Agent | 执行指定测试、复现失败、分析日志 | 独立测试工作区、受限命令及校验 | 命令、退出码、日志引用、失败原因 |
| 审查 Agent | 审查基线到快照的差异与契约 | 快照、差异和只读校验 | 有位置与证据的问题列表 |
| Worker | 在独立快照实现明确修改 | 读、独立草稿写、隔离命令 | 补丁；由主 Agent 冲突检测合入 |

默认同一根任务最多两个子 Run 同时执行；模型服务另有串行限制时按服务能力排队。
子任务不得再次委派。角色名称映射到宿主注册的固定 definition，模型不能指定任意
Agent key、工具集合、能力、Session、目录或其他账户。
测试 Agent 的命令可能生成缓存、报告或改变测试工作区，但不能修改主草稿；
测试后的工作区变化不能自动作为开发补丁合入。

示例：主 Agent 启动分析任务，同时准备界面；修改后并行启动测试与审查。
主 Agent 根据结构化结果修复，针对变动部分重新测试，再提交用户审阅。
简单任务可以不委派，避免无收益的模型调用与延迟。

## 4. 模块划分与接口稳定性

新增独立目录 `ai2apps/app_development/subagents/`，以下为拟定模块：

- `contracts.py`：请求、结果、版本、预算和错误码；优先标准库 dataclass/枚举。
- `snapshots.py`：有界源码快照、内容清单、差异证据和保留策略。
- `policy.py`：角色权限、层级/数量/并发规则、结果过期判断。
- `coordinator.py`：通过宿主接口创建/查询/等待/取消子 Run，组织状态与结果。
- `adapter.py`：接入 AgentRepository、Runtime、Gateway、ProcessManager 和 Coder。

纯逻辑依赖抽象宿主接口，不导入 FastAPI、前端或 PlatformRuntime：
`RunStore`、`SnapshotStore`、`BudgetStore`、`ProcessExecutor`、`EventSink`。
实际数据库操作、事务和 Runtime 调度放在 adapter 或既有 Agent 层。

通用 Runtime 仅增加持久化等待及预算挂钩等必要能力；AI2Apps 角色、源码路径和
清单规则留在 app_development。接口采用 `schema_version: 1`，持久化格式变化必须
有显式迁移；不能把 Python 内部对象或提示词格式当成跨模块协议。

## 5. 工具协议

编码主 Agent 使用专用 `appdev.subagent_*`，保留通用 `agent.delegate` 的原有行为。
六个接口如下；输入通过 JSON Schema 校验，输出由宿主构造并限制内容大小。

| 工具 | 主要输入 | 主要输出 |
| --- | --- | --- |
| `appdev.subagent_start` | role、task、request_key、context、budget | child_run_id、snapshot_id、status |
| `appdev.subagent_status` | child_run_ids | 状态、源码版本、有界结果与证据 |
| `appdev.subagent_wait` | child_run_ids、mode=any/all、timeout_seconds | 已结束结果或等待超时状态 |
| `appdev.subagent_cancel` | child_run_id、reason | 已确认的取消状态 |
| `appdev.subagent_followup` | child_run_id、message、request_key | 后续 Run ID、重新生成的快照 ID |
| `appdev.subagent_merge` | child_run_id、主草稿 revision | 已合入路径、新主草稿 revision |

start 立即返回，不等待模型完成。全部 ID 必须归属于当前根任务和账户。
request_key 幂等：同 key 同 payload 返回原子任务，不同 payload 返回冲突。
followup 首期仅对已结束子任务创建新的子 Run，并关联 `followup_of_run_id`；
运行中的补充要求返回明确 busy，不偷偷重启，也不实现隐式跨 Agent 聊天。
后续 Run 计入子任务数量和预算。已取消根任务不能创建后续任务。

首期最大 4 个子 Run 是累计数量，不只是并发数；达到上限后主 Agent 自行处理
或向用户报告限制，不能通过换 request_key、followup 或新 definition 绕过。

普通失败、超时、取消、过期均返回类型化结果供主 Agent 判断；鉴权与任务绑定
错误保留宿主拒绝语义，不能转成建议模型绕过的可恢复错误。

## 6. 源码快照与版本绑定

源码快照从主草稿生成，沿用现有文件数量、总字节、单文件、秘密文件及符号链接
边界。快照是物化文件副本，不使用会共享写入的硬链接。生成过程中检测草稿变化，
不一致则拒绝本次快照并重新请求，不能给混合版本分配有效 snapshot_id。

snapshot_id 是有界规范化文件清单的内容摘要，包括相对路径、文件 SHA 和字节数。
当前版本不把执行模式纳入内容 ID；它适用于源码内容验收，不证明可执行位一致。它与现有“待应用差异 revision”用途不同，不互相替代。
绑定记录至少包含 task_id、root_run_id、child_run_id、role、snapshot_id、
baseline_id、workspace_id 和创建时间，均由宿主写入受保护存储。

子 Run 继续沿用父 Session，符合既有委派限制；独立文件目录由宿主分配。
ProcessManager 当前按 Session 选择工作区，因此需要一个受校验的子工作区映射：
由 Run 绑定解析根目录，不能让模型传入绝对路径或用普通参数覆盖沙箱根。
子工作区进程不得读取原项目、其他 Session、主草稿、凭据或受保护任务状态。

返回结果同时标明 `inspected_snapshot_id` 和 `current_snapshot_id`。
主草稿已变时显示 stale；首期保守处理，只要内容摘要不同，就不能把原测试/审查
结果当成当前版本通过。界面可保留历史结论，但必须要求重新检查当前版本。
快照/日志保留采用有界策略；活动或被证据引用的快照不能在任务进行时删除。

## 7. 上下文与结果契约

首期不要复制父任务全部历史。主 Agent 提供有界任务说明、必要约束、文件引用和
问题；宿主附加角色指令、源码版本和平台契约。子任务对话与工具轨迹按 Run 分流，
父记忆仅接收有界结果及引用，避免多个子 Run 的工具调用交错污染主上下文。
须检查现有 SessionMemory 投影与摘要继承，不能仅靠新的 system prompt 宣称隔离。
源码、项目文档及子结果均是任务数据，不能扩展宿主权限。

建议统一结果：

```json
{
  "schema_version": 1,
  "child_run_id": "...",
  "role": "tester",
  "status": "completed",
  "inspected_snapshot_id": "...",
  "summary": "指定测试通过，宿主集成未执行",
  "findings": [],
  "checks": [
    {"command": ["python3", "-m", "unittest"], "cwd": ".",
     "process_id": "...", "exit_code": 0, "log_ref": "..."}
  ],
  "artifacts": [],
  "unverified": ["Host Bridge integration"],
  "usage": {"model_tokens": 0, "elapsed_ms": 0}
}
```

示例中的数值是格式示意，不是验收结果。status/usage/process/log 由宿主核验或补充，
不能信任模型自报。findings 包含 severity、相对文件路径、行号、文件 SHA、问题说明
及 evidence_ref。无法验证的位置明确标为 unverified_location，不伪造精确位置。
大日志和报告通过账户/根任务绑定的引用读取；摘要有长度限制并标记截断。
审查通过不能覆盖测试失败，退出码 0 也不代表所有契约已验证。

## 8. 调度、等待与恢复

新增持久化等待关系，记录父 Run、所等子 Run、any/all、截止时间和恢复边界。
采用专用 `DeferredToolAction` 和 `agent_deferred_waits` 持久化等待表。父 Run 保持
queued，claim_next 排除有等待记录的 Run，Coder 展示 waiting_subruns。这样保留既有
状态枚举与暂停/恢复接口；该展示由真实等待关系派生，不是仅修改 progress phase。

wait 操作在事务内同时检查子任务状态并注册等待，避免“子任务刚结束但父任务未被
唤醒”的竞态。进入等待后释放执行 coroutine/全局执行名额，保留 Run 和上下文。
子任务终态事件或等待超时使父 Run 可重新调度，不创建新的主 Run。
恢复必须给原 tool_call_id 恰好一个结果；等待期间不能凭空插入结果或留下未配对
工具调用。不要在持有 Gateway 调用/能力租约时做无限 asyncio 等待。

父主任务和子角色采用不同并发组，同时增加根任务两个活动子 Run 的限额。
即使 Runtime 全局并发为 1，父任务也应能等待、让子任务运行并恢复。
模型调用容量独立于 Run 并发；不能因为模型串行就误报调度死锁。

重启后扫描持久化等待与已结束子 Run，幂等恢复唤醒；不重复启动模型调用或
重跑不确定进程。沿用现有 uncertain/进程恢复语义，必要时报告证据缺失。
父取消级联取消后代、等待关系和对应进程组。根 Run 意外失败也应清理活动子任务。
暂停/恢复需要与现有 API 对齐，不能留下孤儿子进程。

## 9. 总预算与权限

根任务预算覆盖主 Run、子 Run 和 followup。首期沿用主任务 100,000 token 的
默认总额与 900 秒根截止时间，子任务预算只能从剩余额度中分配，不能额外叠加。
保留主任务完成综合和报告所需的额度；各角色具体默认额度在实施验收时校准。

模型调用前事务化预留输入估算与输出额度，结束后按真实 usage 结算并释放未使用额度。
输入按 JSON UTF-8 字节/4 加固定余量估算，不是 tokenizer 给出的严格上界；实际 usage
可能超过预留，下一次调用会被拒绝，不能宣称 100,000 是绝不越界的计费硬上限。
取消、错误、usage 缺失和重启中的预留必须有保守且幂等的结算规则；无 usage 时
保留保守记账并标记估算，不按零消耗处理。预算不足则拒绝新调用，保留已有结果。
若 Provider 无法约束单次输出，上限只能近似控制，必须在 UI/报告说明限制。

角色授权取父任务权限、固定角色允许列表、项目访问权限三者交集。白名单只是
模型工具可见性，工具 handler、Gateway 和进程层也要执行权限校验。
分析/审查无源码写能力、无任意进程能力；测试只可运行隔离命令；所有子任务
无 Apply、发布、安装、Cloud 修改、外部通信或递归委派权限。

## 10. Coder 展示与兼容

原生任务面板增加子任务列表：角色、要求、状态、源码版本、耗时、预算、结果摘要。
可展开证据、日志与未验证项；提供单子任务取消和已完成任务 followup。
任务关闭后依旧持久化，重新打开可恢复列表。用户问题统一汇到主任务面板，明确
标注来源子 Run，首期子 Agent 不自行发起无归属的用户交互。

主草稿 Apply 仍要求没有活动主/子 Run、源码验证通过、差异 revision 匹配和原项目
基线未变。历史 stale 结果不得显示为当前通过。沿用现有静态预览限制和写回备份。
旧任务没有子任务绑定时正常显示；通用 delegate 和外部 CLI Thread 回归测试必须通过。

## 11. 开发顺序

1. 独立模块与角色：先建立 contracts/policy、快照、只读分析/审查及隔离测试角色；
   完成模拟 RunStore/ProcessExecutor 的独立测试，不开放真实并行入口。
2. Runtime 等待与预算：完成状态迁移、等待唤醒、计量与真实子 Run 接入；验收
   全局并发为 1、两子任务并发、取消和重启后，才开放主 Agent 委派工具。
3. Coder 与端到端：加入任务树、证据、stale 展示，验证 App/Mini-App 修复闭环。
4. 独立补丁：worker 在独立草稿写入，返回基线/补丁；主 Agent 通过全量冲突预检
   和 revision 校验合入主草稿，再在当前版本上测试。已实现；不允许并发写主草稿。

每个阶段都要有可单独关闭的入口和兼容性检查。功能关闭后拒绝新建子任务，已有
任务仍可查询/取消；回退前排空或终止活动树。不要直接删除持久化任务或迁移数据。
启用或回退只能改变本地开发环境，不改变生产配置。

## 12. 测试与验收门槛

| 验收领域 | 必测案例 | 通过标准 |
| --- | --- | --- |
| 独立逻辑 | 角色、预算、快照、幂等、stale | 不依赖启动整个平台；有界、无路径越界 |
| 调度 | global_concurrency=1、any/all、终态与注册等待竞态 | 无死锁、无丢失唤醒、结果恰好一次 |
| 并发与预算 | 两子任务、第三排队、预留竞争、followup | 不超角色/根限额，不重复扣费 |
| 权限 | 伪造 role/Session/根 ID/目录、跨账户访问 | 宿主拒绝，无法获取原项目或其他草稿 |
| 实际沙箱 | Runtime Python、测试产物、读取外部项目、网络 | 可运行指定测试，外部读取和网络被拒绝 |
| 结果证据 | 虚报 exit_code、伪造路径/行号、日志截断 | 宿主校验，未知内容明确标记 |
| 版本变化 | 主 Agent 在子任务运行时修改草稿 | 原结果标 stale，不能当作新版本通过 |
| 取消与恢复 | 父取消/失败、等待重启、进程不确定 | 无孤儿进程、无重复危险执行 |
| 记忆隔离 | 多子 Run 工具轮次与摘要、父恢复 | 各 Run 工具配对正确，主历史不受交错污染 |
| 端到端 | App/Mini-App 分析→修改→测试失败→修复→审查 | 原项目审阅前不变，结果与最终源码一致 |
| 兼容 | 既有 delegate、Agent、记忆、工具恢复、Coder CLI | 既有语义和验收不退化 |

模型替身用于验证机制，真实模型用于单独验证实用性。真实验收至少包含一个新建
Mini-App、一个已有 App 修复和一次有意引入的测试失败；记录模型 ID、任务、实际
调用、成本/耗时、源码 diff 和未验证项。不得把替身测试写成真实模型开发成功。

实施在独立临时 Runtime 数据目录、测试项目与快照中完成，不合并实例用户数据。
验证后再接入固定 App-Dev。纯 `ai2apps/` Python 更改按 Helper 重启 Local；若涉及
Runtime、依赖或其他嵌入组件，使用对应固定 builder。Test 需要新构建源码快照。
实施开始即更新 Desktop release ledger，并为每阶段保留验收记录与源文件摘要。

## 13. 本轮交付与后续启动点

本轮按用户批准开始实现，完成独立模块、Runtime 接入、Coder 展示与 worker 合入。
最终验收记录与已知限制见后续实施记录；不会把模型替身测试算作真实模型验收。

相关文档：[原生 App 开发](ai2apps-native-app-development.md)、
[Coder](ai2apps-coder.md)、[原生编码验收](native-app-development-acceptance-2026-10-05.json)。
DeepSeek 的新一轮子 Agent 实现对照应在实施阶段记录具体源文件与固定 commit，
本方案没有宣称以上设计与 DeepSeek 的全部实现一致。


## 14. 实施接口与设计调整（2026-10-05）

- 独立模块已经落地到 `ai2apps/app_development/subagents/`。contracts、policy、
  snapshots 是标准库逻辑；coordinator 与 adapter 是宿主适配层，显式依赖既有
  AgentRepository、数据库、Gateway 和 ProcessManager。Protocol 是接口约定，
  当前不声称整个 coordinator 已可无改动替换为任意 RunStore。
- 固定角色 analyst/tester/reviewer/worker；累计四次委派、子角色组并发二，
  不允许递归。当前并发二是全局角色组上限，比单根任务二更保守。
- 工具为 start/status/wait/cancel/followup/merge。context 是最多 16,384 字符的
  任务数据文本，未实现任意 context_refs 自动读取。status 最多四个子任务的完整
  有界状态，不新增 event cursor。wait any/all 最长 300 秒，超时后父任务恢复。
- SQLite 78 添加绑定、等待和预算预留表；79 迁移旧宿主 App Developer executor，
  不迁移 Package 自有 definition，不删除原有任务。等待注册与 queued 更新同事务；
  重启维护恢复等待，原 tool_call_id 只结算一次。
- 源码物化副本和测试工作区分离；相同 Session 的子进程由宿主 Run 绑定选目录。
  内置 Python 可用，原项目、主草稿、快照基线和网络由实际 macOS Seatbelt 拒绝。
  工具白名单、父能力交集、账户/项目绑定均由宿主核验。
- 子任务只投影本 Run 的角色指令和有界任务说明，不继承父记忆工具。完成结果不
  写入父 Session 对话；父任务通过 status 接收证据。主任务复用既有可回读的记忆/
  checkpoint 压缩，提前压缩累计工具证据，当前请求和原始记录保留。提前压缩使用 compact_context_bytes 软阈值，
  不降低既有 512 KiB 请求硬上限；大段当前输入仍被保护。
- worker 合入只能修改主草稿：revision 校验、所有路径冲突预检、配额预检、载入并
  校验补丁内容 SHA，再逐文件原子写入并保留备份/进度 journal。不支持删除；发生
  I/O 中断时可能部分合入，journal 标明已完成文件，不宣称整个多文件写入原子化。
- 单任务源码仍沿用 512 文件/32 MiB 限制；同 Session 保留的子快照总量最多
  512 MiB，超限明确拒绝，不静默删除仍被引用的证据。日志沿用 ProcessManager
  有界留存与账户/Run 绑定读取。
- 子预算默认 20,000 token/24 step/300 秒；子 deadline 不超过根任务。根任务
  100,000 累计 token，子任务不能使用为主任务保留的最后 10,000 额度。单次输出
  最大 2,048 token。缺 usage 计全部预留并标记估算；错误和重启不释放不确定消耗。
- Coder 展示角色、状态、stale、累计 token、耗时、summary、findings、checks、patch、
  未验证项及日志入口，多组件可分别选择静态预览。Local 换端口时通过宿主 owner-scoped
  latest-task API 恢复最近任务；显式“新任务”优先于异步恢复。UI 的 follow-up 是准备主任务输入，经用户提交后继续；工具
  followup 在活动主任务内创建新尝试，关联旧 child，不是运行中双向聊天。
- 进程终态/退出码来自宿主记录。异步 command 在返回时未结束，源码后验摘要不
  作为完成时的证明，source_changed_during_check 返回未知；模型报告不替代证据。
- Python 接入仅在固定 App-Dev 经 Helper 重启 Local 激活；不触碰 Cloud、不发布。

## 15. DeepSeek 对照来源

对照官方 dsh 仓库本地固定 commit
`5badb15009ae1756c3afe0ae0cef1faafc290ccc`（MIT）：

- `packages/subagent/subagent-in-process-driver/src/index.ts`：父子 Run 生命周期、
  深度和工具边界、创建后发布、取消与清理。
- `packages/subagent/tool-subagent-control/src/index.ts`：控制工具和 interrupt/
  send_message 行为。

本实现移植协作机制，复用 AI2Apps Python 的持久化 Run、能力、记忆与进程系统；
不复制 TypeScript runtime，不宣称 API、消息邮箱或 DeepSeek 全量功能完全一致。


## 16. 验收记录与当前可靠性边界

最终记录写入 `coding-subagents-acceptance-2026-10-05.json`，包含源 commit/源文件 SHA、
真实模型 Run、子角色、工具调用/退出码、源码差异、计量和失败尝试。
模拟模型与真实模型记录分开；Cloud Anthropic 502 未算成功验收。

实用性验收采用本轮新建的非敏感玩具项目，不提交用户业务代码。真实 DeepSeek 和
Terra 已实际执行分析/开发/测试/审查相关工具，worker 补丁由宿主检查并合入主草稿。
验收过程中真实模型会重复规划/读取、误传 revision，且多角色流程累计输入计费较快。
100,000 token 是每根 Run 的默认额度，未提高；超预算明确停止，已有草稿和证据保留。
通过用户入口提交明确收尾要求会创建新的有界主 Run；不得把这种两阶段完成写成
单 Run 全程成功，也不得由子 Agent 递归或自动换 root 来绕过额度。

此次针对实际失败补齐了预算错误类型、余额反馈、merge 参数说明、重复指南识别、
提前压缩软/硬阈值分离、组件登记指引和跨端口恢复。它提升协作能力，不保证任意模型
能在默认预算内完成任意开发任务。编程测试和静态预览不证明 Bridge、移动端或发布。


静态预览的真实验收还发现：opaque-origin iframe 不带登录身份，直接请求相对 JS/CSS
会返回 401。本次 native draft HTML 响应将已授权、同组件的经典 JS/CSS 有界嵌入，
保留 sandbox（无 allow-same-origin）、connect-src none、form-action none；不向 HTML
发放 Cookie/Token，不修改源码文件。defer 经典脚本保留到正文结束后执行。HTML+
嵌入资源最多 2 MiB、单资源最多 1 MiB；模块脚本、async、远程资源明确拒绝，
相对模块图、字体/图像资源完整宿主行为仍不属于本静态预览保证。


最终验收：155 项不同 pytest 检查、12 项纯标准库独立环境检查、9 项 Node 界面检查
通过。真实模型完成已有 App 修复（有意失败测试→worker 合入→tester 退出码 0→
收尾报告）与新 Mini-App（worker 三文件补丁→tester→组件登记→收尾报告）。两例
均通过显式后续 Run 收尾；完整尝试中出现的预算/上下文失败保留在记录里。
实际预览验证 Counter 0→1、Text Stats `hello world`→11 字符/2 词；临时项目在
审阅 Apply 前保持不变，Apply 后两个组件通过 SourceProject 校验。
