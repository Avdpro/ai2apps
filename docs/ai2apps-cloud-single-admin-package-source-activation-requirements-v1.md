# Cloud Package Source 单管理员激活需求 v1

状态：待 Cloud 实现并部署生产

## 目标

当前 AI2Apps 处于单管理员开发阶段。Package Release 与 Checkpoint Release 已支持
“同一 `admin` + 最近密码二次验证（step-up）”的自审批通道；Package Source 新接口没有
复用该通道，而是无条件拒绝登记人激活。这里要求补齐行为一致性，不引入无验证自批，也
不改变 Desktop Update 或其他审批流程。

## API 行为

保持 OpenAPI `1.39.0` 的现有端点、请求体、ETag、幂等键和响应结构兼容：

- `POST .../sources/{sourceId}/validate`
- `POST .../sources/{sourceId}/activate`
- `POST .../sources/rollback`

具体规则：

1. `admin` 在 `stepUpVerified=true` 时，可以激活自己登记的、状态为
   `pending_approval` 的 Source；未完成最近密码验证时返回现有
   `ADMIN_REAUTH_REQUIRED`；
2. `reviewer` 权限保持原规则，不能激活自己登记的 Source；
3. 自激活仍必须提交当前 `If-Match`、`Idempotency-Key`、已通过且未过期的
   `validationId` 与 `validationDigest`；不得跳过 URL、Range、piece、大小或完整 SHA-256
   验证；
4. 同一 `admin` 只有在 `stepUpVerified=true` 时，才可以通过 rollback 恢复自己最初登记
   的已验证 Source；`reviewer` 仍保持登记人与批准人分离；
5. 审计事件继续同时记录 `registeredBy`、`approvedBy`，并增加或明确
   `selfApproval: true` 与 `stepUpRequired: true`，另写入专门的
   `package.artifact_source.self_approval_override` 审计事件；不得伪造成双人审批；
6. 现有 Source ID、validation、revision 和历史审计必须原样保留，不得要求重新登记；
7. 并发、旧 ETag、旧 validation、摘要不符或非 `pending_approval` 状态仍按现有规则拒绝。

## 当前生产数据的收尾

部署后先让现有管理员完成密码二次验证，再用该管理员会话按正式 API 完成
`ai2apps/runtime-omlx@1.5.7`：

1. 对 ModelScope Source `src_2b44203b-e194-4df6-8a1a-3e0ec8bfe797` 调用 `/validate`，
   轮询至 `pending_approval`；
2. 使用最新 ETag 和新 validation 证据激活该 ModelScope Source；
3. 使用最新 ETag 和现有有效 validation 证据激活 GitHub Source
   `src_93a2debf-8a8a-4d14-b485-597142933bb9`；
4. 匿名读取并验证最新 Repository Snapshot 的 Ed25519 签名，确认 Runtime 同时包含
   Cloud、ModelScope、GitHub 三个 Source；
5. 验证旧 `downloadUrl`、Package 身份、文件大小、完整 SHA-256 和 Desktop Build 2249
   清单均未变化。

## 验收测试

- 已完成 step-up 的 admin 登记后可自行激活已通过验证的 Source；
- 未完成 step-up 的 admin 自激活返回 `ADMIN_REAUTH_REQUIRED`；
- reviewer 登记后自行激活仍返回
  `ARTIFACT_SOURCE_SELF_APPROVAL_NOT_ALLOWED`；
- admin 自激活时，旧 ETag、错误 validation ID/digest、失败验证和错误状态均被拒绝；
- 完成 step-up 后，admin 自注册 Source 的 rollback 可成功；未 step-up 的 admin 和
  reviewer 自注册 Source 的 rollback 仍被拒绝；
- 幂等重放不重复递增 revision 或重复创建 Snapshot；
- 全量测试、生产健康检查、Registry/Checkpoint/JWKS/Desktop Update 回归通过；
- 生产 Snapshot 最终显示 `ai2apps/runtime-omlx@1.5.7` 的三源并完成签名验证。
