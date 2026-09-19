# AI2Apps Cloud 首次登录 Session epoch 同步修复要求 V1

状态：Cloud 已于 2026-09-08 完成实现并部署生产；专用 Test Mac 已于 2026-09-09 完成跨两个 access-projection 周期的最终验收
提出方：AI2Apps Test System
问题发现日期：2026-09-08
适用范围：AI2Apps Cloud installation detail、Desktop Local 身份初始化和测试账号登录

## 实施回执

Cloud 工程已经完成本需求的服务端部分：

- 生产镜像：`ai2apps-cloud:installation-session-bootstrap-v1-20260908T144434Z`
- OpenAPI：`1.46.0`
- 全量测试：305 passed、0 failed、1 个可选数据库测试 skipped
- `InstallationDetail` 已将 `localSessionEpoch` 和当前调用者自己的 `accountSessionEpoch` 定义为必填正整数
- 生产数据副本上的登录、绑定、Installation detail 和 access projection 完整流程通过，两处 epoch 完全一致
- 无数据库 migration，旧客户端兼容，生产容器健康且保留了已验证备份和回滚容器

客户端最终验收：

- Test Run：`20260908T170956Z-32018`
- 仅使用 `com.ai2apps.desktop.test` / instance `test` 与 Harness 租用的测试账号
- 首轮 access projection 于 `2026-09-09 01:12:11` 返回 HTTP 200
- 第二轮 access projection 于 `2026-09-09 01:14:11` 返回 HTTP 304
- 第二轮后 Local Session 数量仍为 1，`access_epoch=1` 与 `local_session_epoch=1` 一致，`account_session_epoch=43`
- 刷新 Test Shell 后仍进入已登录 Home，随后 Cloud `/v1/auth/me` 返回 HTTP 200
- Run 完成并释放账号后，下一轮 projection 于 `2026-09-09 01:18:13` 返回 HTTP 403；Installation 转为 `suspended`，Local Session 数量降为 0，Shell 显示 `Session expired`，证明回收撤销语义仍然有效
- Run 最终结论：`SCOPED_PASS`
- 验收产物未读取或保存 Broker Credential、临时密码、lease token、Cookie 或 Bearer

Cloud 证据：

- [实现说明](/Users/avdpropang/sdk/ai2apps-cloud/docs/installation-session-bootstrap-v1.md)
- [生产部署回执](/Users/avdpropang/sdk/ai2apps-cloud/docs/installation-session-bootstrap-production-deployment-2026-09-08.md)
- [OpenAPI 1.46.0](/Users/avdpropang/sdk/ai2apps-cloud/openapi-v1.yaml)

当前唯一未完成项属于客户端测试环境：专用 Test Mac 的 `account doctor` 返回 `credentialConfigured=false`、`credentialAuthorized=false`。在通过批准的安全渠道配置生产 Broker Credential 前，不得启动真实账号租约；配置后按第 8、9 节完成最终验收。

## 1. 修改目的

修复 AI2Apps Desktop 首次绑定 Installation 并登录后，本地 Session 在第一次 Cloud access projection 同步时被立即撤销的问题。

该问题在固定 Test App 与租赁测试账号上稳定出现：登录成功约两分钟后，Shell 显示 Session expired。测试账号 lease 仍处于 active，Cloud 浏览器 Session 和 Local Session 的正常有效期也远长于两分钟，因此这不是 TTL 到期。

## 2. 为什么需要修改 Cloud

测试账号 lease acquire 会按安全要求执行完整账号回收，并递增 `users.account_session_epoch`。该递增必须保留，因为它负责使该测试账号在以前 Device 上遗留的 Local Session 失效。

随后 Desktop 创建新 Organization、Device 和 Installation，并调用：

```http
GET /v1/installations/{installationId}
Cookie: ai2apps_session=...
```

Desktop 使用该响应初始化本地 Installation 和 Core membership。当前客户端已经支持从该响应读取：

- `localSessionEpoch`
- `accountSessionEpoch`

但是当前 Cloud `InstallationDetail` 没有返回这两个字段，OpenAPI 也没有声明它们。客户端为兼容旧 Cloud 只能使用本地默认值 `1`。测试账号经过 lease acquire 后的真实 `accountSessionEpoch` 通常大于 `1`，因此新签发的 Local Session 从创建时就记录了错误的 epoch。

不晚于两分钟后，Desktop 调用 Device-authenticated access projection：

```http
GET /v1/internal/installations/{installationId}/access
Authorization: Device <device-id>.<connector-secret>
```

该接口会正确返回真实 `localSessionEpoch` 和每个成员的 `accountSessionEpoch`。Local 发现 epoch 不相等后，按既定安全规则删除刚创建的 Local Session。用户看到的是“Session 很快过期”，实际是初始投影不完整导致第一次权威同步发生变更。

这不只影响测试账号。任何在首次绑定前已经因 sign-out-all、密码重置、管理员撤销或账号状态变更而使 `accountSessionEpoch > 1` 的普通账号，也可能触发同类问题。测试账号只是因为每次 acquire 都递增 epoch，所以能稳定复现。

## 3. 当前代码证据

Cloud 当前行为：

- `src/test-accounts/service.ts` 的 `cleanupAccount()` 在 acquire/release 时执行 `account_session_epoch = account_session_epoch + 1`。
- `src/installations/service.ts` 的 `getForUser()` 返回 `accessEpoch` 和 `membershipEpoch`，但没有返回 `localSessionEpoch` 或当前用户的 `accountSessionEpoch`。
- 同文件的 `accessProjection()` 已经返回顶层 `localSessionEpoch` 和 membership 内的 `accountSessionEpoch`。
- `openapi-v1.yaml` 的 `InstallationDetail` 缺少这两个字段，而 `InstallationAccessProjection` 已包含它们。

Desktop 当前行为：

- `ai2apps/remote/manager.py` 的 `sync_installation_identity()` 已尝试读取 `localSessionEpoch` 和 `accountSessionEpoch`。
- 字段缺失时，`ai2apps/identity.py` 为新 Installation/membership 使用兼容默认值 `1`。
- `create_local_session()` 把这些 epoch 快照写入 Local Session。
- `apply_access_projection()` 检测到 account epoch 变化时删除对应账号的 Local Session；这是正确的撤销语义，不应弱化。

## 4. Cloud 必须修改的 API 契约

### 4.1 Installation detail

`GET /v1/installations/{installationId}` 的成功响应必须增加两个必填字段：

```json
{
  "installationId": "<uuid>",
  "cloudDeviceId": "<uuid>",
  "accessEpoch": 1,
  "localSessionEpoch": 1,
  "membershipEpoch": 1,
  "accountSessionEpoch": 35
}
```

字段语义：

- `localSessionEpoch`：该 Installation 当前的 `installations.local_session_epoch`。
- `accountSessionEpoch`：当前已认证调用者对应 `users.account_session_epoch`，不是 Core 用户的固定值，也不是 Installation 中其他成员的值。

两个字段均为严格正整数，并且必须与同一时刻 `GET /v1/internal/installations/{installationId}/access` 中对应的权威值一致。

### 4.2 OpenAPI

更新 `openapi-v1.yaml`：

- 在 `InstallationDetail.required` 中加入 `localSessionEpoch` 和 `accountSessionEpoch`。
- 为两个字段声明 `type: integer`、`minimum: 1`。
- 明确 `accountSessionEpoch` 属于当前登录用户，`localSessionEpoch` 属于当前 Installation。
- 按 Cloud 工程的版本规则提升 OpenAPI 版本并生成或更新相关客户端契约。

### 4.3 服务实现

更新 `InstallationService.getForUser()`，在现有权限检查通过后，从同一权威数据库状态返回：

- `context.installation.localSessionEpoch`
- 当前 `userId` 的 `users.accountSessionEpoch`

不得接受客户端提交 epoch，也不得从 Cookie、自定义 header、Installation Core 用户或缓存的历史 projection 推导该值。

## 5. 不应采用的修复

- 不得停止测试账号 acquire/release 时递增 `accountSessionEpoch`。
- 不得让客户端忽略 epoch 不一致。
- 不得延长 Session TTL 来掩盖问题。
- 不得把 Test App、测试邮箱或测试账号池写入通用 Installation API 的特殊分支。
- 不得降低 access projection 的两分钟刷新或撤销语义。
- 不得在响应、日志或审计中记录密码、Session Cookie、lease token、Device credential 或 Local Session token。

## 6. Cloud 回归测试要求

Cloud 工程至少新增以下测试：

1. `accountSessionEpoch > 1` 时，Installation detail 返回当前调用者的准确 epoch。
2. `localSessionEpoch > 1` 时，Installation detail 返回准确的 Installation epoch。
3. 同一状态下，Installation detail 与 access projection 返回的两个 epoch 完全一致。
4. 多成员 Installation 中，成员调用 detail 时返回该成员自己的 `accountSessionEpoch`，不能错误返回 Core 用户的值。
5. 测试账号 acquire 递增 account epoch 后，使用新密码登录并创建 Installation，detail 立即返回递增后的 epoch。
6. 未认证、无 membership、inactive membership 和无权访问其他 Installation 的调用仍按现有策略拒绝。
7. OpenAPI schema 校验覆盖新增必填字段，防止实现与契约再次漂移。
8. 现有 access projection、ETag、sign-out-all、密码重置、管理员撤销和测试账号回收测试全部继续通过。

如果 Cloud 测试环境能够运行 Cloud 与 Desktop Local 的联合契约测试，还应覆盖：

1. 使用 `accountSessionEpoch = 35` 完成首次绑定和 Local 登录。
2. 立即执行第一次 access projection。
3. projection 应被视为同一权威状态，不得删除刚创建的 Local Session。
4. 随后显式把 account epoch 提升到 `36`，下一次 projection 必须删除该 Session。

## 7. 安全与兼容性

- 两个新增字段是版本号，不是 Credential 或 Secret。
- 修改是响应字段扩展；已经忽略未知字段的旧客户端可以继续工作。
- 当前 Desktop 已兼容字段缺失并已具备读取新增字段的代码，因此 Cloud 部署后无需等待客户端升级即可解决当前 Test App 问题。
- 把字段升级为 OpenAPI required 是为了约束新实现和新客户端；Cloud 工程应按现有兼容发布流程验证旧客户端。
- access projection 仍是在线长期撤销的最终权威来源；Installation detail 负责保证首次签发的 Local Session 使用同一份初始权威值。

## 8. 部署与验收顺序

1. Cloud 工程更新服务实现、OpenAPI 和自动测试。
2. 运行 Cloud 全量类型检查、契约测试和测试账号相关测试。
3. 按 Cloud 正式发布流程部署，不直接修改生产数据库；本修复预期不需要数据库 migration。
4. 生产部署后先验证 Installation detail 响应包含两个正整数 epoch，验证过程不得打印 Cookie、账号密码或 Device credential。
5. 在 AI2Apps Test System 使用一个新 Run 租用测试账号并登录固定 `com.ai2apps.desktop.test` / instance `test`。
6. 保持登录跨过至少两次 access projection 周期，并调用 Local `/v1/platform/auth/me` 与 `/v1/platform/auth/session/refresh` 验证 Session 仍有效。
7. 结束 Run，确认账号 release 成功且 Session 随回收失效。

## 9. 验收标准

以下条件必须全部满足：

- Cloud Installation detail 返回正确的 `localSessionEpoch` 和当前调用者 `accountSessionEpoch`。
- OpenAPI 将两字段定义为必填正整数。
- 测试账号 acquire 后首次登录不再以默认 epoch `1` 创建错误的 Local Session。
- 登录跨过首次及第二次 access projection 后仍保持有效。
- 真正发生 account/local/membership/access epoch 变化时，现有撤销行为仍立即生效。
- Cloud 全量测试通过，生产健康检查正常，且没有 Credential、Cookie 或 token 进入日志和验收产物。
- Cloud 工程提供包含发布版本、测试结果、生产验证和回滚点的部署回执。

## 10. 客户端后续防御性工作

Cloud 修复并部署后，Desktop 工程仍建议增加一层防御：在首次签发 Local Session 前主动完成一次 Device-authenticated access projection，并确认初始 identity 与 projection 一致。该客户端工作用于兼容旧 Cloud、缓存和极短竞态，不替代本需求中的 Cloud 契约修复。

该客户端修改属于 AI2Apps Desktop 产品范围，应单独实施并更新 Desktop next-release ledger；Cloud 工程不应在本次任务中修改 Desktop 仓库。
