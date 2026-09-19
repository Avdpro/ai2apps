# AI2Apps Cloud ModelScope Range 激活策略更正 v1

日期：2026-09-17
状态：待 Cloud 实施并升级生产
目标：恢复既有管理员 step-up 自审语义，不改变严格 Range 与完整性验证

## 1. 问题与根因

普通 Package 审核和标准外部 Source 激活一直允许系统管理员在完成管理员二次验证后处理
自己提交或登记的对象。Cloud 通过 `reviewNeedsSelfApprovalOverride` 和
`artifactSourceNeedsSelfApprovalOverride` 实现该合同：

- 非管理员自审仍返回 `SELF_APPROVAL_NOT_ALLOWED` 或
  `ARTIFACT_SOURCE_SELF_APPROVAL_NOT_ALLOWED`；
- 管理员自审必须 `stepUpVerified=true`，否则返回 `ADMIN_REAUTH_REQUIRED`；
- 成功后写入专门的 `self_approval_override` 审计事件。

OpenAPI 1.50.0 的 ModelScope `200 + Content-Range` 升级额外加入了
`assertCompatibleSourceApprover`。当 validation receipt 的 `rangeCompatibility` 不是
`standard` 时，它无条件拒绝登记人与激活人为同一用户，即使该用户是已完成 step-up 的系统
管理员。该检查位于既有 `artifactSourceNeedsSelfApprovalOverride` 之后，因而只改变兼容来源，
造成与历史 Package/Source 发布行为不一致。

这条特殊门禁来自 Local 项目原需求文档中的错误要求，包括“注册人与激活人相同仍拒绝”、
“由不同 reviewer/admin 激活”和“双人审批不降低”。它不是 Cloud 原有发布合同。严格兼容
`200` 已经执行每个 Range 的精确 offset/total/length/body 校验、全部 piece hash、完整 size、
完整 SHA-256、固定 revision、allowlist 和签名 Snapshot；HTTP 状态兼容本身不需要改变操作者
审批模型。

## 2. 必须修改的行为

兼容来源与标准来源使用完全相同的操作者授权规则：

1. 非管理员不得激活自己登记的 Source；
2. 系统管理员可以在 `stepUpVerified=true` 时激活自己登记的 Source；
3. 系统管理员未完成 step-up 时返回 `ADMIN_REAUTH_REQUIRED`；
4. 不同 reviewer/admin 仍可正常激活；
5. 自审成功必须继续写入 `package.artifact_source.self_approval_override`，包含 Source、
   validation、revision、Snapshot digest 和 `stepUpRequired=true`；
6. rollback 恢复兼容来源时使用同一规则，避免激活与回滚语义分叉。

实现上应删除 `assertCompatibleSourceApprover`，以及 activate/rollback 对它的调用；继续使用
`artifactSourceNeedsSelfApprovalOverride` 的既有结果和审计路径。不得通过伪造第二用户、修改
`createdBy`、直接改数据库状态或跳过管理员 step-up 绕过当前门禁。

## 3. 保持不变的安全与完整性门禁

以下行为不得放宽：

- `package-single-range-v2` validation receipt；
- `modelscope-content-range-200` 只允许可信 ModelScope 固定 revision URL；
- 精确 `Content-Range`、`Content-Length`、identity encoding、非 multipart 和有界 body；
- 全部 piece SHA-256、完整 size 和完整 SHA-256；
- validation 必须是该 Source 最新且为 `passed`；
- validation digest、URL、artifact digest/size、piece manifest digest 必须与当前 Release 一致；
- 最新 Source revision/ETag、幂等键和签名 Repository Snapshot；
- 非管理员自审禁止、管理员 step-up、Publisher/管理员权限和完整审计。

本更正不修改 Checkpoint Registry 边界、客户端兼容逻辑、数据库 schema、签名数据格式或
公开 Source 清单。

## 4. 自动化测试

更新现有 ModelScope Range 测试：

1. 同一登记人、`systemRole=admin`、`stepUpVerified=true`：标准、mixed 和
   `modelscope-content-range-200` 均允许激活；
2. 同一登记人、管理员未 step-up：三种模式均返回 `ADMIN_REAUTH_REQUIRED`；
3. 同一登记人、非管理员：三种模式均返回
   `ARTIFACT_SOURCE_SELF_APPROVAL_NOT_ALLOWED`；
4. 不同 reviewer/admin：三种模式均允许激活；
5. 兼容来源自审激活写入 `package.artifact_source.self_approval_override`；
6. rollback 使用相同授权矩阵；
7. Range v2 的 malformed/short/excess/encoding/multipart/SSRF/redirect/timeout、piece 和完整
   SHA 回归全部继续通过；
8. 普通 Package 自审、标准 GitHub/ModelScope 206 Source 激活行为无回归。

## 5. 生产升级与 Runtime 1.7.0 收尾

Cloud 完成测试、生产升级和健康检查后，保留当前 Runtime 1.7.0 Source 与 validation：

```text
source: src_3125a4d0-27d8-4cfc-a9f2-43b0ec8ad3a2
source revision / ETag: 7 / "sources-7"
validation: val_9f67323e-596d-46ef-92bb-13ca61e2b53b
validation digest: a453483dd89e5f719f47f7c81b1a05a1893ddf08e6726c77181598e00fd500d0
status: pending_approval
```

本次更正不改变 validation 内容或 `package-single-range-v2`，因此不应要求重新下载和验证
373,748,488 字节制品。客户端随后用当前 ETag、validation ID/digest 和原激活逻辑的幂等键
重试激活；成功后必须匿名回读新 Repository Snapshot，确认 Cloud、GitHub、ModelScope 三源
active、Snapshot 签名有效，并用兼容开发客户端完成实际下载验收。

Cloud 交付回执应记录生产镜像/版本、测试结果、Source 激活前状态保持不变，以及未直接修改
数据库或伪造审批身份。
