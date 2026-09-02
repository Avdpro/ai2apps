# AI2Apps Browser Agent Sidebar / Builder P0 实现与验收记录

状态：完成  
日期：2026-08-29  
开发入口：`AI2Apps-dev.app`

## 1. 交付结果

P0 已在 AceFox Sidebar 中交付第三个 `Agent` Mini-Entry，并具备：

- “运行 Agent / 制作 Agent”双模式；
- actor 隔离、可持久化的 AgentDraft、Agent Source、不可变编译 generation 与 StepEvidence；
- 自然语言步骤增删改、排序、成功/失败跳转与站点 scope；
- 单步预演、单步运行、完整运行、 durable AgentRun、继续/停止与用户接管；
- 当前页面语义元素 Pick，记录语义目标而不是绝对坐标；
- 原生 WebDriver BiDi 上的 page access、inspect、文章列表提取、click、input、hover、scroll、open 与 complete；
- pointer move/down/up、可见性确认和输入事件组成的自然交互轨迹；
- 本地受限编译器、Source/IR digest、Policy version、编译报告和本机激活；
- 明确法律同意、CAPTCHA、支付/付费墙、敏感输入和越界导航的 fail-closed 策略。

Agent Builder 复用现有 AgentRun / Interaction / Checkpoint，没有引入第二套任务运行系统。浏览器操作只使用经过认证、绑定 mount/Profile/context 的透明 BiDi Gateway；没有增加语义浏览器 REST 副本或 DOM JSWindowActor。

## 2. 关键实现

- `ai2apps/agent_builder/`：Source 模型、严格 P0 编译器、草稿/generation/evidence repository。
- `ai2apps/api/agent_builder.py`：actor-scoped CRUD、compile、activate、evidence 和 AgentRun 接口。
- `ai2apps/agents/browser_builder.py`：基于现有 AgentRuntime 的 durable 浏览器步骤执行器。
- `ai2apps/web/templates/system_apps/agent_mini.html`、`ai2apps/web/static/js/agent_mini.js`：Sidebar Builder、运行与接管 UI。
- `ai2apps/web/static/js/browser_bidi_client.js`：透明 BiDi 上的共享页面、元素、自然交互和结构化提取 helper。
- `ai2apps/browser/shell_bidi_gateway.py`：断开时结束 orphan BiDi session，避免 Mini-Entry 切换竞争。
- `omlx/server.py`：Helper broker 精确路由绕过外层 Local Session Cookie 守卫，仍由每次启动的 Helper bearer token 鉴权。
- `ai2apps/storage/migrations.py`：Platform schema v58，新增草稿、generation 和步骤证据表。
- AceFox Sidebar：页面 Tab 保持用户 Container；可信系统 Mini-Entry 使用 AI2Apps 本地会话 Cookie jar，切换不再跳登录页。

## 3. 实机验收

验收应用：

`/Users/avdpropang/sdk/omlx-moe-cache/apps/ai2apps-acefox/.build/AI2Apps-dev.app`

在真实 Fratello 列表页完成：

1. Chat → Agent → Knowledge → Chat → Agent 连续切换，登录态、草稿列表与 BiDi 能力均保持；
2. 仅输入“提取当前页面里的所有文章标题、链接、作者和发布时间”，AgentRun 完成并持久化 30 条文章；
3. 首条标题为 `The New Unimatic Impronte Collection Leaves A Permanent Imprint`，标题不再混入作者和日期；
4. 30 条中 29 条具有作者和发布时间，缺失项与页面本身的元数据一致；
5. 一键编译后 generation 激活，并在“我的 Agents”中显示 `active`；再次完整运行成功，确定性 P0 编译/执行路径不调用高级模型；
6. 不写 Selector/JavaScript，制作并完整运行 page access → extract list → complete 三步 Agent；
7. Pick 页面搜索按钮后，Source 保存语义特征且页面没有执行原点击副作用；
8. “点击页面上的接受服务条款按钮”在元素查找前即返回 `needs_user`；durable Run 进入 `waiting_input`，显示继续/停止，停止后成为 `cancelled`；
9. 当前 Local 服务启动后的日志无 Helper broker 401；历史 401 截止于修复前的旧进程。

## 4. 自动化验证

P0 定向测试共 84 项通过：

- Agent Builder / Mini-Entry / Chat Mini / AgentRun：43 passed；
- BiDi Gateway / client bootstrap / security boundaries / schema migration：41 passed；
- `agent_mini.js`、`chat_mini.js`、`browser_bidi_client.js` 通过 Node syntax check。

测试覆盖草稿和 generation 隔离、编译图校验、证据持久化、透明 BiDi、orphan session 清理、Sidebar 静态契约、Helper bearer 边界和 schema v58。

## 5. P1 边界

P0 不包含 Discovery 安装/发布、跨 App capability 调用、Knowledge 写入、Workflow/Schedule、全尺寸 Agent App、fixture/validator 管理和 generation 回滚 UI；这些保持在方案的 P1/P2 范围。
