# AI2Apps Cloud 账户与家庭网关容量 V1

状态：待 Cloud 实现
客户端兼容策略版本：`account-capacity-v1`

## 1. 目标

Cloud 根据账户基础等级和付费套餐，限制：

1. 一个账户能够作为 Core 绑定的 installation/设备数量；
2. 该账户作为 Core 的每台设备能够加入的非 Core Member 数量。

限制仅用于准入。等级下降、套餐到期或退款不得解绑已有设备，不得删除、Suspend、
Revoke 已有 Member，也不得使其现有 Session 失效。

## 2. 基础等级额度

| Level ID | 显示名称 | `maxCoreDevices` | `maxMembersPerDevice` |
| --- | --- | ---: | ---: |
| `unverified` | 未验证用户 | 0 | 0 |
| `member` | 注册用户 | 1 | 2 |
| `creator` | 创作者 | 1 | 5 |
| `trusted_creator` | 可信创作者 | 3 | 10 |
| `core_contributor` | 核心贡献者 | 10 | 20 |

Core 自己不计入 `maxMembersPerDevice`。

## 3. 付费套餐额度

付费套餐不能覆盖账户的贡献等级。Cloud 必须分别保存基础 `level` 和
`subscriptionPlan`。

| Plan ID | 显示名称 | `maxCoreDevices` | `maxMembersPerDevice` |
| --- | --- | ---: | ---: |
| `none` | 无付费套餐 | 0 | 0 |
| `subscriber` | 订阅用户 | 5 | 5 |
| `team` | 团队用户 | 20 | 50 |

有效额度逐字段取较大值：

```text
effective.maxCoreDevices =
  max(level.maxCoreDevices, subscriptionPlan.maxCoreDevices)

effective.maxMembersPerDevice =
  max(level.maxMembersPerDevice, subscriptionPlan.maxMembersPerDevice)
```

示例：

| 基础等级 | 付费套餐 | 有效设备数 | 单设备Member数 |
| --- | --- | ---: | ---: |
| 注册用户 | 订阅用户 | 5 | 5 |
| 可信创作者 | 订阅用户 | 5 | 10 |
| 核心贡献者 | 团队用户 | 20 | 50 |

## 4. 订阅状态

Cloud 应把支付系统状态归一为内部套餐投影。只有处于 Cloud 定义的有效服务期内的套餐
才参与额度计算。取消自动续费但尚未到期时仍然有效；服务期结束、退款或强制终止后使用
`none` 的套餐额度重新计算。

重新计算只影响后续准入，不回收现有资源。

## 5. Core设备准入

### 5.1 计数

`coreDevicesUsed` 是当前账户作为 Core/Owner 绑定、且 installation 状态尚未 revoked 的
installation 数量。不能用浏览器Session、Remote Mobile Session或connector凭证数量代替。

同一 installation 的幂等重试、设备改名、凭证轮换、connector重启和Remote重新连接都不算
新增设备。已 revoked/解除绑定的 installation 不占名额。

### 5.2 检查

仅在创建新的 Core installation 绑定时执行：

```text
allow when coreDevicesUsed < effective.maxCoreDevices
```

计数、判断和写入必须在同一个数据库事务/等价原子操作中完成，以账户ID作为并发一致性
边界。不得通过两个并发请求突破上限。

达到上限返回 `HTTP 403`：

```json
{
  "error": {
    "code": "CORE_DEVICE_LIMIT_REACHED",
    "message": "The account has reached its Core device limit.",
    "details": {
      "limit": 5,
      "current": 5,
      "levelId": "member",
      "subscriptionPlanId": "subscriber"
    }
  }
}
```

## 6. Member准入与Pending占位

### 6.1 已用名额

Member名额包含：

- role 不是 `core`/`owner`，status 为 `active` 或 `suspended` 的membership；
- status 为 `pending` 且尚未过期、尚未cancel/reject的invitation。

`revoked` membership不占名额。过期、cancel或reject的邀请不占名额。Suspend不释放名额，
只有Remove/Revoke才释放。

```text
memberSeatsUsed = membersUsed + pendingInvitationsUsed
```

### 6.2 创建邀请

只在创建新的邀请时执行：

```text
allow when memberSeatsUsed < effective.maxMembersPerDevice
```

计数、判断和创建Pending invitation必须在同一个事务/等价原子操作中完成，以installation ID
作为并发一致性边界。

达到上限返回 `HTTP 403`：

```json
{
  "error": {
    "code": "INSTALLATION_MEMBER_LIMIT_REACHED",
    "message": "The installation has no available member seats.",
    "details": {
      "limit": 5,
      "members": 4,
      "pendingInvitations": 1
    }
  }
}
```

### 6.3 邀请生命周期

- 创建Pending invitation时预占一个名额；
- resend同一个仍有效的邀请不新增占位，也不重新执行新增名额检查；
- 接受邀请把已预占名额从Pending转换为membership，不能再次计数；
- 邀请创建后即使账户降级，仍允许在有效期内接受，因为该名额已经被预占并 grandfather；
- 邀请过期、cancel或reject立即释放占位；
- 过期后重新创建/恢复邀请视为新邀请，必须按当前有效额度重新检查；
- 对同一installation和规范化email存在有效Pending邀请时，应返回现有邀请冲突或走明确的
  resend流程，不能重复占位。

## 7. 降级不回退

若现有使用量超过新额度：

- installation和membership保持原状态；
- 已有成员继续登录和使用；
- 已预占且仍有效的邀请可以被接受；
- 新设备绑定和新邀请被拒绝；
- 删除资源会降低使用量，但只有当使用量重新低于当前额度后才允许新增。

例如从每设备5名Member降为2名，当前已有5名：删除1名后剩4名仍不能新增；降到1名后才
能邀请第2名。

## 8. API契约

### 8.1 `GET /v1/levels`

每个等级增加：

```json
{
  "id": "member",
  "displayName": "注册用户",
  "limits": {
    "maxCoreDevices": 1,
    "maxMembersPerDevice": 2
  }
}
```

### 8.2 `GET /v1/auth/me`

用户对象增加：

```json
{
  "user": {
    "level": {"id": "trusted_creator", "displayName": "可信创作者"},
    "subscriptionPlan": {
      "id": "subscriber",
      "displayName": "订阅用户",
      "status": "active",
      "currentPeriodEndsAt": "2026-09-16T00:00:00Z"
    },
    "capacity": {
      "effectiveLimits": {
        "maxCoreDevices": 5,
        "maxMembersPerDevice": 10
      },
      "usage": {"coreDevices": 3},
      "grandfathered": false
    }
  }
}
```

没有付费套餐时仍返回 `subscriptionPlan.id = "none"`，避免客户端猜测空值。

`grandfathered` 表示当前设备使用量是否超过当前有效设备额度，仅用于展示，不改变权限。

### 8.3 `GET /v1/installations/{installationId}`

增加：

```json
{
  "capacity": {
    "effectiveLimits": {
      "maxCoreDevices": 5,
      "maxMembersPerDevice": 10
    },
    "usage": {
      "members": 8,
      "pendingInvitations": 1,
      "memberSeats": 9
    },
    "availableMemberSeats": 1,
    "grandfathered": false
  }
}
```

这里的有效额度必须按installation的Core账户计算，不能按当前查看者或被邀请成员的等级计算。

### 8.4 写接口

以下既有写接口增加最终执法，不新增Local私有绕过入口：

- installation/device bind/register接口：执行Core设备准入；
- `POST /v1/installations/{installationId}/invitations`：执行Member准入；
- invitation accept：消费已有预占，不创建第二份占位；
- invitation cancel/reject/expire和membership revoke：释放相应名额。

## 9. 审计与隐私

审计记录至少包含：actor、账户/installation、操作、允许/拒绝、有效额度、操作前使用量、
基础等级ID、套餐ID和策略版本。不得记录邀请token、密码、Cookie或邮件正文。

## 10. 客户端兼容

Local已经提供 `/v1/platform/cloud/capacity-policy` 作为Cloud上线前的展示回退，并识别：

- `CORE_DEVICE_LIMIT_REACHED`
- `INSTALLATION_MEMBER_LIMIT_REACHED`
- `user.subscriptionPlan`
- `user.capacity.effectiveLimits` / `user.capacity.usage.coreDevices`
- `installation.capacity.effectiveLimits` / `installation.capacity.usage`

Cloud字段上线后优先于Local回退表。最终准入始终以Cloud写接口为准。

## 11. 验收测试

Cloud至少覆盖：

1. 五个基础等级与三个套餐的全组合逐字段max测试；
2. 未验证用户不能绑定Core设备；
3. 注册用户第1台设备成功、第2台失败；
4. 注册用户每设备2名Member，第3个新邀请失败；
5. Pending邀请占位、过期/cancel/reject释放；
6. 两个并发设备绑定不能越过最后一个名额；
7. 两个并发邀请不能越过最后一个Member名额；
8. resend不重复占位；接受邀请只把Pending转换成membership；
9. 降级后已有设备、Member、Session和有效Pending邀请保持可用；
10. 超额状态删除部分资源后，未降到当前额度以下时仍不能新增；
11. 升级套餐后无需迁移即可立即新增；
12. installation容量必须按Core账户而不是当前成员账户计算；
13. 错误响应和OpenAPI使用稳定大写错误码；
14. 审计不包含秘密和邀请token。
