# AI2Apps Browser Control Architecture

## Decision

WebDriver BiDi is the single browser-control protocol for AI2Apps. Main App,
trusted Mini-Entries, Knowledge, Chat, and WebAgent use the same protocol for
page inspection and browser automation.

AI2Apps must not create a second semantic browser API that mirrors BiDi. The
AI2Apps BiDi Gateway is a protocol-transparent security and lifecycle boundary:
it forwards BiDi commands, responses, and events without renaming methods or
changing their payload shapes.

## Topology

```text
AceFox WebDriver BiDi
        |
        | authenticated loopback WebSocket
        v
AI2Apps BiDi Gateway
        |-- Main App host bridge
        |-- trusted Sidebar Mini-Entries
        |-- Chat and Knowledge
        `-- WebAgent runtimes
```

AceFox starts BiDi by default for the authenticated AI2Apps user Profile. The
raw listener remains loopback-only and requires the per-launch 256-bit bearer
credential. The credential and raw endpoint are never exposed to Local HTML.
The Helper owns them and issues revocable, actor-bound Gateway sessions.

## Gateway contract

The Gateway exposes the complete BiDi command and event surface. It may:

- authenticate the AI2Apps instance, actor, App, and Mini-Entry mount;
- enforce declared browser capabilities;
- bind a caller to an AceFox Profile, window, or browsing context;
- multiplex request IDs and events;
- apply message-size, rate, and lifetime limits;
- audit method names and outcomes without logging page data or credentials;
- reconnect or revoke sessions when AceFox restarts.

It must not replace methods such as `script.evaluate`,
`browsingContext.captureScreenshot`, or `input.performActions` with an
AI2Apps-specific copy. Convenience behavior belongs in a shared client SDK
built on the raw protocol.

## Capability model

- `browser.read`: context tree, URL/title, DOM evaluation, selection, and
  screenshots.
- `browser.interact`: navigation, input actions, dialogs, and scrolling.
- `browser.automation`: tabs, windows, downloads, network events, and
  interception.
- `browser.webdriver-bidi`: the complete protocol for trusted system Apps and
  WebAgent runtimes.

The Main App host may request the full capability. A Mini-Entry receives a
mount-bound session through the host bridge and never receives the underlying
bearer credential.

## Current-page binding

AceFox publishes the active top-level BiDi browsing-context ID whenever the
selected tab changes. A Sidebar mount is bound to that ID and window. Commands
that omit a target may use the binding; commands with an explicit target must
remain inside the granted Profile scope.

Firefox may rotate its generated top-level navigable UUID after a BiDi session
disconnects. The shared client therefore keeps its session alive for the
Mini-Entry lifetime. When reconnecting, it accepts a replacement ID only if a
fresh `browsingContext.getTree` has exactly one top-level context with the
Sidebar-bound URL; an ambiguous match fails closed and asks for a context
refresh.

This small privileged binding is the only browser-window responsibility that
may remain in Firefox UI code. It must not extract DOM, run Readability,
capture screenshots, or implement interaction commands.

## Native Sidebar user actions

The Sidebar toolbar menu provides panel refresh and user-initiated site-data
clearing. Site-data clearing is native Firefox privacy UI, not a browser
control API: it reads the selected HTTP(S) URI, shows the schemeless site in a
confirmation, and invokes Firefox ClearDataService for cookies, site storage
and caches in the current Profile. Internal pages disable the action. It is
not callable by a Mini-Entry, Agent, Gateway method, or JSWindowActor message.
DOM inspection, page interaction and automation continue to use BiDi only.

## Shared client SDK

AI2Apps provides optional helpers on top of the full BiDi connection:

- wait for render and page stability;
- run Readability, then fall back to cleaned rendered HTML;
- remove hidden consent, advertisement, navigation, and dialog nodes;
- read the current selection;
- capture the visible viewport for a multimodal model;
- detect and handle cookie declarations under PageAccess policy;
- serialize common input actions.

These helpers are clients of BiDi, not a replacement protocol. Callers may use
any native BiDi method directly.

## Product flows

### Chat Sidebar

Before every request, Chat evaluates the current rendered page through BiDi.
If the chosen model declares image input and the user enables it, Chat also
captures the visible viewport through `browsingContext.captureScreenshot`.
The page and screenshot are treated as untrusted model input.

Local and AI2Apps-managed Cloud image-capable models receive the screenshot as
an OpenAI-compatible PNG Data URL. Cloud support was deployed with OpenAPI
1.26.0 and passed the first client production acceptance request on 2026-08-28.
The contract and limits are recorded in
`docs/ai2apps-cloud-browser-screenshot-input-requirements.md`. Local must not
publish a private screenshot to an arbitrary public URL.

### Knowledge webpage import

Static HTTP plus Readability remains an optimization when explicitly selected
or when Auto determines it is sufficient. AceFox mode, dynamic fallback, and
user-assisted login all use the same Profile-bound BiDi session. Import tabs
are closed after extraction unless the user is actively controlling them.

### WebAgent

WebAgent receives the full protocol according to its capability grant. Complex
automation must compose native BiDi commands and events rather than request
new server-side wrapper endpoints.

### Agent Sidebar and Builder

The Browser Sidebar exposes Agent beside Chat and Knowledge. Its trusted
Mini-Entry can run page-scoped Agents and author natural-language Agent Source.
Direct step testing still compiles an ephemeral structured plan, passes it
through deterministic policy, and executes approved actions through native
BiDi. The product behavior and staged implementation are defined in
`docs/ai2apps-browser-agent-sidebar-builder-plan.md`.

## Prohibited designs

- A JSWindowActor request/response protocol for DOM extraction, screenshots,
  or browser interaction.
- A REST or WebSocket API that redefines the BiDi method catalog.
- Exposing the raw AceFox debugging port or bearer credential to Local HTML.
- Selecting a browser window by focus, title, enumeration order, or inferred
  embedding structure instead of an explicit BiDi browsing-context binding.
- Launching a second temporary Profile when the operation is intended to use
  the authenticated user's AceFox Profile.

## Migration

1. Publish authenticated full-protocol Gateway sessions to the Main App host.
2. Bind Sidebar mounts to the selected BiDi browsing context.
3. Move Chat current-page extraction and screenshots to the shared BiDi SDK.
4. Move Knowledge user-assisted completion from Managed Browser extraction to
   the same BiDi session.
5. Delete the legacy Actor extraction messages after all consumers migrate.


## AI2Apps 公用 WebAgent 调用与后台采集（2026-10-09）

本节是所有 AI2Apps App 调用 WebAgent 的统一约束，包括 AI 浏览器、情报中心、定时任务、Workflow 和其他可信 Local App。调用方负责业务参数和结果处理，执行权始终属于 Local 后台；不得依赖前台 HTML 页面、页面定时器或前台 BiDi 连接推进 Agent。

- 可信 Local 调用方通过 `ai2apps.browser.invocation.WebAgentInvocation.submit` 提交已激活能力的固定 generation，或经共享编译器校验的内部只读程序。程序单独持久化在 `browser_task_programs`，不能由公开任务 API 的 input 字段注入。
- 所有调用使用 `BrowserTaskRepository` 的统一队列与 actor/Profile 并发门控；`BackgroundBrowserRunner` 是唯一浏览器执行器。已有 `create_ir_run` 直接入口保留兼容性，同样执行 Task admission，不另建应用私有浏览器执行循环。
- 多能力 Agent 必须显式传入 capability；只有单能力或无导出的旧 Agent 可以使用兼容默认入口。
- 入队校验当前 owner、session 访问权、能力 generation 所有权及状态；任务绑定 caller_app_id、独立原生 Tab、Profile userContext。应用不得复制登录状态或按前台焦点接管页面。
- 情报中心由 `IntelligenceCollector` 随 Local 生命周期运行：频道 claim 与 collection job 原子写入，后台定时触发，来源读取进入统一 Browser Task，结果生成使用 actor 的后台模型上下文。关闭情报中心页面不影响采集。
- 业务采集幂等键固定为 collection/source/phase；Local 重启后读取既有 Task/AgentRun 的持久结果，未知操作沿用 action journal 的暂停与人工协助机制，不重放点击/提交。原有编译站点规则继续复用；规则漂移通用回退，学习候选必须通过实际网页结果比对后才能激活。
- 前台 HTTP 只提交、取消及提供人工协助；共享 actor-scoped SSE 推送 Task/采集状态，断线重连重新读取投影。前台不得周期轮询推进采集或按网页生命周期取消后台工作。
- 社交来源继续执行冷却、帖子初筛、正文复筛与证据覆盖标记；微博正文必须从列表点击进入，不能退化为直接访问正文 URL。验证码或法律同意保持人工处理。
- 情报生成成功后才提交内容指纹；知识库同步、实体和热点整理由后台继续处理，派生整理失败不撤销已保存情报。

验证与当前实施范围见 `ai2apps/docs/webagent-background-migration.md`；原有旧式前台执行迁移记录不能视为所有 App 已完成迁移的证据。


### 平台通用搜索 WebAgent（2026-10-09）

所有需要浏览器网页搜索的可信 Local App 可复用 `builtin:web:search` / `web.search`，通过上述统一 Browser Task 调用，默认 Google、结果不可用时回退免费 Bing 网页搜索。能力输出统一为 query/provider/items/count，items 至少包含 title/url；编译执行不依赖前台和逐次 AI。语义标题与引擎区域提取器位于 Local BiDi 客户端 SDK，不能新增搜索专用浏览器控制协议。未来 API provider 使用同一输出契约与平台秘密存储。完整调用、失败和扩展约束见 `ai2apps/docs/platform-search-agent.md`。现有 research HTTP Tool 尚未迁入此入口，不能将本项视为所有搜索调用方已迁移。


## WebAgent task page lifecycle

Local WebAgent Tasks default to closing the pages they create when the root
run completes, fails or is cancelled. Cleanup belongs to the shared background
runner, not to an individual calling App or the generated agent prompt.

- Record the creating run and native Profile identity for the root context.
  Persist SDK-created contexts and new opener-linked pages observed during an
  action in the run and Task browser context. User-supplied contexts are borrowed,
  not owned; never close them merely because a Task used them.
- Waiting for input, approval or assistance is not completion. Preserve those
  contexts until the Task resumes or is cancelled.
- A trusted caller may pass `retain_pages_reason` to `WebAgentInvocation.submit`
  when the user needs the result page or a continuing Task needs it. Direct run
  callers may put the same explicit reason in `browser_context`. Page text and
  generic model responses do not select retention. Record the reason on the Task.
- After close requests, query native BiDi `browsingContext.getTree` again. Record
  `cleanup.state` as `verified`, `pending` or `retained`, with remaining context
  IDs, reason and timestamp. A successful close response alone is not proof.
- Reconcile pending cleanup, including after Local restarts, by reconnecting to
  recorded context IDs without creating or navigating replacement pages.
  Profile mismatches are never closed and remain pending for inspection.
- Historical pages without recorded ownership are not swept by URL or by the
  currently focused tab. Abrupt interruption before ownership can be recorded
  likewise cannot justify closing an unproven page.

Explicit reader navigation outside WebAgent Tasks continues to retain its page.

## Composite Task trees (2026-10-10)

TaskTreeRepository owns durable actor-scoped composite nodes. Parent and root bindings are immutable and resolved from an authorized parent; trusted WebAgentInvocation callers may pass parent_task_id, never arbitrary root IDs. Intelligence collections create collection/source nodes and attach Browser Tasks beneath them. BrowserTaskRepository remains the single admission authority, and BackgroundBrowserRunner remains the only browser executor. No additional browser-control protocol is introduced.

Admission counts root/Profile groups, falling back to the independent Browser Task ID for legacy calls. Different Profiles under one root consume separate global slots. Each group permits one active browser child; composite parents and non-browser processing consume no browser slot. Interrupted/waiting work and recorded pending page cleanup keep their slot. Workbench counters use the same group identity.

Composite finishing is durable and waits for descendant termination and recorded owned-page cleanup (verified or explicitly retained). Startup failures without created resources need no cleanup receipt. Monitor reconciliation resumes finishing after restart. Cancelling a subtree prevents new children and queued browser claims, delegates running cancellation to Agent Runtime, and waits for cleanup before final cancellation. Existing action-journal uncertainty rules continue to prohibit blind replay. Failed collection retries use a new root; restart recovery retains the same root and stable phase IDs.


### Task 树完整接入（2026-10-10，Schema 89）

本条补齐综合任务树第一阶段。情报中心刷新使用 collection 根任务，预先建立各 source 子任务；列表提取和每篇正文读取作为 source 下的 browser_execution；跨来源去重、翻译、摘要、保存与派生整理作为根下独立 organize。source 的证据与日志落库，Local 恢复复用结果；已保存的业务 run 可恢复尚未结束的 organize，无需重新摘要。

AI Browser 排队、测试、直接能力执行无父任务时自动创建 webagent 根；有父任务时创建 browser_execution。Schema 89 的 execution_task_id 将 Browser Task 与对应节点绑定。agent.call 内部调用创建持久 capability_call 帧，嵌套帧共享同一 Agent Run、Tab、动作日志与根/Profile 执行组，不增加浏览器并发计数。父/根绑定仍由数据库验证，客户端不可任意指定根来绕过门控。

取消先使运行中的 Browser Task 进入 cancelling，实际 Run 终止后才确认终态；根任务等待后代终止及自有页面 verified/retained 清理回执。SSE 与快照共用数据库游标，工作台 task_tree 只暴露元数据，不推送完整证据结果。历史未绑定 execution_task_id 的任务保留兼容逻辑。所有页面控制继续使用原有原生 BiDi 与受保护 Gateway，不新增语义浏览器 API。

本次 66 项 Python 与 28 项前端定向回归通过。代码尚未在真实实例重启加载，原生浏览器与真实 F1 验收待进行；部署需要 Local 重启自动迁移 Schema 89。

## AI Browser Web-Agent Mini-Apps

AI Browser hosts ordinary App Package Mini-Apps under placement `ai2apps.ai-browser`, with a fixed
sandbox UI and independent declared WebAgent capabilities. All capability execution uses the shared
Local `WebAgentInvocation`/Browser Task queue, also used by Intelligence Center; the UI submits commands
and receives SSE-driven status through the existing mount-bound Studio MessageChannel. No foreground
execution loop or second browser API is permitted. See the
[Web-Agent Mini-App Package contract](ai2apps-web-agent-mini-app-package-contract-v1.md) for manifests,
SDK, lifecycle, security and the two-capability Web Reader example.


### Source Task page reuse

Trusted Local callers may request reuse within an explicit owning parent Task.
Sequential browser children can transfer a completed child's Task-created
context only within the same actor, source Task and Profile, after validating
the live native userContext. Ownership transfer is persisted atomically; the
old child no longer owns cleanup. Validation tasks may retain independent
contexts. User tabs and contexts from other Task scopes must never be adopted.

Successful children can keep the context while the source is running. Source
completion enters finishing and waits for the retained context to be closed
and verified. Failed/cancelled executions close their contexts. Restart cleanup
uses recorded context IDs without creating or navigating replacement pages.
All inspection, navigation and closing continue through native authenticated
BiDi; this lifecycle metadata introduces no alternate browser protocol.


### Browser command failure and navigation recovery (2026-10-13)

A BiDi response timeout is not a page-load deadline. The Local SDK records method and timeout without credentials or page parameters. GET navigation can detach/reconnect its private attachment and inspect the same owned context/Profile: continue when the requested URL is already present, otherwise retry navigation once. Missing or mismatched contexts fail closed without launching/adopting another Tab. Other uncertain mutations are never replayed automatically.

The shared runner commits an explicit failed browser-action response with action_outcome_unknown and automatic_replay_allowed=false, delivers it to the Agent, and wakes normal failure/recovery transitions. A durable failure response is replayable as data, not as another browser command. Startup converts unfinished action journal records to failure observations; it does not assume mutation success. If error delivery itself fails, cancel and perform normal terminal cleanup instead of leaving a permanently paused flow. Human login/consent/confirmation remains a separate needs_user state. Shopping and Intelligence use this common mechanism. This supersedes automatic pausing for ordinary transport exceptions and recovered browser action journal uncertainty above.


### Bounded child pools (2026-10-13)

Trusted WebAgentInvocation calls may declare parallel_limit (1–3) for children bound to an authorized owning Task. Root/Profile grouping remains the admission quota; inside a group, the strictest active/candidate child limit controls admission, including pending cleanup. Default and social reuse tasks remain serial. Caller input cannot set arbitrary root identity or parallel limits through the public browser task submission API. Shared Profile input locks serialize SDK pointer, keyboard, scroll and upload operations while navigation/inspection can overlap across separately owned contexts. Pool results retain input order; cancellation propagates to workers and root finishing still waits for descendants and verified cleanup. AI Browser displays composite roots with child drilldown; actor-scoped root cancellation cancels the owning collection or subtree. This supersedes the previous one-active-child restriction for explicitly opted-in trusted Tasks.

## Shared DOM visibility policy

`ai2apps/web/static/js/browser_dom_visibility.js` is the single visibility policy for browser page readers and observed native input targets. Python's `browser/dom_visibility.py` and the front-end BiDi client bind this function locally into each page script; no page-global API is installed. Shared snapshots, list recovery, search readers, sorting and Shopping controls use it. Legacy backend snapshot/authentication/relocation and consent scripts include the identical source.

A node is excluded when it or a composed ancestor (including a Shadow DOM host) is hidden, inert, aria-hidden, display:none, visibility:hidden/collapse, content-visibility:hidden, or effectively below 5% opacity. Opacity is accumulated through ancestors. Result readers require a nonzero rendered box but may read offscreen rendered results; input/consent callers can additionally request viewport intersection. Structural snapshot containers can omit the box requirement so display:contents parents do not discard visible children. Matching text or a stale selected class on a hidden duplicate never establishes a visible control or sort selection. Keep explicitly authorized hidden file-upload handling separate from ordinary click targets.
