# AI2Apps 多用户网关：Cloud 项目工作清单

状态：Draft v0.1
日期：2026-08-15
对接 Local 文档：`docs/ai2apps-multi-user-gateway.md`

账户等级、付费套餐、Core设备数和单设备Member数的新增准入规则见
[`ai2apps-cloud-account-capacity-v1.md`](ai2apps-cloud-account-capacity-v1.md)。
Core 设备列表、权威改名和撤销接口的完成契约见
[`ai2apps-cloud-device-management-v1.md`](ai2apps-cloud-device-management-v1.md)。

## 1. 目的与交付边界

本文是交给 `coder.ai2apps.com` / AI2Apps Cloud 项目的实施清单。目标是补齐 Local 无法
自行建立的权威身份、设备、组织成员和统一计费能力，使一个 Local installation 可以：

1. 绑定一个核心账户和一个 Organization；
2. 允许多个 Cloud 账户在该 installation 上分别创建本地 Session；
3. 所有 Cloud 模型调用固定扣 installation 核心/结算账户；
4. 成员移除、角色变化或设备撤销能在确定窗口内让 Local Session 失效；
5. 后续能够安全建立 AI2Apps 节点间模型/Service 联邦。

Cloud 是以下数据的权威来源：

- Cloud user identity；
- Organization、membership、role 和 membership epoch；
- installation/device 绑定、状态、access epoch 和 billing owner；
- Device credential 的签发、轮换与撤销；
- Cloud AI 请求的扣点与 usage ledger；
- Owner reauth 和高风险设备操作授权。

Local 继续是以下数据的权威来源，Cloud 第一版不得要求上传：

- Chat/Session/Message 正文；
- Attachment、Workspace、Artifact 内容；
- 本地 Secrets、Terminal、Coder 文件和本地 Agent 执行详情；
- 本地模型 cache 内容；
- AppInstance 的本地状态。

## 2. 现有 Cloud 能力应优先复用

Local 当前已经调用或验证以下 Cloud 协议雏形：

- `/v1/remote/devices`；
- `/v1/remote/devices/{device_id}/credentials/rotate`；
- `/v1/remote/devices/{device_id}/revoke`；
- `/v1/internal/remote/mobile/exchange`；
- `/v1/internal/remote/devices/{device_id}/access`；
- `/v1/remote/jwks.json`；
- `/v1/ai/responses`、`/v1/ai/images/*` 和 AI request cancel/status；
- `/v1/points`、`/v1/points/ledger`；
- `/v1/admin/reauth`。

Cloud 项目应审计并扩展这些接口，形成统一的 installation identity 和 member handoff，
不要并行创建一套与 Remote device 无关的新设备身份、JWT、epoch 或 credential 系统。

## 3. P0：阻塞 Local 多账户正式启用的工作

### CLOUD-001：冻结共享身份契约与 OpenAPI

Cloud 与 Local 共同使用以下不可由浏览器请求体覆盖的 principal 字段：

```json
{
  "actorUserId": "usr_...",
  "installationId": "ins_...",
  "cloudDeviceId": "dev_...",
  "organizationId": "org_...",
  "organizationType": "household",
  "billingAccountId": "acct_...",
  "role": "member",
  "membershipEpoch": 4,
  "accessEpoch": 7
}
```

角色枚举至少支持：

```text
core, owner, admin, developer, member, child, guest
```

要求：

- household 第一版至少开放 `core`、`member`，其他角色可保留；
- business 支持 `owner`、`admin`、`developer`、`member`、`guest`；
- `billingAccountId` 必须由 installation 绑定记录解析，不能接受 Local 请求字段指定；
- 所有 epoch 是严格单调递增正整数；
- 发布 OpenAPI、错误码、JWT claims 和至少一组 Cloud/Local 共用测试向量。

验收：同一个测试 handoff 在 Cloud 和 Local 中解析出完全一致的 principal；伪造 role、
billing account、installation 或 epoch 的测试全部失败。

### CLOUD-002：统一 Installation/Device 绑定

基于现有 Remote device 模型增加或确认以下权威字段：

```text
installation_id
cloud_device_id
organization_id
organization_type
core_user_id
billing_account_id
status: active | suspended | revoked
access_epoch
credential_version
credential_expires_at
created_at / updated_at
```

建议语义接口，URL 可按现有路由统一：

```text
POST /v1/installations/bind
GET  /v1/installations/{installation_id}
POST /v1/installations/{installation_id}/credentials/rotate
POST /v1/installations/{installation_id}/revoke
```

要求：

- bind 必须要求核心账户登录和近期 Owner reauth；
- 一个 installation 第一版只能绑定一个 Organization 和 billing owner；
- 重复 bind 同一权威关系幂等；绑定到不同核心账户/组织必须冲突，不得静默覆盖；
- Device credential 只在首次签发或 rotate 时返回一次 secret；Cloud 只保存安全摘要；
- revoke/suspend/rotate 必须推进 `access_epoch`；
- credential 使用与现有 `Authorization: Device ...` 兼容的独立设备认证；
- 成员登录不得轮换或覆盖 Device credential；
- Device credential 不能作为浏览器 Cookie 返回。

验收：旧 credential 在 rotate/revoke 后失效；成员 Cloud Cookie 不能改变 installation 的
核心账户或扣费账户。

### CLOUD-003：Organization 与 Membership 管理

Cloud 增加或确认权威 membership 数据：

```text
organization_id
user_id
role
status: invited | active | suspended | revoked
membership_epoch
invited_by
joined_at / revoked_at / updated_at
```

需要支持的业务操作：

```text
create household/business organization
invite member
accept/reject invitation
list members
change role
suspend/revoke member
resend/cancel invitation
```

权限规则：

- household core 可管理 household member/child/guest；
- business owner/admin 按策略管理成员；
- 普通成员不能邀请、提权或改变 billing owner；
- 每次 status/role 改变推进该成员 `membership_epoch`；
- Owner/core 的删除、转移和最后一名 Owner 保护需要单独高风险流程；
- revoke 不立即删除 Local 内容，只使访问授权失效。

验收：成员降权或 revoke 后，旧 handoff 不能再次 exchange；epoch check 能发现变化；
并发重复邀请和接受操作具有明确幂等结果。

### CLOUD-004：通用 Member Handoff

把现有 Remote Mobile handoff 泛化为 LAN Desktop、LAN Mobile 和 Remote Mobile 共用的
一次性交换协议。

建议流程：

```text
成员浏览器在 Cloud 完成登录/接受邀请
  -> Cloud 创建绑定 installation 的一次性 handoff
  -> 浏览器返回 Local，携带短期 opaque handoff code
  -> Local 使用 Device credential 向 Cloud exchange
  -> Cloud 返回短期签名 member assertion
  -> Local 验签并创建自己的 HttpOnly opaque Session Cookie
```

建议接口语义：

```text
POST /v1/installations/{installation_id}/member-handoffs
POST /v1/internal/installations/{installation_id}/member-handoffs/exchange
GET  /v1/installation-auth/jwks.json
```

handoff 要求：

- 一次性、短 TTL（建议 1～5 分钟）、高熵、数据库只保存摘要；
- 绑定 installation、用户、Organization、登录目的和 redirect target；
- exchange 必须由对应 installation 的有效 Device credential 调用；
- 成功或失败达到次数上限后不可重放；
- redirect target 使用 allowlist，禁止开放重定向；
- 不在 URL 中放长期 token、Cloud Cookie 或 Device credential。

签名 member assertion 至少包含并验证：

```text
iss, aud, sub, jti, iat, nbf, exp
installation_id, cloud_device_id, organization_id
role, membership_epoch, access_epoch
```

要求复用或兼容当前 Remote token 的 JWKS、issuer 和 key rotation 机制。JWT 不作为 Local
长期浏览器 Session；Local 交换成功后只保存自己的 opaque token digest。

验收：handoff 重放、跨设备 exchange、错误 audience、过期、旧 epoch、已撤销成员和开放
redirect 测试全部失败；三个入口产生相同身份语义。

### CLOUD-005：Device 与 Membership Epoch Check

扩展现有 `/v1/internal/remote/devices/{device_id}/access`，提供 Local 可批量或单用户检查的
轻量接口。

建议响应：

```json
{
  "installationId": "ins_...",
  "deviceStatus": "active",
  "accessEpoch": 7,
  "organizationId": "org_...",
  "memberships": [
    {
      "userId": "usr_...",
      "status": "active",
      "role": "member",
      "membershipEpoch": 4
    }
  ],
  "checkedAt": "..."
}
```

要求：

- 仅允许对应 Device credential 读取本 installation 的最小授权投影；
- 不返回成员邮箱、密码资料、Cloud Cookie、余额或无关 Organization 数据；
- 支持 ETag/If-None-Match 或等价版本机制，减少轮询开销；
- 明确 Cloud 不可达、device suspended、member revoked 和 epoch mismatch 的错误码；
- 给出最大撤销传播窗口，建议在线状态不超过 1～5 分钟；
- 支持 Local 启动时检查和运行期定时检查。

验收：只 revoke 一个成员不会使其他成员 Session 失效；device revoke 会使全部成员在线
Cloud 能力和下一次授权检查失效。

### CLOUD-006：Device-authenticated AI 与固定 Billing Owner

现有 `/v1/ai/responses`、`/v1/ai/images/*`、status 和 cancel 接口需要支持 Device
credential 调用，并把扣费主体固定解析为 installation 的 `billing_account_id`。

权威关系：

```text
actor            = installation 的 active member
charged account  = installation.billing_account_id
device           = authenticated installation/device
```

要求：

- 不能从请求 JSON、成员 Cookie或任意 `billingAccountId` header 选择扣费账户；
- actor attribution 必须在 Device credential 保护下提交，并由 Cloud 验证该 actor 是当前
  Organization 的 active member，且 membership epoch 未过期；
- 成员的个人 Cloud 账户余额不得覆盖 installation billing owner；
- admission 时冻结 model route、billing owner、request ID 和幂等键；
- 同步文本/图片响应必须返回稳定 `requestId`，流式响应必须在
  `response.created` 中返回同一个 ID；status/cancel 路径继续使用该 ID；
- reserve、complete、failed、cancel、disconnect、timeout、retry 必须完整结算；
- 相同 installation + idempotency key + 等价请求不能重复扣点；不等价请求必须冲突；
- cancel 只能取消同一 authenticated installation 的目标 request；
- 流式请求即使客户端中断，也必须完成 charge/release 收尾；
- suspended/revoked device 或 member 不得发起新的 Cloud AI 请求；
- 可按 Organization/member 配置模型 allowlist、并发、每日/月度点数上限。

usage ledger 至少记录：

```text
request_id / idempotency_key
installation_id / cloud_device_id
organization_id
billing_account_id
actor_user_id
model / provider route
input_tokens / output_tokens / cache usage
points_reserved / points_charged / points_released
status / error category
created_at / completed_at
```

不得记录完整 Prompt、回答正文、附件正文、Tool 参数或 Local Session Cookie。

验收：核心账户和两个成员并发调用全部只扣同一个 billing owner；actor attribution 分开；
伪造 billing owner、跨 installation cancel、重复 retry 和断流不会造成错扣或重复扣点。

### CLOUD-007：Usage 与成员可见性

需要提供：

```text
GET current actor usage
GET owner/admin installation aggregate usage
GET owner/admin usage grouped by member/model/time
```

要求：

- 普通成员只能读取自己的聚合用量，不读取 Organization 余额和他人明细；
- household core、business owner/admin 可读取设备总量与成员聚合；
- 默认不向管理员返回 Prompt/回答正文；
- 支持按 request ID 查询本人请求的结算状态；
- 所有管理查询需要角色和近期 reauth 分级保护。

验收：成员 A 不能按 user ID 查询成员 B；管理员聚合总量等于成员聚合与系统请求之和。

### CLOUD-008：Owner Reauth、设备恢复和高风险操作

扩展现有 `/v1/admin/reauth`，签发极短期、目的绑定的 reauth grant，至少覆盖：

```text
installation.bind
installation.rotate_credential
installation.revoke
installation.transfer（可后置）
organization.member.role_change
organization.owner_change
billing.view_sensitive
```

要求：

- grant 包含 actor、purpose、resource、iat/exp/jti，不能跨目的复用；
- 成员普通登录 Session 不能代替 Owner reauth；
- 高风险操作产生不含秘密和正文的安全审计；
- 第一版若不支持 transfer，应明确返回稳定的 `not_supported`，不能静默重绑；
- 定义核心账户丢失后的人工恢复流程和安全等待期。

验收：过期 grant、错误 purpose/resource、非 Owner/Admin 和重放全部失败。

## 4. P1：完成家庭/小企业产品所需的 Cloud 工作

### CLOUD-009：Organization Policy Projection

状态：**Cloud 已于 2026-08-15 部署生产，Local 已完成 v1.6.0 客户端对接。**

Cloud 保存并向对应 Device credential 下发最小策略投影：

```text
allowed roles
App/model allowlist
per-member model and points quota
concurrency limits
offline grace upper bound
membership/device epoch policy
```

Local 可以采用更严格策略，但不能放宽 Cloud 权益、模型或点数限制。策略记录需要版本号
和 ETag；变更需审计并能触发 Local 刷新。

已交付的生产契约为 `GET/PATCH /v1/installations/{installationId}/policy` 和
`GET/PATCH /v1/installations/{installationId}/members/{userId}/quota`。写入要求当前
`If-Match: "policy-{version}"`，并分别使用用途为 `organization.policy.change`、
`organization.member.quota_change` 的一次性 Owner grant。Cloud 最终执行组织/成员模型
allowlist 交集、成员并发限制和 UTC 自然月点数额度；Local 只负责安全代理、编辑界面和投影刷新。

### CLOUD-010：邀请、离职与保留策略元数据

为 business 增加员工邀请、离职原因、数据保留选择和移交目标的控制面。Cloud 只保存
策略和操作审计，不自动读取或搬运 Local 内容。实际本地数据保留、导出、移交或删除由
Local 在获得明确授权后执行。

状态：已由 Cloud invitation delivery v2 / OpenAPI 1.7.0 交付。当前邀请记录保存规范化的
目标邮箱（以及目标账户已经存在时的 user ID），接受接口会将当前账户与邀请目标比较；不匹配的
账户即使获得链接也不能接受。已完成的产品闭环包括：

- 创建邀请成功后，使用现有 SMTP 基础设施向目标邮箱发送邀请信。邮件包含组织/设备显示名、
  邀请人、初始角色、过期时间和原始 `inviteUrl`；不得使用会泄漏 fragment 邀请码的跟踪跳转。
- 邀请发送失败不会把已创建的邀请伪装成已投递。创建响应返回不含秘密的投递状态，支持 Owner
  重发；重发或重新邀请同一邮箱时，只保留并投递最新有效邀请。
- 接受页面在用户点击前显示目标邮箱（未认证或非目标账户时只显示掩码），并明确提示当前登录
  账户是否匹配。错误账户不应显示可用的“接受邀请”按钮，而应引导“使用其他账户登录”。
- 已提供不消耗邀请码的预检能力。邀请码仍只通过 POST body 从 URL fragment 传入；响应仅返回组织
  显示信息、角色、过期时间、掩码邮箱和当前账户是否符合条件，禁止把邀请码写入 URL、日志、
  Cookie、分析事件或浏览器持久化。
- 错误账户使用稳定错误 `INVITATION_EMAIL_MISMATCH`，不与过期、撤销或已使用
  邀请混为同一 UI 文案；服务端接受操作仍须再次执行邮箱/user ID 校验，不能依赖页面预检。
- 契约测试覆盖邮箱规范化、已有账户 user ID 绑定、页面预检和重发边界；生产部署记录确认 migration
  `0021`、健康/就绪、邀请页及 preview 错误契约。邀请码只保存 keyed digest，不进入列表或审计正文。

Local Account App 已消费该契约：展示 `delivery` 状态、失败类别和尝试次数，列出不含秘密的 pending
邀请，并提供 Cancel 与 Send again。重发响应中的新链接和二维码只在当前页面内存中展示，不持久化；
列表永远不包含 code、URL 或二维码。

### CLOUD-011：设备与成员安全审计

记录并允许 Owner/Admin 查看：

- bind、rotate、revoke、suspend、reauth；
- invite、accept、role change、member revoke；
- handoff create/exchange/replay rejection；
- epoch mismatch、credential failure、异常调用量；
- AI reserve/charge/release 的元数据关联。

日志不得包含 credential、handoff code、JWT、Cookie、Prompt 或回答正文。

### CLOUD-013：通知与撤销加速（可选）

轮询 epoch check 是正确性基础。在此基础上可增加 WebSocket/SSE/WebPush 之类的提示，
通知 Local 立即刷新 device/member epoch。推送消息只能作为加速信号，不能替代 Local 向
Cloud 权威接口重新检查。

## 5. P2：节点联邦需要的 Cloud 工作（不阻塞首批多账户）

以下工作在家庭/企业身份和统一计费稳定后启动。

状态：**Cloud 已于 2026-08-16 完成 CLOUD-101～105 并部署生产，公开契约为
OpenAPI 1.10.0。** 已交付独立 NodeLink credential、一次性 pairing、purpose-bound Owner
grant、版本化 NodeGrant、相对路径 connector export 注册、一跳 `model.chat@1`、MCP
initialize/ping/tools/list/tools/call、流式/取消/幂等/环路与并发保护、固定上游 billing
identity、元数据用量审计和 Local 双实例 CI fixtures。客户端对接说明与 fixtures 位于 Cloud
仓库 `docs/federation-v1.md`、`docs/client-integration-v1.md` 和
`fixtures/federation-v1/`。

Local 生产对接复核发现一个待修兼容项：`POST .../mcp` 的 `tools/list` 目前只筛选
`mcp.tool`，会漏掉 OpenAPI 已允许的 `mcp.service` 与 `mcp.agent`。请改为包含所有
`mcp.*` connector kind，并增加 Service/Agent discovery + `tools/call` 契约测试。其余已验证的
JWKS、Device pairing 创建和错误边界与 OpenAPI 1.10.0 一致。

### CLOUD-101：Node Pairing 与 NodeLink Credential

- 下级创建 pairing request，上级 Owner/Admin 显式接受或拒绝；
- credential 独立于成员 Cookie、Device credential 和管理员 API key；
- credential 支持短期签发、轮换、过期、revoke 和 grant epoch；
- 双方只获知必要的 installation identity，不自动加入彼此 Organization。

### CLOUD-102：NodeGrant 控制面

NodeGrant 权威副本由上游持有，至少包含：

```text
upstream_installation_id / downstream_installation_id
allowed_capabilities / allowed_models
concurrency_limit
token / points / time quotas
billing_policy
grant_epoch
expires_at / revoked_at
```

第一版 billing policy 固定为上游 installation billing owner 承担费用。

### CLOUD-103：窄化 Federation Gateway

- 首个版本只导出 `model.chat@1`；
- 提供 descriptor discovery、invoke/stream/cancel 和下级 scoped usage/health；
- 禁止暴露 `/v1/platform/*`、`/admin/*`、`/mobile/*`、App Catalog、Session、Secrets、
  Terminal、Browser control 和任意主机副作用 Tool；
- 只允许一跳，验证 route path 无重复 installation；
- request admission 后冻结 serving node 和 billing route；
- cancel、timeout、disconnect 和 idempotent retry 只影响对应 request。

### CLOUD-104：联邦审计与计费归属

第一版记录：

```text
actor = downstream current member
origin installation = downstream
serving installation = upstream
charged account = upstream installation billing owner
```

即使上游使用本地免费模型，也要记录 token、运行时间和配额消耗。Cloud/上游不能信任
下级自报的 billing account，actor attribution 也不能扩大 NodeGrant。

### CLOUD-105：MCP Capability Relay

在 CLOUD-101～104 的 NodeLink/NodeGrant 基础上增加跨网络 MCP 中继，使下级 Local 能使用
上级明确分享的 Tool、Service 和 Agent。Cloud 只负责寻址、鉴权与字节流中继，不执行
能力，也不保存 MCP 参数或结果正文。

最低契约：

```text
POST /v1/federation/nodes/{nodeId}/mcp
Authorization: Device/NodeLink credential
Content-Type: application/json
body: MCP JSON-RPC initialize / ping / tools/list / tools/call
```

实现要求：

- 上级 connector 只注册窄化的 share endpoint，不注册 `/admin`、`/apps` 或
  `/v1/platform` 管理面；
- Cloud 在转发前校验 NodeGrant epoch、expiry、上下级 installation、允许的 export ID、
  并发与用量额度；
- `tools/list` 只能返回 NodeGrant 允许且当前仍 active 的 Tool/Service/Agent MCP 投影；
- `tools/call` 的名称必须再次做服务端 allowlist 校验，不能只相信先前的 list；
- 保留 MCP stream/cancel/disconnect 语义；连接断开必须释放并发预留；
- relay token 必须短期、purpose-bound、不可作为 Cloud Account Cookie 或 Local Core
  credential 使用；
- Node ID 与完整 `ancestorNodeIds` 随连接握手传递，Cloud 和两端都拒绝重复 Node，防止
  `A -> B -> A`；
- revoke/epoch change 在承诺窗口内终止新调用，活动调用按明确策略 cancel 或自然结束；
- 日志只记录 request ID、上下级 Node、export ID、方法、耗时、字节数、结果码；不得记录
  Prompt、Tool arguments、Agent message、Service payload、响应正文或任何 token；
- 对 model relay 保留 OpenAI-compatible chat/stream 接口；Cloud 模型本身仍不允许作为
  Local 分享模型，避免二次转售和计费归属混淆。

Cloud 需交付 OpenAPI、connector 协议、短期 token/JWKS 规则、断线重连与幂等规则、
配额/审计字段、撤销时序，以及供 Local 双实例 CI 使用的 mock/contract fixtures。

## 6. 统一错误码建议

Cloud 至少提供稳定的机器可读错误码：

```text
installation_not_found
installation_binding_conflict
device_suspended
device_revoked
device_epoch_mismatch
device_credential_expired
membership_not_found
membership_inactive
membership_epoch_mismatch
role_not_allowed
owner_reauth_required
owner_reauth_invalid
handoff_invalid
handoff_expired
handoff_replayed
handoff_device_mismatch
organization_policy_denied
model_not_allowed
member_quota_exceeded
installation_quota_exceeded
billing_reserve_failed
idempotency_conflict
request_not_found
request_not_owned
```

所有错误响应应包含 `requestId`；可重试错误明确 `retryable` 和可选 `retryAfter`。401、403、
404、409、422、429、503 的使用需在 OpenAPI 固定，Local 不应靠错误文案判断状态。

## 7. 安全与隐私验收清单

- [ ] 浏览器无法获得 Device credential；
- [ ] 成员 Cookie 无法替换 installation billing owner；
- [ ] Local 请求体/header 无法自选 billing account；
- [ ] handoff 不能重放、跨 installation 使用或开放重定向；
- [ ] JWT/JWKS 支持 key rotation，旧 key 有明确重叠期；
- [ ] revoke/epoch change 在承诺窗口内生效；
- [ ] 一个成员 revoke 不误伤其他成员；
- [ ] device revoke 使整台 installation 失去 Cloud 调用能力；
- [ ] 跨 Organization、跨 installation 的 IDOR 测试全部返回拒绝；
- [ ] usage/审计不包含 Prompt、回答、附件、Workspace 或 Secrets 正文；
- [ ] credential、handoff、JWT、Cookie 不进入日志；
- [ ] AI stream/cancel/retry 的结算满足幂等和最终一致；
- [ ] 限流同时覆盖 user、installation、Organization 和 IP/异常行为维度；
- [ ] 所有高风险操作要求 purpose-bound Owner reauth。

## 8. Cloud 项目交付物

首批对接需要以下可独立验收的产物：

1. 更新后的 Cloud OpenAPI；
2. migration 和数据回填/兼容策略；
3. Device credential、member assertion、JWKS 和 epoch 协议说明；
4. Organization/membership 管理 API；
5. 通用 member handoff 及 exchange API；
6. Device-authenticated AI 与 billing ledger 改造；
7. usage、reauth 和审计 API；
8. Cloud 单元/集成/安全测试；
9. 供 Local CI 使用的 contract fixtures 和 mock server；
10. 灰度、回滚、credential rotation 和旧 Remote Mobile 兼容方案。

建议 Cloud 项目按以下顺序交付：

```text
CLOUD-001 contract
  -> CLOUD-002 installation/device
  -> CLOUD-003 membership
  -> CLOUD-004 handoff + CLOUD-005 epoch check
  -> CLOUD-006 billing AI
  -> CLOUD-007 usage + CLOUD-008 reauth
  -> P1 business policy/audit
  -> P2 node federation
```

Local 开始真实成员登录对接的最低就绪条件是 CLOUD-001～005；允许成员使用 Cloud 扣点
模型的最低就绪条件还必须包含 CLOUD-006。CLOUD-006 完成前，Local 即使已建立成员
Session，也只能安全开放纯本地、不需要 Cloud 权益或扣点的能力。

## 9. Federation 对接复核（2026-08-16）

Local 已完成 NodeLink list、NodeGrant、credential rotate/import、revoke、Agent MCP
connector、Relay JWT 取消校验和策略错误分类。Cloud 当前代码仍有一个阻塞两机完整验收的
投影问题：`tools/list` 只筛选 `kind === "mcp.tool"`，但 OpenAPI 1.10.0 允许
`mcp.tool`、`mcp.service`、`mcp.agent`，且 `tools/call` 已接受所有 `mcp.*`。

Cloud 还需：

- 将 federation `tools/list` 的筛选改为所有 `mcp.*` connector kind；
- 增加 Tool、Service、Agent 三种 connector 的 list/call contract test；
- 提供两 Installation fixture，覆盖 NodeGrant、rotate 后旧 credential 失效、revoke、
  concurrency/quota 和 stream disconnect/cancel。

这些完成后即可在第二台电脑上执行最终真实 E2E；无需再新增 Local 管理接口。
