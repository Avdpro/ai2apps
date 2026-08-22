# AI2Apps 多用户与节点联邦 AI 网关设计及初步开发计划

Status: Product direction agreed; architecture draft v0.3
Last updated: 2026-08-16
Related: [AI2Apps Platform Architecture](ai2apps-platform-architecture.md),
[AI2Apps Mobile Entry Design](ai2apps-mobile-entry.md),
[AI2Apps Cloud SSE Bridge](ai2apps-cloud-sse-bridge.md),
[Cloud 项目工作清单](ai2apps-cloud-work-items.md),
[Local Knowledge 与 RAG](ai2apps-local-knowledge-rag-architecture.md)

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

多个 AI2Apps installation 还可以建立受控的上游节点关系。下级节点继续运行自己的
App、Agent loop 和本地 Session，只把明确授权的模型或 Service 请求发送给上游节点；
上游的 App、AppInstance、Session 和管理界面不向下级开放。这使家庭可以组合轻量
NAS 与高性能 AI 主机，也使企业可以组合员工/部门节点与中心 GPU 节点。

## 2. 产品模型

### 2.1 家庭与小企业使用同一底层模型

底层采用通用的 Organization 概念，家庭和企业只是两种策略预设：

```text
Organization
├── type: household | business
├── billing owner
├── memberships
└── installations
    ├── local AppInstances / Sessions / data
    └── optional upstream NodeLink
```

| 概念 | 家庭模式 | 小企业模式 |
| --- | --- | --- |
| Organization | 家庭 | 企业或团队 |
| Billing owner | 核心账户 | 企业所有者或结算账户 |
| Member | 家庭成员 | 员工或访客 |
| Installation | 家庭 AI 网关 | 企业 AI 节点 |
| Upstream Node | 高性能 Mac/GPU 主机 | 中心或部门算力节点 |
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
2. 由当前 installation 自己承载或直接调用 Cloud 的计费模型请求，统一扣当前核心
   账户或组织结算账户；调用获准的上游节点时按第 10.5 节的联邦计费策略执行。
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
11. 一个 installation 可以显式绑定一个上游 AI2Apps 节点，并调用上游授权的模型或
    Service capability。
12. 节点联邦只共享 Service，不共享或远程挂载上游 App、AppInstance 和 Session。
13. 下级 Chat、Agent loop、消息和附件仍由下级节点持有；上游只执行有界的 Service
    request，并按下级 installation 与 Session 隔离短期运行 cache。
14. 第一版节点联邦只允许单上游、单跳和显式 allowlist，禁止递归转发和自动形成网状
    拓扑。
15. 第一版上游节点产生的计费由上游核心/结算账户承担，上游管理员通过模型、点数、
    并发和时间配额控制共享成本。

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
- stable Service identity、External Service 运行模式和 Service Gateway 路由基础；
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
8. Service Gateway 尚无 AI2Apps-to-AI2Apps 的节点凭证、远程 discovery、NodeGrant、
   hop 限制和联邦调用审计。

### 4.3 不应采用的方案

- 不在 Local 保存成员密码或实现本地密码重置；
- 不为每个成员启动一份完整模型；
- 不让成员登录覆盖设备核心计费凭证；
- 不仅靠前端隐藏敏感 App；
- 不信任请求体或客户端 header 自报 `actor_user_id`、角色或计费账户；
- 不默认将 Chat 正文、附件或 Workspace 上传 Cloud；
- 不在第一版引入跨设备 Session 同步和冲突合并。
- 不把节点联邦实现为远程登录上游管理后台、同步上游 App Catalog 或挂载上游 App；
- 不使用核心账户 Cookie、成员 Cookie 或管理员 API key 作为节点间长期凭证；
- 不在第一版允许上游继续转发给自己的上游。

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

### 6.1 直接请求的计费主体固定为 installation owner

所有由当前 installation 自己承载或直接调用 Cloud 的计费推理请求采用：

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

当当前 installation 把请求转交给获准的上游 AI2Apps 节点时，不再属于本节的直接
请求。第一版由实际提供 Service 的上游 installation 承担费用，详细规则见第 10.5 节。

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

## 10. 上游节点与 Service 联邦

### 10.1 产品场景

家庭模式可以用低功耗 NAS 承担网关、App、Session 和数据存储，把高成本模型请求交给
同一家庭的一台高性能 Mac 或 GPU 主机。小企业可以让员工或部门节点调用中心 AI
服务器提供的模型、embedding、rerank 等能力，而各节点继续持有自己的 App 和业务
Session。

该能力称为 Node Federation。界面可使用“上级设备”或“上游 AI 节点”，但它不是
人员管理层级，也不表示上游管理员自动成为下级 Organization 的成员。

```text
下级 App / Agent
  -> 下级 Service Gateway
     -> local Service，或 RemoteServiceBinding
        -> 上游 Federation Gateway
           -> 上游明确导出的 Model/Service
```

调用方向是 Service request，不能反向变成上游对下级 App、文件或桌面的控制通道。

### 10.2 App 与 Session 边界

下级节点负责：

- App Catalog、AppInstance 和 UI Entry；
- Chat/Agent loop、Session、Message、Attachment 和 Workspace；
- 用户认证、App 权限和本地 capability policy；
- 选择本地或上游 Service route；
- 向用户提示数据将被发送到哪个上游节点。

上游节点只负责：

- 对节点凭证和 NodeGrant 鉴权；
- 执行被导出的 Service capability；
- 对下级节点实施模型、并发、token、点数和时间配额；
- 返回流式结果、usage 和有界错误；
- 保存不含正文的调用与结算审计。

上游不得向下级发布 App Catalog、App Entry、AppInstance、Session、Secrets 或管理 API。
多轮对话由下级发送当前调用所需的上下文；上游不得把它转化为用户可见的上游 Chat
Session。上游若保留 KV/prefix cache，namespace 至少包含下级 installation 和下级
Session 标识，并应用 TTL 和撤销清理。

### 10.3 配对与 NodeGrant

节点关系必须由双方核心账户或管理员显式确认：

```text
下级创建 pairing request
  -> 上级管理员确认下级 installation
  -> 上级选择允许的 capability/model/quota
  -> 上级签发可轮换的 node credential
  -> 下级 SecretBackend 保存凭证
```

授权记录至少包含：

```text
NodeGrant
├── upstream_installation_id
├── downstream_installation_id
├── allowed_capabilities
├── allowed_models
├── concurrency_limit
├── token/points/time limits
├── billing_policy
├── grant_epoch
└── expires_at / revoked_at
```

节点凭证必须独立于核心账户 Cookie、成员本地 Session 和管理员 API key，并支持轮换、
过期和立即 revoke。实际权限采用交集：

```text
成员权限 ∩ 下级节点策略 ∩ 上游 NodeGrant = 最终可执行权限
```

上游首先信任经过认证的节点身份，不能信任下级任意自报的 actor、role、capability 或
billing account。actor attribution 必须由节点凭证保护并只用于审计/配额，不能扩大
NodeGrant。

### 10.4 调用链与防循环

联邦请求上下文至少包含：

```text
actor_user_id
origin_installation_id
serving_installation_id
organization_id
session_id
request_id / trace_id
billing_account_id
route_path / hop_count
```

第一版只允许一个上游和一跳：下级发出的 `hop_count=0` 请求在上游执行，上游禁止再次
联邦转发。双方验证 route path 不包含重复 installation ID。超时、取消和客户端断开
必须沿调用链传播，但只能影响对应 request，不能按 Session 或节点粗粒度终止其他请求。

上游不可用时默认返回明确错误。下级可以配置显式本地 fallback，但请求开始后不能静默
切换到不同付费路径；route 和 billing identity 在请求 admission 时冻结。

### 10.5 联邦计费

第一版采用“提供资源的一方承担费用”：

```text
actor                = 下级当前成员
origin installation  = 下级节点
serving installation = 上游节点
charged account       = 上游 installation 的 billing owner
```

上游管理员主动授权共享算力，因此同时设置每日/月度点数、最大并发、允许模型和时间段。
即使调用的是不扣 Cloud 点数的本地模型，也应记录 token、运行时间和资源用量，供上游
执行公平调度。

未来如需由下级承担 Cloud 费用，必须增加 Cloud 签名的跨 installation billing
delegation；不能让下级通过请求字段指定扣费账户，也不能在第一版隐式实现。

### 10.6 第一版允许的 Service

首个 MVP 只导出 `model.chat@1`，稳定后按风险递增支持：

1. model embedding；
2. rerank；
3. image generation；
4. 无副作用、schema 明确的业务查询 Service；
5. `knowledge.remote.search@1` 与 `knowledge.remote.get@1`。

Knowledge Federation 不是通用 Knowledge Service 的远程开放。它只能查询 core 显式发布的
federated bucket，同时受 NodeGrant bucket allowlist、quota、expiry 和 grant epoch 约束。
private bucket 固定不可分享，installation shared bucket 只在本机可见；跨节点只返回有界
excerpt 和短期 citation handle，不导出 blob、SQLite、FTS、embedding 或向量索引。详细
contract 与开发阶段见 Local Knowledge/RAG 文档的 5.4 和 K11。

第一版禁止通过联邦导出 Terminal、Secrets、Browser control、设备管理、App mounting
以及可产生任意主机副作用的 Tool。跨节点 Agent delegation 也不进入第一版；下级
Agent 只能把单次、已授权的 Service call 交给上游。

## 11. 初步数据模型

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

node_links
  id
  local_installation_id
  remote_installation_id
  direction: upstream
  status
  credential_backend_key
  grant_epoch
  created_at / updated_at

node_grants
  id
  upstream_installation_id
  downstream_installation_id
  allowed_capabilities_json
  allowed_models_json
  quota_json
  billing_policy
  expires_at / revoked_at

remote_service_bindings
  id
  node_link_id
  local_service_id / capability
  remote_service_id
  status
  routing_policy_json
```

外键和触发器应保证 user-scoped AppInstance 必须有 owner，system-scoped instance 不得
伪装为用户资源。成员移除不应直接级联删除数据；先禁用访问，再由核心账户选择保留、
移交、导出或删除。

NodeGrant 的权威副本在上游；下级只缓存调用所需的 grant 投影。node credential 本体
只存 SecretBackend，不进入 SQLite 明文字段。联邦 usage/event 记录必须能同时关联
origin、serving installation、actor、request 和 billing policy。

## 12. API 与运行时改造方向

### 12.1 新的公共依赖

建立一个统一身份解析依赖，而不是各 Router 单独读 Cookie：

```python
async def require_principal(request: Request) -> RequestPrincipal: ...

def require_capability(name: str): ...
```

它负责解析本地用户 Session、校验 installation 和 membership epoch，并构造不可由
客户端覆盖的 principal。内部 API key、自动化和兼容 OpenAI 客户端应映射为明确的
service principal，而不是匿名核心用户。

### 12.2 建议增加或泛化的接口

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

节点联邦需要以下语义，具体 URL 由 federation contract 固定：

```text
create/accept/reject node pairing
list/rotate/revoke NodeLink credentials
create/update/revoke NodeGrant
discover only exported Service descriptors
invoke/stream/cancel a granted Service request
read downstream-scoped usage and health
```

上游 Federation Gateway 必须使用独立、窄化的路由面，不能把完整
`/v1/platform/*`、`/admin/*`、`/mobile/*` 或任意 localhost 端口发布给下级。下级将
获准的远程能力绑定为稳定的 External Service，App 和 Agent 不直接持有物理 URL。

现有 Remote Mobile endpoints 应尽量演进或复用这些 contract，避免产生第二套身份和
撤销协议。

## 13. 开发计划

### Phase G0：契约与威胁模型

目标：在改 schema 前固定身份、计费和信任边界。

- 定义 `InstallationIdentity`、`RequestPrincipal`、role 和 capability vocabulary；
- 决定 Cloud device credential 与当前 Cookie session 的迁移方式；
- 定义 installation binding、member handoff、epoch check 和 billing contract；
- 定义 NodeLink、NodeGrant、单跳 route 和 federation billing contract；
- 明确家庭成员隐私、儿童模式和企业离职数据的默认政策；
- 完成威胁模型：伪造 actor、篡改 billing owner、IDOR、Cookie theft、成员撤销延迟、
  confused deputy、跨用户/跨节点 cache 泄漏、联邦循环和下级伪造扣费主体；
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

### Phase G5：上游模型与 Service 联邦

目标：家庭/企业下级节点可安全调用一个上游节点的模型，但不能访问其 App 和管理面。

- 实现 NodeLink 配对、独立 node credential、轮换和 revoke；
- 实现上游持有的 NodeGrant、模型 allowlist、并发/token/点数/时间配额；
- 增加窄化的 Federation Gateway 和远程 Service descriptor discovery；
- 将上游 `model.chat@1` 绑定为下级稳定的 External Model Service；
- 为后续 Knowledge Federation 预留 allowed bucket、read-only search/get capability、
  result-bytes quota 和短期 citation audience；G5 不直接暴露任何 Knowledge bucket；
- 下级 Chat/Agent 保持本地 Session，stream/cancel/usage 沿单次请求传播；
- 实现 route path、hop count、请求幂等和循环拒绝；
- 上游使用自己的 Device billing credential，并记录 origin installation 和 actor；
- 明确错误、本地 fallback 和请求开始后 billing route 冻结规则；
- 验证上游 App Catalog、AppInstance、Session、Secrets、Terminal 和管理 API 不可达。

验收：一个下级成员能在本地 Chat Session 中流式调用上游模型；费用只扣上游核心
账户；上游可按下级撤销和限额；取消、断流、重试不串请求或重复计费；下级无法发现或
调用任何未导出的上游能力。

### Phase G6：小企业策略与生命周期

目标：在不分叉产品后端的前提下提供 Business preset。

- 增加 owner/admin/developer/member/guest 默认角色；
- 多管理员、Owner 恢复和设备转移；
- 员工邀请、离职、数据保留/移交/清除；
- 组织级 App、Agent、模型、Tool、点数和并发策略；
- 审计导出、设备资产和安全事件视图；
- 可选的备份/导出，不默认同步 Chat 正文。

验收：管理员可完成员工完整入职和离职；离职账户无法继续使用旧 Session；保留数据的
归属和访问权限明确；家庭模式不因企业能力增加而变复杂。

## 14. 测试矩阵

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
upstream installation owner
downstream installation core/member
revoked or quota-exhausted NodeLink
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
- 同一 Cloud 账户在两台设备上的本地 Session 相互独立；
- 下级只能发现 NodeGrant allowlist 中的 Service 和模型；
- 下级不能访问上游 App、Session、Secrets、Terminal、管理 API 或任意端口；
- 联邦 Chat 的历史保留在下级，上游不创建用户可见 Session；
- 上游 cache 按下级 installation 与 Session 隔离，revoke/TTL 后正确清理；
- 联邦请求的 stream、cancel、timeout、disconnect 和 idempotent retry 沿调用链正确传播；
- 上游禁止第二跳和包含重复 installation ID 的 route path；
- 上游不可用时按显式策略报错或本地 fallback，不静默改变扣费路径；
- 联邦请求只扣上游 billing owner，且 origin、actor、serving node 可审计；
- NodeGrant revoke、credential rotation 和 quota exhaustion 在确定窗口内生效。

## 15. 可观测性与隐私

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
federation requests/latency/errors by origin and serving installation
NodeGrant denials, quota exhaustion and credential/epoch failures
route/hop rejection and upstream fallback outcomes
```

Cloud 保存结算和安全审计所需元数据；Local 保存内容和详细执行数据。任何未来的跨设备
同步都必须是新的、显式选择的加密能力，不能通过扩展 usage telemetry 偷渡实现。

联邦调用还必须在下级 UI 明确显示实际执行节点。Prompt 和必要上下文即使不持久化在
上游，也会通过网络发送给上游；这必须是用户可理解的信任边界，而不能仅作为后台路由
细节隐藏。

## 16. 第一实现切片建议

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

节点联邦应作为身份、所有权和统一计费稳定后的独立实现切片。其首个端到端只包含一条
`model.chat@1` 上游绑定，不与多用户 Chat migration 放在同一个 PR 中。

## 17. 暂不进入第一版的事项

- 跨设备 Chat/Session 同步；
- 多 installation 共享同一个 SQLite 控制面；
- 企业 SAML/SCIM；
- 跨组织共享 Session 或 Workspace；
- 核心账户默认读取成员聊天正文；
- 每用户独立加载模型或独立 expert bank；
- 复杂按席位结算；
- 自动把家庭 Organization 转换为企业 Organization；
- Local 自建密码、短信、邮箱或账户恢复系统；
- 多上游自动选择、负载均衡或网状联邦；
- 上游继续调用第二级上游；
- 跨节点 App mounting、Session 同步或 Agent delegation；
- 通过联邦开放 Terminal、Secrets、Browser control 或任意主机副作用 Tool；
- 由下级承担上游 Cloud 费用的跨 installation billing delegation。

这些能力应在身份、所有权、统一计费和撤销边界稳定后再讨论。

## 18. 当前实施状态（2026-08-16）

当前已开始实施 Local 端第一批基础能力，尚未修改 `coder.ai2apps.com` 或其他
AI2Apps Cloud 服务端：

- schema v23 已加入 installation、membership、本地登录 Session 和
  `app_instances.owner_user_id`；
- 已建立同时包含 actor、installation、organization、billing owner、role 和 epoch 的
  `RequestPrincipal`，并保留旧 installation API key 的核心主体兼容路径；
- 本地登录 Session 使用随机 opaque token，数据库只保存 token digest；membership epoch
  或角色变化后，旧 Session 授权立即按当前投影重新校验；
- Chat singleton、thread CRUD 和 API 已按当前设备上的 actor 隔离；核心账户首次进入时会
  接管旧 `user:local` Chat instance，普通成员不能接管；
- 系统 App manifest 已声明访问 capability；Catalog、launch、entry、focus、suspend、close
  和 mount 已统一执行角色及 AppInstance owner 校验；
- 内置系统 App 中，Household member/child/guest 默认只能访问 Account 和 Chat；Business
  developer 可访问 Account、Chat 和 Coder；core/owner 以及 business admin 可访问管理类 App；
- Agent 与 Secrets 的后端 API 已增加同一 principal capability 防线，成员不能靠隐藏 URL
  绕过 App Catalog；现有 `/admin` Coder 与 Terminal API 继续由原 admin authentication
  保护；
- Workspace、ResourceHandle、Artifact、Attachment、通用 Message 和 Session Event API
  已沿 `Session -> AppInstance.owner_user_id` 统一校验；已知外部 ID 的越权请求返回 404；
- 用户态 Event stream 必须带当前主体拥有的 Session 或 AppInstance scope，不能订阅设备级
  未过滤事件；旧 installation admin principal 保留管理兼容入口；
- AgentRun 的读取、交互、取消、暂停、恢复、重试和事件入口已沿 Session ownership 校验；
  非旧管理员主体的 AgentRun 列表只返回自己拥有 Session 下的运行记录；
- schema v24 已为 Coder Project 增加 `owner_user_id`，Coder Thread 通过 Project 继承归属；
  核心账户首次进入时接管旧项目，Developer 之间的 project/thread/file/dev-session IDOR
  被 Manager 和新 `/v1/platform/coder/*` API 双重拒绝；
- Coder 前端的 Project、Thread、文件、构建和 TestFlight 请求已迁移到 principal-aware
  platform API；旧 `/admin/api/coder` 暂留作核心管理员兼容入口；
- `ToolCallContext` 已携带 actor、installation、organization、billing owner 和 membership
  epoch；Agent Runtime 从可信 Session ownership 与 installation membership 投影派生这些
  字段，Tool audit event 同步记录非正文身份元数据；
- 已新增不可变 `ModelInvocationContext`；Agent 的模型调用不接受 action/request 自报身份，
  而是从 `Session -> AppInstance.owner_user_id -> installation membership` 反查实际 actor，
  同时固定携带 installation 的核心 billing account；一参数、二参数旧 Model Provider 仍兼容，
  新 Provider 可接收第三个可信 context；
- Agent 内部模型请求使用由 installation、actor、membership epoch 和本地 Session 哈希得到的
  opaque cache namespace；通用 prefix-KV cache 和支持连续 Session 的自适应引擎均以此隔离，
  同一 Cloud 账户在另一台设备或另一条 Session 上不会共享该命名空间；
- Local Cloud AI facade 已拒绝客户端伪造 actor、organization、installation、membership epoch
  或 billing account 字段，并为文本/图片模型请求写入不含 Prompt/正文的本地 request audit；
  实际 Cloud 请求现已使用绑定设备的 Device credential，并由 Cloud 根据 installation
  权威解析核心 billing owner；文本模型端到端已验证请求状态、核心账户扣点和流水关联；
- Cloud facade 的登录、退出、密码、点数、等级、权益与管理员重新认证接口已限制为
  core/owner；普通成员只能使用模型发现和模型调用，不能读取或改变核心账户状态；
- schema v25 已新增仅含元数据的 `cloud_ai_requests` ownership ledger，将幂等键和 Cloud
  request ID 绑定到本地 actor、installation 与核心 billing account；不保存 Prompt、回答、
  图片或凭据；文本流的 `response.created/completed/failed/cancelled` 和同步文本/图片响应会更新
  本地状态；按 ID 查询只允许原 actor，成员取消也只能命中自己的记录；core/owner 可以取消
  本设备请求，但不能通过该接口读取其他成员的逐请求状态或正文；
- 同一个 Cloud 幂等键只能由原 actor 对同一模型操作重试，其他成员复用会在请求离开 Local
  之前返回冲突，避免核心账户共享 Cloud Session 时发生跨成员幂等碰撞；
- Service/Tool HTTP 管理面已按 system management capability 保护；非旧管理员主体查询
  ToolInvocation 或直接调用 Tool 时还必须提供自己拥有的 Session scope；
- 核心账户旧 Chat 接管、多用户 CRUD/IDOR、App 可见性、实例 IDOR、敏感 API 403、Shell
  兼容等回归测试已通过。
- Local 已实现通用 installation member handoff 交换：使用 Device credential 消费一次性
  handoff，按独立 audience 验证 Ed25519 assertion 的 installation/device/organization/role/
  membership epoch/access epoch 和五分钟有效期，JWT 不落盘也不进入浏览器；交换成功后只签发
  当前设备的 opaque `HttpOnly`、host-only、`SameSite=Strict` Session Cookie；平台 API 可从该
  Cookie 恢复 `RequestPrincipal`，并提供 `auth/me` 与只撤销当前 Session 的 `auth/logout`。
- macOS 客户端已注册 `ai2apps://auth/complete#handoff=...`，只把 fragment 转交给当前配置端口的
  `/auth/complete`；由浏览器完成页立即清除 fragment、调用本机 handoff exchange，使 HttpOnly
  Cookie 落在实际使用 Local 的浏览器中。Account App 已显示当前 Local principal，支持粘贴完整
  一次性链接切换用户，以及关闭当前成员 Session 后返回核心设备账户。
- 已使用当前核心 Cloud 账户、线上 `coder.ai2apps.com` handoff API 和本机 Device credential
  完成真实端到端验证：Cloud 创建 `lan_desktop` handoff、本机交换返回 201、Cookie 随后的
  `auth/me` 返回 200 且身份字段一致；测试过程不输出或持久化 handoff、Cloud Cookie 或设备密钥。
- Desktop Shell、Catalog、App content、launch/focus/suspend/close、mount 和 App resource
  路由现已接受 Local member Cookie；Shell 只渲染当前角色可见的 App，普通成员不显示系统控制
  入口，直接猜 Agent/Coder URL 或复用其他成员 instance/session/mount ID 均按 404 拒绝。
- Account App 可作为所有成员的本地身份与退出入口，但只有 core/owner 会得到 Cloud 管理能力和
  核心 API key；完成成员 handoff 时还会清除浏览器中遗留的核心 API key，避免同一浏览器切换
  身份后继续携带安装管理员凭据。
- `/v1/models`、`/v1/models/status` 和 `/v1/chat/completions` 已接受 Local member Cookie；成员
  调用 AI2Apps Cloud 模型时使用 Device credential，并附带可信 actor 和 membership epoch，
  Cloud 仍按 installation 核心账户结算。无 Cookie/API key 的请求仍返回 401。
- Local 在运行时启动时立即读取 Cloud installation access projection，之后每 120 秒使用
  `ETag/If-None-Match` 复核；完整投影在一个 SQLite 事务中应用，避免只更新部分成员。
- 单个 membership 的 role、status 或 epoch 变化只删除该成员的 Local 登录 Session；成员从
  完整投影中消失也按 revoked 处理。installation access epoch 变化、device suspend/revoke
  则删除该 installation 的全部 Local 登录 Session。临时网络故障保留最后一次有效的本地投影，
  不将“离线”误判为“撤销”；Cloud AI 仍由 Cloud 在每次请求时执行最终 Device/member 授权。
- Account App 的核心账户管理面已接入 Cloud installation detail、成员列表、邀请、取消邀请、
  角色变更、暂停、恢复和移除。浏览器不能选择 installation；角色变更的 Owner password 只用于
  Local 向 Cloud 换取一次性、用途绑定的 grant，password/grant 均不落盘且 grant 不返回浏览器。
  成员状态或角色修改成功后，Local 会立即刷新 access projection，无需等待下一次 120 秒轮询。
- Cloud 登录后会先验证该账号与当前 installation 的成员关系；未登记账号会立即退出 Cloud、删除
  Local 持有的 Cloud Session、清空邮箱/密码/handoff 输入，并只显示一次“不属于当前设备”的说明。
  即使 Cloud logout 暂时失败，Local Cookie 也必须删除。设备管理区不会向未登记账号显示。
- Account App 已接入 Cloud v1.6.0 organization policy 和 member quota API：核心账户可以编辑
  App/model allowlist、组织默认月度点数、并发数、离线宽限，以及每成员的模型/月度点数/并发覆盖。
  所有写入都携带当前 policy ETag；Owner password 只在 Local 内换取用途绑定的一次性 grant，
  password/grant 不落盘也不返回浏览器。`412 POLICY_VERSION_MISMATCH` 会重新读取最新策略，避免
  静默覆盖；成功写入会立即刷新完整 access projection。
- 邀请创建现在直接展示 Cloud 返回的 fragment-based `inviteUrl` 及由 Local 临时生成的二维码，
  可复制、扫码或在新标签打开 Cloud 接收页面；Local 不拼接 URL、不持久化邀请码。Cloud 已将邀请
  绑定到规范化目标邮箱，在接受时强制校验当前账户，并完成 SMTP 投递、非消耗预检、错误账户提示与
  resend code 轮换。Local Account App 会显示投递状态/尝试次数/失败类别和不含秘密的 pending 列表；
  Owner 可取消或重发，重发后的新链接与二维码仍只在当前页面内存中出现。接收者完成注册、验证、登录
  和接受后，再用 installation handoff 建立当前设备独立 Session。创建期间页面明确显示正在等待 Cloud
  邮件投递；创建响应返回后先在本地立即显示二维码并更新 pending 行，再后台读取 Cloud 权威列表校准。

当前 Cloud/Local 已具备 installation 绑定、Device credential、member handoff、Cloud 强制策略与
统一计费所需的后端契约；桌面协议回调、浏览器 Session、成员 Desktop Shell、在线撤销、核心成员
管理、组织策略、每成员配额及邀请接收入口均已完成。下一步产品闭环是对邀请接受后的 handoff
引导做完整人工验收，并验证策略拒绝、月度额度、并发限制与 ETag 冲突的端到端提示。Workspace、附件、
Artifacts、Events 和 AgentRuns 的 API 入口隔离已经完成，但底层内部调用仍依赖可信 runtime
边界；Coder 的 Terminal WebSocket 尚待 Local member Cookie middleware 就绪后迁移，独立
Documents/Secrets 归属仍待后续 Local 切片逐项完成。当前模型 context、Local audit 与
KV/prefix cache namespace 已完成本地边界，但不能替代 Cloud 端最终计费授权。v25 Cloud
request ledger 当前覆盖 principal-aware `/v1/platform/cloud/ai/*` 多用户入口；Desktop Chat
的 `/v1/chat/completions` 已具备成员身份与 Cloud 最终计费授权，但尚需复用同一 ledger 写入路径，
使 Desktop Chat 也具备一致的本地逐请求状态、取消和审计能力。
