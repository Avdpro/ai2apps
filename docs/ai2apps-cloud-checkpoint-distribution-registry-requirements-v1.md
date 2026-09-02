# AI2Apps Cloud Checkpoint Distribution Registry 增量需求 v1

状态：**Cloud 生产已部署，等待首个真实 distribution 端到端发布**  
日期：2026-08-27  
需求方：AI2Apps Local / ACPF / Models  
目标实现仓库：`/Users/avdpropang/sdk/ai2apps-cloud`

生产交付（2026-08-27）：OpenAPI `1.23.0`，镜像
`ai2apps-cloud:checkpoint-registry-v1-20260826T181150Z`，migration 总数 35；Checkpoint
相关 5 张表及不可变触发器已生效，干净发布测试 173/173，通过 HIGH/CRITICAL 为 0 的安全扫描。
部署记录见 Cloud 仓库
`docs/checkpoint-distribution-registry-production-deployment-2026-08-27.md`（文档提交
`bd98f91`）。本文件以下章节保留为契约与验收基线，不代表要求重做已交付能力。

## 0. 重要说明：复用现有 Cloud，不重做 Registry

本需求不是重建 Publisher、Package Registry、审核后台或 Repository trust。当前
`ai2apps-cloud` 已经具备以下权威实现，Checkpoint 必须直接复用：

| 已有能力 | 现有实现 | Checkpoint 的要求 |
| --- | --- | --- |
| Account Session、角色和管理员 step-up | `src/auth/`、Registry route preHandler | 原样复用 |
| Publisher、namespace、membership | `publishers`、`publisher_members` 等 | 原样复用 |
| Publisher Ed25519 key enrollment/状态 | `publisher_keys`、key challenge | 原样复用，不建第二套 key |
| Package submission/review/publication 状态机 | `src/registry/service.ts` | 抽取/复用授权和状态转换模式 |
| Reviewer 自审限制和管理员 override | `reviewNeedsSelfApprovalOverride` | 原样复用 |
| Append-only audit event | `audit_events` | 增加 checkpoint event type |
| Repository online signer、公钥和 pin | `src/repository/`、`/v1/registry/repository-key` | 复用同一公钥，使用独立签名域和独立 metadata version |
| Drizzle/PostgreSQL、OpenAPI、测试框架 | 现有工程基础 | 只做增量 migration/schema/routes/tests |

不能复制一套 `CheckpointPublisher`、账户、Reviewer、管理员或 Repository key 系统。若现有
Package Registry 的内部函数只接受 Package，应先提取资源无关的授权、review transition、审计和
签名辅助函数，再由 Package 与 Checkpoint 两个资源适配器共同调用。

之所以仍建议 Checkpoint 使用独立业务表和公开 Index，是因为它没有 Package artifact，身份键是
`distributionId`，签名正文、不可变字段、生命周期和 Local 消费协议也不同。独立表不是重做信任
系统，而是避免把 checkpoint JSON 伪装成 `.ai2service` 或污染 Package release 数据模型。

## 1. 交付目标

Cloud 增加独立的 Checkpoint Distribution Registry，使 AI2Apps Local 能够：

1. 通过现有、已 pin 的 Repository Ed25519 公钥取得短期有效的签名 Checkpoint Index；
2. 通过 `distributionId` 取得 Publisher 签名的不可变 distribution envelope；
3. 将一个 Model Package 的 `modelId + repoId + HF revision` 绑定到经过字节校验的
   ModelScope/Hugging Face 来源；
4. 在 Hugging Face 不可达时，仅使用 ModelScope 下载，并仍以同一文件 SHA-256 和 piece
   hashes 完成端到端校验；
5. 保持 Publisher、Reviewer、Platform Administrator 和 Repository signer 四类权限分离。

Cloud 不代理模型文件，不保存 checkpoint，不生成 Publisher 签名，也不持有 Publisher 私钥。
Cloud 只保存、审核和发布签名 envelope，并生成签名 Index。

## 2. 已实现的 Local 契约

Cloud 实现必须与以下 Local 代码兼容，不得自行改变字段名、签名域或 URL：

- `ai2apps/checkpoint_distribution.py`
- `ai2apps/checkpoint_registry.py`
- `ai2apps/checkpoint_acquisition.py`
- `ai2apps/checkpoint_publishing.py`

公开读取路径已经固定：

```text
GET /v1/registry/repository-key
GET /v1/checkpoint-distributions/index/latest
GET /v1/checkpoint-distributions/{distributionId}
```

`envelopeUrl` 必须是同一 Cloud origin 下的相对路径，且必须位于
`/v1/checkpoint-distributions/` 下。Local 会拒绝跨 origin URL、路径逃逸、Index 回滚、过期
Index、Publisher 身份不一致和 digest 不一致。

## 3. Publisher distribution envelope

### 3.1 Envelope 格式

```json
{
  "schemaVersion": "ai2apps.checkpoint-distribution-envelope.v1",
  "payload": {
    "domain": "ai2apps.checkpoint-distribution.v1",
    "publisherId": "<publisher UUID>",
    "publisherKeyId": "<publisher key UUID>",
    "manifestDigest": "sha256:<64 lowercase hex>",
    "manifest": {}
  },
  "signature": {
    "keyId": "<same publisher key UUID>",
    "algorithm": "Ed25519",
    "value": "<base64url without padding>"
  }
}
```

签名正文必须是：

```text
UTF8("AI2APPS-CHECKPOINT-DISTRIBUTION-V1\n") || JCS(payload)
```

`manifestDigest` 必须等于：

```text
"sha256:" + lowercase_hex(SHA256(JCS(payload.manifest)))
```

Cloud 必须使用 Registry 中该 Publisher key 的 Ed25519 公钥重新验证签名，不得信任 envelope
自报的公钥、fingerprint、Publisher ID 或 key ID。

### 3.2 Manifest 最低校验

Manifest schema 为 `schemaVersion: 1`，Cloud 需要提供严格 JSON Schema，并执行与 Local 等价的
拒绝式验证：

- 顶层身份：`distributionId`、`modelId`、`repoId`、40 位小写 HF commit、format、quantization；
- `estimatedSizeBytes` 等于所有非空文件 size 之和；
- 文件路径安全、唯一，包含 size 和 SHA-256；
- piece size 为 1–64 MiB 范围内的 2 次幂；
- piece hash 数量等于规范文件流的实际 piece 数；
- 每个文件至少有一个已验证 source；
- source 仅允许 `huggingface`、`modelscope`；
- HF revision 必须是 40 位 commit；MS revision 不得是 `main/master/latest/head`；
- source repo/path/revision/access 完整；
- V1 `managedSources` 必须为空；
- `redistributionPolicy != allowed` 时禁止 P2P；本阶段所有发布物的 P2P 必须关闭。

Cloud 不需要重新计算几十 GB 的文件哈希，但必须验证 Publisher 签名和结构。AI2Apps 第一方
distribution 的审核流程必须附带构建收据，并通过 `builder` 区分两种模式：默认
`checkpoint-metadata-verified-v1` 从一个固定 HF 快照计算 SHA-256/piece hashes，并与 MS 固定
revision 返回的完整文件清单、大小和最终 SHA-256 对照；`checkpoint-full-dual-download-v1` 用于
首次镜像基线、定期抽审、元数据缺失和高风险发布，读取两个完整快照逐字节验证。未来可增加隔离
的异步 Hub verification worker，但不得在 API 进程下载或解析模型文件。

## 4. 签名 Checkpoint Index

### 4.1 格式

```json
{
  "schemaVersion": "ai2apps.checkpoint-index-envelope.v1",
  "payload": {
    "domain": "ai2apps.checkpoint-index.v1",
    "version": 1,
    "generatedAt": "2026-08-27T00:00:00Z",
    "expiresAt": "2026-08-28T00:00:00Z",
    "distributions": [
      {
        "distributionId": "dist_...",
        "status": "published",
        "envelopeUrl": "/v1/checkpoint-distributions/dist_...",
        "manifestDigest": "sha256:...",
        "publisher": {
          "id": "<publisher UUID>",
          "key": {
            "id": "<publisher key UUID>",
            "fingerprintSha256": "<64 lowercase hex>",
            "publicKeyPem": "-----BEGIN PUBLIC KEY-----..."
          }
        }
      }
    ]
  },
  "signature": {
    "keyId": "<repository key fingerprint>",
    "algorithm": "Ed25519",
    "value": "<base64url without padding>"
  }
}
```

签名正文：

```text
UTF8("AI2APPS-CHECKPOINT-INDEX-V1\n") || JCS(payload)
```

### 4.2 Index 规则

- 复用现有 prototype Repository signer，但使用独立签名域；不得复用 Publisher key；
- Checkpoint Index `version` 独立单调递增，不与 Package metadata version 混用；
- 发布、yank、revoke 或 Publisher key 状态变化后，在同一业务事务完成状态变更和 version 分配；
- Index 默认有效期 24 小时，在剩余有效期低于 15 分钟时刷新；
- 历史 Index 可按 version 保存用于审计，但公开 `latest` 只返回当前有效版本；
- V1 Index 只列 `published` distribution。被 revoke/yank 的项目从新 Index 中删除，但历史记录和
  envelope 不得被数据库覆盖；
- Repository 公钥继续由现有 `/v1/registry/repository-key` 返回，Local 仍使用应用外 pin 的
  fingerprint 验证。

## 5. 提交、审核和发布 API（现有状态机的资源适配）

沿用现有 Package Registry 的权限、状态枚举、授权判断、Reviewer 自审限制、管理员 step-up 和
audit writer，只增加 Checkpoint 资源适配器及独立路径：

```text
POST /v1/checkpoint-distribution-submissions
GET  /v1/checkpoint-distribution-submissions/{submissionId}
GET  /v1/publisher-checkpoint-distribution-submissions?status=&limit=
GET  /v1/prototype/checkpoint-distribution-submissions?status=&limit=
POST /v1/prototype/checkpoint-distribution-submissions/{submissionId}/review-request
POST /v1/prototype/checkpoint-distribution-submissions/{submissionId}/reviews
POST /v1/prototype/checkpoint-distribution-submissions/{submissionId}/publication
POST /v1/prototype/checkpoint-distributions/{distributionId}/yank
POST /v1/prototype/checkpoint-distributions/{distributionId}/revoke
```

提交使用 JSON，不使用 multipart：

```json
{
  "envelope": { "schemaVersion": "ai2apps.checkpoint-distribution-envelope.v1" },
  "verificationReceipt": {
    "builder": "ai2apps.checkpoint-publishing/v1",
    "fileCount": 28,
    "pieceCount": 6912,
    "estimatedSizeBytes": "57982058496",
    "verifiedProviders": ["huggingface", "modelscope"]
  }
}
```

限制：请求正文和 envelope 分别不超过 16 MiB；整数超过 JS safe integer 时 API 使用十进制字符串。
Receipt 是审核证据，不进入签名 Manifest，也不能替代 Publisher 签名或 Local 字节校验。

状态机：

```text
candidate -> review_pending -> approved -> published
                         \-> rejected
published -> yanked | revoked
```

权限、自审限制、管理员 step-up、Release Bot 方向和审计要求与现有 Package publication 完全一致。
同一 `distributionId` 发布后不可换 manifest、Publisher、key 或 digest；重复提交相同字节应返回已有
记录，不同字节必须返回 `409 DISTRIBUTION_IMMUTABLE`。

## 6. 数据库增量模型

只新增 Checkpoint 业务记录；外键复用现有 users、publishers、publisher_keys，状态字段复用现有
`release_status` 和 `review_decision` enum，不复制账户、Publisher 或权限表：

```text
checkpoint_distribution_submissions
  id, distribution_id, model_id, repo_id, revision
  publisher_id, publisher_key_id, manifest_digest
  envelope_json, verification_receipt_json
  release_status, submitted_by, created_at, updated_at

checkpoint_distribution_reviews
  id, submission_id, reviewer_user_id, decision, note, created_at

checkpoint_distributions
  distribution_id, submission_id, publisher_id, publisher_key_id
  model_id, repo_id, revision, manifest_digest
  envelope_json, status, status_reason, published_at

checkpoint_repository_metadata
  version, envelope_json, generated_at, expires_at
```

关键约束：

- `distribution_id` 全局唯一；
- `(distribution_id, manifest_digest)` 不可变；
- Publisher/key 外键必须指向提交时仍 active 的现有记录；
- published row 不允许 ordinary UPDATE 改 identity/envelope/digest；
- review 和 audit append-only；
- JSONB 只能存经过 schema、签名、大小和深度验证的 bounded JSON；
- 发布事务失败时不得出现已 published 但未进入新 Index 的中间状态。

## 7. Model Package 联动门禁

Cloud Package submission/review 流程还需增加服务端门禁，不能只依赖 Local 构建脚本：

1. 对新提交的 Model Service Package 解析已验证 archive 内的 `service.yaml`；
2. 每个 `models[].weights` 必须有合法 `distribution_id`；
3. distribution 必须已经 `published`；
4. distribution Publisher 必须等于 Package Publisher；
5. `modelId`、`repoId`、HF revision 必须分别等于 model id、weights repo/revision；
6. 任一绑定失败，拒绝 Package publication，返回具体 model ID；
7. 历史已发布 Package 不回写、不撤销，只有新版本或重新提交时执行新门禁；
8. Runtime、无 weights 的 Service、App 和 Agent 不受此门禁影响。

建议错误码：

```text
CHECKPOINT_DISTRIBUTION_REQUIRED
CHECKPOINT_DISTRIBUTION_NOT_FOUND
CHECKPOINT_DISTRIBUTION_NOT_PUBLISHED
CHECKPOINT_DISTRIBUTION_BINDING_MISMATCH
CHECKPOINT_DISTRIBUTION_PUBLISHER_MISMATCH
```

## 8. 安全与隐私要求

- 不接收 Publisher 私钥、HF token、ModelScope cookie/token、Hub 最终 CDN URL 或模型文件；
- 不在日志、audit context 或错误正文记录完整 envelope、piece hashes、公钥以外的凭据；
- 解析前执行 JSON body、数组数量、字符串长度、嵌套深度限制；
- 公开 envelope 响应使用 `Content-Type: application/json`、immutable ETag 和安全缓存策略；
- Index 短期缓存，envelope 可长期 immutable 缓存；
- 所有提交、审核、发布、yank、revoke、Index version 变化写 append-only audit event；
- 数据库/API 被攻破不能伪造 Publisher 签名；对象或 CDN 被篡改必须被 Local digest/signature 拒绝；
- Cloud 暂时离线时，Local 只可使用尚未过期且通过签名验证的缓存 Index/envelope。

## 9. OpenAPI 与共享测试向量

Cloud 交付必须同时更新：

- `openapi-v1.yaml`；
- `schemas/checkpoint-distribution-manifest-v1.schema.json`；
- `schemas/checkpoint-distribution-envelope-v1.schema.json`；
- `schemas/checkpoint-index-envelope-v1.schema.json`；
- 一组由固定 Ed25519 key 生成的跨语言 JSON/JCS/signature 测试向量；
- TypeScript 单元测试、PostgreSQL 集成测试、路由鉴权测试和 repository signer 测试。

测试向量必须覆盖字段顺序变化、Unicode、错误 padding、错误签名域、digest 大小写、Index 回滚、
过期/未来时间、跨 origin URL、mutable revision、重复路径、piece 数量错误和 Publisher/key 不匹配。

## 10. Cloud 验收清单

- [x] 合法 Publisher envelope 能提交并验证；篡改任一 manifest 字节后失败；
- [x] 非 Publisher member、inactive key、错误 Publisher/key 和越权 namespace 被拒绝；
- [x] Reviewer 复用现有角色、自审审计和管理员边界；
- [x] 发布后 `GET distributionId` 返回原始不可变 envelope；
- [x] 发布后生成更高版本的签名 Index；
- [x] 旧 Index、过期 Index、错误 repository signature 均被契约测试拒绝；
- [x] 相同 ID + 不同 digest 无法覆盖；yank/revoke 不删除历史审计；
- [x] 新 Model Package 缺 distribution 或绑定不匹配时无法发布；App、Agent、Runtime
  和无模型权重的 Service 不受影响；
- [x] Cloud 不可用时，已经安装并验证的 Package/模型继续运行；
- [x] 用 Qwen Image 2512 的真实 Publisher envelope 完成首次端到端联调（Submission
  `e5ab2cf1-b045-4177-9aa2-bbbe6d189c93`，Checkpoint Index version 2）。

## 10.1 最小实施差异

如果 Cloud 团队希望按最小 PR 拆分，建议只有四组变化：

1. **Contract**：3 个 JSON Schema、JCS/Ed25519 checkpoint envelope verifier 和固定测试向量；
2. **Persistence/service**：Checkpoint submission/distribution/review/metadata 增量表，以及复用现有
   Registry 授权、review transition、audit、Repository signer 的 Service adapter；
3. **Routes**：提交/审核/发布、公开 envelope、公开 latest Index；
4. **Package gate**：在现有 Package publication 校验中查询已发布 distribution 并核对
   Publisher、model ID、repo ID、revision。

现有登录、Publisher Console、Package artifact storage、Package Repository metadata、评分、评论、
Discover 搜索和 Package 下载均不需要重写。

## 11. 不属于本次 Cloud 交付

- 下载 ModelScope/Hugging Face checkpoint；
- checkpoint blob、torrent 或 piece 的托管与转发；
- P2P Tracker、DHT、做种策略和贡献奖励；
- HF/ModelScope 用户凭据管理；
- 算力共享、Points/Gas/Cash 结算；
- Local 下载任务、缓存、暂停恢复和 Worker 激活 UI。

这些能力不得阻塞本需求中的签名 Registry MVP。
