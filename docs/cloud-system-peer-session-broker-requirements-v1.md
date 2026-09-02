# AI2Apps Cloud 系统级 Peer Session Broker 变更需求 V1

状态：交给 Cloud 项目实施

日期：2026-08-27

本文只定义 Cloud 变更需求。本地 AI2Apps/oMLX 仓库不得直接修改或部署 Cloud 代码。

## 1. 目标与边界

在现有 Messager Device Key、Peer Assertion、FRP Presence 和 System Message 上增加通用、短时、
purpose-bound 的 Peer 控制面，服务于 Messager 内容、Model Share 推理和后续 Checkpoint Piece。

Cloud 负责身份、发现、短期 Grant、Candidate、Presence、Feature Flag 和最小元数据，不保存或
处理 Message、Prompt、媒体、模型输出和 Checkpoint Piece 正文。

对 Messager 和 Model Share，Cloud/Local 必须共同保证传输透明：Direct P2P 是首选优化，FRP
C/S 是标准回退。Direct 建连失败不能直接变成业务失败；只有目标 Device/Provider 在两条路径
下都不可达，且无法重新撮合时，模型调用才失败，Messager 则使用 Offline Message。

FRP 回退不得改变 Compute Contract 已冻结的价格、资产、优先级或 Provider Net；Relay 成本由
系统 Rate Card、平台费和容量策略事前覆盖，不能在回退时要求 App 或用户二次确认价格。

## 2. API 需求

建议新增：

```text
POST   /v1/peer/device-keys/challenges
PUT    /v1/peer/device-keys/{protocol}
GET    /v1/peer/device-keys/{protocol}
POST   /v1/peer/sessions
POST   /v1/peer/sessions/{sessionId}/candidates
GET    /v1/peer/sessions/{sessionId}/candidates
POST   /v1/peer/sessions/{sessionId}/observations
DELETE /v1/peer/sessions/{sessionId}
GET    /v1/peer/jwks.json
```

Model Offer、Request、Contract 和 Lease 使用独立 `/v1/model-sharing/*` API，不能塞进 Broker。

创建 Session 请求示例：

```json
{
  "protocol": "ai2apps.messager/v2",
  "peerUserId": "...",
  "peerDeviceId": "...",
  "purposeId": "conversation-or-contract-id",
  "requestedTransports": ["direct_quic", "relay_https"],
  "clientNonce": "..."
}
```

响应包含 `sessionId/expiresAt/grant/self/peer/transportPolicy`。`transportPolicy` 至少冻结 Direct/
Relay 可用状态、最大 Bytes、最大 Streams 和 Policy Version。Messager/Model Share 的正常策略
必须提供 FRP 回退；路径选择由 Local Core 执行，不暴露给 App。

## 3. Grant 合同

必须绑定：

```text
iss / aud / sub / jti
session_id
protocol / protocol_version
purpose_id / purpose_type
initiator user/device/installation/access epoch/key id/key epoch
recipient user/device/installation/access epoch/key id/key epoch
allowed transports
max bytes / max streams
iat / nbf / exp
policy version
```

Audience 按协议分离。MessageGrant、JobGrant、DownloadGrant 不能互换。Grant/JWT 不落库，只保存
JTI/Hash 和 metadata-only 签发结果。

## 4. Candidate Broker

Candidate 只允许绑定的两个 Device 访问，字段严格限定为：

```text
candidate_id / session_id / device_id
type: lan | ipv6 | srflx | mapped | relay
transport: udp | tcp
address / port / priority / generation / expires_at
```

- TTL 60–120 秒，关闭或过期后立即不可读；
- 最长 10 分钟内物理清理；
- 不进入 System Message、普通 Audit Context 或长期分析表；
- 日志不得输出 address、port 或完整 Candidate；
- 禁止枚举其他 Session；
- 按 Device、User、Session 和来源 IP 共同限流；
- Observation 只保存路径类型、耗时、粗错误和协议版本。

## 5. 业务授权

Messager：当前有效好友；任一方向拉黑即拒绝新 Grant；选择 Primary 或用户指定 Device；Relay
由双方设置和平台 Policy 共同决定。

Model Share：必须有冻结的 Compute Contract 和唯一 CommitLease；Offer、Model/Revision、结算
模式和 Lease 匹配；Cloud 不接收 Prompt/媒体/输出；不存在 MCP/Agent/Service/Tool purpose。

Checkpoint：绑定签名 Distribution Manifest、Revision、许可和 Piece 范围；许可不允许再分发
时拒绝；禁止 Relay；独立 Feature Flag 开启后才签发。

## 6. Presence、System Message 与披露

Cloud 可保存在线状态、协议版本、Direct/Relay 能力布尔值、粗 NAT/网络分类、最近成功路径类型
和粗区域。不能公开真实设备名、精确地址、长期 IP、完整硬件或其他用户 Candidate。只有已撮合
且取得 Grant 的双方可读取本 Session 信息。`online=true` 必须基于当前 Heartbeat 和可用 Work
Connection，不能只因历史 NewProxy 成功。

System Message 只承载低频事件：Transfer offered/completed/failed，以及 Model Job committed、
started、progress、completed、failed 和 Artifact expiring。禁止包含正文、文件 Bytes、Session Key、
完整 Grant/Assertion、Candidate/IP 和 Noise/QUIC Frame。高频 Token、Chunk ACK、Keepalive 和
Candidate 只走 Peer Data Plane/Broker。

## 7. 数据模型与保留

建议表：

```text
peer_device_keys
peer_sessions
peer_session_candidates
peer_session_observations
```

- Device + Protocol 只能有一个 active static key；
- Session 控制记录最长保留 24 小时，之后只保留聚合统计；
- Candidate 最长保留 10 分钟；
- Observation 不含 IP、正文、文件名、模型输入或输出；
- Key Lifecycle 和撤销进入追加式 metadata-only 审计。

## 8. Relay Edge

- 只开放精确、版本化、方法受限 Endpoint，其他 Local API default deny；
- 不记录 Body、Authorization、Cookie、Grant 或密文；
- 按 Session、Device、User、协议、Bytes 和并发限流；
- Messager、Model Share 使用不同 Endpoint 和策略；
- Checkpoint 不开放 Relay；
- 提供区域/协议 Kill Switch 和平台 Relay Exposure 上限；
- Model Relay 必须保持文本、媒体、流式输出和 Artifact 的应用协议兼容；平台可以做带宽、并发、
  配额和成本控制，但不能让 Direct 失败本身成为业务错误。

## 9. 错误码与 Feature Flag

错误码至少包括：

```text
PEER_PROTOCOL_UNSUPPORTED
PEER_DEVICE_KEY_UNAVAILABLE
PEER_RELATIONSHIP_REQUIRED
PEER_PURPOSE_NOT_AUTHORIZED
PEER_SESSION_EXPIRED
PEER_SESSION_REVOKED
PEER_CANDIDATE_LIMIT_EXCEEDED
PEER_TRANSPORT_NOT_ALLOWED
PEER_RATE_LIMITED
PEER_POLICY_DISABLED
MODEL_SHARE_CONTRACT_INVALID
MODEL_SHARE_LEASE_INVALID
CHECKPOINT_REDISTRIBUTION_FORBIDDEN
```

响应不能泄露用户存在性、对方地址、Key Bytes、Candidate 或内部风控原因。

Feature Flag：

```text
peer_session_broker
peer_direct_quic
peer_relay_https_v2
messager_peer_v2
messager_peer_files
model_share_peer_v1
model_share_relay
checkpoint_peer_v1
```

每项支持全局、区域、协议版本和账户 Pilot；安全事件可立即撤销活动 Grant/Lease。

## 10. 验收交付物

- 两个 Device 只能访问自己的 Session/Candidate；
- 错误 Audience/Protocol/Purpose 在 Cloud 和 Local 都被拒绝；
- TTL、撤销、Key Rotation 和 Access Epoch 变化即时生效；
- Candidate、Grant、密文和正文不进入数据库、日志、Audit 或指标；
- FRP Edge 只允许精确 Endpoint/方法，其他路径 404；
- Presence 不把无 Work Connection 的 Device 标记为可连接；
- 三种业务 Grant 不能互换，重复请求全部幂等；
- Rate Limit/Kill Switch 在多实例部署一致；
- 交付 OpenAPI、JSON Schema、合法/负向 Fixture、Migration、Commit 和 Staging 验收记录。
