# WebAgent 后台执行迁移

2026-10-09：执行权已切换到 Local。前台页面负责提交、观察和人工协助；关闭工作台或 Shell 窗口不会结束任务。原生 AceFox 浏览器进程仍是浏览器执行所需的宿主，Helper 可在没有 Shell 前台时启动它。停止 Local、退出 Helper 或关闭任务自己的浏览器页面不等同于关闭工作台。

## 执行与通信

- `BackgroundBrowserRunner` 由 Local 生命周期启动，领取能力队列，并处理 AgentRun 的 durable `browser_bidi_action` 交互。试运行、能力调用和 Schedule/Workflow 共用 `create_ir_run`，固定能力 generation、能力参数/变量/步骤和有效工作指导。
- Runner 通过原生 WebDriver BiDi 执行；`BackgroundPage` 是 Local SDK，共享现有 DOM、Readability 和站点提取规则。没有新增语义浏览器 REST/WS API，也没有用隐藏 HTML 页代替执行器。
- 拟人指针、导航后等待、稳定检查、输入、长文本分段、上传入口拦截、窗口关联、范围检查和自适应模型规划均在 Local 调度。只有需要 DOM 的函数在目标网页上下文运行。
- 浏览器控制仍经过受保护的原生 Session；Local HTML 不获得调试端点或 bearer。后台模型调用使用 actor/session 上下文，不转发浏览器 Cookie或伪造 HTTP Request。
- 前端使用 HTTP 提交/取消/继续/确认；一个工作台 SSE 订阅任务投影，运行观察通过 Agent SSE。前端不再领取队列或执行 Local-owned 浏览器动作，旧 claim/start 和响应入口拒绝抢占执行权。
- SSE 初始快照与游标来自同一个 SQLite 快照，支持 `Last-Event-ID` 重放、actor 隔离和断开释放。输入、凭据和大结果不放进状态事件；结果按事件通知读取。
- Local 监视器在没有工作台请求时也会更新任务。5 秒兜底仅检查租约，不是前端周期刷新。目录在手动刷新、窗口重新获得焦点或元数据变更时更新。

## Profile 与宿主

保留 Shell 原有 actor/Profile 到 native userContext 的绑定和登录数据；没有切换到独立磁盘 Agent Profile，也不复制 Cookie、数据库或 Profile 状态。每个运行创建独立 context，验证其 userContext，并持久化明确绑定。继续运行不会按焦点、标题或枚举次序接管其他页面。

固定 App Dev 内的原生 Shell chrome 负责 protected BiDi bootstrap 和 Profile 生命周期。关闭 UI 会卸载 Local HTML、隐藏窗口并保留原生宿主；重新打开固定 App 可恢复界面。Helper 的 `browser.host.ensure` 在冷启动时写入与 Launcher 一致的私有进程/automation 描述，支持后台启动。此逻辑不依赖 Local HTML。

## 恢复与人工协助

- 动作日志先提交 `started` 再执行原生操作，执行结果先持久化为 `completed` 再响应 Agent 交互。
- 已完成日志可直接恢复结果，即使浏览器已经不可用，也不重放动作。
- Local 重启遇到没有结果的动作会标为 `uncertain` 并暂停；不会自动重发发送、发布、删除或上传。页面/连接消失也暂停原运行。结果未知时需要检查原页面后取消并重新运行，不允许盲目“继续”。
- 创建运行期间重启，可从 `browser_task_id` 恢复已提交 AgentRun；未创建运行的 Local 队列任务可重新入队。
- 登录、验证码、敏感输入和法律同意产生持久人工协助交互；动态高影响操作要求持久确认。前台关闭期间保持等待。协助后新建动作交互，不重放旧请求。
- 关闭 SSE 只停止观察，不取消或暂停后台执行。人工协助可激活任务明确绑定的原页面。

## 验证

- 86 项 Python 定向回归通过，涵盖队列并发/actor 隔离、持久日志恢复、结果未知禁止重放、人工协助继续、列表输出、站点范围、能力参数/变量、旧情报 Agent 与 BiDi 恢复。
- 28 项 Node 定向回归通过，涵盖工作台增量事件、终态观察、输入/上传和 200K 分段；共享 DOM 生成资源检查、两个前端入口语法检查通过。
- 原生 AceFox 验收使用可丢弃 userContext 和本地测试站：200K Unicode 完整输入、上传入口点击/文件选择拦截、两条结构化列表；HTTP 客户端关闭后真实 Local Runner 完成队列并保存输出；SDK 断开重连保留页面数据。
- 固定 App Dev 的现有“读取文章列表”能力实测完成，保存 19 条结果；再次提交后立即关闭 Shell 窗口，后台仍完成并保存 19 条，执行所有者为 Local。
- 仅启动 Helper 时的冷启动验收通过：未加载 Local HTML 即可建立 protected BiDi 连接，再打开固定 App 恢复界面。
- App Dev 按固定构建脚本重建并保留实例数据；79 项 Swift 测试、签名与打包检查通过。没有发布生产版本或修改 Cloud。

## 验收命令

从仓库父目录执行 Python 测试，避免子目录的 `secrets` 包遮蔽标准库：

```sh
.venv/bin/python -m pytest ai2apps/tests/test_browser_background.py ai2apps/tests/test_browser_workspace.py ai2apps/tests/test_browser_workspace_events.py tests/test_ai2apps_agent_builder.py -q
.venv/bin/python -m pytest ai2apps/tests/test_agent_draft_run_inputs.py ai2apps/tests/test_agent_local_variables.py ai2apps/tests/test_web_agent_calls.py ai2apps/tests/test_intelligence_site_agents.py ai2apps/tests/test_shell_bidi_recovery.py -q
AI2APPS_NATIVE_ACCEPTANCE=1 AI2APPS_SHELL_AUTOMATION_PATH="$HOME/Library/Application Support/AI2Apps/instances/app-dev/run/shell-automation.json" .venv/bin/python -m pytest ai2apps/tests/test_browser_background_native.py -q
node --test ai2apps/tests/ai_browser_workspace.test.cjs ai2apps/tests/agent_run_outcome_focus.test.cjs ai2apps/tests/agent_browser_request_failure.test.cjs ai2apps/tests/browser_interaction_modes.test.cjs
```

原生验收不得用于生产实例，亦不得输出描述文件里的 credential。通用完整测试集中仍有与此次迁移无关的旧 fixture 不一致（模型元数据调用次数/JSON repair/mock identity 和前端函数抽取依赖）；上述定向回归独立记录，不以它们替代所有项目测试。

## 情报中心与 App 共用调用机制（2026-10-09 补齐）

此前的“迁移完成”只覆盖 AI 浏览器运行入口与 Agent/Schedule 的执行器，不代表情报中心采集已脱离前台。本阶段将情报采集的编排也迁入 Local，统一架构约束见仓库级 `docs/ai2apps-browser-control-architecture.md` 的“AI2Apps 公用 WebAgent 调用与后台采集”。

可信 Local App 使用 `WebAgentInvocation.submit` 提交任务，携带 owner、已授权 session、Profile、caller_app_id、稳定幂等键，以及固定的 Agent/generation/capability。多能力 Agent 必须显式选择能力；无能力导出的旧 Agent 兼容 `agent.<draft_id>.run`。内部编译程序独立落库，公开 input 不能注入 IR。调用方不创建私有执行循环；队列、并发门控、独立 Tab、Profile 绑定、动作日志、协助与取消全部复用 Browser Task。

情报中心的 `IntelligenceCollector` 随 Local 启停，原子持久化 claim/job，后台触发频道定时更新，恢复时按 collection/source/phase 复用已完成的 Task 结果。采集、站点规则验证/激活、去重、帖子筛选、摘要、知识库同步及派生整理均在后台运行。Cloud 工作模型沿用既有身份绑定的后台 Cloud 调用入口；本地模型沿用后台调度入口，不依赖 HTTP Request 或前台 Cookie。

前台通过 HTTP 提交/取消，通过共享 actor-scoped SSE 接收采集变更，再读取最新投影；不按固定时间刷新、不执行采集动作。交互式搜索推荐和手动图片操作仍可使用前台 SDK，它们不是后台 WebAgent 的执行通道。

新增 schema 87 保存内部任务程序。原有 Agent Source 不需要迁移；旧编译规则保持复用，漂移后才进行通用提取和受验证的学习。模型摘要或引用校验失败不会提交内容指纹，重试仍能读取该批证据。取消后的任务不会被迟到的浏览器错误重新置为运行中。

### 本阶段验收

- 47 项 Python 定向回归、9 项 Node 回归通过；包含原子 claim/job、旧能力兼容、多能力显式选择、内部程序调度、actor/Profile 隔离、Cloud 后台路由、重启结果复用、去重、失败不提交指纹和 SSE。
- 固定 App Dev 真实“腕表”频道：提交后切换到 AI 浏览器，卸载情报中心页面；后台完成 run `84ca46ee61314ec985a90b785aa56712`。检查 20 条、跳过 16 条、读取 3 篇、生成 3 篇情报，知识库已同步数由 28 增至 31，待同步 0。
- 同一轮列表 + 3 篇正文共 4 个 Browser Task 均 completed，复用编译规则 4 次、fallback 0、learning_calls 0，来源读取 21,757 ms。摘要与派生整理仍按业务需要调用 AI；编译提取不等于整个情报业务零 AI。
- 实测也覆盖失败路径：旧规则预检失败与 Cloud 路由缺口已修复；一次模型正文缺少引用被拒绝，后续重试成功。微博读取到一篇后第二篇定位失败，任务保守中断，经取消后保存部分结果；本阶段不宣称所有社交站点端到端成功或绕过验证码。
- 仅重启固定 app-dev Local 加载 Python 修改、刷新 HTML；未发布生产版本，未修改 Cloud 服务端代码。
