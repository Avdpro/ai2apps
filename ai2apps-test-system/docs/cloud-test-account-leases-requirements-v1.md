# AI2Apps Cloud 测试账号租约要求 V1

状态：Cloud OpenAPI 1.45.0 已于 2026-09-08 部署生产；Desktop ATS 客户端已完成对接，等待专用测试 Mac 配置 Broker Credential 后做端到端验收。

## 1. 目标与边界

AI2Apps ATS 使用固定账号池 `test1@ai2apps.com` 至 `test10@ai2apps.com`。账号平时必须禁用；一次测试 Run 原子租用一个账号时，Cloud 临时启用账号、轮换为随机密码并清除既有设备与 Session。Run 结束后再次轮换密码、禁用账号并撤销本次设备与 Session。

该能力只能服务 `com.ai2apps.desktop.test` / `test`，不能成为任意账号管理 API。Cloud 必须维护服务器端固定 allowlist，不能信任客户端提交的邮箱、域名、SQL 条件或账号数量。

## 2. 认证与权限

- 接口使用专用机器凭证或等价的工作负载身份；普通用户 Session、Owner 密码和管理员浏览器 Cookie 均不得调用。
- 本机凭证一次性配置在 macOS Keychain 的 `AI2Apps Test Account Leases` / `broker-access-token`，不得写入仓库、命令行、环境报告或 Codex prompt。
- Cloud 对调用方、Run、lease、测试账号 immutable user ID、动作和结果写审计；审计不得包含邮箱、临时密码、lease token、Cookie 或设备元数据正文。

## 3. 获取租约

`POST /v1/test-account-leases`

请求：

```json
{
  "poolId": "desktop-test-v1",
  "runId": "20260908T053358Z-94042",
  "ttlSeconds": 7200,
  "client": {
    "bundleId": "com.ai2apps.desktop.test",
    "instanceId": "test"
  }
}
```

Cloud 在同一事务或等价原子边界中：

1. 校验工作负载身份、pool、Run ID、固定 bundle/instance 和 TTL 上限；
2. 按数据库锁选择一个未租用且属于服务器 allowlist 的账号；
3. 把残留或过期 lease 标记为 expired，并先执行完整回收；
4. 撤销该账号所有 active/suspended Device、Installation、pairing、handoff、proxy lease 和 Cloud Session，提升相关 access epoch；
5. 临时启用账号并生成至少 128 bit 随机强度、满足正式密码策略的密码；
6. 保存密码哈希，不保存明文；创建带绝对 `expiresAt` 的 active lease；
7. 只在成功响应中返回一次明文密码和随机 lease token。

成功响应：

```json
{
  "leaseId": "opaque-id",
  "email": "test3@ai2apps.com",
  "password": "one-time-random-value",
  "leaseToken": "opaque-release-capability",
  "expiresAt": "2026-09-08T07:33:58Z"
}
```

同一 `poolId + runId` 重试必须幂等。第一次响应在网络层不确定时，服务端应先回收该 lease，再创建新密码的新 lease，或提供等价的不泄密恢复协议；不能让客户端猜测结果，也不能再次返回之前的明文密码。

池耗尽返回 `409 TEST_ACCOUNT_POOL_EXHAUSTED`，可提供最早可用时间，但不能暴露其他 Run ID、调用方或密码。

## 4. 释放租约

`POST /v1/test-account-leases/{leaseId}/release`

```json
{
  "runId": "20260908T053358Z-94042",
  "leaseToken": "opaque-release-capability"
}
```

Cloud 必须验证 lease ID、Run ID 和常量时间比较的 token，然后原子执行：

1. 撤销账号所有 Cloud Session；
2. 撤销本次及任何残留 Device/Installation、pairing、handoff 和 proxy lease，提升 access epoch；
3. 再次生成随机密码并只保存哈希，且不把新密码返回客户端；
4. 禁用账号；
5. 把 lease 标记为 released，保存完成时间和清理计数。

返回 `{"status":"released"}`。重复释放必须幂等并返回相同状态。

## 5. TTL 与崩溃恢复

- Cloud 定时任务至少每分钟回收过期 active lease，步骤与显式 release 完全一致。
- 客户端可以做 heartbeat 延长租约，但总时长不得超过服务器上限；V1 默认 2 小时，上限 4 小时。
- ATS 的正常、失败和中止路径都执行 release；进程被强杀、机器断电或网络断开时由 TTL 兜底。
- release 失败时，报告必须是 `BLOCKED` 并显示 `account cleanup pending`；不得把账号回收失败隐藏成测试通过。

## 6. 客户端 Harness 行为

1. 只为声明 `requires: [test-account]` 的用例获取租约。
2. 明文密码和 lease token 只保存在 macOS Keychain，Key 为 Run ID；`state.json` 只记录 lease ID、邮箱、到期时间和状态。
3. Harness 启动并复验固定 Test App 后，把密码直接提交给 Test Local 的正式 `/v1/platform/cloud/auth/login`，随后用 `/auth/me` 验证 Session。密码不经过 Codex、Computer Use 或截图。
4. teardown 先调用 Test Local `/auth/logout` 清除本地 Cloud Session，再调用 Cloud release，最后删除 Keychain lease secret。
5. 任何响应、异常、日志、timeline、截图和报告都不得包含临时密码、lease token、Bearer 或 Cookie。

## 7. Cloud 验收

Cloud 项目至少覆盖：10 个账号并发互斥、池耗尽、同 Run 幂等、跨 Run token 拒绝、非 allowlist 永远不可租用、获取时旧设备/Session 清理、释放时新设备/Session 清理、密码两次轮换、禁用恢复、TTL 回收、release 幂等、并发 acquire/release、审计脱敏，以及普通用户或管理员 Session 调用被拒绝。

部署后在专用 Test 机器运行：

```shell
./bin/ai2apps-test account configure
./bin/ai2apps-test account doctor
./bin/ai2apps-test select --priority P0
```

`configure` 只能通过隐藏输入写 Keychain。不得增加 `--token` 命令行参数。
