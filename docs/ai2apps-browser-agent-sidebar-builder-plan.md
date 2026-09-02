# AI2Apps Browser Agent Sidebar 与自然语言 Agent Builder 方案

状态：P0、P1、P1.1、P2、P3 MVP 已实现（通用 Agent 平台；Web Agent 为首个可执行类型）  
日期：2026-08-29  
依赖：ai2apps-browser-control-architecture.md、
ai2apps-publishable-adaptive-web-agent-architecture.md、
ai2apps-capability-provisioning-framework-v1.md、agent-task-runtime.md

## 1. 决策摘要

AceFox Browser 侧边栏在 Chat 和 Knowledge 之外增加 **Agent**：

- Chat 负责理解页面、解释和对话；
- Knowledge 负责把页面内容加入知识桶并选择对话知识范围；
- Agent 负责操作页面、提取结构化数据、运行自动化，并制作可复用 Agent。

Agent Mini-Entry 同时提供“运行 Agent”和“制作 Agent”两个模式。用户可以用自然语言逐步描述
任务，在当前真实页面单步或完整试运行，纠正错误后将成功轨迹编译为本地 Agent。复杂 Schema、
版本、测试、权限和发布管理进入完整 Agent App，侧边栏保持轻量和所见即所得。

Agent 的权威资产是 Agent Source，而不是一次对话、录制坐标或可直接执行的脚本。自然语言
步骤执行前必须生成受限候选动作并经过 Policy Engine；编译后生成本机 Compiled Agent IR。

~~~text
Natural-language Agent Source
             |
             v
     ephemeral safe plan
             |
      Policy Engine gate
             |
             v
 Interaction Executor -> native WebDriver BiDi -> current AceFox page
             |
       evidence + correction
             |
             v
      Source Compiler
             |
             v
Local Compiled Agent IR -> replay test -> save / schedule / publish Source
~~~

### 1.1 Agent App 的系统边界

`Agents` 是全系统 Agent 管理、运行、编排、调度和版本中心，不是 Web RPA 专用 App。
Web Agent Builder 是第一个类型化 Builder；后续 Knowledge、Workflow、Research、Coding、
App capability 和 Composite Agent 均复用通用 Agent Source、输入输出 Schema、Capability、
AgentRun、Checkpoint、Generation、Schedule、审计和发布模型。URL、BiDi、页面指纹和站点
scope 等字段只属于 Web Agent 类型，不能进入通用 Agent 核心的必填契约。

### 1.2 动态建议决策

P1 不实现动态建议，也不在打开网页、切换 Sidebar 或页面更新时隐式调用任何模型。用户主动
制作、解释或修复 Agent 时才可以进入显式模型流程。建议系统如需重启设计，应作为独立后续
项目重新评估 Token、隐私、缓存和可解释性，不阻塞 Agent 平台 P1。

## 2. 产品目标与非目标

### 2.1 目标

- 在当前页面发现并运行匹配的本地或 Discovery Agent。
- 用户无需理解 Selector、JavaScript 或 BiDi 即可制作 Agent。
- 自然语言 Step 可以直接安全试运行，也可以编译为确定性或混合型 IR。
- 支持单步、从当前步骤、完整、预演和用户接管。
- 把用户对错误元素、步骤或输出的纠正沉淀到 Source 和编译证据。
- 支持 compiled、interpreted、adaptive 混合 Pipeline。
- 支持保存到“我的 Agents”、固定网站、Workflow、Schedule 和 Discovery。
- 全程绑定明确的 AceFox Profile、窗口和当前 BiDi browsing context。

### 2.2 非目标

- 不在 Mini-Entry 内实现完整 IDE、代码编辑器或 Package 发布后台。
- 不录制绝对屏幕坐标作为 Agent 的主要表达。
- 不让模型或 Local HTML 获得原始 AceFox endpoint、Bearer credential 或无限制 BiDi grant。
- 不静默接受法律条款、规避 CAPTCHA、机器人验证或付费墙。
- 不把 Chat 的总结、解释、翻译功能重复放入 Agent。

## 3. 信息架构

Browser Sidebar 顶部保持统一一级切换：

~~~text
[Chat] [Knowledge] [Agent]
~~~

Agent 内部使用二级切换：

~~~text
[运行 Agent] [制作 Agent]
~~~

### 3.1 运行 Agent

默认页面包含：

1. 当前页面卡片：标题、origin、页面类型、登录/渲染状态；
2. 自然语言任务输入；
3. 当前网站已安装和本地 Agent；
4. 当前/最近 AgentRun；
5. 用户接管和权限提示。

紧凑布局示意：

~~~text
┌──────────────────────────────┐
│ AI2Apps  Chat Knowledge Agent│
├──────────────────────────────┤
│ Current page                 │
│ Fratello · Latest            │
│ ● Ready  ● Signed in         │
├──────────────────────────────┤
│ What should the Agent do?    │
│ [找出今天新增的所有文章……   ]│
│                       [Run]  │
├──────────────────────────────┤
│ Suggested                    │
│ [移除页面干扰] [提取文章列表] │
│ [读取当前文章] [监听页面更新] │
├──────────────────────────────┤
│ Agents for this site         │
│ Fratello Latest · Verified   │
│ Locally compiled · Healthy   │
│                 [Run][Detail]│
├──────────────────────────────┤
│ Recent runs                  │
│ ✓ Extracted 32 articles      │
└──────────────────────────────┘
~~~

P1 不生成动态建议。运行入口只展示用户显式创建/安装、且由确定性 site scope 匹配的 Agent。

### 3.2 制作 Agent

Builder 的主对象是步骤卡片：

~~~text
┌──────────────────────────────┐
│ Agent · 制作新 Agent         │
├──────────────────────────────┤
│ Name [读取网站最新文章      ]│
│ Scope [fratellowatches.com  ]│
├──────────────────────────────┤
│ 1 打开输入的网页             │
│   success → step-2           │
│   [试运行] [编辑]            │
│                              │
│ 2 移除可以安全关闭的页面遮挡  │
│   success → step-3           │
│   needs_user → pause         │
│   [试运行] [编辑]            │
│                              │
│ 3 提取文章的标题和链接        │
│   success → done             │
│   failed → step-6            │
│   [试运行] [编辑]            │
│                              │
│ [+ 添加自然语言步骤]         │
├──────────────────────────────┤
│ [预演] [试运行全部] [编译]   │
└──────────────────────────────┘
~~~

复杂编辑通过“在 Agent App 中打开”进入全尺寸视图。

## 4. Agent Source 编辑模型

### 4.1 自然语言 Step

最小 Step 允许只写：

~~~json
{
  "name": "step-2",
  "desc": "找到并点击页面上的搜索按钮，成功转 step-3，如果失败或找不到，转 step-6"
}
~~~

编辑器即时解析并展示但不隐藏修改：

- 动作意图：查找、点击；
- 目标语义：搜索按钮；
- 成功、找不到和失败跳转；
- 预计效果等级和权限；
- 仍未明确的输入、输出或成功条件。

推荐的规范化 Source：

~~~json
{
  "name": "step-2",
  "desc": "找到并点击页面上的搜索按钮",
  "execution": {
    "mode": "adaptive",
    "runtime_model": "lightweight",
    "max_model_calls": 1
  },
  "constraints": {
    "allowed_operations": ["inspect", "scroll", "hover", "click"],
    "max_actions": 5,
    "same_origin": true
  },
  "on": {
    "success": "step-3",
    "not_found": "step-6",
    "needs_user": "pause",
    "failed": "step-6"
  }
}
~~~

### 4.2 Agent 级字段

Agent Source 至少包括：

- 名称、说明、Source version；
- 输入和输出 Schema；
- site scope；
- capability 与效果申请；
- Step 图和终止条件；
- 模型分级与预算；
- 禁止行为；
- fixture、测试和示例；
- Source digest 与作者 provenance。

### 4.3 AI 辅助编辑

用户可以用自然语言修改 Source：

- “在提取之前增加关闭 Cookie 提示的步骤”；
- “找不到搜索按钮时改用页面顶部搜索框”；
- “只保留今天发布的文章”；
- “把前三篇文章保存到腕表知识桶”；
- “从 step-3 开始重试”。

AI 必须生成可审阅的 Source diff。扩大 origin、增加上传/提交、访问 Knowledge 或提高效果
等级时必须单独提示，不能随普通文字修改静默授权。

## 5. 试运行模型

### 5.1 运行范围

每个步骤支持：

- 预演当前步骤：定位和展示计划，不执行效果动作；
- 试运行当前步骤；
- 从这里开始；
- 单步连续运行；
- 完整重放。

Agent 级支持在当前页面运行，或创建临时页面从头运行。临时页面由 Run 关闭；用户原有页面
不自动关闭。

### 5.2 自然语言直接执行

“直接执行”在产品上是即时体验，在安全上仍有预编译：

~~~text
Step description
→ bounded page observation
→ ephemeral structured action plan
→ deterministic policy check
→ Interaction Executor
→ postcondition verification
~~~

模型每次只能提出允许集合中的结构化动作；不能直接持有无限制 BiDi Session。默认动作上限、
时间、页面、origin、模型调用和输出字节均由 AgentRun 预算控制。

### 5.3 执行模式

- compiled：只执行验证过的 IR；
- interpreted：模型根据当前页面提出动作，适合探索；
- adaptive：已编译动作优先，失败时允许局部模型恢复。

Builder 可以保存混合型 Agent，不要求第一次就把所有 Step 固化。随着成功样本增加，稳定
Step 可以逐步由 interpreted/adaptive 晋升为 compiled。

### 5.4 运行反馈

步骤卡片展示：

~~~text
✓ step-2 completed

Matched: Search button
Action: natural pointer click
Evidence: search input became visible
Duration: 1.2s

[接受结果] [换一种方式] [选择正确元素] [编辑描述]
~~~

普通视图显示语义结果；调试视图可展开候选元素、IR、BiDi 方法名、模型升级原因、Validator、
interaction seed 和失败证据，但默认不展示敏感页面数据。

## 6. 用户纠正与证据沉淀

### 6.1 选择正确元素

用户进入页面 Pick 模式后选择正确元素。系统记录：

- role、accessible name、label 和文本；
- 稳定属性与多个 Selector 候选；
- 相对语义位置和所属重复容器；
- 页面结构指纹；
- 点击前后可观察状态；
- 用户否定过的候选。

绝对坐标仅作为一次交互证据，不进入 Agent Source 的主要目标描述。

### 6.2 接受与拒绝

- “接受结果”把动作和 postcondition 作为正样本；
- “这不是目标”保存负样本并避免立即重复；
- “换一种方式”允许局部重新解释；
- 修改描述生成 Source revision；
- 纠正只保存在当前 actor 的私有草稿，除非用户明确发布。

### 6.3 编译证据

编译器使用实际命中元素、动作结果、用户纠正、输入输出样本、页面指纹和 Validator 结果，
而不是只根据自然语言猜测稳定 Selector。

## 7. 编译、验证与输出

点击“编译 Agent”后：

1. 规范化 Agent Source；
2. 验证图结构和终止条件；
3. 推断并最小化 capability；
4. 生成类型化 Compiled Agent IR；
5. 固化已经验证的目标、动作和 postcondition；
6. 为不稳定 Step 保留有界模型 fallback；
7. 生成输入输出 Schema、Validator 和 fixture；
8. 在临时页面完整重放；
9. 保存不可变 local generation；
10. 输出编译报告。

结果示例：

~~~text
step-1  compiled
step-2  compiled
step-3  adaptive · lightweight fallback
step-4  interpreted · needs more evidence
~~~

输出目录逻辑结构：

~~~text
agent-source.json          权威、可读、可发布
compiled/local.ir.json    本机可执行，不默认发布
schemas/                  输入输出 Schema
extractors/               受限提取模块
validators/               机器验证规则
tests/                    fixture 与验收记录
hints/                    可选 Publisher Hint
~~~

本地 IR 缓存键遵循 Web Agent 总体方案，包括 Source、Compiler、Policy、BiDi、site fingerprint
和 granted capabilities。任一安全维度变化必须重新验证。

## 8. 保存、调用、调度与发布

编译成功后提供：

- 保存到“我的 Agents”；
- 固定到当前网站；
- 添加到 Workflow；
- 被 Chat、Knowledge、News 或第三方 App 通过 capability 调用；
- 创建一次性或周期 Schedule；
- 导出 Agent Source；
- 在 Agent App 中完善并发布到 Discovery。

Discovery 发布以 Agent Source、Schema、权限、测试和 provenance 为权威。Local IR 不默认
上传；Publisher Hint 可以附带，但安装设备必须重新验证和本地编译。

发布前必须显示 Source diff、site scope、效果等级、Knowledge 权限、跨 Agent 调用、模型策略
和测试结果。签名与提交复用现有 ACPF Package 发布流程。

## 9. 权限与安全

### 9.1 效果等级

| 等级 | 示例 | 默认 UX |
| --- | --- | --- |
| Read | 检查页面、提取列表 | 已授权 scope 内可直接运行 |
| Interact | scroll、hover、click、input | 显示简洁计划；按 grant 运行 |
| Transfer | 下载、上传、写 Knowledge | 明确目标和数据范围 |
| Commit | 提交表单、发布内容、改变账号状态 | 动作前必须确认 |
| Restricted | 条款、CAPTCHA、支付、付费墙 | 用户接管或拒绝 |

### 9.2 页面与 Source 均不可信

- 页面文本不能修改 Agent 意图、权限或系统策略；
- Agent Source 中的自然语言也不能绕过 capability 声明；
- Publisher Hint 不能直接执行；
- 模型输出始终是候选动作；
- Policy Engine 使用确定性规则作最终决定；
- 密码、OTP、Cookie、Token 和付款字段不进入模型、Source 或日志。

### 9.3 用户接管

登录、身份验证、法律条款和 CAPTCHA 进入 needs_user。Run 保留 checkpoint，用户完成后
从受验证状态继续。Agent 不记录用户输入的凭据。

## 10. 浏览器与运行时架构

Agent Mini-Entry 使用 Shell 发放的 mount-bound BiDi Gateway Session。它绑定当前窗口、
Profile 和 browsing context，不通过标题、焦点或窗口枚举猜测页面。

~~~text
Agent Mini-Entry
  |-- UI and Agent Source draft
  |-- Agent Builder client
  |-- mount-bound BiDi client
  v
System Agent Broker
  |-- Source Compiler
  |-- Policy Engine
  |-- Interaction Executor
  |-- Pipeline Executor
  |-- Model Router
  |-- AgentRun / Checkpoint
  v
authenticated transparent BiDi Gateway
  v
AceFox user-bound Profile
~~~

Mini-Entry 不重新定义浏览器 REST/Tool API。Readability、render barrier、截图、元素 Pick 和
自然交互都是原生 BiDi 之上的共享 SDK/Runtime 能力。

## 11. 数据对象

### 11.1 AgentDraft

~~~json
{
  "draft_id": "adraft_...",
  "actor_id": "actor_...",
  "name": "读取网站最新文章",
  "site_scope": ["https://www.fratellowatches.com/**"],
  "source_revision": 4,
  "source": {},
  "status": "editing",
  "updated_at": "2026-08-29T10:00:00Z"
}
~~~

### 11.2 StepEvidence

~~~json
{
  "step_id": "step-2",
  "run_id": "arun_...",
  "page_fingerprint": "sha256:...",
  "outcome": "success",
  "target_semantics": {
    "role": "button",
    "accessible_name": "Search"
  },
  "postcondition": "search_input_visible",
  "user_feedback": "accepted"
}
~~~

### 11.3 CompileReport

包含 Source/IR digest、编译器与 Policy 版本、各 Step 模式、权限差异、测试结果、警告、失败
原因和是否允许激活。

## 12. API 与事件草案

~~~text
POST /v1/platform/agent-drafts
GET  /v1/platform/agent-drafts/{draft_id}
PATCH /v1/platform/agent-drafts/{draft_id}
POST /v1/platform/agent-drafts/{draft_id}/steps/{step_id}/dry-run
POST /v1/platform/agent-drafts/{draft_id}/steps/{step_id}/run
POST /v1/platform/agent-drafts/{draft_id}/runs
POST /v1/platform/agent-drafts/{draft_id}/compile
POST /v1/platform/agent-drafts/{draft_id}/activate
POST /v1/platform/agent-drafts/{draft_id}/export
~~~

主要事件：

~~~text
agent_builder.draft.created/updated
agent_builder.step.plan_ready/started/completed/failed
agent_builder.element_pick.started/completed/cancelled
agent_builder.user_correction.recorded
agent_builder.compile.started/completed/failed
agent_builder.local_generation.activated
agent_builder.user_attention.required/resolved
~~~

正式实现优先复用 AgentRun 和现有事件 Envelope，不新建第二套任务运行系统。

## 13. UI 状态与错误处理

Sidebar 必须覆盖：

- 无活动网页：提示打开页面，仍可编辑草稿；
- 页面切换：明确询问将 Run 绑定新页面或保留原 Run；
- BiDi 重连：按 Browser Control Architecture 重新确认唯一 context；
- Step 找不到目标：显示候选和 Pick 模式；
- 页面导航超出 scope：阻止并请求扩展权限；
- 登录/CAPTCHA/条款：暂停并请求接管；
- 模型不可用：compiled Step 继续；interpreted Step 等待或降级；
- 页面漂移：保留旧 IR，创建 local repair generation；
- 编译失败：保留草稿、证据和可定位错误，不丢失用户编辑；
- Sidebar 关闭：AgentRun 按类型继续、暂停或 checkpoint，不依赖 DOM 生命周期。

## 14. 开发计划

### P0：当前页面自然语言 Builder

实现状态：**完成（2026-08-29）**。实现与验收记录见
`ai2apps-browser-agent-sidebar-builder-p0-implementation.md`。

范围：

- Agent 作为 Chat/Knowledge 之后的第三个 Sidebar Tab；
- “运行 Agent / 制作 Agent”二级界面；
- AgentDraft 与自然语言 Step 增删改排；
- Step 解析、固定状态迁移和权限预估；
- 当前步骤预演、试运行、完整运行；
- 当前页面 Pick 正确元素；
- natural click/input/hover/scroll；
- AgentRun 进度、暂停、停止和用户接管；
- 编译为本地混合 IR，保存到“我的 Agents”。

首个示范 Agent：Fratello 当前列表页提取文章标题、URL、作者和时间。

验收：

- 用户不写 Selector/JS 可完成三步 Agent；
- 错误目标可通过 Pick 纠正；
- 编译后完整重放成功；
- 第二次健康运行不调用高级编译模型；
- Sidebar 切换和重开不丢草稿或 Run；
- 付费墙、条款和 CAPTCHA fail closed。

### P1：站点 Agent 运行与产品互通

实现状态：**完成（2026-08-29）**。

范围：

- 将全尺寸 Agents App 建设为通用 Agent 中心，Web Agent 只是首个 Agent 类型；
- 当前网站已安装/本地 Web Agent 的确定性匹配、健康状态和运行历史；
- Chat → Agent、Agent → Chat、Agent → Knowledge 上下文交接；
- Agent 调用 Knowledge 写入和 Bucket 选择；
- 为 News 等其他 App 提供稳定的 capability + 输入输出 Schema 调用契约；
- 添加到 Workflow、一次性与周期 Schedule；
- Agent App 全尺寸编辑页，覆盖 Draft、Source、Generation、Run 和 Schedule；
- fixture、Validator、CompileReport 和 local generation 回滚。

明确不包含：动态建议、页面打开时模型调用、后台页面语义分析以及为建议功能建立的 Token
预算或缓存。P1 的站点匹配、健康状态与 capability 列表均由已保存的 Source、Generation、
site scope 和 Evidence 确定性计算。

已落地接口包括：

- `GET /v1/platform/agent-capabilities` 与显式 capability invoke；
- Chat → Agent、AgentRun → Chat/Knowledge 交接；
- Workflow 创建、编辑和运行；
- 一次性/周期 Schedule 创建、暂停、恢复、立即运行及 dispatch 历史；
- generation 列表、显式激活与回滚；
- CompileReport 中的 JSON Schema、fixture 与 Validator 结果。

Schedule 只创建普通、可审计的 AgentRun，不另建第二套执行器。Web Agent 仍通过 Sidebar 的
透明 WebDriver BiDi 客户端完成页面动作；无人值守运行若需要浏览器页面，会停留在可恢复的
交互 checkpoint，等待绑定用户 Profile 的 AceFox context 可用。

验收：

- Chat 中描述的任务可生成 AgentDraft；
- Agent 结果可写入用户选择的 Knowledge Bucket；
- 本地 Agent 可被另一个 App 通过 capability 调用；
- 一次性和周期 Schedule 可创建、启停、立即运行并保留 dispatch/AgentRun 记录；
- 升级或 repair 不破坏旧 generation 和 checkpoint。

### P1.1：一个网站一个 Site Agent

实现状态：**完成（2026-08-29）**。

P1.1 将对象边界收敛为 `Site Agent → Capabilities → Steps`。同一用户、同一规范化网站默认只有
一个 Web Site Agent；文章列表、正文读取、站内搜索等操作是它的 Capability，不再各自创建
Agent。Capability 是跨 App 调用入口，Step 只是 Capability 内部的执行节点。

自然语言制作入口先创建有 7 天有效期的临时 Recipe。Recipe 可以在当前页面试运行，但只有
用户明确选择“加入当前网站 Agent”或“另建网站 Agent”后才成为持久化 Capability，避免每次
Chat/Sidebar 操作都污染 Agent 列表。加入后需要重新编译并显式激活 generation。

兼容迁移按规范化 hostname（去除 `www.`、小写与 IDNA）归并旧 Web Draft：优先保留已有
active generation 的记录为主 Site Agent，把其他 Source 无损转为 Capability，并将旧 Draft
标记为 archived。旧 Draft、generation、Evidence 和 Run 均保留可追溯，不做删除。

已落地契约：

- `ai2apps.site-agent-source/v1` 与 `ai2apps.compiled-site-agent/v1`；
- `POST /v1/platform/agent-recipes`、Recipe 试运行与显式 commit；
- `POST /v1/platform/site-agents/reconcile`；
- capability invoke 选择并只执行对应子 IR；
- Sidebar 制作入口的 Recipe 确认流与 Site Agent/Capability 编辑。

### P2：Discovery、安装编译与发布

实现状态：**MVP 完成（2026-08-29）**。实现与验收记录见
`ai2apps-site-agent-p2-p3-implementation.md`。

范围：

- 按当前 origin/path/capability 搜索 Discovery Agent Source；
- 安装前显示 Publisher、权限、测试和 Source 摘要；
- 安装时编译、首次运行站点绑定与 calibration；
- Publisher Hint 隔离和本地验证；
- Source diff、版本、签名和标准 Package 发布；
- Discovery 安装、升级、回滚和健康反馈。

验收：

- 干净设备不直接执行 Publisher IR/JS；
- 恶意 Source 或 Hint 的越权动作被 Policy Engine 阻止；
- 发布 Agent 可在另一设备重新编译并得到等价 Schema 输出；
- 权限扩大必须重新授权。

### P3：自适应学习与生态

实现状态：**MVP 完成（2026-08-29）**。已实现健康/漂移、Circuit、候选修复、增量 Site State、
调度配额、Knowledge 写入和 App dependency。更多 capability 模板与社区治理可在后续版本扩展。

范围：

- interpreted/adaptive Step 基于成功证据晋升为 compiled；
- 轻量模型局部恢复和高级模型 drift repair；
- 多页面、分页、下载、上传和效果性 Agent；
- 周期 Schedule、News 等 App 的长期调用；
- 私有团队 Source、Publisher patch 和社区质量评分；
- Agent 模板、复用 Step 和 capability composition。

验收：

- 网站小改时局部修复，不重编整个 Agent；
- 修复结果以新 generation 激活并可回滚；
- 长期任务具备预算、幂等、checkpoint 和用户接管；
- Discovery 健康度不上传私有页面正文、截图或凭据。

### P4.0：Discovery 与版本治理

实现状态：**客户端 MVP 完成（2026-08-29）**。实现与验收见
`ai2apps-site-agent-p4-0-discovery-package-governance.md`。

- 精确发送 origin/path/capability/output schema Registry 查询，同时保留旧 Cloud `q` 兼容；
- 在 Agent App 内完成下载验签、权限确认、本地编译与候选生成；
- 新版默认不替换稳定 generation；支持 manual、pinned、显式激活和 digest 回滚；
- 安装失败恢复旧 Package，生命周期操作写入本地审计；
- Cloud 精确索引由 Cloud 项目按 `ai2apps-cloud-site-agent-discovery-requirements.md` 实现。

P4.1/P4.2 尚未进入实施阶段，需要另行讨论。

## 15. 测试矩阵

- 静态页面、SPA、iframe、Shadow DOM、懒加载和无限滚动；
- 页面切换、Tab 关闭、Sidebar 重载、AceFox/BiDi 重连；
- 中文/英文自然语言 Step 和歧义跳转；
- compiled/interpreted/adaptive 混合执行；
- Selector 漂移、重复元素、隐藏元素和错误 Pick；
- click/input/hover/scroll 的真实事件链和可重复 interaction seed；
- 只读、交互、写 Knowledge、提交和 restricted 效果等级；
- 页面 Prompt injection、恶意 Source、Publisher Hint 和模型越权；
- 密码、OTP、Cookie、截图和日志隐私；
- 编译失败、模型超时、预算耗尽和用户中止；
- Source revision、local generation、回滚和 Discovery 重编译；
- VoiceOver、键盘导航、窄 Sidebar 和 Dark Mode。

## 16. 成功指标

- 用户首次制作三步 Agent 的完成率和中位耗时；
- Step 首次试运行成功率与用户纠正率；
- 用户纠正后再次命中率；
- compiled Step 比例及 Tier 1/Tier 2 调用率；
- 编译后完整重放成功率；
- 权限提示理解率和高风险误执行数；
- 本地 Agent 再运行、调度和跨 App 调用率；
- Discovery Agent 安装后首次绑定成功率；
- drift 检测、局部修复和回滚成功率。
