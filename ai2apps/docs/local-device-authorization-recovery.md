# Local 设备授权恢复

设备授权投影接口明确拒绝凭据时，Local 仍暂停 Installation 并撤销已有本地 Session。账户密码正确不代表设备凭据有效，不能直接把本地 suspended 改回 active。

Core 账户从标准登录入口再次登录时，对原 suspended Installation 执行恢复：

1. 用该浏览器的 Cloud 登录会话读取原 Installation，核对 Installation/Device/组织/Core/计费身份全部保持不变，并要求当前登录者为 Core/Owner。
2. Cloud 原设备必须 active；Installation 若明确为非 active，不恢复。校验 epoch 不倒退。
3. 调用既有设备凭据更新接口，将新凭据保存到同一 SecretBackend key；不注册新设备，不读取或迁移其它实例凭据。
4. 同步原绑定并通过 Device 身份重新取得完整授权投影。只有这一步成功，才继续原有一次性 member handoff 和本地 Session 签发。

恢复与周期授权投影刷新通过同一互斥锁串行，防止旧拒绝响应覆盖刚恢复的绑定。恢复失败保持 suspended；revoked 绑定不自动恢复。Cloud 权威授权及签名校验保持原规则。

此操作不删除情报、Todo、附件、文章或执行记录，也不更改 owner ID。进行实例修复前应使用 SQLite backup 备份数据库，不复制或合并 Dev/App-Dev/生产实例。

Dev 2026-10-15 排障：原设备授权返回 REMOTE_DEVICE_AUTHORIZATION_DENIED，正常 Cloud 登录 200，但本地 suspended 提前阻断激活，形成恢复死路。增加本流程用于修复原设备凭据；Cloud 设备真正被禁用时仍需由账户管理员处理。
