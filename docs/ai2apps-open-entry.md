# AI2Apps Open Entry 技术设计与开发计划

Status: Architecture draft v0.1
Last updated: 2026-08-17
Scope: AI2Apps Local Runtime、Desktop/Web 管理面、Mobile/FRP 公网入口；Cloud
边缘接入的具体实现需与 Cloud 项目协同

Related:

- [AI2Apps Mobile Entry Design](ai2apps-mobile-entry.md)
- [AI2Apps 多用户与节点联邦 AI 网关](ai2apps-multi-user-gateway.md)
- [AI2Apps Cloud Relay — Local Integration](ai2apps-cloud-relay-local-integration-v1.md)
- [AI2Apps Local Capability Sharing](ai2apps-local-capability-sharing-v1.md)

## 1. 目标

AI2Apps App 当前有三个平台内入口：

```text
entry          -> Desktop Shell 中的完整 App
mini_entry     -> Conversation 的 inline/sidebar 小入口
mobile_entry   -> Mobile Shell 中的手机入口
```

Open Entry 增加两个面向非 Local、非平台用户的入口：

```text
desktop_open_entry -> 外部桌面浏览器
mobile_open_entry  -> 外部手机浏览器
```

用户可以把本机运行的小游戏、工具或 AI App 通过受控 FRP URL 分享给朋友；企业可以把
产品咨询、售前问答、预约、信息收集等 App 发布给客户。访客不需要安装 AI2Apps，也不
需要成为该 installation 的成员。

Open Entry 是一个新的发布和安全边界，不是普通 Entry 的响应式别名。它必须同时解决：

- 显式发布与立即撤销；
- Desktop/Mobile 外部 UI 选择；
- 匿名或受口令保护的 Visitor Session；
- 每位访客的数据、AppInstance 和 Agent Session 隔离；
- 独立、最小化的 Open Bridge 与 API；
- FRP 路由、TLS、Host 绑定和公网滥用防护；
- 并发、请求、Token、时间和成本配额；
- 企业品牌、审计、留存和客户会话管理。

## 2. 非目标

第一版不做以下事情：

- 不把 `/admin`、`/apps`、`/mobile` 或 `/v1/platform` 暴露到 Open URL；
- 不允许访客进入 Desktop/Mobile Shell、App Catalog、Account 或设备管理；
- 不把 Open Visitor 创建为 Cloud Account、Organization Member 或 Local Member；
- 不自动公开已安装 App，也不把 `mobile.ready` 等同于 Open Ready；
- 不允许 Open Entry 继承内部 Entry 的 capability grant；
- 不提供任意外部 URL、CDN、localhost 端口或宿主文件访问；
- 不在第一版提供公开应用商店、搜索引擎收录或跨 installation 状态迁移；
- 不将节点联邦、Capability Sharing Grant 或 Remote Mobile Session 当作 Open Session。

## 3. 核心产品模型

### 3.1 两道显式授权门

开放一个 App 必须经过两道独立的门：

1. **Package declaration**：开发者声明该包包含经过 Open 安全约束的 UI 和能力；
2. **Open Publication**：installation 的 Core/Owner 显式创建并启用一次发布。

只有 `open.ready: true` 不会产生公网 URL。安装、升级或启用 App 也不会自动恢复已经
暂停或撤销的 Publication。

```text
App package declares Open Ready
        +
Owner creates an Open Publication
        +
FRP route is active and policy admits request
        =
Visitor can open the URL
```

### 3.2 身份分层

Open Visitor 不是现有 `RequestPrincipal` 中的成员用户。运行时应使用独立主体：

```text
OpenPrincipal
├── publication_id
├── publication_revision
├── visitor_id            随机、伪匿名，不由客户端指定
├── visitor_session_id
├── installation_id       服务节点，由服务端绑定
├── billing_account_id    发布者承担，来自 installation
├── access_mode           unlisted | passcode | authenticated
└── policy_epoch          撤销和策略更新版本
```

Open API 不接受客户端自报的 `visitor_id`、`installation_id`、计费账户、capability 或
AppInstance ID。所有这些值都从 Publication 与 HttpOnly Session 解析。

### 3.3 个人版与企业版共用底层对象

| 能力 | 个人分享 | 企业客户交互 |
| --- | --- | --- |
| 默认可见性 | `unlisted` 高熵链接 | `unlisted` 或受控域名 |
| 访问控制 | 可选访问码、有效期 | 访问码、外部身份提供方可扩展 |
| 会话 | 每位访客隔离 | 每位客户隔离，可配置留存 |
| 品牌 | 基础标题、图标 | Logo、颜色、自定义域名、法律链接 |
| 配额 | 小并发、请求/Token 上限 | Publication 级预算、速率和并发策略 |
| 运营 | 基础访问计数 | 会话状态、转人工、线索导出、审计 |

底层不硬编码“小游戏”和“客服”两类 App；二者只是不同 Publication policy preset。

## 4. App Manifest 契约

### 4.1 推荐格式

```yaml
schema: ai2apps.app/v1
id: com.example.product-guide
name: Product Guide

entry:
  kind: sandbox
  resource: ui/entry.html

mobile:
  ready: true

mobile_entry:
  kind: sandbox
  resource: ui/mobile.html

open:
  ready: true
  surfaces:
    - desktop
    - mobile
  session_mode: per_visitor
  requested_capabilities:
    - app.agent.invoke
  data_policy:
    accepts_uploads: false
    contains_user_content: true

desktop_open_entry:
  kind: sandbox
  resource: ui/open-desktop.html

mobile_open_entry:
  kind: sandbox
  resource: ui/open-mobile.html
```

`open` 声明包的技术能力和安全预期；Publication 决定一次实际发布的 URL、有效期、
访问模式、配额、品牌和最终允许能力。Manifest 不应携带公网域名、FRP credential、
访问码或生产配额。

### 4.2 Entry 选择规则

Open Entry 与内部 Entry 不互相降级：

```text
desktop request -> desktop_open_entry
mobile request  -> mobile_open_entry
```

如果 App 希望同一套 UI 同时服务桌面和手机，应显式声明：

```yaml
open:
  ready: true
  surfaces: [desktop, mobile]
  mobile_fallback: desktop_open_entry

desktop_open_entry:
  kind: sandbox
  resource: ui/open-responsive.html
```

规则如下：

1. Desktop 不降级到 `entry`；
2. Mobile 不降级到 `mobile_entry`、`mini_entry` 或 `entry`；
3. Mobile 只有在 `mobile_fallback: desktop_open_entry` 时才能复用 Desktop Open UI；
4. Publication 只能启用 manifest `open.surfaces` 声明的 surface；
5. 声明了但无效的高优先级资源必须使包校验失败，不能在运行时静默换 UI；
6. surface 选择只影响 UI，不改变身份、权限或配额。

这样可以避免开发者只考虑内部登录用户，却意外把内部管理 UI 发布给匿名访客。

### 4.3 Renderer 与资源约束

MVP 只允许：

```text
desktop_open_entry.kind = sandbox
mobile_open_entry.kind  = sandbox
```

后续可在 Open Shell 具备等价 CSP 和测试覆盖后增加 `schema` 与 `safe-html`。第三方 Open
Entry 永远不允许 `host` renderer。

Open package 必须满足：

- HTML、CSS、JavaScript、字体、图片和其他依赖全部进入 package index；
- 只使用包内相对资源或 Open Gateway 明确允许的静态资源；
- 禁止 `/admin/*`、`/apps/*`、`/mobile/*`、任意 `/v1/platform/*`、localhost、任意
  Local Service 端口和外部 CDN；
- 禁止 inline script/style、inline event handler、`eval` 和动态代码生成；
- CSP 默认 `default-src 'none'`，按 renderer 最小化开放 script/style/img/font/connect；
- iframe 保持 sandbox，不授予 `allow-same-origin`，除非将来完成独立资源 Origin 隔离；
- 所有资源继续执行 package digest、文件大小和 MIME 校验；
- 上传能力必须在 manifest 和 Publication 中同时显式开启，并经过类型、大小、数量、
  病毒/内容策略检查。

### 4.4 包校验错误

建议新增稳定错误码：

```text
invalid_open_declaration
open_entry_missing
invalid_desktop_open_entry
invalid_mobile_open_entry
open_entry_resource_missing
open_entry_renderer_denied
open_surface_missing
open_mobile_fallback_invalid
open_capability_not_declared
```

## 5. Open Publication

### 5.1 Publication 不是 AppDefinition 的布尔字段

一次 Publication 固定到一个可复现的 App release：

```text
OpenPublication
├── id
├── installation_id
├── owner_user_id / organization_id
├── app_definition_id
├── package_id / package_version / effective_digest
├── slug
├── status                 draft | active | paused | revoked | expired
├── policy_epoch
├── enabled_surfaces
├── access_policy
├── session_policy
├── quota_policy
├── capability_policy
├── branding
├── created_at / updated_at / expires_at
└── active_revision
```

发布必须固定 `effective_digest`，不能在包升级后无审查地指向新代码。升级流程创建新的
Publication revision，完成校验后原子切换；管理员可以回滚到仍受信任的上一 revision。

### 5.2 状态语义

- `draft`：可预览，不存在公网数据面；
- `active`：FRP 路由和 Local admission 均可接受访客；
- `paused`：临时停止，可由 Owner 恢复；
- `revoked`：永久撤销当前分享身份，旧 URL 和 Session 均失效；
- `expired`：达到截止时间后自动失效，可复制策略创建新 Publication。

`pause`、`revoke`、包被禁用、trust 失效、额度耗尽和 installation 解绑都必须在新的
Open 请求到达运行时前 fail closed。已建立的 streaming 请求应在有限窗口内取消。

### 5.3 Access policy

MVP 支持：

```text
unlisted  -> 依赖至少 128 bit 熵的不可枚举 slug
passcode  -> 高熵 slug + 访问码，服务端只保存慢哈希
```

`public`（可发现和可索引）与外部身份提供方登录推迟到企业阶段。URL fragment、query
parameter 和浏览器 localStorage 都不能保存长期 FRP 或管理 credential。

访问码连续失败需要 Publication + IP 前缀的组合速率限制；审计只保存截断或 keyed hash
后的网络标识，不长期保存原始 IP，除非企业数据政策明确要求且向访客披露。

## 6. Visitor 与实例隔离

### 6.1 Open Visitor Session

首次访问通过 Publication admission 后，Local 创建独立 Session，并返回：

- `Secure`、`HttpOnly`、`SameSite=Lax/Strict` 的不透明 Cookie；
- 仅绑定一个 Publication、policy epoch 和浏览器 scope；
- 绝对过期时间与空闲过期时间；
- 服务端保存 token digest，不保存明文 token；
- passcode 验证成功只提升当前 Visitor Session，不产生平台登录态。

Cookie path 应限制在该 Open Publication 的路径。撤销 Publication 或增加 policy epoch
会使全部旧 Visitor Session 立即失效。

### 6.2 AppInstance 策略

默认且 MVP 唯一支持：

```text
session_mode: per_visitor
```

每位访客获得独立 Open AppInstance、Home Session、Agent Session、Workspace namespace
和短期状态。Open AppInstance 必须带 `publication_id` 和 `visitor_session_id`，不能通过
内部 Catalog、Shell route 或普通成员 API 枚举。

明确禁止：

- 把发布者正在使用的内部 AppInstance 直接交给访客；
- 多位陌生访客默认共享一个可写 AppInstance；
- 访客用猜测的 ID 聚焦或读取另一个 Visitor 的实例；
- Open Session 绑定到内部 ConversationSession；
- Publication 撤销后继续恢复旧 Open AppInstance。

未来如需多人游戏或共享白板，应引入显式的 `shared_room` 领域对象与邀请机制，不能把
`per_visitor` 的隔离检查关闭来实现。

### 6.3 生命周期与清理

Open AppInstance 状态建议为：

```text
active -> idle -> expired -> purged
```

Visitor 断开只释放并发槽，不立即删除状态。清理由 Publication retention policy 控制。
个人版默认短留存；企业版可配置留存，但必须区分：

- 会话正文和上传内容；
- 运营元数据；
- 安全审计；
- 汇总用量。

删除 Visitor Session 时，应级联取消未完成 Run、关闭临时 Agent Session、删除临时文件，
但审计和计费 ledger 按各自政策保留。

## 7. Open Bridge 与能力模型

### 7.1 独立 Bridge

Open Entry 不加载现有 Shell Bridge 或 Mobile Bridge。建议只暴露版本化接口：

```javascript
window.ai2appsOpen = {
  ready(),
  getContext(),
  navigate(path),
  invoke(action, input),
  cancel(requestId),
  downloadArtifact(artifactToken),
  close()
}
```

MVP 中 `invoke` 只能调用 App manifest 声明、Publication 批准、运行时策略允许的命名
action。浏览器不能提交底层模型 ID、Tool 名、Service URL、Agent ID、capability 名称或
计费主体来绕过 action policy。

Open Bridge 明确不提供：

- `openEntry`、`mountMiniEntry`、Dock、Launcher 或 Catalog；
- `requestCapability` 或由访客批准敏感能力；
- 任意 App/实例/Session 导航；
- 任意 Tool、Service、Agent 或模型调用；
- 本地文件选择、Terminal、Secrets、Browser control 和设备管理；
- 未经一次性下载 token 授权的 Artifact 路径。

### 7.2 三层能力交集

有效能力必须是三者交集：

```text
manifest requested capabilities
  INTERSECT Publication approved capabilities
  INTERSECT runtime Open allowlist
```

Open capability grant 与内部 App capability grant 使用不同 audience。即使同一 App 的
Owner 已在 Desktop 中批准某项能力，Open Visitor 也不能继承。

MVP 推荐只允许无宿主副作用的窄 action：

- 使用明确绑定的本地模型或允许计费的 Cloud 模型；
- 创建该 Visitor 私有的 Agent Run；
- 读写该 Visitor 的 App state；
- 生成并下载该 Visitor 自己的 Artifact；
- 调用专门标记为 Open-safe、输入输出有界的 App Service action。

任何需要人工批准的交互在 Open 面默认拒绝。企业“转人工”应创建显式运营事件，而不是
让访客获得审批能力。

## 8. 公网路由与 FRP 边界

### 8.1 路由拓扑

```text
Visitor Browser
  -> HTTPS public origin / custom domain
  -> Cloud edge admission and coarse rate limit
  -> authenticated FRP tunnel bound to one installation
  -> Local Open Gateway
  -> Publication admission
  -> Open Shell / resource / action API
  -> isolated Open AppInstance
```

FRP 是传输边界，不是 App authorization。Cloud edge 和 Local 必须同时验证 Publication
route binding；Cloud route 存在不能替代 Local 的 status、epoch、digest、quota 和 Session
检查。

### 8.2 独立 allowlist

公网 tunnel 只转发：

```text
GET/HEAD  /o/{slug}
GET       /o/{slug}/assets/*
POST      /v1/open/{slug}/sessions
POST      /v1/open/{slug}/passcode/verify
GET       /v1/open/{slug}/bootstrap
POST      /v1/open/{slug}/actions/{action}
DELETE    /v1/open/{slug}/session
GET       /v1/open/{slug}/artifacts/{one_time_token}
```

具体路径可在实现时调整，但 Open listener/router 必须采用正向 allowlist。不得依赖主应用
router 注册顺序或“未在 UI 中显示”来阻止 `/admin`、`/mobile`、`/apps`、模型 API、MCP
或管理 API 被公网访问。

Open Gateway 必须验证：

- 请求 Host/SNI 与 Publication route 或自定义域名绑定一致；
- Cloud-to-Local tunnel assertion 的 installation、route、epoch、audience 和短时有效期；
- 不接受任意 `X-Forwarded-*` 作为身份或安全协议判断；
- production 只生成 HTTPS URL；
- response 不泄漏 Local hostname、端口、路径、API key 或内部实体 ID；
- disconnect 能取消 streaming 推理并释放 Publication 并发槽。

### 8.3 Desktop/Mobile surface 选择

初始 HTML 是很小的 Open Shell。它根据 Client Hints/UA 与 viewport 给出默认 surface，
浏览器可在 UI 中切换 Desktop/Mobile 视图。Bootstrap 请求携带 surface，但服务端只把它
当作展示偏好，并重新按 manifest 与 Publication 校验。

设备判断错误最多导致布局不理想，不能改变权限、数据域、配额或可用 action。

## 9. 配额、计费与滥用防护

### 9.1 Admission 顺序

每次 action 在进入模型、Agent 或 Service 前按顺序执行：

```text
Publication active/epoch/digest
-> Visitor Session
-> Origin/CSRF
-> action allowlist and schema
-> per-IP/passcode abuse limit
-> per-session rate and budget
-> Publication concurrency and budget
-> installation/account entitlement
-> reserve usage
-> execute
-> settle usage and audit
```

预算预留必须原子化，不能让并发请求越过上限。流式请求从 admission 到结束、取消或断开
都占用并发槽。

### 9.2 配额维度

Publication policy 至少支持：

```text
expires_at
max_active_visitors
max_concurrent_requests
requests_per_minute
requests_per_session
input_tokens_per_session
output_tokens_per_session
tokens_per_day
max_run_seconds
max_upload_bytes
```

Cloud 计费模型由 installation 的权威 `billing_account_id` 承担。访客永远不能改变计费
主体或选择 Publication 未允许的模型。Local 模型即使不扣 Cloud 点数，也必须执行并发、
Token 和运行时间限制，防止公开 URL 耗尽本机资源。

超限返回稳定的非敏感错误，不应暴露发布者余额、订阅等级或本机负载细节。

### 9.3 安全基线

- 管理操作必须由 Core/Owner/Admin 完成，高风险发布和自定义域名建议要求 reauth；
- Open 写请求使用 Session-bound CSRF token 并校验 Origin；
- Bridge `postMessage` 使用精确 Origin、mount token、Visitor Session 和 request ID；
- 不使用 `postMessage(..., '*')`；
- 对 action JSON Schema、深度、字段数、字符串长度和总 body 大小设上限；
- 上传文件在解析前执行 magic/MIME/大小校验，并放入隔离目录；
- 错误响应、日志和审计不得包含 passcode、Cookie、FRP credential、prompt 正文或 Secret；
- Publication revoke、App disable、package trust 失败和 tunnel revoke 都必须 fail closed；
- 所有 Open renderer 通过专门的 CSP、iframe escape、IDOR、CSRF、SSRF 和断连测试。

## 10. API 草案

### 10.1 管理面

管理 API 走现有平台身份与角色检查，不通过 Open Gateway：

```text
GET    /v1/platform/open/candidates
GET    /v1/platform/open/publications
POST   /v1/platform/open/publications
GET    /v1/platform/open/publications/{publicationId}
PATCH  /v1/platform/open/publications/{publicationId}
POST   /v1/platform/open/publications/{publicationId}/activate
POST   /v1/platform/open/publications/{publicationId}/pause
POST   /v1/platform/open/publications/{publicationId}/rotate-url
POST   /v1/platform/open/publications/{publicationId}/revoke
POST   /v1/platform/open/publications/{publicationId}/revisions
POST   /v1/platform/open/publications/{publicationId}/rollback
GET    /v1/platform/open/publications/{publicationId}/sessions
DELETE /v1/platform/open/publications/{publicationId}/sessions/{sessionId}
GET    /v1/platform/open/publications/{publicationId}/usage
GET    /v1/platform/open/publications/{publicationId}/audit
```

写操作使用 expected revision，避免两个管理页面互相覆盖。`rotate-url` 使旧 slug、旧 Visitor
Session 和未完成 passcode challenge 失效。

### 10.2 数据面响应

Bootstrap 只返回渲染和当前 Visitor 所需的最小信息：

```json
{
  "publication": {
    "display_name": "Product Guide",
    "surface": "mobile",
    "branding": {"theme": "system"}
  },
  "entry": {
    "renderer": "sandbox",
    "content_url": "/o/3P.../assets/ui/open-mobile.html",
    "effective_digest": "sha256:..."
  },
  "session": {
    "expires_at": "2026-08-18T12:00:00Z",
    "csrf_token": "..."
  },
  "bridge": {
    "version": "open.v1",
    "actions": ["ask_product"]
  }
}
```

不得返回内部 `app_definition_id`、普通 AppInstance ID、owner、billing account、Local API
地址、模型凭证或未授权 action。

## 11. 持久化模型

建议新增独立表，不扩展现有 Mobile mount check constraint 来冒充 Open：

```text
open_publications
open_publication_revisions
open_visitor_sessions
open_app_sessions
open_usage_ledger
open_audit_events
```

关键约束：

- `slug` 全局/设备路由范围内唯一，保存 digest 或允许安全索引的不可逆表示；
- Publication revision 固定 package version 与 effective digest；
- Visitor token 与 passcode 只保存 digest；
- `open_app_sessions` 唯一绑定 publication + visitor session + instance；
- usage reservation 与 settlement 具有幂等 request ID；
- revoke 不删除审计，但使 policy epoch 单调增加；
- 用户内容和审计元数据分表、分 retention policy；
- 普通 App 查询默认排除 Open AppInstance，只有 Open manager 和授权运营接口可访问。

建议的事件名称：

```text
app.open.publication.created
app.open.publication.activated
app.open.publication.paused
app.open.publication.revoked
app.open.visitor.started
app.open.visitor.expired
app.open.entry.mounted
app.open.action.started
app.open.action.completed
app.open.action.denied
app.open.quota.exhausted
app.open.entry.unmounted
```

默认审计只保存 Publication、Visitor pseudonym、action、状态、用量、耗时和错误码；不复制
prompt、模型输出、上传正文或 Artifact 内容。企业内容留存是单独且可见的策略。

## 12. 与现有实现的关系

当前实现可以复用：

- AppDefinition、package index、digest、签名、trust 和 renderer 基础；
- AppInstance、Session、AgentRun、Artifact 的生命周期能力；
- Mobile Gateway 的 FRP/handoff 经验、Host 校验和受限公网 router 模式；
- 多用户设计中的 installation、organization、billing owner 与 request ledger；
- Local Sharing 的 grant、并发、原子请求预算、撤销和元数据审计模式；
- Shell 的 iframe pool、mount token、lifecycle event 思路。

不能直接复用其权限语义：

- `resolve_mobile_entry()` 只能解析平台 Mobile UI，不能解析 Open Entry；
- `/v1/mobile/*` 需要成员/Remote Mobile Session，Open Visitor 不属于该身份域；
- `app_mounts` 当前 placement/entry_source 只覆盖内部 Entry，Open 应有独立 mount/session；
- Shell Bridge 和 Mobile Bridge 的能力面过宽；
- Capability Share Grant 面向受信客户端 API，不是浏览器 Visitor App；
- Node Federation 明确不开放 App 或上游 Session，不能拿来承载 Open Entry。

## 13. 开发阶段

### O0 — 契约与威胁模型

- 固定 manifest schema、Publication、OpenPrincipal、Open Bridge v1 和错误码；
- 完成 STRIDE/滥用案例评审，特别覆盖公网推理成本、IDOR、Bridge escape 和撤销；
- 固定 Local/Cloud/FRP 各自负责的 admission 检查；
- 建立 Desktop/Mobile Open 示例 App 和恶意测试包。

验收：设计评审确认 Open Visitor 不能进入任何内部 route、身份或实例。

### O1 — Package 与本地预览

- archive 校验 `open`、`desktop_open_entry`、`mobile_open_entry`；
- Coder/App Studio 生成 Open authoring guide；
- 增加 Desktop/Mobile Open Preview，使用真实 Open CSP 和 Bridge mock；
- 测试资源索引、renderer、fallback 和 capability declaration。

验收：无 Open 声明的旧包保持兼容；无效 Open 声明 fail closed。

### O2 — Local Publication MVP

- 新增 schema、repository、manager、管理 API 和 Open 管理 UI；
- 支持 `unlisted`、expiry、pause、rotate、revoke；
- 建立 Visitor Session、per-visitor AppInstance、Open Shell 与 Open Bridge；
- 增加请求/并发/Token/运行时间配额和 metadata audit；
- 先在 loopback 测试入口运行，不启用公网路由。

验收：两个浏览器访客完全隔离；撤销后旧 URL、Cookie、Run 和下载 token 均失效。

### O3 — FRP 分享 MVP

- Cloud 创建 publication route binding 与短时 tunnel assertion；
- Local Open Gateway 只注册 allowlist routes；
- 生成 HTTPS unlisted URL 和 QR；
- Cloud edge 与 Local 双层速率/并发限制；
- 验证断连取消、tunnel revoke、Host mismatch 和 Local 离线错误页。

验收：真实外网桌面和手机可以运行示例 App，无法探测内部 API，额度不可并发超发。

### O4 — 个人版完善

- passcode、分享有效期 preset、基础访问统计；
- 响应式单 Entry 显式 fallback；
- 访客状态清理与发布者可见的安全诊断；
- 游戏/工具场景的弱网恢复和资源缓存。

### O5 — 企业客户交互

- 自定义域名、品牌、法律/隐私链接；
- Publication 级预算、部门权限和运营角色；
- 客户会话检索、明确的内容留存、导出和删除；
- 转人工事件与外部 CRM connector，但不扩大 Visitor Bridge；
- 可选外部身份提供方、验证码和企业 WAF/CAPTCHA；
- 灰度 revision、流量切分和快速回滚。

## 14. 测试与发布门禁

### 14.1 必测矩阵

| 维度 | 最低覆盖 |
| --- | --- |
| Surface | Desktop、Mobile、显式 responsive fallback、缺失 entry |
| Access | unlisted、passcode、过期、pause、revoke、rotate |
| Isolation | 双访客、双 Publication、内部成员与 Visitor、ID 猜测 |
| Renderer | sandbox CSP、资源 digest/MIME、iframe escape、外部 URL |
| Bridge | action allowlist、伪造 postMessage、重放、超时、cancel |
| Quota | 并发竞争、流式断连、Token 上限、reservation rollback |
| FRP | Host mismatch、旧 epoch、tunnel revoke、Local offline |
| Lifecycle | package disable、升级、revision 切换、回滚、清理 |
| Privacy | 日志脱敏、Cookie scope、audit 无正文、删除流程 |

### 14.2 MVP 发布门禁

在启用真实公网分享前必须满足：

1. Open listener 无法访问 `/admin`、`/apps`、`/mobile`、`/v1/platform`、模型和 MCP
   通用端点；
2. Open Visitor 无法读取或聚焦内部/其他访客 AppInstance、Session、Artifact；
3. 无 manifest 声明、无 Publication、非 active、epoch/digest 不匹配全部 fail closed；
4. 并发 admission 下请求、Token 和并发预算不超发；
5. revoke/rotate 在确定窗口内终止旧 Session 和运行中请求；
6. CSP、CSRF、Origin、Bridge token、package resource integrity 测试全部通过；
7. 日志、错误、analytics 和 audit 不包含 credential、passcode、Cookie 或默认正文；
8. 真实 FRP 桌面/手机测试记录 Cloud/Local commit、URL 类型、延迟、TPS、内存、并发和
   撤销时间。

## 15. 已确定决策与待确认项

已确定：

1. Open Entry 面向非 Local、非平台 Visitor；
2. 提供 Desktop Open Entry 和 Mobile Open Entry；
3. Open Ready 与实际 Publication 分离，默认不公开；
4. Open Entry 不降级到任何内部 Entry；
5. Visitor 默认按人隔离 AppInstance/Session；
6. FRP 只负责传输，Local 保留最终 admission；
7. 使用独立 Open Bridge、OpenPrincipal、Open Gateway 和 capability audience；
8. 发布者/installation 承担资源和模型费用；
9. 个人分享与企业客户交互共用底层 Publication 模型。

实现前仍需产品确认：

1. 个人版默认分享有效期与并发/Token 配额；
2. Open App 是否允许 Cloud 计费模型，还是 MVP 仅允许本地模型；
3. 企业运营人员能否读取客户会话正文，以及默认留存多久；
4. 自定义域名和外部身份提供方由 Cloud 还是企业自有边缘终止；
5. Publication URL 是否需要 Cloud 账户持续在线校验，还是允许有限离线宽限；
6. 第一版是否只交付 `unlisted`，将 passcode 延后到 O4。
