# Administrator verification 可选有效期：Cloud 修改需求

## 目标

Account App 的 Administrator verification 支持由管理员选择验证有效期：5、15、60、180 分钟。Local 只负责转发密码和所选时长，不保存密码；最终有效期必须由 Cloud 校验、持久化并执行。

## API 合同

扩展现有接口：

```http
POST /v1/admin/reauth
Content-Type: application/json

{
  "password": "<administrator password>",
  "durationMinutes": 60
}
```

要求：

- `durationMinutes` 只能是整数 `5`、`15`、`60`、`180`。
- 为兼容旧客户端，字段缺省时按 `15` 分钟处理。
- 字符串、浮点数、负数和其他整数必须返回 `400 INVALID_REQUEST`，不能静默回退或截断。
- 密码校验失败继续返回现有的 `401 INVALID_CREDENTIALS`。
- 非管理员继续返回现有的 `403 ADMIN_REQUIRED`。
- 成功响应结构保持兼容：

```json
{
  "verifiedAt": "2026-08-27T08:00:00.000Z",
  "expiresAt": "2026-08-27T09:00:00.000Z"
}
```

- `expiresAt` 应为 `verifiedAt + durationMinutes`，但不得晚于当前 Cloud Session 的绝对过期时间。
- 更新 OpenAPI：请求增加 `durationMinutes` 枚举 `[5, 15, 60, 180]`、默认值 `15`，接口描述不再写死 15 分钟。

## 会话与数据模型

目前仅保存 `admin_verified_at` 并按固定 15 分钟判断，无法准确表达每次选择的有效期。Cloud 应：

- 为 Session 增加可空的 `admin_verified_until`（timestamp with time zone）。
- 新的管理员验证同时写入 `admin_verified_at` 和 `admin_verified_until`。
- 权限判断以 `admin_verified_until > now` 为准。
- 对迁移前的 Session 保持兼容：当 `admin_verified_until` 为空且 `admin_verified_at` 非空时，仍按旧规则 `admin_verified_at + 15 分钟` 判断；不要因上线新功能把既有 15 分钟窗口延长到 180 分钟。
- `/v1/auth/me` 返回的 `adminStepUpExpiresAt` 使用实际的 `admin_verified_until`；旧 Session 使用上述 15 分钟兼容计算。
- 管理员登录时已有的初始 step-up 行为保持 15 分钟，除非产品另行决定。

## 审计与安全

- `account.admin.reauthenticated` 审计事件增加 `durationMinutes` 和 `expiresAt`，不得记录密码。
- 所有敏感审核、发布和管理员接口必须使用同一个“当前 step-up 是否仍有效”的判断，不能只判断 `admin_verified_at` 是否非空。
- 现有 reauth 速率限制保持不变。
- 180 分钟只影响本次管理员 step-up，不得延长 Cloud Session 本身，也不得跨 Session 或跨设备生效。
- 再次验证应覆盖当前 Session 的旧有效期，以最新一次成功选择为准。

## 验收标准

- 分别选择 5、15、60、180 分钟后，响应 `expiresAt` 与服务器时间的差值正确（允许测试执行耗时误差）。
- 缺省 `durationMinutes` 时仍为 15 分钟。
- 传入 `30`、`"60"`、`60.5`、`null` 均被拒绝。
- 5 分钟窗口过期后敏感接口返回 `ADMIN_REAUTH_REQUIRED`；60 和 180 分钟窗口在各自有效期内可用。
- Session 先于所选窗口到期时，step-up 同时失效。
- 数据库中已有的旧 15 分钟验证不会在部署后意外延长。
- OpenAPI 合同测试、AuthService 单元测试和管理员路由集成测试覆盖以上场景。
