# Codex Remote Personal Cloud 变更需求 v1

状态：待交付 AI2Apps Cloud 项目实现

适用范围：AI2Apps Cloud API、账户认证页、Remote Device、FRP Edge、审计与撤销投影

目标账户：部署时将规范化邮箱 `avdpro@me.com` 解析并冻结为唯一 Cloud Account ID；运行时只比较 Account ID，不以可变邮箱、别名或请求自报字段作为授权依据。

> 本文只定义 Cloud 侧合同。当前仓库不得直接修改或部署 Cloud 代码。Codex
> Thread、Prompt、批准内容和本地 App Server 协议全部留在用户 Mac 上；Cloud 只负责
> 账户门禁、短期配对证明、撤销状态和现有 FRP 管道准入。

## 1. 目标

1. 仅目标 Account ID 可以创建或消费 Codex Remote 配对。
2. 手机扫描插件显示的一次性 QR/URL 后，必须执行一次新的交互式登录；现有 Cloud、
   AI2Apps 或 Remote Mobile Cookie 不能直接满足本次登录。
3. 登录成功后签发用途、账户、Device、Bridge 实例和一次性 challenge 全部绑定的短期
   EdDSA assertion。
4. 插件可立即使一个未使用 QR/URL、一个已配对手机会话或当前 Bridge 的全部远程会话
   失效。
5. Cloud/FRPS/Edge 不保存或记录 Prompt、模型输出、Thread 正文、命令、文件差异或批准
   内容。
6. 复用现有 AI2Apps FRPS/Edge 基础设施和安全策略，但由个人插件建立一条用途固定的
   Codex Remote proxy；不得改造 AI2Apps Desktop 的既有 Remote Mobile proxy，也不允许
   客户端选择 subdomain、remote port、local address 或任意上游。

## 2. 非目标

- 不向其他账户、Organization Member 或普通 AI2Apps 用户开放。
- 不成为 AI2Apps 通用远程管理、Terminal、文件或浏览器控制能力。
- 不由 Cloud 列出、读取、缓存或同步 Codex Project/Thread。
- 不允许 Cloud 代替本机批准 Codex 操作。
- 不监听或解析 iMessage 回复；iMessage 仅由本机发送状态提醒。
- 不把现有 Remote Mobile、Messager、Federation 或 Installation handoff assertion 改作
  Codex Remote assertion。

## 3. 账户门禁

Cloud 部署配置包含唯一的 `codexRemotePersonalAccountId`。部署工具首次根据规范化邮箱
`avdpro@me.com` 查出 Account ID，并要求查询结果恰好为一个；之后配置和数据库只保存
Account ID。

所有 Codex Remote 入口同时校验：

- 当前交互式登录 Account ID 等于目标 Account ID；
- Device 属于该 Account/Installation 且状态为 `active`；
- Device credential 版本、过期时间和 access epoch 有效；
- 功能总开关为启用状态；
- challenge、grant 和 Bridge 实例均未过期或撤销。

其他账户访问配对页时返回统一的不可用页面，API 返回稳定的 `404` 或通用 `403`，不得
泄漏目标邮箱、Account ID、Device 或功能开通状态。

## 4. 新鲜登录要求

扫码入口不得接受已有浏览器登录态作为最终证明。进入配对页后必须：

1. 清除或隔离本次流程使用的认证事务；
2. 强制显示登录界面并要求用户重新提交凭据；
3. 登录完成时产生 `auth_time`，且 challenge 兑换时距当前时间不超过 120 秒；
4. 登录账户不是目标 Account ID 时，流程失败且 challenge 不被消费；
5. 登录成功也不自动兑换，页面显示目标 Mac/Bridge 的非秘密名称并要求用户确认连接；
6. 密码、MFA、登录 Cookie 和恢复材料不得经过 FRP 或发送给 Local。

如 Cloud 认证栈支持 `prompt=login`、`max_age=0` 或等价机制，应使用认证栈的正式能力，
不得用前端隐藏 Cookie 或仅显示一个“继续”按钮来模拟重新登录。

## 5. Pairing challenge

### 5.1 创建

```http
POST /v1/codex-remote/pairing-challenges
Authorization: Device <deviceId>.<connectorSecret>
Content-Type: application/json

{
  "bridgeInstanceId": "cbr_<opaque>",
  "bridgeKeyFingerprint": "<canonical fingerprint>",
  "displayName": "<bounded local display name>"
}
```

Cloud 必须从 Device credential 推导 Account、Installation 和 Device，不接受请求自报这些
身份。响应：

```json
{
  "pairingId": "crp_<opaque>",
  "pairingUrl": "https://coder.ai2apps.com/codex-remote/pair#challenge=<one-time-code>",
  "expiresAt": "<RFC3339>",
  "revision": 1
}
```

要求：

- challenge 使用至少 192 bit CSPRNG 熵，Cloud 只保存带服务端 pepper 的不可逆摘要；
- 五分钟后过期，只能成功消费一次；
- secret 放在 URL fragment 中，避免进入常规 HTTP access log和 Referer；
- 插件在本地把 URL 渲染为 QR，Cloud 不需要保存 QR 图片；
- 每个 Device 最多 3 个 pending challenge，创建接口按 Device/Account/IP 限流；
- `displayName` 只用于确认页，长度和字符集受限并按纯文本转义。

### 5.2 兑换

确认连接后，Cloud 原子消费 challenge，并签发最长 120 秒的 EdDSA assertion，audience
固定为 `ai2apps-codex-remote-pair-v1`。claims 至少包含：

- `iss`、`aud`、`jti`、`iat`、`nbf`、`exp`、`auth_time`；
- 目标 Account ID；
- Installation ID、Device ID、Device access epoch；
- `bridgeInstanceId`、Bridge key fingerprint；
- `pairingId` 和 challenge revision；
- 新建的 `remoteGrantId`、grant revision；
- 固定 role `personal_admin`。

断言通过 URL fragment 返回至现有 Device public origin 的固定 Codex Remote completion
路径。Cloud 不允许调用方提供任意 redirect URI。Local 验证 Cloud JWKS、完整 claims、
本机 Device/Bridge/key 绑定、时间窗和 JTI 一次性消费后，才创建本地 HttpOnly Session。

## 6. 撤销 API 与状态机

### 6.1 作废未使用 QR/URL

```http
POST /v1/codex-remote/pairing-challenges/{pairingId}/revoke
Authorization: Device <deviceId>.<connectorSecret>
If-Match: "<revision>"
```

状态机：

```text
pending -> consumed
pending -> revoked
pending -> expired
```

`consumed`、`revoked` 和 `expired` 均为终态；重复 revoke 幂等返回当前状态。Local 插件
同时维护自己的 challenge 记录，并以本机状态为即时权威：用户点击作废后，即使 Cloud
暂时不可达，本机也立刻拒绝该 challenge 后续完成请求；Cloud 同步可重试。

### 6.2 断开单台已配对手机

```http
POST /v1/codex-remote/grants/{remoteGrantId}/revoke
Authorization: Device <deviceId>.<connectorSecret>
If-Match: "<revision>"
```

撤销后：

- 该 grant 不能续期或建立新 Remote Session；
- Local 在收到撤销投影后关闭对应 SSE/WebSocket，并删除本地 Session；
- 已到达 Local 但尚未提交给 Codex 的写请求必须拒绝；
- 已经提交给 Codex 的操作不得谎报为未提交，页面显示最终状态未知或实际结果。

### 6.3 全部断开

```http
POST /v1/codex-remote/bridges/{bridgeInstanceId}/revoke-all
Authorization: Device <deviceId>.<connectorSecret>
If-Match: "<bridge-revision>"
```

Cloud 原子增加 Bridge access epoch，撤销全部 pending challenge 和 active grant。插件也在
本地先增加 epoch、关闭全部连接，再调用 Cloud。旧 assertion、Cookie、grant 和断线重连
均因 epoch 不匹配失败。

## 7. 撤销投影

Local 每次建立会话和执行写操作前都检查本地 grant/epoch。Cloud 提供不含秘密的条件读取：

```http
GET /v1/codex-remote/devices/{deviceId}/projection
Authorization: Device <deviceId>.<connectorSecret>
If-None-Match: "<etag>"
```

投影只包含 Bridge revision、有效 grant ID/revision/expiry 和 revoked pairing ID 的短期窗口。
Local 至少每 60 秒刷新；Cloud 可选用现有 Device 控制通道发送只含 ID/revision 的刷新提示，
但提示本身不作为授权依据。

## 8. FRP 与页面边界

- 继续使用现有 AI2Apps FRPS 集群、TLS public origin、Edge 鉴权与 Device 信任根；不新增
  一套隧道产品或通用远程机制。
- 为插件签发用途固定、短期、可撤销的 `codex_remote` proxy lease。该 lease 只能把 Cloud
  分配的随机 public route 转发到固定 `127.0.0.1:47133`；Cloud 从注册过的 Bridge/Device
  推导 proxy name、route 和 upstream，客户端请求中的这些字段一律忽略或拒绝。
- 插件使用 Cloud 返回的受限 lease 启动自己的 `frpc` 子进程；不得读取、复用或修改
  AI2Apps Desktop 既有 frpc 配置、进程、connector secret 或 Remote Mobile proxy。
- lease 最长 10 分钟并支持无缝续租；Bridge/Device/grant/revoke-all 任一失效时停止续租，
  Edge 在 60 秒内移除 route。单个 Bridge 同时最多一条 active proxy lease。
- Cloud 必须提供以下接口，认证身份从已注册的 Device/Bridge credential 推导：

```http
POST /v1/codex-remote/bridges/{bridgeInstanceId}/proxy-leases
Authorization: Device <deviceId>.<connectorSecret>
Content-Type: application/json

{"localService":"codex-remote-v1"}
```

```json
{
  "leaseId": "crl_<opaque>",
  "expiresAt": "<RFC3339>",
  "publicOrigin": "https://<cloud-assigned-route>",
  "frpc": {
    "serverAddr": "<fixed FRPS host>",
    "serverPort": 7000,
    "proxyName": "<cloud-assigned opaque name>",
    "authToken": "<short-lived scoped secret>"
  }
}
```

`frpc` 配置不返回可变 local IP/port；插件固定补入 `127.0.0.1:47133`。Cloud 另提供
`POST .../proxy-leases/{leaseId}/renew` 与幂等 `.../revoke`。响应和日志不得包含长期 Device
connector secret。
- 页面不得取得 Device connector secret、Codex App Server socket/token 或本地管理 API key。
- QR/URL 只建立当前 Codex Remote grant，不授予其他 AI2Apps 管理能力。
- 页面 Session 使用 `Secure`、`HttpOnly`、host-only Cookie，固定 Path，`SameSite=Strict`，
  15 分钟闲置过期、最长 8 小时；批准操作还必须要求 session 最近 10 分钟内有用户活动。

## 9. 审计、隐私与错误

Cloud 仅记录：Account/Device/Installation/Bridge/grant/pairing 的 opaque ID，事件类型，状态，
时间，来源 IP 的现有安全摘要，错误码和 revision。禁止记录：

- challenge、完整 pairing URL、assertion、Cookie 或 Connector Secret；
- Thread 标题、ID、Prompt、回复、模型输出；
- 命令、cwd、文件路径、diff、工具输入输出、批准理由或批准决定正文；
- iMessage 地址或内容。

建议事件：`codex_remote.pairing.created|consumed|revoked|expired`、
`codex_remote.grant.created|revoked|expired`、`codex_remote.bridge.revoked_all`、
`codex_remote.auth.denied`。外部错误保持通用，详细原因仅进入无秘密安全审计。

## 10. 验收测试

1. `avdpro@me.com` 对应的冻结 Account ID 可在强制重新登录后完成一次配对。
2. 已有 Cloud Cookie 不能跳过重新登录，`auth_time` 超窗不能兑换。
3. 其他账户即使拿到完整 QR/URL 也不能消费，且响应不泄漏目标账户。
4. 同一 challenge 并发兑换只有一次成功。
5. 插件作废 pending QR 后，本机立即拒绝；Cloud 恢复后最终状态收敛为 revoked。
6. challenge 过期、篡改、重复使用、错误 Device/Bridge/key/audience 全部失败。
7. 撤销单个 grant 会关闭对应手机会话，但不影响其他仍有效 grant。
8. `revoke-all` 后所有旧 assertion、Session 和重连请求失败。
9. Device suspend/revoke、credential rotation、access epoch 变化都会使 Codex Remote 失效。
10. Cloud/Edge/FRPS/审计日志 canary 扫描确认没有 URL secret、assertion、Prompt、命令或批准正文。
11. FRP 断开与恢复不会复活已撤销 QR、grant 或 Bridge epoch。
12. 大量 Codex Project/Thread 不增加 Cloud 配对或页面登录负载；Thread 数据始终只在 Local
    按需分页读取。

## 11. Cloud 项目交付物

- 数据迁移和唯一 Account ID allowlist 配置；
- 配对、重新登录、兑换、单项撤销、全部撤销和投影 API；
- 独立 EdDSA audience、JSON Schema、JWKS 验证 fixture；
- 登录页和确认页；
- 单元、并发、重放、越权、撤销、FRP 与真实手机 E2E 测试；
- 无秘密审计、指标、限流与告警；
- Cloud commit、部署版本、OpenAPI 版本和回滚方案。
