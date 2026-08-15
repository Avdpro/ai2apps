# AI2Apps 多用户 AI 网关设计与初步开发计划

Status: Product direction agreed; architecture draft v0.1
Last updated: 2026-08-15
Related: [AI2Apps Platform Architecture](ai2apps-platform-architecture.md),
[AI2Apps Mobile Entry Design](ai2apps-mobile-entry.md),
[AI2Apps Cloud SSE Bridge](ai2apps-cloud-sse-bridge.md)

## 1. 目标

AI2Apps Local 不再只被视为单用户 Mac 上的模型服务，而应能作为常在线的
家庭或小企业 AI 网关。一个 Local installation 绑定一个核心账户，由核心账户拥有
设备、承担统一计费并管理敏感能力；其他经过授权的成员可以同时使用 Chat 等开放
App，并在当前设备上拥有各自独立的 AppInstance、Session、消息、附件和运行状态。

该设计复用 `coder.ai2apps.com` 已有的账户、登录、权益、点数和 Remote Access
体系，不在 Local 内建立另一套用户名、密码或账户恢复系统。

核心产品原则是：

> Cloud 管理身份、组织关系、设备归属、授权版本和计费；Local 运行模型、App、
> Agent 与 Service，并保存当前设备上的私有 Session 和工作数据。

第一版不提供跨设备 Session 同步。同一 Cloud 账户在不同 AI2Apps 设备上登录时，
分别拥有各设备本地的 Session 集合。

## 2. 产品模型

### 2.1 家庭与小企业使用同一底层模型

底层采用通用的 Organization 概念，家庭和企业只是两种策略预设：

```text
Organization
├── type: household | business
├── billing owner
├── memberships
└── installations
    └── local AppInstances / Sessions / data
```

| 概念 | 家庭模式 | 小企业模式 |
| --- | --- | --- |
| Organization | 家庭 | 企业或团队 |
| Billing owner | 核心账户 | 企业所有者或结算账户 |
| Member | 家庭成员 | 员工或访客 |
| Installation | 家庭 AI 网关 | 企业 AI 节点 |
| 管理权限 | 核心账户 | Owner/Admin |
| 使用空间 | 每成员本机空间 | 每员工本机空间 |

界面可以使用“家庭”和“企业”等友好名称，但数据库、API 和策略层不应把通用对象
硬编码为 `family` 或 `core_user_only`，以免后续企业模式需要重写。

### 2.2 两类身份必须分离

每个授权请求同时具有实际使用身份和计费/设备归属身份：

```text
RequestPrincipal
├── actor_user_id       当前实际操作的人
├── organization_id     当前家庭或企业
├── billing_account_id  统一承担费用的主体
├── installation_id     当前 Local installation
├── role                当前成员角色
└── membership_epoch    授权版本
```

- `actor_user_id` 用于 App 可见性、Session 所有权、数据隔离、配额和审计；
- `billing_account_id` 用于模型调用扣点、订阅和权益；
- `installation_id` 约束数据与凭证只属于当前设备；
- `role` 与 capability policy 决定可进入哪些 App、可调用哪些 Tool；
- `membership_epoch` 用于成员移除、降权和设备撤销后的快速失效。

不得使用一个含义模糊的 `user_id` 同时承担操作者、设备所有者和计费账户三种职责。

## 3. 已确认的产品决策

1. 每个 Local installation 必须绑定一个核心账户后才能启用完整产品能力。
2. 所有经该 Local 发起的计费模型调用统一扣核心账户或组织结算账户的点数。
3. Cloud 必须根据权威的设备绑定决定扣费主体，不能信任 Local 上传的任意账户 ID。
4. 核心账户拥有设备设置、成员管理、结算和敏感 App 权限。
5. 家庭成员可以使用 Chat 等开放 App，但不能默认访问 Coder、Agent Manager、
   Terminal、Secrets、Models 或设备管理。
6. 每个成员在当前设备上拥有独立的用户级 AppInstance 和 Session。
7. Session、消息、附件、Workspace 和个性化状态第一版只保存在当前设备。
8. 同一账户在不同设备上的 Session 暂不同步、合并或互相发现。
9. 模型、只读权重、MoE expert bank、kernel 和调度器可以跨成员共享；由用户内容
   派生的 KV/prefix cache、取消状态和 Session continuation 必须隔离。
10. 核心账户可以查看设备用量和安全事件，但默认不因此获得读取其他成员聊天正文
    的权限。儿童监护或企业留存属于单独、显式的策略。

## 4. 当前实现基础与缺口

### 4.1 可以直接复用的能力

当前代码已经具备：

- `coder.ai2apps.com` Cloud 注册、登录、邮箱验证、密码恢复、`/auth/me`、权益和点数；
- 私有持久化 Cloud Session 和本地 Cloud API facade；
- Remote device 注册、配对、credential rotation、revoke 和 usage；
- Cloud handoff、Ed25519 JWT/JWKS 校验、`device_id`、`sub`、`access_epoch`；
- 15 分钟、HttpOnly、restart-invalidated 的本地 Remote Mobile Session；
- SQLite App、AppInstance、Session、Message、Event、AgentRun、Workspace、Artifact、
  Service、Tool 和 capability 基础设施；
- App 的 `system`、`user`、`session` singleton scope；
- oMLX EnginePool、batched engine、请求调度和共享模型运行时；
- Mobile Shell、Mobile Ready App、远程设备入口和受限 Mobile API。

因此本项目不需要重建账户系统、Session 数据库、模型并发引擎或 Remote 身份协议。

### 4.2 当前单用户假设

以下假设阻止了真正的多成员使用：

1. `PlatformRuntime` 只创建一个全局 `AI2AppsCloudClient`，其 Cookie 表示整台设备
   当前唯一的 Cloud 登录态；第二个用户登录会改变同一个会话。
2. Remote handoff 已经把 Cloud JWT 的 `sub` 保存为 `owner_user_id`，但多数 Mobile
   路由验证后丢弃该身份，调用的仍是全局 Shell/Chat singleton。
3. Chat singleton key 当前固定为 `ai2apps.general-chat:user:local`。
4. `app_instances`、Projects、Coder threads 和部分本地资源尚无一致的用户所有权。
5. `/v1/platform/*` 主要由 installation API key 保护，认证结果不是带角色和
   membership epoch 的用户 principal。
6. App Catalog、Repository 按 ID 读取、Workspace、Document、Agent 和 Tool
   invocation 还没有统一的 actor ownership 检查。
7. Cloud 调用尚未明确区分“设备统一计费凭证”和“成员本地登录 Session”。

### 4.3 不应采用的方案

- 不在 Local 保存成员密码或实现本地密码重置；
- 不为每个成员启动一份完整模型；
- 不让成员登录覆盖设备核心计费凭证；
- 不仅靠前端隐藏敏感 App；
- 不信任请求体或客户端 header 自报 `actor_user_id`、角色或计费账户；
- 不默认将 Chat 正文、附件或 Workspace 上传 Cloud；
- 不在第一版引入跨设备 Session 同步和冲突合并。

## 5. 身份、绑定与登录流程

### 5.1 Installation 首次绑定

```text
Local setup
  -> 核心账户在 coder.ai2apps.com 登录并完成 reauth
  -> Cloud 创建或绑定 installation/device
  -> Cloud 返回设备身份和可轮换凭证
  -> Local SecretBackend 保存凭证
  -> Local 保存 core/organization 的非秘密投影
```

一台 installation 第一版只绑定一个 Organization 和一个 billing owner。更换核心
账户是独立的高风险操作，必须经过 Cloud reauth 和显式转移流程，不能由普通成员登录
或 Cloud Cookie 更新隐式触发。

转移流程必须先定义以下资源的归属策略：成员、Session、Secrets、Projects、安装包、
审计记录和未结算请求。第一阶段可以不实现转移，只提供解绑并清空本地用户数据的
受控流程。

### 5.2 成员授权

成员关系由 Cloud 维护：

```text
organization_memberships
├── organization_id
├── user_id
├── role
├── status
├── membership_epoch
└── joined_at / revoked_at
```

家庭核心账户或企业 Owner/Admin 在 Cloud 管理成员。Local 只缓存最小授权投影，且
不能在本地把普通成员提升为 Owner。

### 5.3 LAN 与 Remote 共用 handoff

现有 Remote Mobile handoff 应泛化为统一的 Cloud-to-Local 登录流程：

```text
Browser -> coder.ai2apps.com login/invite acceptance
        -> one-time handoff bound to installation/device
Local   -> exchange handoff with Cloud
        -> verify signed identity and membership
        -> create local HttpOnly user session
```

LAN 桌面、LAN Mobile 和远程 Mobile 使用同一个身份语义，仅入口 URL、Cookie Secure
要求和网络通道不同。Cloud token 必须约束 issuer、audience、installation/device、
`sub`、role、membership epoch、iat、exp 和 jti。

### 5.4 Local Session

本地浏览器只持有不透明 Cookie；Local 仅保存 token digest：

```text
local_login_sessions
├── token_digest
├── installation_id
├── actor_user_id
├── organization_id
├── role
├── membership_epoch
├── created_at
├── expires_at
└── last_access_check_at
```

Local 应定期向 Cloud 检查设备和成员 epoch。成员被移除、设备被 revoke 或角色降权后，
旧 Session 必须在确定的短窗口内失效。Cloud 暂时不可达时可允许已有 Session 在有限
离线宽限期内使用纯本地模型和数据，但不得使用需要在线权益或扣点的 Cloud 能力。

## 6. 统一计费模型

### 6.1 计费主体固定为 installation owner

所有通过该设备产生的计费推理请求采用：

```text
actor            = 当前成员
charged account  = installation 的 billing_account_id
device           = installation/device
```

Cloud 通过设备凭证解析权威的 `billing_account_id`。Local 可以提交 actor attribution，
但 Cloud 只能接受由设备凭证或受签名委托保护的 actor，不能据此改变扣费主体。

Cloud usage ledger 至少记录：

```text
request_id
installation_id / device_id
billing_account_id
actor_user_id
model
input/output/cache usage
points_reserved / charged / released
created_at
```

核心账户可以查看设备总用量和按成员聚合。普通成员默认只查看自己的用量，不查看组织
余额、其他成员明细或 Provider 凭证。

### 6.2 分离设备凭证与成员 Session

当前全局 Cloud Cookie 需要拆分语义：

- **Device billing credential**：安装级、保存在 SecretBackend、可轮换、绑定核心
  账户，用于 Cloud AI、目录、组织权益及设备控制面；
- **Member local session**：用户级、短期、只用于证明当前 actor 和本地访问权限；
- **Owner reauth grant**：极短期，仅用于转移设备、管理成员、查看敏感结算或其他
  高风险操作。

成员的 Cloud 登录不得覆盖 Device billing credential，也不得把成员自己的点数账户
变成该设备的临时扣费主体。

## 7. App、Agent 与 Capability 权限

### 7.1 用 capability 表达权限

App 不应仅硬编码 `core_only`，而应声明访问所需 capability：

```yaml
access:
  capabilities:
    - app.coder.use
```

第一版内置策略可映射为：

| App/能力 | Household core | Household member | Business owner/admin | Business developer/member |
| --- | --- | --- | --- | --- |
| Chat | Allow | Allow | Allow | Allow |
| 普通家庭/业务 App | Allow | 按 App | Allow | 按 App |
| Dashboard/Account | Allow | Deny | Allow | Deny/Read-only |
| Models/Downloads | Allow | Deny | Allow | Read-only/按策略 |
| Coder | Allow | Deny | Allow | Developer 可用 |
| Agent Manager | Allow | Deny | Allow | 按策略 |
| Terminal | Allow | Deny | Allow | Developer 可用 |
| Secrets/Trust Center | Allow | Deny | Allow | 仅授权项 |
| Remote/成员/结算管理 | Allow | Deny | Owner/Admin | Deny |

家庭第一版可以只暴露 `core` 和 `member` 两个角色；底层 capability contract 仍保持
通用，为企业的 `owner`、`admin`、`developer`、`member`、`guest` 预留空间。

### 7.2 Agent Manager 与 Agent Runtime 分离

“成员不能访问 Agent”应解释为：成员不能进入 Agent Manager、创建/修改 Agent、
安装 Tool、查看底层 Prompt 或授予新能力。Chat 仍可在服务器端调用预先批准、受限的
Agent Runtime，否则搜索、文档问答和家庭自动化无法工作。

成员发起的 AgentRun 必须继承其 `RequestPrincipal` 和 Session，不得借用核心账户的
工具权限。核心账户承担费用不代表成员自动继承核心账户的 Secrets 或 capability。

### 7.3 后端是安全边界

权限至少在以下层同时生效：

1. App Catalog 过滤不可见 App；
2. App launch/focus/mount API 校验 capability；
3. Session/Repository 验证资源 owner；
4. AgentRun 和 ToolCallContext 携带 actor、organization、installation；
5. Service Gateway 再次验证 GrantLease/capability；
6. Event 和审计查询按角色过滤。

前端隐藏入口不是授权机制，知道 URL 或资源 ID 不能绕过后端检查。

## 8. 本地数据与 Session 隔离

### 8.1 每成员独立的用户 singleton

当前 Chat singleton：

```text
ai2apps.general-chat:user:local
```

应迁移为：

```text
ai2apps.general-chat:user:{cloud_user_id}
```

因为每个 installation 当前使用独立数据库，第一版无需在 key 中重复 device ID。若
未来共享数据库或迁移 Session，可升级为：

```text
ai2apps.general-chat:installation:{installation_id}:user:{cloud_user_id}
```

同样的 user singleton 规则适用于 Account 等按成员持有状态的 App。Models、Trust
Center 等真正的设备控制 App 可以继续采用 system singleton，但访问受 capability
限制。

### 8.2 所有权继承

建议核心关系为：

```text
app_instances.owner_user_id
  -> sessions.app_instance_id
     -> messages / attachments / workspace / artifacts / agent_runs
```

直接属于用户而不自然依附 Session 的对象，例如 Project、Coder thread、Secret 和
个人设置，需要独立的 `owner_user_id` 或明确的 organization/shared scope。

Repository 的所有按 ID 读取、更新、删除接口都必须验证 ownership，不能只在 list
接口添加 `WHERE owner_user_id = ?`。随机 ID 不是访问控制。

### 8.3 共享与隔离边界

| 资源 | 默认边界 |
| --- | --- |
| 模型权重、kernel、MoE expert bank | installation 全局共享 |
| 模型目录与设备指标 | 共享，但按角色过滤细节 |
| continuous batching | 可跨成员共享计算 |
| KV cache/会话 continuation | actor + Session 隔离 |
| 私人 Prompt 派生的 prefix cache | actor 或 Session namespace |
| 公共固定 system prefix | 可显式标记后共享 |
| Chat、附件、Workspace、Artifacts | actor 私有 |
| 组织共享知识库 | 显式 organization scope 与 ACL |
| Secrets/Provider keys | owner 与 capability 隔离 |
| 用量 | owner 看聚合；成员看本人 |

核心账户默认不能读取其他成员 Chat 正文。家庭儿童监护和企业数据留存若需要内容访问，
必须通过独立政策、明显的 UI 告知和审计实现。

## 9. 并发、调度和资源治理

无需为每位成员加载一份模型。现有 EnginePool 和 batched engine 继续共享模型运行时，
请求新增归属元数据：

```text
installation_id + actor_user_id + session_id + request_id
```

第一版资源治理至少包含：

- 每成员最大并发请求；
- 每成员/角色每日点数或 token 预算；
- 每 Session 最大上下文和 KV cache；
- 交互 Chat、语音、后台任务的优先级；
- 按 actor 精确取消，不能清理其他成员请求；
- queue time、TTFT、TPS、token、points 和失败原因的归属统计；
- 核心账户可配置但不能绕过系统内存保护的组织级上限。

共享 batch 必须保持序列边界；任何日志、错误、stream、tool result 或 cache reuse 都不
得将一个成员的内容返回给另一个成员。

## 10. 初步数据模型

以下是逻辑模型，具体 migration 应在实现前结合现有 schema 22 和 repository 查询审查：

```text
installations
  id
  cloud_device_id
  organization_id
  organization_type
  core_user_id
  billing_account_id
  access_epoch
  status
  created_at / updated_at

local_users
  cloud_user_id
  display_name_cache
  avatar_cache
  last_seen_at

installation_memberships
  installation_id
  cloud_user_id
  role
  status
  membership_epoch
  last_verified_at

local_login_sessions
  token_digest
  installation_id
  actor_user_id
  role_snapshot
  membership_epoch
  expires_at
  last_access_check_at

app_instances
  ...existing columns
  owner_user_id nullable

projects / coder_threads / secrets
  ...existing columns
  owner_user_id or organization scope
```

外键和触发器应保证 user-scoped AppInstance 必须有 owner，system-scoped instance 不得
伪装为用户资源。成员移除不应直接级联删除数据；先禁用访问，再由核心账户选择保留、
移交、导出或删除。

## 11. API 与运行时改造方向

### 11.1 新的公共依赖

建立一个统一身份解析依赖，而不是各 Router 单独读 Cookie：

```python
async def require_principal(request: Request) -> RequestPrincipal: ...

def require_capability(name: str): ...
```

它负责解析本地用户 Session、校验 installation 和 membership epoch，并构造不可由
客户端覆盖的 principal。内部 API key、自动化和兼容 OpenAI 客户端应映射为明确的
service principal，而不是匿名核心用户。

### 11.2 建议增加或泛化的接口

具体 URL 可在实现阶段统一，所需语义包括：

```text
GET  local auth/me
POST local auth/handoff/exchange
POST local auth/logout
GET  local organization/members projection
GET  local installation/binding
POST owner reauth
GET  current actor usage
GET  owner installation usage
```

Cloud 侧需要支持：

```text
installation bind/status/transfer
organization membership invite/list/revoke
member handoff for an installation
device-authenticated AI invocation charged to billing owner
membership/device epoch check
owner/admin usage aggregation
```

现有 Remote Mobile endpoints 应尽量演进或复用这些 contract，避免产生第二套身份和
撤销协议。

## 12. 开发计划

### Phase G0：契约与威胁模型

目标：在改 schema 前固定身份、计费和信任边界。

- 定义 `InstallationIdentity`、`RequestPrincipal`、role 和 capability vocabulary；
- 决定 Cloud device credential 与当前 Cookie session 的迁移方式；
- 定义 installation binding、member handoff、epoch check 和 billing contract；
- 明确家庭成员隐私、儿童模式和企业离职数据的默认政策；
- 完成威胁模型：伪造 actor、篡改 billing owner、IDOR、Cookie theft、成员撤销延迟、
  confused deputy、跨用户 cache 泄漏；
- 更新 Cloud OpenAPI 与 local contract tests。

验收：同一个请求中 actor、billing owner、installation 和 role 的权威来源无歧义；
Cloud 与 Local 对扣费和撤销语义有一致测试向量。

### Phase G1：Installation 绑定与多用户本地登录

目标：允许一个核心账户绑定设备，多名成员同时拥有本地登录 Session。

- 增加 installation/member/session 持久化或可靠投影；
- 把全局 Cloud 登录态拆成 Device credential、Member session、Owner reauth；
- 泛化 Remote handoff，支持 LAN/Desktop/Mobile；
- 增加 `RequestPrincipal` FastAPI dependency 和本地 `auth/me/logout`；
- 保留当前 installation API key 作为兼容 service/admin principal；
- 实现 epoch 定期检查、Session expiry、logout 和 revoke；
- 不改变 oMLX 模型、scheduler、router 或 kernel。

验收：核心账户和两个成员可在三个浏览器同时登录；互不覆盖 Cookie；移除一个成员后
只使该成员失效；Cloud 不可达时行为符合离线策略。

### Phase G2：App 可见性与敏感能力

目标：成员只能看到和调用授权 App/能力。

- App manifest/descriptor 增加 access capability；
- 给系统 App 建立 household/business 默认策略；
- Catalog、launch、focus、mount 和资源入口统一校验；
- 分离 Agent Manager 权限和受限 Agent Runtime 权限；
- ToolCallContext、GrantLease 和 audit event 加入 actor/organization/installation；
- 拒绝客户端自报 capability 和 provider identity。

验收：成员无法通过隐藏 URL、直接 API 或已知 instance ID 访问 Coder、Agent Manager、
Terminal、Secrets 和设备设置；核心账户仍可完整使用。

### Phase G3：用户级 Chat 与本地数据隔离

目标：每名成员拥有当前设备独立的 Chat singleton 和 Session 数据。

- schema migration 为 AppInstance 等资源增加 ownership；
- 将 `user:local` 迁移到绑定设备的核心账户；
- Chat Repository 所有方法接受 authoritative principal/owner scope；
- scope Messages、Attachments、Workspace、Artifacts、AgentRuns 和 Events；
- KV/prefix cache 使用 actor/Session namespace；
- 增加跨用户 IDOR、并发、取消、stream 和 cache isolation 测试。

验收：两个成员同时创建、读取、生成、上传、取消和归档时无任何数据串线；服务重启后
所有权仍正确；同一账户在第二台设备没有自动出现第一台设备的 Session。

### Phase G4：核心账户统一计费

目标：所有成员的计费调用稳定归属 installation billing owner。

- Cloud 增加或确认 device-authenticated AI invocation；
- Local Cloud gateway 按 RequestPrincipal 记录 actor，但使用 Device credential；
- ledger 同时记录 actor、device 和 charged account；
- owner 看到设备总量和成员聚合，成员只看到本人；
- 增加组织/成员配额、并发限制和模型 allowlist；
- 覆盖 reserve、complete、failed、cancel、disconnect、idempotent retry 和 credential
  rotation 的结算测试。

验收：多成员并发请求全部只扣核心账户；不存在成员 Cookie 覆盖计费主体、重复扣点或
失败不释放；审计能还原实际 actor。

### Phase G5：小企业策略与生命周期

目标：在不分叉产品后端的前提下提供 Business preset。

- 增加 owner/admin/developer/member/guest 默认角色；
- 多管理员、Owner 恢复和设备转移；
- 员工邀请、离职、数据保留/移交/清除；
- 组织级 App、Agent、模型、Tool、点数和并发策略；
- 审计导出、设备资产和安全事件视图；
- 可选的备份/导出，不默认同步 Chat 正文。

验收：管理员可完成员工完整入职和离职；离职账户无法继续使用旧 Session；保留数据的
归属和访问权限明确；家庭模式不因企业能力增加而变复杂。

## 13. 测试矩阵

至少覆盖以下主体：

```text
household core
household member A
household member B
business owner
business admin/developer/member
installation service principal
revoked member
expired session
```

关键测试：

- 多浏览器同时登录不会互相注销或改变计费主体；
- 成员 A 无法按 ID 读取/更新/删除成员 B 的资源；
- A 取消请求不会终止 B 的生成或清理 B 的 KV cache；
- 跨成员 continuous batch 输出、tool call 和流式事件不串线；
- 成员不能访问敏感 App 的页面、API、mount、Service 或 Tool；
- Agent Runtime 不会因核心账户统一付费而继承核心 Secrets；
- 所有成员调用只扣 installation billing owner，actor attribution 正确；
- Cloud retry/idempotency、断流、取消和失败释放不重复扣点；
- revoke、role downgrade、device epoch rotation 在约定窗口内生效；
- 核心账户历史 `user:local` 数据迁移完整且可回滚；
- 数据库重启、Local 重启和 Cloud 暂时不可达时保持预期边界；
- 同一 Cloud 账户在两台设备上的本地 Session 相互独立。

## 14. 可观测性与隐私

Local 和 Cloud 日志应使用 request、actor、installation 和 trace 的不可逆或内部 ID，
不得记录 Session Cookie、Device credential、完整 Prompt、回答正文、附件正文或完整
Tool 参数。

建议指标：

```text
requests/points/tokens by installation and actor
queue time / TTFT / TPS by workload class
active sessions and concurrent generations
authorization denials by capability and App
membership/device epoch check failures
Cloud settlement reserve/charge/release outcomes
cache hit rate without recording cache content
```

Cloud 保存结算和安全审计所需元数据；Local 保存内容和详细执行数据。任何未来的跨设备
同步都必须是新的、显式选择的加密能力，不能通过扩展 usage telemetry 偷渡实现。

## 15. 第一实现切片建议

第一个 PR/开发切片应保持小而可验证，只完成以下内容：

1. 新增 `RequestPrincipal` 和 installation/member 逻辑模型；
2. 在测试中用已有 Remote JWT `sub` 构造两个不同 principal；
3. 将 Chat singleton resolver 从常量 `user:local` 改为显式 owner key；
4. 让 Chat API/Repository 在所有操作中使用 principal scope；
5. 把现有 local Chat 数据迁移给 installation core user；
6. 添加双用户 Chat CRUD、IDOR 和并发隔离测试；
7. 暂不修改 Cloud 计费、Coder、Agent 或模型 runtime。

该切片先证明“同一设备、两个 Cloud 用户、两套本地 Chat Session”成立。之后再把同一
principal contract 扩展到 App Catalog、Workspace、Documents、Agent、Coder 和统一
计费，能降低一次性横跨整个系统的风险。

## 16. 暂不进入第一版的事项

- 跨设备 Chat/Session 同步；
- 多 installation 共享同一个 SQLite 控制面；
- 企业 SAML/SCIM；
- 跨组织共享 Session 或 Workspace；
- 核心账户默认读取成员聊天正文；
- 每用户独立加载模型或独立 expert bank；
- 复杂按席位结算；
- 自动把家庭 Organization 转换为企业 Organization；
- Local 自建密码、短信、邮箱或账户恢复系统。

这些能力应在身份、所有权、统一计费和撤销边界稳定后再讨论。
