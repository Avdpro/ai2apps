# AI2Apps 可发布、自适应与加速型 Web Agent 技术方案

状态：实施方案 v0.3；产品 P2/P3 MVP 已实现  
日期：2026-08-29  
依赖：`ai2apps-browser-control-architecture.md`、`agent-task-runtime.md`、
`ai2apps-package-publication-runbook.md`、`ai2apps-package-runtime-isolation-macos-v1.md`、
`ai2apps-browser-agent-sidebar-builder-plan.md`

## 1. 决策摘要

AI2Apps 将 WebDriver BiDi 定义为唯一浏览器控制底层，在其上建设可安装、可发布、
可被任意 App 调用的 Web Agent 能力层。

Web Agent 的权威开发与发布形态是声明式 **Agent Source**：由自然语言意图、结构化输入输出、
能力申请、效果边界、流程关系和测试组成，而不是发布后可直接执行的任意 JavaScript 或 BiDi
命令。安装时由本地编译器完成意图检查、权限收敛和静态验证；首次运行时再结合真实页面完成
站点绑定、试运行和校准，生成本机实际执行的 **Compiled Agent IR**。

加速机制不是缓存一次 LLM 回答，也不要求后续绝对无模型。高级能力模型适合首次编译、复杂
页面理解和重大修复；健康运行优先执行已验证的确定性 IR，并允许按 Agent 策略调用少量本地
或低成本轻量模型完成语义定位、Blocker 分类、字段归一化和局部恢复。

一个面向网站发布的单位称为 **Web Agent Pack**。它是普通 ACPF Contract v1 Package，
可以通过 Discovery 查找、安装、升级、回滚和卸载。Pack 导出稳定 capability，而不是把
内部 CSS Selector、JavaScript 或 BiDi 会话直接暴露给调用 App。Publisher 可以附带预编译
提示以加速首次绑定，但提示不具有本地执行信任，必须重新校验。

核心路径如下：

```text
App / Sidebar / Knowledge / Scheduler
                 |
                 v
          System Agent Broker
                 |
       capability + URL resolver
                 |
                 v
        Web Agent Runtime (ACPF)
          |             |
          |             +-- signed Web Agent Pack / local patch
          v
   authenticated BiDi Gateway
                 |
                 v
        AceFox user-bound Profile
```

## 2. 目标与非目标

### 2.1 目标

- 首次访问陌生网站时可通过 Zero-shot 生成可验证的站点 Pipeline。
- 开发者可用偏自然语言的步骤描述 Agent，由编译器生成严格、可重放的 IR。
- Discovery 以 Agent Source 为权威发布物，本地编译结果为唯一实际执行版本。
- 后续运行在无结构漂移时不依赖高级模型；轻量模型调用必须有明确任务、输入边界和预算，
  显著低于首次编译成本。
- Discovery 可按 capability、origin、路径、页面类型和兼容性发现 Web Agent Pack。
- Chat、Knowledge、News、Workflow 和第三方 App 使用同一调用协议。
- Pipeline 失败时区分网络、登录、Blocker、付费墙和结构漂移，避免错误修复。
- Zero-shot 修复生成本地派生版本，不原地改写已签名 Package。
- 运行结果具备来源、版本、时间、提取方式、校验结果和 checkpoint。
- Agent 运行遵守 App、Package、用户 Profile 和网站范围的最小权限。

### 2.2 非目标

- 不建立一套复制 WebDriver BiDi 方法目录的 REST/Tool API。
- 不允许 Pack 获得 AceFox 原始端口、Bearer Token、Cookie 或 Host Secret。
- 不保证绕过登录、CAPTCHA、机器人验证、付费墙或内容授权限制。
- 不默认复制或重新发布网站完整内容。
- 不把任意模型生成 JavaScript 直接作为可信 Host 代码执行。
- 不把 Publisher 附带的 Compiled IR 当成本机可信执行物。
- 不把一次空结果直接解释为“没有新内容”。

## 3. 核心概念

### 3.1 Capability

Capability 是 App 依赖的稳定语义契约，例如：

```text
web.page_access
web.article_feed
web.read_document
web.site_search
web.forum_threads
web.product_list
web.product_detail
web.event_schedule
```

Capability 定义输入、输出、效果等级和权限上限。不同 Pack 可以提供同一 capability，
调用 App 不需要依赖某个具体实现。

### 3.2 Agent Source

Agent Source 是面向人、Discovery 和编译器的权威表示，允许自然语言步骤，但必须同时提供
机器可验证的输入输出、能力、效果和跳转边界。例如：

```json
{
  "name": "step-2",
  "desc": "找到并点击页面上的搜索按钮",
  "execution": {"mode": "adaptive", "runtime_model": "lightweight"},
  "on": {"success": "step-3", "not_found": "step-6", "failed": "step-6"}
}
```

自然语言是待编译数据，不是绕过策略的指令。编译器必须把目标、允许动作、验证条件和状态
迁移显式化；无法消除的高风险歧义进入审核或 `waiting_input`。

### 3.3 Compiled Agent IR

Compiled Agent IR 是严格、类型化、可重放的本地执行图。它记录 Source digest、编译器和策略
版本、目标站点指纹、权限集与测试结果。IR 支持三种步骤模式：

- `compiled`：只运行已验证动作，不调用模型；
- `interpreted`：在明确动作和预算边界内由模型提出结构化动作；
- `adaptive`：优先运行已编译动作，失败时允许轻量模型局部恢复，必要时升级高级模型。

模型只能提出候选动作；Runtime 的确定性 Policy Engine 负责授权，Interaction Executor
负责真实执行。

### 3.4 Web Agent Pack

面向一个网站或网站集合的已签名 Package，包含：

- capability exports；
- URL scope 与页面类型匹配规则；
- Agent Source；
- 可选 Publisher Compiled Hint、只读提取器候选和生成 provenance；
- 输出 JSON Schema；
- 结果 Validator；
- 页面结构指纹与测试 fixture；
- Blocker/CMP 识别扩展规则；
- 兼容版本与所需 Runtime；
- license、provenance、publisher 和更新说明。

默认一个网站发布一个 Site Agent；一个 Pack 可以包含一个或多个网站的 Site Agent。文章列表、
正文读取、站内搜索和分页是 Site Agent 内的多个 Capability，不是多个独立 Agent。只有权限域、
账号体系或产品边界确实独立时才拆分 Site Agent。

### 3.5 Pipeline

Pipeline 是有界、声明式的执行图。标准步骤由 Runtime 实现，站点专用代码仅用于有界
提取与规范化。

### 3.6 Site State

Site State 保存增量比较需要的 checkpoint、已见 Item、内容指纹、上次成功时间和
Pipeline generation。它属于 `installation + actor/profile + capability + normalized source`，
不属于某个 Package 版本，因此升级或本地修复后仍可连续比较。

### 3.7 Interaction Executor

`click`、`input`、`hover`、`drag` 和 `scroll` 是高层语义动作。Runtime 通过统一
Interaction Executor 将其转换为原生 BiDi `input.performActions`，而不是让 Agent 生成
鼠标坐标。

交互 Profile 包括：

- `instant`：内部测试和明确允许的快速操作；
- `natural`：真实滚动、命中点、分段指针轨迹、停留、键盘事件和动作后验证；
- `accessibility`：优先可访问性语义、焦点和键盘导航。

自然交互用于兼容 hover、focus、lazy render 和真实事件链，不用于规避 CAPTCHA、机器人验证
或访问限制。每个 Run 保存 `interaction_seed`，使带受控时序变化的操作仍可复现。

### 3.8 Local Patch

网站漂移后的 Zero-shot 修复保存为本地不可变派生版本，例如：

```text
com.ai2apps.webagents.fratello@1.3.0
com.ai2apps.webagents.fratello@1.3.0+local.1
```

本地 Patch 不继承 Publisher 签名身份，不自动上传，也不覆盖原始 Artifact。

## 4. Package 与 Discovery 契约

Web Agent Pack 使用现有 Contract v1 签名、提交、审核和发布流程。以下为 Pack 内部目标
manifest；字段进入正式实现前应纳入 Package schema 校验：

```yaml
schema: ai2apps.web-agent/v1
id: com.ai2apps.webagents.fratello
name: Fratello Web Agents
version: 1.3.0
publisher: {id: example-publisher}
runtime:
  provider: ai2apps.runtime.web-agent
  protocol: ai2apps.web-agent-worker/v1
compatibility:
  ai2apps: ">=0.1.0"
  webdriver_bidi: ">=1"
site_scopes:
  - origin: https://www.fratellowatches.com
    paths: ["/archives/**", "/**"]
exports:
  - capability: web.article_feed
    source: agents/fratello.site-agent.json
    capability_id: article-feed
    compiled_hint: hints/article-feed.ir.json
    input_schema: schemas/article-feed-request.json
    output_schema: schemas/article-feed-result.json
    effects: read_only
  - capability: web.read_document
    source: agents/fratello.site-agent.json
    capability_id: read-document
    compiled_hint: hints/read-article.ir.json
    input_schema: schemas/read-document-request.json
    output_schema: schemas/web-document.json
    effects: read_only
permissions:
  browser: [read, interact]
  site_origins: [https://www.fratellowatches.com]
  secrets: []
  direct_network: false
tests:
  fixtures: tests/fixtures/
  contract: tests/contract.json
```

Manifest 权限是申请，不是授予。安装授权和每次运行的 capability grant 分开处理。
`compiled_hint` 为可选不可信提示，不能在下载后直接执行；本地编译器可采用、修改或完全丢弃。

Discovery 查询键至少包括：

- normalized origin；
- pathname pattern；
- capability；
- output schema/version；
- AI2Apps、Runtime 与 BiDi 兼容版本；
- locale、登录态变体和可选页面指纹。

Resolver 排序原则：

1. 已安装且已授权；
2. origin 精确匹配；
3. path 越具体越优先；
4. 页面类型与结构指纹匹配；
5. 最近验证成功；
6. 用户固定版本；
7. Publisher 信任、版本和健康度。

Discovery 结果只能被展示和安装，不能在校验签名和授权前执行远程代码。Discovery 搜索与审核
以 Agent Source、能力声明、效果边界和测试为核心；Publisher Compiled Hint 不构成安全证明。

## 5. Agent Broker 与调用契约

Broker 是 Core 的可信控制面，负责解析、授权、运行和审计。App 调用 capability，而不是
直接启动 Pack Worker：

```json
{
  "capability": "web.article_feed",
  "target": {
    "url": "https://www.fratellowatches.com/archives/"
  },
  "options": {
    "only_new": true,
    "limit": 50,
    "profile": "current-user"
  },
  "context": {
    "consumer_app_id": "ai2apps.news",
    "purpose": "daily-source-collection"
  }
}
```

标准返回 Envelope：

```json
{
  "run_id": "arun_...",
  "status": "completed",
  "result": {
    "items": [],
    "new_items": [],
    "updated_items": [],
    "checkpoint": "opaque-checkpoint"
  },
  "provider": {
    "package_id": "com.ai2apps.webagents.fratello",
    "version": "1.3.0",
    "pipeline_id": "article-feed",
    "pipeline_generation": 4
  },
  "provenance": {
    "source_url": "https://www.fratellowatches.com/archives/",
    "collected_at": "2026-08-28T10:00:00Z",
    "extraction_method": "site_pipeline",
    "authenticated_profile": true
  },
  "validation": {
    "status": "passed",
    "confidence": 0.98,
    "warnings": []
  }
}
```

Broker 的职责：

- 验证调用 App、actor、Package 和 capability；
- 将 URL 规范化并检查 site scope；
- 解析已安装 Provider 或查询 Discovery；
- 建立受约束的 BiDi Gateway session；
- 创建持久化 `AgentRun` 与幂等 action key；
- 限制时间、步骤、模型 Token、结果字节和页面数量；
- 校验输出 Schema、provenance 和 checkpoint；
- 提交 Site State；
- 发布事件并返回调用方。

## 6. Agent Source、编译与 Pipeline IR

开发者优先编写 Agent Source，不要求手写底层 IR。Source 可以混合自然语言步骤与结构化
约束：

```json
{
  "id": "article-feed",
  "steps": [
    {
      "name": "find-search",
      "desc": "找到并点击页面上的搜索按钮",
      "execution": {"mode": "adaptive"},
      "constraints": {
        "allowed_operations": ["inspect", "scroll", "hover", "click"],
        "max_actions": 5
      },
      "on": {"success": "enter-query", "not_found": "fallback", "failed": "fallback"}
    }
  ]
}
```

编译器将它转换为有界、声明式执行图；目标候选、交互策略、验证条件和所有状态迁移必须显式。
例如编译后的步骤可包含：

```json
{
  "id": "find-search",
  "type": "browser.interact",
  "operation": "click",
  "target": {
    "role": "button",
    "intent": "search",
    "candidates": [
      {"aria_role": "button", "accessible_name": "搜索"},
      {"aria_role": "button", "accessible_name": "Search"},
      {"css": "button[type='submit']"}
    ]
  },
  "interaction": {"profile": "natural", "ensure_visible": true},
  "verify": {"any": ["navigation", "network_activity", "page_state_changed"]},
  "on": {"success": "enter-query", "not_found": "fallback", "failed": "fallback"}
}
```

目标 Pipeline 示例：

```json
{
  "id": "article-feed",
  "version": 3,
  "match": {
    "origin": "https://www.fratellowatches.com",
    "path_pattern": "^/archives(?:/page/\\d+)?/?$"
  },
  "steps": [
    {"type": "open", "target": "$input.url", "page": "temporary"},
    {"type": "wait_render", "policy": "interactive-and-layout-stable"},
    {"type": "invoke", "capability": "web.page_access"},
    {"type": "wait_render", "policy": "post-interaction-stable"},
    {"type": "evaluate", "module": "extractors/article-feed.js"},
    {"type": "normalize", "schema": "ArticleList"},
    {"type": "validate", "rules": "validators/article-feed.json"},
    {"type": "diff", "state_key": "$source.identity"},
    {"type": "close", "when": "created_by_run"}
  ]
}
```

标准步骤包括：

- `open`、`navigate`、`close`；
- `wait_render`、`wait_selector`、`wait_network_quiet`；
- `browser.interact`，覆盖 click/input/hover/drag/scroll 等语义动作；
- `invoke` 另一个 capability；
- `evaluate` 有界只读 JS；
- `model` 有 Tier、输入边界、预算、允许动作和输出 Schema 的模型步骤；
- `readability` 与 cleaned rendered HTML fallback；
- `scroll`、`paginate`；
- `normalize`、`validate`、`deduplicate`、`diff`；
- `checkpoint`、`request_user`；
- `emit`。

需要浏览器交互的步骤由 Runtime 使用原生 BiDi 组合实现。Pipeline 协议不能重新定义
`script.evaluate`、`input.performActions` 等 BiDi 方法目录。

Runtime 只接受固定状态集合，例如 `success`、`not_found`、`retryable_error`、
`needs_user`、`restricted` 和 `failed`。编译器不得依赖运行时参数猜测或隐式跳转来
修复不完整 Source。

## 7. PageAccessAgent

`web.page_access` 是通用前置能力，识别和处理 Cookie、隐私通知、推广弹窗、登录墙、
地区/语言选择及其他页面阻碍。

默认策略：

| 类型 | 默认行为 |
| --- | --- |
| Cookie | 拒绝非必要或仅允许必要项 |
| 纯信息隐私通知 | 关闭或确认已阅读 |
| 服务条款/具有约束力的同意 | `waiting_input`，不得自动接受 |
| Newsletter/App 推广 | 关闭 |
| 通知权限 | 拒绝 |
| 登录墙 | 使用绑定 Profile；失效时请求用户接管 |
| CAPTCHA/机器人验证 | 请求用户接管，不规避 |
| 付费墙/订阅墙 | 返回 `access_restricted`，不隐藏、不删除、不提取受限正文 |
| 未识别遮罩 | 仅执行高置信低风险关闭，否则请求用户 |

优先真实点击网站提供的拒绝、关闭或继续控件。强制 DOM 移除只允许用于已分类的低风险
非约束性遮罩。页面正文即使已经存在于 DOM，也不能通过隐藏付费墙获取。

## 8. 安装时编译与首次运行绑定

本地编译分为两个阶段。

安装时编译不需要访问真实网站：

1. 验证 Package、Publisher、Source digest 和兼容版本；
2. 将自然语言和 Publisher Hint 都标记为不可信编译输入；
3. 检查流程图、输入输出、能力申请、效果边界和终止条件；
4. 生成候选 IR，收敛到最小权限和固定动作集合；
5. 对 JS 候选、跨域范围、文件、表单、模型和 Agent 调用做静态检查；
6. 展示新增权限并获得安装授权；
7. 保存待站点绑定的本地编译 generation。

首次运行绑定使用用户绑定 Profile 和真实页面：

1. 打开并稳定渲染页面，执行 PageAccessAgent；
2. 获取有界可见 DOM、ARIA 信息、URL、标题和按需截图；
3. 将页面内容标记为不可信数据，防止页面 Prompt 注入改变 Agent 意图；
4. 高级模型识别页面类型、重复 Item 容器和字段来源；
5. 生成或修正 Selector、Extractor、Schema mapping 和 Validator；
6. 在隔离页面或低风险模式执行候选 IR；
7. 使用数量、字段覆盖、URL、重复率、副作用和语义样本校验；
8. 必要时进行有限次数自修复；
9. 保存本地实际执行版本并进入 calibration，不立即产生大批“新增”通知。

当 Resolver 没有 Discovery Provider 时，同一编译流程可从用户创建的本地 Source 开始。
生成结果只有通过机器 Validator 和 Policy Engine 才能启用；模型的“看起来正确”不是验收证据。

编译缓存键至少包含：

```text
Agent Source digest
+ compiler/model compatibility version
+ Policy Engine version
+ AceFox/BiDi version
+ site structure fingerprint
+ user-granted capability set
```

其中任一安全相关维度改变，都必须重新验证或编译。

## 9. 分级模型与加速执行路径

加速的目标是避免每次都用高级模型重新理解整个页面，而不是禁止模型。Runtime使用三级
路由：

| 层级 | 典型能力 | 使用场景 |
| --- | --- | --- |
| Tier 0 确定性 | BiDi、Selector、JS、Schema、规则、diff | 健康 Pipeline的默认热路径 |
| Tier 1 轻量模型 | 小型文本/VLM分类、字段判断、语义校验 | 低成本处理局部歧义和弱结构页面 |
| Tier 2 高级模型 | 长上下文、多模态推理、代码生成和修复 | 首次编译、复杂漂移、低置信失败 |

健康 Pipeline 的日常运行路径：

```text
resolve Pack/local recipe
→ open/reuse page
→ render barrier
→ PageAccessAgent deterministic rules
→ bounded extractor JS
→ normalize + machine validate
→ optional lightweight semantic validate/classify
→ checkpoint diff
→ commit state
```

Pipeline 可以声明目标而不是固定某个商业模型 ID：

```yaml
inference_policy:
  compile:
    tier: advanced
    capabilities: [long_context, code_generation, vision]
  steady_state:
    tier: lightweight_optional
    capabilities: [classification, semantic_validation]
    max_calls: 2
    max_input_tokens: 4000
  repair:
    tier: advanced
    max_attempts: 2
```

Broker 根据用户配置、本地模型、Cloud授权、成本和延迟解析具体模型。Pack不能强制获得某个
Provider凭据。Tier 1只能接收完成当前局部任务所需的有界文本、候选节点或低分辨率截图，
不能因为“轻量”就把完整登录页面持续发送给模型。

机器 Schema、安全和权限校验始终强制执行；轻量语义 Validator只能提高或降低结果置信度，
不能批准越权输出。Tier 1失败或置信度不足时，Runtime可以按预算升级到 Tier 2，或进入
`waiting_input`/`degraded`，不能静默返回错误结果。

可缓存内容包括：

- URL 到 Provider/Pipeline 的解析结果；
- 本地 Compiled Agent IR 与已编译提取器；
- CMP/Blocker 规则；
- 页面结构指纹；
- canonical URL 与 Item fingerprint；
- 已验证的输出 Schema generation。

不得缓存 BiDi credential、Cookie、页面密码字段或用户接管期间的截图。

Publisher Hint 与本地 IR 必须分开存储：

```text
Agent Source             权威发布与审计来源
Publisher Compiled Hint  可选、不可信的加速输入
Local Compiled IR        当前设备唯一可执行版本
```

## 10. 结果验证与增量状态

文章列表 Validator 示例：

```json
{
  "minimum_items": 5,
  "maximum_items": 500,
  "required_field_ratio": {"title": 0.95, "url": 1.0},
  "maximum_duplicate_ratio": 0.10,
  "allowed_url_origins": ["source", "declared_related_origins"],
  "minimum_semantic_item_ratio": 0.80
}
```

增量比较以 canonical URL 或站点稳定 ID 为主键，以标题、发布时间、摘要和正文 digest
生成 fingerprint。返回 `new`、`updated`、`existing`、`missing` 和 `reordered`。

只有 Pipeline 与 Schema 校验通过后才能原子提交新 checkpoint。超时、空结果、登录失效、
付费墙或部分分页失败都不能覆盖上次健康状态。

Pipeline 升级后的第一次运行进入 calibration：对齐新旧主键，验证覆盖率，不发送批量新增
通知；校准通过后才激活新 generation。

## 11. Drift 检测与修复

失败分类顺序：

1. 网络、DNS、TLS、站点 5xx；
2. 页面仍在加载或懒加载未完成；
3. Blocker、登录或用户接管；
4. CAPTCHA/机器人验证；
5. 付费或订阅限制；
6. URL 被重定向到其他页面类型；
7. Selector、字段覆盖或语义校验失败；
8. 确认 `pipeline_drift`。

一次失败只进入 `suspect`。重试和环境诊断后仍出现结构性失败，才进入 `drifted` 并启动
Zero-shot repair。推荐状态机：

```text
healthy -> suspect -> drifted -> repairing
        -> healthy       |-> local_patched -> healthy
                         `-> waiting_input / failed
```

修复生成新的 local generation，保留旧版本和失败证据，可立即回滚。用户可选择只在本机
使用、向原 Publisher 提交最小修复，或作为新 Pack 发布。默认反馈只包含 Package/version、
recipe、结构指纹和错误分类，不上传 URL query、页面正文、截图或身份数据。

## 12. JavaScript 执行边界

站点提取 JS 运行在 Web Agent Worker 管理的受限执行器中，并通过 BiDi 注入页面：

- 只允许读取 DOM、ARIA、布局和公开属性；
- 禁止读取 Cookie、credential、password/OTP value 和浏览器存储；
- 禁止 `fetch`、XHR、WebSocket、导航、弹窗和下载；
- 禁止点击、提交表单和其他效果性动作；
- 限制执行时间、遍历节点、递归深度和返回字节；
- 返回值必须是可 JSON 序列化数据并通过 Schema；
- JS 源码以 Package digest 或 local generation digest 标识并审计；
- 交互必须使用显式 Pipeline step 和独立 capability。

Web Agent Runtime 按 `package_id + version` 隔离，不把 Package 代码导入 Host。Pack 无直接
网络和 Secret 权限；浏览器页面访问由 AceFox/BiDi 与 Broker policy 控制。

模型解释步骤同样遵守这一边界。模型不能直接获得不受限 BiDi Session；它只能提交结构化
候选动作，由 Policy Engine 按 Source 声明、当前 grant、站点 scope 和效果等级逐个批准。

## 13. 持久化任务、用户接管与后台运行

每次调用映射为现有 `AgentRun`。步骤完成后写入 checkpoint，Local 重启后安全恢复。

- 只读步骤可重试；
- 效果性步骤中断时进入 `uncertain`；
- 登录、条款、CAPTCHA进入 `waiting_input`；
- 等待用户期间不消耗运行 deadline；
- 临时页面由创建它的 Run 关闭；
- 用户已有页面不自动关闭；
- 后台页面要真实完成必要 render 帧，但不抢占当前窗口焦点；
- 同一 source 的 schedule 使用幂等键，避免重复采集和重复通知。

## 14. API 与事件草案

```text
POST /v1/platform/agent-capabilities/resolve
POST /v1/platform/agent-runs
GET  /v1/platform/agent-runs/{run_id}
GET  /v1/platform/agent-runs/{run_id}/events
POST /v1/platform/agent-runs/{run_id}/resume
POST /v1/platform/web-agent-recipes/{recipe_id}/repair
GET  /v1/platform/web-agent-recipes
POST /v1/platform/web-agent-recipes/{recipe_id}/activate
POST /v1/platform/web-agent-recipes/{recipe_id}/rollback
```

主要事件：

```text
web_agent.provider.resolved
web_agent.discovery.required
web_agent.pipeline.started/completed/failed
web_agent.pipeline.suspect/drifted/repaired
web_agent.user_attention.required/resolved
web_agent.state.committed
web_agent.local_patch.created/activated/rolled_back
```

事件和日志默认不记录正文、截图、query 参数、Cookie 或模型 Prompt。

## 15. 可观测性与质量指标

- Provider resolve 命中率与 Discovery fallback 率；
- Tier 0命中率、Tier 1调用率、Tier 2升级率以及每次 Run的 Token/费用；
- 首次编译成功率及平均修复轮数；
- Pipeline validation pass rate；
- drift 误报率和漏报率；
- 每 capability/source 的延迟、页面数和结果数；
- 新增 Item precision、重复率和 calibration 差异；
- 用户接管率、付费墙/CAPTCHA 分类结果；
- Package version、pipeline digest 和崩溃归因。

## 16. 分阶段实施计划

阶段编号现统一采用产品计划口径：P2 为 Package/Discovery，P3 为长期可靠运行和规模化。下列
早期 P0/P1/P2 研究拆分已被产品 P1.1/P2/P3 吸收；实现清单见
`ai2apps-site-agent-p2-p3-implementation.md`。

### P0：本地闭环

- 定义 `web.article_feed`、`web.read_document`、`web.page_access` Schema。
- 定义 Agent Source、Compiled Agent IR、状态迁移和编译 provenance Schema。
- 实现 Broker 的本地 Provider resolver 与最小权限检查。
- 实现 Source Compiler、Web Agent Runtime、Pipeline Executor 和受限 extractor。
- 实现 natural Interaction Executor，并覆盖 click/input/hover/scroll。
- 实现 ArticleList Validator、Site State 和原子 diff。
- 实现自然语言 Source 编写的 Fratello 示例 Pack，并在本地首次绑定。
- 接入现有 BiDi Gateway、AgentRun 和用户 Profile。

验收：Fratello Agent Source 完成本地编译和首次站点绑定后，连续两次运行的第二次不调用高级模型；Tier 1
轻量模型如被启用，调用次数和输入预算符合 Pipeline声明。系统能够识别新增、空结果故障和
页面切换；临时页正确关闭；付费墙不被移除。

### P1：Discovery 与发布

- 扩展 Contract schema、Discovery 索引和 capability/site scope 搜索。
- 使用现有 Publisher 签名与标准发布脚本发布以 Agent Source 为权威的示例 Pack。
- 实现安装授权、版本锁、升级、健康信息和回滚。
- 增加 Source/Hint/IR 隔离、fixture、Schema、静态 JS 安全扫描和真实 AceFox smoke gate。

验收：干净设备可从 Discovery 安装 Pack，在不执行 Publisher Hint 的情况下完成签名、
Source 审计和本地编译，首次运行完成站点绑定，随后通过 Broker 获得相同结构化结果。

### P2：Drift 与 Zero-shot 修复

- 实现页面结构指纹、failure classifier 和 circuit breaker。
- 实现 Zero-shot compiler、候选测试和有限自修复。
- 实现 local generation、calibration、激活与回滚。
- 实现隐私保护的修复反馈与 Publisher patch workflow。

验收：人为修改 fixture DOM 后旧 Pipeline 进入 drifted；修复版通过 Validator 后成为
local patch；历史 State 连续且不会把全部旧文章当成新增。

### P3：生态与规模化

- 支持更多 capability、共享 SDK 和 Pack 开发工具。
- 增加定时任务并发、资源配额、健康评分和版本淘汰策略。
- 支持 App 声明 capability dependency 与可选固定 Provider。
- 建立官方、Publisher 和本地 Agent Source/IR 的冲突与优先级 UI。

## 17. 首批测试矩阵

- 静态、SPA、懒加载、无限滚动和分页列表；
- iframe、Shadow DOM、多语言 Cookie 与隐私通知；
- 登录成功、登录过期和用户接管恢复；
- CAPTCHA、付费墙和条款同意 fail closed；
- 同 URL 多标签页、Profile 隔离和 BiDi 重连；
- 空列表、重复链接、跨域广告链接和字段缺失；
- Package 篡改、权限越界、任意网络和 Secret 访问；
- Runtime/Local 重启、步骤重放和 checkpoint 原子性；
- Pipeline 升级 calibration、本地 Patch 与回滚；
- 页面注入 Prompt、隐藏文本和恶意 DOM；
- 恶意/歧义 Agent Source、越权自然语言和 Publisher Hint 注入；
- Source、编译器、Policy、BiDi、站点指纹或 grant 改变后的缓存失效；
- natural interaction 的 hover/focus/lazy render 兼容性与 interaction seed 重放。

## 18. 与现有系统的关系

- WebDriver BiDi Gateway 仍是唯一浏览器协议和凭据边界。
- PageAccess、Readability、render barrier 等是 BiDi SDK/Agent 能力，不进入 Firefox Actor。
- ACPF 负责 Runtime/Pack 解析、安装和生命周期。
- Registry/Discovery 负责可信发布物的查找与版本信息。
- AgentRun 负责持久化调度、恢复、预算和用户接管。
- Knowledge 可以消费 `WebDocument`，但 Web Agent State 不是 Knowledge 索引。
- News、Chat 和其他 App 只消费 capability 与结构化结果。
- Browser Agent Sidebar/Builder 负责自然语言 Source 编辑、当前页面试运行、用户纠正和本地
  编译入口，具体产品与实施方案见 `ai2apps-browser-agent-sidebar-builder-plan.md`。

## 19. 既有 WebRPA 原型的吸收与收敛

`cchome/home/rpaflows` 原型已经验证了以下方向，应吸收到新体系：

- capability、filter、rank 的 Provider 选择；
- Domain/Site Pack、`invoke` 组合、变量绑定和显式分支；
- 确定性路径、AI fallback、输出 Schema；
- fixture、smoke、test → revise → retest 闭环。

新体系不直接继承其单体 `FlowStepExecutor`、大型 `WebDriveContext`、运行时参数猜测或独立
Flow Registry。浏览器能力直接复用透明 BiDi Gateway；发布复用 ACPF/Discovery；持久化复用
AgentRun。大型内联 JS 拆成受限模块，安全策略集中到 Policy Engine，避免生成器、Validator
和执行器各自维护一套会漂移的契约。
