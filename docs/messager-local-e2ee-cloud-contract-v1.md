# Messager Local E2EE 与 Cloud 合同 v1

> Cloud 工程的可执行任务、冻结 API、数据库、JWT、错误码和验收清单见
> [`cloud-messager-peer-identity-implementation-v1.md`](cloud-messager-peer-identity-implementation-v1.md)。

## 1. 状态与目的

Cloud 合同已由 `ai2apps-cloud` commit
`28953f685ef1884b35d9a95d9036b07f246fb029` 实现，migration 为
`0030_puzzling_husk.sql`，OpenAPI 为 `1.19.0`，compatibility delta 为无；当前尚未发布生产。
客户端以 Cloud 的
`docs/messager-peer-identity-client-integration-v1.md`、JSON Schema 和 fixture vectors
为机器可验证的最终合同。本文前半保留最初的威胁模型和需求推导；若示例路径或字段与
OpenAPI 1.19.0 不同，以已冻结的 OpenAPI/fixture 为准。

本文记录 AI2Apps Messager 从“Cloud 离线消息首版”进入“Local 点对点端到端加密”前必须补齐的跨仓库合同。当前 Cloud Profile 只公开 `primaryNode.publicOrigin` 和 `online`，这两项只能证明节点可达性提示，不能证明该 URL、Local Device、消息身份公钥和目标 Cloud `userId` 属于同一主体。

客户端不得信任 FRP 端点返回的自声明公钥，也不得把现有 Remote Mobile、Installation member handoff 或 Federation assertion 改作消息认证。这些 token 的 audience、授权对象和权限语义均不同。

## 2. 最小 Cloud 能力

### 2.1 Device 消息密钥登记

Core Device 使用既有 Device credential 登记消息身份公钥：

```http
PUT /v1/remote/devices/{deviceId}/messager-key
Authorization: Device <deviceId>.<secret>
Content-Type: application/json

{
  "keyId": "msgk_<opaque>",
  "algorithm": "<reviewed-protocol-key-suite>",
  "publicKey": "<canonical-base64url>",
  "proof": "<proof-of-possession>"
}
```

Cloud 必须验证 Device credential、当前 Installation binding、Device 状态和 proof of possession。私钥只保存在 Local 系统安全存储中，不上传 Cloud。

密钥轮换或 Device revoke 必须使旧 key 立即不可用于新的握手。历史消息解密密钥是否保留由 Local 策略决定，Cloud 不托管。

### 2.2 好友定向的短期 Peer assertion

已登录发送方为一个当前好友请求目标节点证明：

```http
POST /v1/messager/peer-assertions
Content-Type: application/json

{ "recipientUserId": "<friend-user-uuid>" }
```

Cloud 只有在双方仍是好友、未屏蔽、目标 primary Device active 且已登记有效消息公钥时才签发。响应至少包含：

```json
{
  "assertion": "<compact-EdDSA-JWT>",
  "peer": {
    "userId": "<recipient-user-uuid>",
    "deviceId": "<target-device-uuid>",
    "publicOrigin": "https://device-<slug>.ai2apps.com",
    "keyId": "msgk_<opaque>",
    "algorithm": "<reviewed-protocol-key-suite>",
    "publicKey": "<canonical-base64url>"
  },
  "expiresAt": "<RFC3339>"
}
```

JWT 必须使用独立 audience，例如 `ai2apps-messager-peer-v1`，最长有效期不超过 120 秒，并绑定：

- issuer、audience、JWT ID、签发/生效/过期时间；
- 请求方 user ID；
- 目标 user ID、Device ID、Device access epoch；
- 目标 public origin、消息 key ID、算法和公钥指纹；
- friendship/relationship epoch 或等价的可撤销版本。

Local 接收端必须验证 Cloud 签名、完整 claims、目标是本机、时间窗、一次性 nonce/握手 ID 和当前关系状态。assertion 仅允许建立 Messager 会话，不能授予 Local membership、App、模型、工具、文件或计费权限。

## 3. Local 传输合同

公开端点使用独立版本路径，例如：

```text
POST /v1/messager/peer/v1/handshakes
POST /v1/messager/peer/v1/messages
GET  /v1/messager/peer/v1/messages/{clientMessageId}
```

具体握手和双向 ratchet 必须选择经过审查、有维护实现的 Noise/Signal 类协议后冻结；在选型完成前不自行拼装 X25519、HKDF 和 AEAD 成为自有协议。协议至少满足双向身份绑定、前向保密、重放防护、乱序/重复处理和密钥轮换。

FRP、反向代理和 Cloud 只能看到固定上限的密文、必要路由元数据和结果码。Local 日志及审计不得记录明文、附件内容、私钥、会话密钥或完整 assertion。

## 4. 降级规则

`primaryNode.online=false` 可直接判定没有当前 Local 候选；`online=true` 仍必须以实际解析、握手和发送结果为准。

只有下列明确结果允许进入 Cloud offline fallback：

- 没有 primary node 或有效消息公钥；
- Cloud 明确返回目标不可用/关系有效但无 Local transport；
- 建连在规定时间内未到达“请求可能已提交”阶段；
- 对端以稳定错误声明当前不支持或暂不可用。

若密文请求可能已提交但确认丢失，发送端必须使用相同 `clientMessageId` 查询或重试 Local，不能立刻向 Cloud 再发一份明文。只有 Local 返回确定的未接收结果后才能降级。

## 5. 必测安全场景

- FRP DNS/路由被替换时，因 assertion 中 origin、Device 和 key 指纹不匹配而失败；
- 自声明 key、过期 assertion、错误 audience、错误目标 Device、关系撤销和 epoch 变化均失败；
- 同一握手 nonce 和消息 ID 重放不产生第二条消息；
- Local 确认丢失时不触发 Local/Cloud 双发；
- Device revoke 或密钥轮换后不能建立新会话；
- 两个 Local 实例端到端测试证明 Cloud/FRP/审计记录中没有正文；
- Cloud 完全不可达时，已有有效短期会话的行为按冻结协议执行，不能无限延长 assertion。

## 6. 当前客户端行为

客户端已接入 OpenAPI 1.19.0 合同和 `noiseprotocol 0.3.1`：

- Ed25519/X25519 私钥按 Cloud Device 原子保存在 Local SecretBackend；challenge proof 严格使用 8 行加末尾 LF；
- peer assertion 使用独立 JWKS 验证 EdDSA、完整 claims、90 秒时间窗、response/key/origin/本机 Device 绑定；未知或轮换 kid 最多刷新 JWKS 一次；
- Local 公开入口为 `POST /v1/messager/peer/v1/handshakes` 与 `POST /v1/messager/peer/v1/messages`；
- Noise 协议固定为 `Noise_IK_25519_ChaChaPoly_SHA256`，`handshakeId` 写入 prologue，`jti` 与 handshake ID 写入双向握手 payload；responder 将 Noise 恢复出的 initiator static key 与 assertion 公钥绑定；
- assertion JTI 和 handshake ID 在 SQLite v38 中一次性消费，消息按 owner、peer、`clientMessageId` 去重；
- 在线文本优先 Local E2EE。建连在正文提交前明确失败时才允许 Cloud offline fallback；正文可能已提交但 ack 丢失时写为 `result_unknown`，不降级、不自动重发；
- 首版 Local E2EE 仅支持文本。在线时选择图片会 fail closed；离线图片继续使用既有 Cloud 两阶段附件合同。

尚待完成的验收项是以两套真实 Local Installation、Cloud 本地环境和 FRP 映射执行双实例联调，覆盖关系撤销、屏蔽、Device/key 轮换、结果未知及 Cloud/FRP/审计无正文检查。
