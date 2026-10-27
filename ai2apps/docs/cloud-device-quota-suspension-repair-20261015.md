# Cloud 修复交接：已有 Dev 设备被 quota 暂停

日期：2026-10-15，Asia/Shanghai。状态：Cloud 阻塞；本地数据保留，未改绑、未重新注册设备。

## 实测证据

账户：avdpro@me.com，Core 用户 b8696bee-d730-46b6-848c-e41f1f96a0b4。

通过该账户已登录的标准 Cloud GET 接口核实：

| 记录 | ID | Cloud 状态 | suspensionReason |
| --- | --- | --- | --- |
| 当前本地 Dev 实际绑定，名称 MacIntel · AI2Apps | cedeacbd-24bd-47e8-b184-cfdfdbe2f2c3 | suspended | quota |
| 当前绑定 Installation | 23c1b9d7-1cc1-4e6d-bd3c-489af8c367a2 | suspended，accessEpoch=2，role=core | 关联上行设备 |
| 另一条名为 Dev 的设备 | d1bb570c-c871-4ee3-b917-589cfacdf71e | active | null |
| App-Dev（旁证，不自动修改） | 98f3c5ab-6c8e-42f6-83ea-d049d82a114f | suspended | quota |

不能按显示名称把本地 Dev 对应到名为 Dev 的另一条记录。Cloud GET Installation 返回的 cloudDeviceId 明确是 cedeacbd…e2f2c3。

14:36 起 Device 授权投影接口返回 403 REMOTE_DEVICE_AUTHORIZATION_DENIED，Local 按原安全契约暂停 Installation 并清除 Local Session。14:54 用户密码登录 200，原 Installation 与 Device 的账户读取均 200，但恢复检查确认 Cloud 设备仍非 active，因此没有轮换凭据，也没有签发 Session。错误不是密码错误或本地文章/Todo 被删除。

## 必须遵守的产品规则

仓库 docs/ai2apps-cloud-account-capacity-v1.md 第 1、4、5 节：容量只用于新增绑定准入；等级下降、订阅结束或退款不应回收已有设备/成员，不应使已有 Session 失效。凭据轮换、重连和同一 Installation 的幂等请求不算新增设备。

## Cloud 项目需要执行

1. 查审计记录、容量重算、套餐/等级投影、历史迁移，定位为何上述已有设备在 14:15 左右被 quota 暂停。不要仅调高账户额度掩盖回收逻辑。
2. 为该账户恢复原设备 cedeacbd-24bd-47e8-b184-cfdfdbe2f2c3 及原 Installation 23c1b9d7-1cc1-4e6d-bd3c-489af8c367a2 的合法 active 状态，保留所有原 ID、组织/Core/计费归属与原 URL。不新建 Device/Installation、不把本地数据改挂 d1bb570c…cdf71e、不撤销其它设备释放配额。
3. epoch 只能单调前进，不能回退。检查现有凭据是否因暂停而失效：若失效，允许该设备原 Core 使用标准凭据轮换流程恢复，不接受本地伪造 active。原 revoked 设备、安全/风控/管理员暂停不得被 quota 修复顺带复活。
4. 修正生产容量计算：超额时保留既有资源，仅拒绝新增；区分 quota 与管理员/凭据/撤销原因，返回稳定错误码和可显示的原因。
5. App-Dev 同为 quota 暂停，作为同源问题检查；恢复操作需按账户授权范围单独记录审计，不复制实例数据。

## 验收

- 原账户 GET Device 与 Installation 均 active，cloudDeviceId 仍为 cedeacbd…e2f2c3；Device 授权投影 200。
- 原 Core 在固定 Dev 正常登录；凭据如需轮换只操作原设备，标准 handoff/签名/epoch 检查继续有效。
- 既有 3 个情报频道、125 篇情报，5 个 Todo 目录、132 个项目可见。备份为 Dev data/recovery-backups/device-auth-20261015-144629。
- 重启 Local 及周期投影复查后不再次变为 suspended。超额账户新增绑定失败，已有连接与 Session 不受配额降级影响。
- 覆盖真实 suspended/revoked 不恢复、错账户/错设备拒绝、并发容量更新、幂等轮换不占新名额。

## Local 已做的工作与边界

已添加“原 Core 登录验证原 authority → Cloud 原设备 active → 标准凭据更新 → Device 投影复验 → 签发 Session”的恢复路径，56 项定向回归通过。当前 Cloud 仍明确 suspended/quota，Local 正确拒绝绕过它，不能靠改本地 SQLite 或清空实例解决。

按照本仓库 Cloud 变更边界，此文档交 Cloud 开发项目修复、部署与审计；本仓库不直接修改 Cloud 服务端或生产数据库。
