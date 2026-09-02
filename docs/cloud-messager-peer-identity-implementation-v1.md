# AI2Apps Cloud：Messager Peer Identity 实施任务 v1

状态：交 Cloud 工程实施与联调  
日期：2026-08-23  
调用方：AI2Apps Local / `ai2apps.messager`

## 1. 交付目标

Cloud 需要为 Local-first Messager 提供一个独立、用途受限、可撤销的身份合同，使发起方 Local 能验证：

1. 当前 Cloud 用户与对方仍是好友且双方未互相屏蔽；
2. 对方选中的 primary Device、FRP `publicOrigin` 和 Messager 公钥属于同一个有效 Cloud Device；
3. 发起方用户、当前 Device 和发起方 Messager 公钥也由 Cloud 绑定；
4. 一份短期 assertion 只可用于指定双方和指定握手，不能变成 Local membership、Remote Mobile、Federation、模型、工具、文件或计费授权。

这项交付不负责转发消息正文，不保存会话、密文、附件或 Local 状态，也不改变现有 System Message 离线兜底接口。

## 2. 不可复用的现有 token

以下 audience 均不得接受为 Messager peer 身份：

- `ai2apps-remote-mobile-v1`；
- `ai2apps-installation-member-v1`；
- `ai2apps-federation-relay-v1`。

Messager 使用独立 audience、独立 claims schema 和显式 validator。即使底层复用现有 Ed25519 signer/JWKS 轮换机制，也不能使用“接受多个 audience”的通用验证器。

## 3. 固定密码套件与编码

Cloud v1 只登记和签发下列 suite：

```text
noise_ik_25519_chachapoly_sha256_v1
```

每个 Device 登记两把公钥：

- `identitySigningPublicKey`：Ed25519 raw public key，32 bytes；
- `staticDhPublicKey`：X25519 raw public key，32 bytes。

两者在线路上均使用无 padding 的 canonical base64url，解码后必须恰好 32 bytes。Cloud 不生成、不接收、不托管任何私钥。

Ed25519 key 用于登记 proof of possession，并在后续 Local 握手中绑定 Noise static DH key。实际 Noise 握手、会话密钥和 ratchet 均由 Local 实现；Cloud 不参与密码协商。

## 4. 数据库迁移

建议增加两张表；命名可遵循 Cloud 现有 Drizzle 风格，但约束语义必须一致。

### 4.1 `messager_device_key_challenges`

```text
id uuid primary key
device_id uuid not null references remote_devices(id) on delete restrict
nonce_digest bytea not null
access_epoch bigint not null
expires_at timestamptz not null
consumed_at timestamptz null
created_at timestamptz not null
```

- challenge plaintext 只返回一次；数据库只保存 keyed digest 或 SHA-256 digest；
- TTL 为 300 秒；
- 成功登记必须在同一事务内消费 challenge；
- 过期、已消费、Device 不匹配和 access epoch 不匹配均不可复用。

### 4.2 `messager_device_keys`

```text
id uuid primary key
device_id uuid not null references remote_devices(id) on delete restrict
suite text not null
identity_signing_public_key bytea not null
identity_signing_fingerprint_sha256 text not null
static_dh_public_key bytea not null
static_dh_fingerprint_sha256 text not null
key_epoch bigint not null
device_access_epoch bigint not null
status text not null check status in ('active','rotated','revoked','stale')
created_at timestamptz not null
updated_at timestamptz not null
retired_at timestamptz null
```

必须有：

- 每个 Device 最多一条 `status='active'` 的 partial unique index；
- `(device_id, key_epoch)` unique；
- 两个 fingerprint 均为 raw 32-byte key 的小写 hex SHA-256；
- `key_epoch` 从 1 开始，只增不减；
- 相同 Device、access epoch、suite 和两把相同公钥的重试幂等返回当前记录，不增加 epoch；
- 不同公钥的登记在一个事务内把旧 active key 标记为 `rotated`，再创建新 key；
- Device revoke/suspend 后不能签发 assertion；revoke 应把 active key 标记为 `revoked`；
- Device credential rotation 导致 `accessEpoch` 变化后，旧 key 视为 `stale`，Local 必须重新登记。不要自动把旧 key 绑定到新 epoch。

不要把公钥放进 `user_profiles` 或公开 Profile 响应。公钥只向通过授权的当前好友返回。

## 5. Device key API

以下接口全部使用既有：

```http
Authorization: Device <deviceId>.<secret>
```

Cloud 必须从 credential 得到 Device，不接受请求体或路径覆盖 authenticated Device ID。

### 5.1 创建一次性登记 challenge

```http
POST /v1/messager/device-key-challenges
Authorization: Device <deviceId>.<secret>
```

成功：

```http
201 Created
Cache-Control: no-store

{
  "challengeId": "<uuid>",
  "challenge": "<32-random-bytes-base64url>",
  "deviceId": "<authenticated-device-uuid>",
  "accessEpoch": 7,
  "expiresAt": "2026-08-23T12:05:00.000Z"
}
```

每 Device 最多每分钟 6 次，额外使用现有全局 Device credential rate limit。

### 5.2 登记或轮换 key

```http
PUT /v1/messager/device-key
Authorization: Device <deviceId>.<secret>
Content-Type: application/json

{
  "challengeId": "<uuid>",
  "suite": "noise_ik_25519_chachapoly_sha256_v1",
  "identitySigningPublicKey": "<base64url-32-bytes>",
  "staticDhPublicKey": "<base64url-32-bytes>",
  "proof": "<base64url-ed25519-signature-64-bytes>"
}
```

proof 对以下 UTF-8 字节签名；字段之间是单个 LF，结尾也有 LF，不做 JSON canonicalization。等价 TypeScript 构造必须是：

```ts
const proofPayload = Buffer.from([
  "ai2apps-messager-device-key-registration-v1",
  challengeId,
  challenge,
  authenticatedDeviceId,
  String(currentAccessEpoch),
  "noise_ik_25519_chachapoly_sha256_v1",
  identitySigningPublicKey,
  staticDhPublicKey,
].join("\n") + "\n", "utf8");
```

Cloud 使用请求中的 Ed25519 public key 验证 proof。验证成功只能证明 signing private key 的 possession；X25519 private key 的 possession 由后续 Noise IK 握手验证。proof 将两把公钥绑定，不能替换其中一把后复用。

首次登记返回 `201`，幂等重试和轮换返回 `200`：

```json
{
  "keyId": "<uuid>",
  "deviceId": "<uuid>",
  "suite": "noise_ik_25519_chachapoly_sha256_v1",
  "identitySigningPublicKey": "<base64url>",
  "identitySigningFingerprintSha256": "<64-lowercase-hex>",
  "staticDhPublicKey": "<base64url>",
  "staticDhFingerprintSha256": "<64-lowercase-hex>",
  "keyEpoch": 1,
  "deviceAccessEpoch": 7,
  "status": "active",
  "createdAt": "<RFC3339>",
  "updatedAt": "<RFC3339>"
}
```

所有成功和错误响应均 `Cache-Control: no-store`。

### 5.3 查询当前登记

```http
GET /v1/messager/device-key
Authorization: Device <deviceId>.<secret>
```

- 当前 key 有效时返回上面的完整对象；
- 没有 key 返回 `404 MESSAGER_DEVICE_KEY_NOT_REGISTERED`；
- key 的 access epoch 已过期返回 `409 MESSAGER_DEVICE_KEY_STALE`，不得把 stale key 当 active 返回。

该接口用于 Local 重启时比较安全存储中的 key，避免无意义轮换。

## 6. Peer assertion API

### 6.1 认证

```http
POST /v1/messager/peer-assertions
Authorization: Device <deviceId>.<secret>
X-AI2Apps-Actor-User-Id: <current-local-principal-user-uuid>
X-AI2Apps-Membership-Epoch: <positive-integer>
Content-Type: application/json
```

Cloud 必须复用 Installation principal 的现有构造与校验：authenticated Device active、Installation binding active、actor 是该 Installation 的 active member、membership epoch 和 access epoch 精确匹配。请求体不能提供或覆盖 actor、Device、Installation、organization、role、billing identity 或 epoch。

### 6.2 请求

```json
{
  "recipientUserId": "<friend-user-uuid>",
  "handshakeId": "<sender-generated-uuid>"
}
```

`handshakeId` 由 Local 为一次逻辑握手生成，网络重试保持不变。Cloud 不需要持久化 assertion，但相同 Device、actor、recipient 和 handshake ID 在 assertion 有效期内应返回语义等价结果；若实现缓存，缓存不得超过 JWT expiration。

每 user/device 对每分钟最多 30 次；429 使用现有标准错误 envelope 和 `Retry-After`。

### 6.3 权威查询与拒绝顺序

在一个一致性读或事务快照中验证：

1. initiator Device、Installation principal 和 initiator active Messager key；
2. recipient user 存在且 active，且不是 initiator；
3. `social_friendships` 中当前 pair 存在；
4. 任一方向均不存在 `social_blocks`；
5. recipient `user_profiles.primary_public_device_id` 存在；
6. recipient Device active，仍归 recipient 所有，并具有 active、非 stale Messager key；
7. authoritative `publicOrigin` 从 recipient Device 的 `publicSlug` 派生，不接受数据库外 URL 或请求体 URL；
8. `online` 使用现有 Remote proxy lease/heartbeat 规则计算，不能由调用方提供。

如果关系在签名之前变化，整个签发失败。已经签发的 assertion 最多存活 90 秒；v1 接受关系撤销最多 90 秒的有界传播延迟，不引入每次握手 Cloud introspection。

### 6.4 成功响应

```http
201 Created
Cache-Control: no-store

{
  "assertion": "<compact-EdDSA-JWT>",
  "handshakeId": "<same-uuid>",
  "expiresAt": "<RFC3339>",
  "self": {
    "userId": "<actor-user-uuid>",
    "deviceId": "<authenticated-device-uuid>",
    "installationId": "<uuid>",
    "accessEpoch": 7,
    "keyId": "<uuid>",
    "keyEpoch": 3,
    "suite": "noise_ik_25519_chachapoly_sha256_v1",
    "identitySigningPublicKey": "<base64url>",
    "staticDhPublicKey": "<base64url>"
  },
  "peer": {
    "userId": "<recipient-user-uuid>",
    "deviceId": "<primary-device-uuid>",
    "installationId": "<uuid>",
    "accessEpoch": 11,
    "publicOrigin": "https://device-<32-hex>.ai2apps.com",
    "online": true,
    "keyId": "<uuid>",
    "keyEpoch": 5,
    "suite": "noise_ik_25519_chachapoly_sha256_v1",
    "identitySigningPublicKey": "<base64url>",
    "staticDhPublicKey": "<base64url>"
  }
}
```

`online=false` 仍可返回 assertion；它只是最近 heartbeat 提示。客户端可直接选择 Cloud offline，也可以做一次有界 Local 尝试。没有 primary Device 或有效 peer key 时不返回 assertion，而是返回下述稳定错误。

## 7. JWT 冻结合同

### 7.1 Header 与时间

```text
alg = EdDSA
typ = JWT
iss = ai2apps-cloud
aud = ai2apps-messager-peer-v1
default lifetime = 90 seconds
maximum lifetime = 90 seconds
nbf = iat - 5 seconds
maximum verifier clock skew = 30 seconds
```

JWKS：

```http
GET /v1/messager/jwks.json
Cache-Control: public, max-age=300, stale-if-error=3600
```

可以复用当前 Remote signer 的部署 key 和轮换集合，但必须通过上述独立 endpoint 暴露，并添加独立 `signMessagerPeer` 与 claims validator。

### 7.2 Claims

```json
{
  "iss": "ai2apps-cloud",
  "aud": "ai2apps-messager-peer-v1",
  "sub": "<initiator-user-uuid>",
  "jti": "<uuid>",
  "iat": 1787460000,
  "nbf": 1787459995,
  "exp": 1787460090,
  "handshake_id": "<uuid>",
  "initiator_user_id": "<same-as-sub>",
  "initiator_device_id": "<uuid>",
  "initiator_installation_id": "<uuid>",
  "initiator_access_epoch": 7,
  "initiator_key_id": "<uuid>",
  "initiator_key_epoch": 3,
  "initiator_identity_signing_key_sha256": "<64-lowercase-hex>",
  "initiator_static_dh_key_sha256": "<64-lowercase-hex>",
  "recipient_user_id": "<uuid>",
  "recipient_device_id": "<uuid>",
  "recipient_installation_id": "<uuid>",
  "recipient_access_epoch": 11,
  "recipient_key_id": "<uuid>",
  "recipient_key_epoch": 5,
  "recipient_identity_signing_key_sha256": "<64-lowercase-hex>",
  "recipient_static_dh_key_sha256": "<64-lowercase-hex>",
  "recipient_public_origin": "https://device-<32-hex>.ai2apps.com",
  "friendship_pair_key_sha256": "<64-lowercase-hex>"
}
```

`friendship_pair_key_sha256` 为 canonical `min(userId):max(userId)` UTF-8 字节的 SHA-256，只用于把签发审计关联到被验证的关系，不作为 Local authority。

Local verifier 将：

- 只接受上述 `alg/typ/iss/aud`；
- 验证 `sub == initiator_user_id`、全部 UUID、时间和最大 lifetime；
- 验证响应 `self/peer` 与 claims 中 Device、Installation、access epoch、key ID、key epoch、origin 完全一致；
- 对响应中的 raw public key 重新计算 SHA-256 并与 claims 比较；
- 发起端验证 `self.deviceId` 是本机，接收端验证 `recipient_device_id` 是本机；
- 接收端缓存已接受的 `(jti, handshake_id)` 直到 `exp + clockSkew`，拒绝重放；
- 不从 assertion 创建 Local session、member 或 capability grant。

## 8. 稳定错误码

所有错误沿用 Cloud 标准 envelope，包含 `requestId` 和 `retryable`，客户端只按 code 分支。

| HTTP | code | retryable | 说明 |
| --- | --- | --- | --- |
| 400 | `MESSAGER_KEY_FORMAT_INVALID` | false | suite、base64url、key 长度、proof 长度或请求字段非法 |
| 400 | `MESSAGER_SELF_PEER_NOT_ALLOWED` | false | recipient 是 actor 自身 |
| 401 | 现有 Device auth code | false | credential 无效；不要增加可枚举差异 |
| 403 | `MESSAGER_FRIEND_REQUIRED` | false | 当前不是好友；随后刷新 Relationship |
| 404 | `MESSAGER_KEY_CHALLENGE_INVALID` | false | challenge 不存在或不属于当前 Device，统一响应 |
| 404 | `MESSAGER_PEER_NOT_FOUND` | false | recipient 不存在/inactive/发生屏蔽，统一响应 |
| 404 | `MESSAGER_DEVICE_KEY_NOT_REGISTERED` | false | 查询当前 Device key 时没有登记 |
| 409 | `MESSAGER_KEY_CHALLENGE_EXPIRED` | false | challenge 已过期 |
| 409 | `MESSAGER_KEY_CHALLENGE_REPLAYED` | false | challenge 已消费 |
| 409 | `MESSAGER_KEY_PROOF_INVALID` | false | proof 验证失败 |
| 409 | `MESSAGER_DEVICE_KEY_STALE` | false | key 的 Device access epoch 已变化 |
| 409 | `MESSAGER_INITIATOR_KEY_UNAVAILABLE` | false | 当前 Device 没有有效 active key |
| 409 | `MESSAGER_PEER_KEY_UNAVAILABLE` | false | 好友没有 primary Device 或有效 active key；允许 Cloud offline fallback |
| 429 | 现有 rate-limit code | true | 保留 handshake ID 后退避 |
| 503 | `MESSAGER_ASSERTION_SIGNER_UNAVAILABLE` | true | signer/JWKS 未就绪 |

对未认证请求，不得通过 challenge 或 peer 错误区分 Device、用户、好友、屏蔽或 key 是否存在。

## 9. Audit、日志与隐私

允许记录的安全审计事件：

```text
messager.device_key.registered
messager.device_key.rotated
messager.device_key.staled
messager.peer_assertion.issued
messager.peer_assertion.denied
```

允许字段仅限 actor/user/Device/Installation/key ID、key epoch、access epoch、握手 ID、JWT JTI、结果 code、时间和公钥 fingerprint。禁止写入：

- private key、challenge plaintext、proof、compact JWT；
- raw public key（fingerprint 足够）；
- Cloud session、Device secret 或 authorization header；
- 消息正文、密文、附件、Noise handshake payload 或会话密钥；
- 完整 FRP 请求体。

Peer assertion API 响应必须 `Cache-Control: no-store`；不得进入 CDN/public cache。JWKS 是唯一可公开缓存的新增响应。

## 10. 代码与共享产物

Cloud 工程需要交付：

1. Drizzle schema 和 migration；
2. `src/messager/` service、routes、validation，以及 `RemoteTokenSigner.signMessagerPeer` 或等价独立 signer；
3. `GET /v1/messager/jwks.json`；
4. OpenAPI paths 和 component schemas；
5. `schemas/messager-device-key-v1.schema.json`；
6. `schemas/messager-peer-assertion-claims-v1.schema.json`；
7. `fixtures/messager-peer-identity-v1/vectors.json`，含测试 Ed25519 JWK、合法 compact JWT 和负向 mutation；
8. Cloud client integration 文档中增加 Local E2EE 前置接口，但继续明确 System Message fallback 不是 E2EE；
9. 部署配置说明：signer key/JWKS 轮换沿用或独立配置、无明文 secret 日志、migration/rollback 步骤。

fixture 至少固定一组：

- Device key registration canonical proof bytes、public key、signature；
- 合法 peer assertion 与完整 claims；
- 错误 audience、过期、未来签发、超 90 秒 lifetime；
- self/peer Device mutation；
- key fingerprint、origin、handshake ID mutation；
- unknown/retired `kid`。

## 11. 必须通过的 Cloud 测试

### Device key

- Device credential 缺失/错误被拒绝；
- challenge 过期、重放、跨 Device 使用被拒绝；
- 非 canonical base64url、错误长度、弱/全零 X25519 key、错误 proof 被拒绝；
- 首次登记、相同请求幂等恢复、真实轮换及 key epoch 单调；
- credential/access epoch 变化使旧 key stale；
- Device suspend/revoke 后不再签发 assertion；
- 并发两个不同 key 登记最终只有一个 active key。

### Peer assertion

- actor membership、membership epoch、Device access epoch 均由 Cloud 验证；
- 自发、自身、非好友、任一方向 block、inactive user 被正确拒绝；
- target primary Device 缺失、revoked、stale/no key 被拒绝；
- `publicOrigin` 只由 authoritative public slug 派生；
- assertion 绑定双方 user/Device/Installation/access epoch/key epoch/fingerprint/origin/handshake ID；
- JWT audience、lifetime、JWKS 和 key rotation 行为符合第 7 节；
- friendship 在事务竞争中被删除时不签发；
- 响应、日志和 audit 不含 secret、compact JWT、raw public keys（响应按合同例外）以外的敏感内容；
- rate limit 和标准错误 envelope 可由客户端稳定处理。

### 兼容性

- 现有 Profile、Social、System Message、Remote Mobile、Installation member assertion、Federation、AI API 回归全绿；
- public Profile 不新增 Device ID、Installation ID 或 public key；
- Cloud offline 文本和单图接口行为完全不变；
- 不安装新客户端的现有 Device 无需迁移或重新绑定。

## 12. 联调验收请求

Cloud 工程完成后，请向 AI2Apps 客户端工程提供：

1. 实现 commit/tag；
2. migration 名称与 rollback 限制；
3. 更新后的 OpenAPI 和上述两个 JSON Schema；
4. fixture vectors；
5. 本地或 staging Cloud base URL；
6. 一组可创建两个用户、两台 Device、好友关系和 primary Device 的测试步骤；
7. Cloud 测试命令及通过数量；
8. 明确是否完全按本文路径、字段、错误码和 TTL 实现；如有差异，在客户端开始修改前列成 compatibility delta。

AI2Apps 客户端将在收到这些产物后实现 Device key 安全存储、proof、peer assertion verifier、Noise transport、确认/查询、Local-first 降级状态机和双 Local 实例验收。
