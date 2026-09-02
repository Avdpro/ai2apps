# Cloud Package Source 复验状态转换热修需求 v1

状态：已于 2026-09-03 完成生产热修并验收

生产回执：
`/Users/avdpropang/sdk/ai2apps-cloud/docs/package-source-revalidation-state-transition-hotfix-production-deployment-2026-09-03.md`

结果：生产镜像
`ai2apps-cloud:package-source-revalidation-state-v1-20260902T200248Z` 已部署，269/269
测试通过；现场 ModelScope Source 无需重新下载即从 `validating` 恢复为
`pending_approval`。随后已由 step-up admin 通过正式 API 激活。

## 生产复现

`ai2apps/runtime-omlx@1.5.7` 的 ModelScope Source
`src_2b44203b-e194-4df6-8a1a-3e0ec8bfe797` 从历史 `validation_failed` 调用正式
`POST .../validate` 后：

- 新 validation `val_6cf39b63-ec0a-4fec-9fe1-bc0ad1c97ea4` 已为 `passed`；
- size、完整 SHA-256、Range 和 piece manifest 全部通过；
- validation digest 为
  `059a9ec86705d3e5e31164c8f42d92ca03103c678cb524ad763b4ac9b7dca9a7`；
- Source 状态错误地停留在 `validating`；
- `/activate` 只接受 `pending_approval`，导致已经通过的 Source 无法激活。

复现时 Runtime 公共 Snapshot v101 已发布 Cloud + GitHub；修复并激活后，公共 Snapshot
v102 已发布 Cloud + ModelScope + GitHub。

## 根因

`RegistryService.runArtifactSourceValidation(..., registration=false)` 只在 `registration=true`
时把通过验证的 `validating` Source 更新为 `pending_approval`；复验路径固定传入 `false`。
失败分支也只在 `registration=true` 时更新 Source 状态，因此复验失败同样可能永久停在
`validating`。

## 必须修复

1. 对非 `active`、非 `disabled` Source：最新复验通过后，将同一 Source 从 `validating`
   原子转换为 `pending_approval`；复验失败后原子转换为 `validation_failed`。
2. `active` 或 `disabled` Source 的后台复验不得意外改变其发布状态；只更新 validation 和
   审计记录。
3. 状态转换必须限定 validation 仍是该 Source 最新 validation，防止较早的慢任务覆盖较新
   结果。
4. 保留 revision 递增、幂等、审计、最新 validation 绑定和并发保护。
5. 部署后修复现有这条卡住记录：优先通过正常恢复逻辑把 Source 置为
   `pending_approval`；如必须再次调用 `/validate`，应复用刚完成的完全验证证据，不能再次
   下载 457,410,846 字节。
6. 使用当前 step-up admin、最新 ETag 和上述最新通过证据激活 ModelScope，生成新签名
   Snapshot，并匿名确认 Runtime 包含 Cloud + GitHub + ModelScope 三源。

不得直接伪造 active 状态、修改历史 validation、覆盖旧 Snapshot 或跳过签名生成。

## 验收

- 历史 `validation_failed` Source 复验通过后进入 `pending_approval`；
- 历史 `validation_failed` Source 复验失败后回到 `validation_failed`；
- 并发两次复验只有最新 validation 能决定 Source 状态；
- active/disabled Source 复验不改变发布状态；
- Runtime ModelScope Source 成功激活，公共 Snapshot 签名验证通过并显示三源；
- GitHub active 状态、旧 `downloadUrl`、Package 身份、完整摘要和 Desktop Build 2249 不变；
- 全量测试与生产 Registry、Checkpoint、JWKS、Desktop Update 探针通过。
