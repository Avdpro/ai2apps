# AI2Apps Account 与 Messager 开发计划 v1

系统级 P2P、Messager 文件传输和 Model Share 共用数据面的后续方案见
[`ai2apps-system-peer-transport-development-plan-v1.md`](ai2apps-system-peer-transport-development-plan-v1.md)。

## 1. 目标

本轮按两个连续阶段交付：

1. 重构 Account App 的信息架构，把现有能力按栏目组织，降低单页堆叠和误操作风险；
2. 开发第一版 Messager App，以 Local 节点间的端到端加密通信为主，只有 Local 通道不可用时才使用 Cloud System Message 作为离线兜底。

实现期间不得削弱既有身份、权限、复验、设备、成员、组织策略、配额和审计边界。Cloud 社交关系只用于发现和消息准入，不能替代 Local 的 `core/member/guest`、Session、Capability 或 App 授权。

## 2. 已确认的产品边界

### 2.1 Account

Account 管理“我是谁、我如何登录、我在当前 Local 上的身份、我的设备和组织管理权限”。好友对话和消息历史不进入 Account。

首轮信息架构：

- Overview：Cloud 身份、级别、积分、权益和容量摘要；
- Devices：Cloud Device、主要 Device（接入新 Profile API 后）、Remote connector、手机配对和流量；
- Members & Policy：成员、邀请、角色、成员配额和组织策略；
- Security：当前 Local principal、成员 handoff、退出、Owner 密码复验和管理员 step-up；
- Activity：积分 ledger；后续如 Cloud 提供面向用户的安全审计查询，再加入独立审计视图，不能用 ledger 冒充安全审计。

未登录时继续直接展示注册、登录、邮箱验证和密码重置流程，不让栏目导航阻挡身份恢复。

### 2.2 Messager

Messager 以统一会话 UI 承载两种 transport：

- `local_e2ee`：优先通道。两端 Local Messager 通过对方 Cloud 返回的 `primaryNode.publicOrigin` 建立连接；FRP 负责可达性，消息正文必须在应用层端到端加密；
- `cloud_offline`：仅在 Local 通道明确不可用时使用。v1 Cloud 合同会保存可读正文，不得在 UI 中标记为端到端加密或“安全私聊”。

`primaryNode.online` 只是最近 heartbeat 提示，不能单独决定降级。客户端必须实际尝试 Local 连接，并处理请求已成功但确认丢失的状态。

## 3. Account 功能保留清单

以下既有能力在重构前建立回归基线，重构后必须全部存在并保持服务端授权语义：

### 身份与会话

- Cloud 注册、登录和退出；
- 邮箱 8 位验证码验证和重新发送；
- 密码重置申请和重置确认；
- Cloud Session 恢复；
- 当前 Local principal 展示；
- 一次性 member handoff exchange；
- Local member 退出；
- 已登记 Cloud member 激活；
- 未登记、inactive、member 和 manager 状态区分；
- 密码、handoff、grant 和 Session 不进入 `localStorage`。

### 高风险操作与审计边界

- 撤销 Device 前的 Owner 密码复验；
- 修改 Organization Policy 前的 Owner 密码复验；
- 修改成员角色前的 Owner 密码复验；
- 修改成员配额前的 Owner 密码复验；
- Cloud admin step-up verification 及有效期展示；
- 一次性复验 grant 继续由 Local/Cloud bridge 使用，前端不得持久化；
- UI 重组不得绕过服务端角色、policy version/ETag 或复验检查；
- 日志、错误提示和前端状态不得保存密码、Cookie、connector secret 或一次性 token。

### 管理能力

- Cloud Device 列表、重命名、状态和永久撤销；
- Remote Device 注册、启动、停止、credential rotation、重新登记；
- 手机 pairing challenge、二维码、复制和系统分享；
- Organization Policy 查看与修改；
- 成员邀请、邮件投递状态、重发、取消及 pending 列表；
- 成员角色、暂停、恢复、移除；
- 成员月度点数与并发配额；
- Account level、subscription、设备/席位容量；
- Points、entitlements 和 ledger；
- Core 用户的 Local UI language 设置。

## 4. Account 实施步骤

1. 为现有模板增加栏目导航和响应式布局，不修改原 API 路径和危险操作处理函数；
2. 用 Alpine `activeSection` 控制栏目显示，隐藏无权访问的管理栏目；
3. 提供 hash 深链与刷新后的安全默认栏目，但不在浏览器持久化账户状态；
4. 把高风险操作放在清晰的 Security 或对应管理栏目中，保留密码复验说明；
5. 加入模板合同测试，逐项断言注册、验证、重置、handoff、Owner 复验和 admin step-up 未丢失；
6. 运行 Account、Cloud client、Remote、Shell 和本地化测试；
7. 浏览器检查桌面与窄屏布局、键盘导航、错误和 loading 状态。

## 5. Messager v1 架构

### 5.1 模块

- `MessagerStore`：会话列表、消息分页和聚合状态；
- `SocialStore`：好友、申请、Relationship 与屏蔽状态；
- `PeerResolver`：从 Cloud Profile 获取 `userId` 和服务端返回的 `primaryNode.publicOrigin`；
- `LocalMessagerTransport`：Local endpoint 发现、对端认证、加密会话和消息确认；
- `CloudOfflineTransport`：System Message 文本与单图的两阶段兜底；
- `SystemInboxStore`：未读数、系统消息、已读和归档；
- `MessageRepository`：按 Local principal 隔离的会话、消息、投递尝试和去重状态。

### 5.2 稳定身份与消息 ID

- 用户关系和会话以 Cloud `userId` 为主键，邮箱和 handle 只用于查找；
- 每次逻辑发送生成稳定 UUID `clientMessageId`；
- Local 重试与 Cloud 幂等重试复用同一逻辑 ID；
- 接收端按 sender user/device、conversation 和 message ID 去重；
- transport attempt 使用独立 attempt ID，不能把一次网络尝试当成一条新消息。

### 5.3 发送状态机

```text
draft -> queued -> resolving_peer -> connecting_local -> sending_local
                                                   |-> sent_local
                                                   |-> local_unavailable
local_unavailable -> sending_cloud -> sent_cloud | result_unknown | failed
```

只有明确不可达、受支持的超时结论或无可用 Local endpoint 才进入 Cloud fallback。如果 Local 请求可能已提交但确认丢失，必须先使用稳定消息 ID 查询/重试并消除重复风险；不能立即双发。

### 5.4 Local 安全合同

在实现正文传输前先确定并测试：

- Local Messager capability endpoint 和版本协商；
- 对端 user/device identity 的可验证证明；
- 好友关系检查与撤销后的会话失效；
- 成熟协议支持的握手、密钥派生、前向保密和重放防护；
- 密钥保存在系统安全存储或受保护的 Local secret store，不进入网页存储；
- FRP、Cloud、日志和审计只能看到必要元数据，不能看到 Local 消息正文或密钥；
- 安全审计只记录 sender/recipient 的稳定匿名或授权身份、transport、结果、时间和关联 ID，不记录正文与附件。

不自行设计密码学。v1 在确定现有身份密钥条件后选择经过审查的 Noise/Signal 类协议和库。

### 5.5 Cloud 离线兜底

- 仅好友可发送，关系变化后刷新 Relationship；
- 正文不超过 4,000 字符；
- 图片只接受 PNG/JPEG/WebP、最大 2 MiB 和最大 8,192×8,192；
- 上传任务保存 `attachmentId/expiresAt`，绑定发送复用同一 `clientMessageId`；
- 带图响应丢失且附件变为不可用时显示“发送结果未知”，不自动重新上传重复发送；
- 私有附件使用带 Session 的 fetch 转 Blob，组件销毁时 revoke object URL；
- Cloud 消息在 UI 中明确标记为离线兜底且不是 E2E。

## 6. Messager v1 交付切片

1. 注册 `ai2apps.messager` System App、路由、导航、权限和中英文文案；
2. 建立本地会话/消息存储 schema、principal 隔离和去重约束；
3. 接入 Cloud Profile、公开 Profile、Social Relationship、好友与申请；
4. 完成会话列表、好友选择和文字对话 UI；
5. 定义并实现 Local Messager discovery/authentication/encryption transport；
6. 完成 Local-first 文本消息、确认、重试和断线状态；
7. 接入 System Inbox 和 Cloud 纯文字 offline fallback；
8. 将收到的 `user.offline_message` 合并进对应本地会话；
9. 加入单图片上传、私有下载和结果未知状态；
10. 完成双 Local 实例、Local 离线、关系撤销、重复请求和安全日志测试。

## 7. 首版验收标准

### Account

- 桌面和窄屏均按栏目展示，不再是单页连续堆叠；
- 不同角色只能看到可用栏目，但服务端仍是最终授权者；
- 本文第 3 节的所有能力均有模板合同或 API 回归覆盖；
- 注册、邮箱验证、密码重置、member handoff、Owner 复验和 admin step-up 可用；
- 任何 password、Cookie、grant、connector secret 均不被持久化或写入日志。

### Messager

- 好友可创建会话，非好友、自身、屏蔽和失效用户被正确拒绝；
- 对端 Local 可用时只走 Local E2E transport；
- 对端 Local 明确不可用时才走 Cloud fallback；
- 同一逻辑消息不会因重试或 transport 切换重复展示；
- UI 明确区分 Local E2E 与 Cloud offline；
- Cloud 未使用时现有 Local Apps、Remote Device、模型和账户能力不受影响；
- 双实例测试证明正文不进入 FRP/Cloud 日志和元数据审计。

## 8. 暂不承诺

- Cloud 会话线程、typing、presence、reaction、编辑、撤回、送达或对方已读回执；
- 多附件或任意文件；
- 以 Cloud 好友关系授予 Local membership、模型、工具、文件或其他 App 权限；
- 在当前 Cloud plaintext offline 合同上宣称端到端加密；
- 未经安全设计评审的多设备密钥同步和历史消息漫游。

## 9. 变更与验证记录

每个交付切片记录：源 commit、修改文件、迁移、测试命令与结果、安全边界变化、已知限制和下一步。涉及身份、复验、加密、密钥、日志或审计的变更必须单独列出，不能混在纯 UI 说明中。

### 2026-08-23：Account 栏目化与 Messager App shell

- 源 commit：`66736cca`，分支 `experiment/moe-cache`；
- Account 已增加 Overview、Devices、Members & Policy、Security、Activity 栏目；
- 原注册、登录、邮箱验证、密码重置、member handoff、Owner 复验和 admin step-up DOM/API 路径全部保留；
- Account 已接入 Profile、主要 Device 与社交链接 Local facade 和表单；
- Messager 已注册为 user singleton System App，首个 UI 切片包含好友查询/申请、好友列表、系统消息箱和 Cloud 离线文字消息；
- Cloud offline 的 Local audit 只记录 actor、installation、recipient、clientMessageId 和 transport，不记录正文；
- 在线好友的 Local E2E transport 尚未具备可审计的身份握手合同，因此当前 fail closed：不发送，也不静默降级到 Cloud；
- 完整 Local E2E 的下一前置项是确定“Cloud Profile userId ↔ Local Device ↔ 消息身份公钥”的可验证绑定与撤销合同，不能仅信任 FRP URL 返回的自声明 key；
- 定向 Shell/extension/Cloud 回归通过；真实 Local UI 启动在当前执行环境因 Metal device 不可用而无法完成，未绕过该运行时限制。

### 2026-08-23：Messager 本地消息账本与离线闭环

- 数据库 schema 升级到 v36，增加按 Local principal 隔离的 conversation/message 表；
- Cloud 入站按 `(ownerUserId, remoteMessageId)` 去重，Cloud 出站按 `(ownerUserId, clientMessageId)` 去重；
- Cloud offline 成功响应写入本地会话，System Inbox 中的 `user.offline_message` 自动合并到本地历史；
- UI 在正文未改变时复用同一 `clientMessageId`，避免网络结果不确定后的重复发送；
- 增加本地只读会话/消息 API，服务端从可信 principal 注入 owner，客户端不能指定或覆盖 owner；
- 入站/出站安全审计只保存参与者、消息 ID、transport 等元数据，不保存正文；
- Messager、Cloud facade、Shell 的 124 项定向回归通过，另有 4 项数据库迁移回归通过；完整 storage 文件会触发 MLX 导入，并在当前无 Metal 的沙箱中中止；
- Local E2EE 的 Cloud 身份与密钥绑定缺口已形成独立合同草案：`docs/messager-local-e2ee-cloud-contract-v1.md`。
- Account、Remote、Cloud、Shell、本地化与 Messager 的 194 项联合回归通过；Ruff、Account/Messager JavaScript 语法检查和 `git diff --check` 通过。

### 2026-08-23：Cloud offline 单图附件

- 数据库 schema 升级到 v37，本地消息只保存附件 ID、媒体类型、大小、尺寸与私有 content path，不保存图片字节；
- Local facade 支持单文件 multipart 上传，先执行 2 MiB 硬上限，再交由 Cloud 做 magic-byte、媒体类型和尺寸权威验证；
- 私有下载由 Local 使用当前 Cloud Session 代理，响应强制 `private, no-store`、`nosniff` 和限制性 CSP，并再次限制为 PNG/JPEG/WebP 与 2 MiB；
- Messager composer 支持 PNG/JPEG/WebP 预览、移除、图片-only 消息，以及上传后复用相同 attachment/client message ID；
- 若可能已成功的带图发送重试返回 `SYSTEM_MESSAGE_ATTACHMENT_NOT_AVAILABLE`，UI 显示“发送结果未知”，不会自动重新上传或生成新消息 ID；
- 会话切换和页面卸载均回收 Blob object URL；图片不进入 `localStorage` 或公共 URL；
- 附件、幂等、私有下载与 Messager UI 的 15 项定向测试通过。
- 加入附件后，Account、Remote、Cloud、Shell、本地化与 Messager 的联合回归扩大为 198 项并全部通过；4 项数据库 bootstrap/migration 回归通过。

### 2026-08-23：Cloud 工程交接

- 将身份与密钥绑定草案细化为 Cloud 可直接实施的任务文档：`docs/cloud-messager-peer-identity-implementation-v1.md`；
- 冻结 Device key challenge/登记/查询、peer assertion 和 JWKS API；
- 冻结 Noise IK v1 key suite、登记 proof 字节合同、JWT audience/claims/90 秒 TTL、稳定错误码及审计红线；
- 给出 Drizzle/PostgreSQL 数据模型、轮换/stale/revoke 语义、OpenAPI/Schema/fixture 产物和 Cloud 测试矩阵；
- Cloud 完成后需提供 commit、migration、OpenAPI、JSON Schema、fixture、staging 地址和 compatibility delta，客户端再开始 verifier 与双 Local transport 联调。

### 2026-08-23：Cloud 合同接入与 Local E2EE 首版

- 已核对 Cloud commit `28953f685ef1884b35d9a95d9036b07f246fb029`、migration `0030_puzzling_husk.sql`、OpenAPI 1.19.0、实现文档、Schema 和合法/负向 fixture；compatibility delta 为无，生产尚未部署；
- 新增 `noiseprotocol>=0.3.1,<0.4`，协议固定为 `Noise_IK_25519_ChaChaPoly_SHA256`，没有自行拼装密码学原语；
- 每个 Cloud Device 的 Ed25519 身份私钥和 X25519 static 私钥以单个原子 key bundle 保存在命名隔离的 SecretBackend，数据库、网页状态和审计均不保存私钥；
- 完成 challenge proof、Device key 登记/恢复、EdDSA JWT/JWKS 严格 verifier，以及 Cloud response、key fingerprint、origin、Installation/Device/access epoch 的绑定校验；
- 新增独立公共 peer ingress，Noise prologue 绑定 handshake ID，握手 payload 双向绑定 assertion JTI；responder 校验 Noise 恢复出的 initiator static key；
- 数据库 schema 升级到 v38，持久化一次性 assertion JTI/handshake ID replay 防护；Local 入站按 `(ownerUserId, peerUserId, clientMessageId)` 幂等去重；
- Messager 在线纯文本现已调用 Local E2EE；只有正文提交前的明确不可达/Cloud 权威不可用结果可进入 Cloud fallback。正文发送后 ack 丢失落为 `result_unknown`，不会 Cloud 双发；
- 首版图片仍仅支持 Cloud offline。好友在线时图片 fail closed，等待后续附件分块 E2EE 协议；
- 当前新增身份、fixture、Noise、replay、repository、public ingress 与 Shell 定向测试 15 项通过；storage 非生命周期测试 16 项通过；Ruff、JSON、JavaScript syntax 和 `git diff --check` 通过；
- 两个 FastAPI/oMLX 生命周期测试仍因当前沙箱没有 Metal Device 在导入 MLX 时中止，与本轮 Messager 代码无关；真实双 Installation + 本地 Cloud + FRP 联调仍是发布前门禁。
