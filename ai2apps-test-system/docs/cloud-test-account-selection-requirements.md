# Pipeline 指定测试账号的 Cloud 修改需求

## 问题、影响和修改原因

Pipeline 将采用显式“启动 Test Helper”动作，动作可配置不登录、自动分配测试账号或指定测试账号。
当前 Broker 只能从池中自动分配账号，因此客户端无法可靠保证用户选择的账号被租用。不得通过反复申请/释放、读取密码、绕过租约或直接 Cloud 数据库操作模拟选择。

## 当前契约与代码证据

- Cloud `src/test-accounts/routes.ts` 的 `POST /v1/test-account-leases` 仅接受 `poolId/runId/ttlSeconds/client`，`exactObject` 拒绝其他字段。
- Cloud `src/test-accounts/service.ts` 的 `acquire` 从可用成员中选取 slot；现有相同 Run 恢复路径复用租约。
- Harness `src/ai2apps_test/accounts.py` 的 `TestAccountManager.acquire` 无指定账号参数。
- 本次 Run 的 `accessibility-permission` 属于客户端 macOS 权限问题，不是 Cloud 账号选择问题；本需求不应被当作该错误的修复。

## 所需接口与行为

1. 为申请租约增加可选 `accountEmail`。省略时完全保持现有自动分配行为。
2. 指定邮箱必须规范化并严格属于配置的测试账号池；不接受任意用户邮箱，不创建账号。
3. 指定账号繁忙、禁用或不可用时返回稳定可识别错误，绝不静默分配其他账号。
4. 选择和加锁、租约创建须在同一事务内，保留并发互斥。
5. 相同 Run 的重试必须返回同一账号的有效租约；若已有租约与本次指定账号不一致，返回明确冲突，不隐式轮换账户。
6. 返回结构、临时凭据、TTL、heartbeat、release、安全日志脱敏沿用现有协议。

## 安全与兼容

- 仍要求正式 Broker Credential、固定 Test bundle/instance 和合法 poolId。
- 不新增公开账号登录接口；凭据仅由 Harness 保存到 Keychain，不进入 UI、Case、Pipeline 或 Run 产物。
- 保留旧客户端兼容，新增参数必须可选。不需要客户端枚举生产账户。
- 不得削弱设备限制或辅助功能权限检查。

## 回归与验收

- 无 accountEmail 时旧请求/恢复/释放流程通过。
- 指定每个池内邮箱时返回账号严格匹配。
- 非池账号、错误类型、禁用账号被拒绝。
- 并发申请同一账号仅一个成功；忙时无其他账号回退。
- 相同 Run 同账号重试可恢复，换账号请求冲突。
- 临时密码/lease token 不出现在日志、错误信息或审计明文中。

## 部署顺序与客户端后续

1. Cloud 工程实施、回归、更新 OpenAPI 并部署，提供交付回执。
2. Harness 接入 `accountEmail`，在租约返回后再次校验邮箱，不匹配时释放并阻断。
3. Pipeline 新增 `start-helper` 动作与登录模式/账号选择，默认不隐式启动实例、不隐式租用账号；启动和登录失败只记录到当前动作，后续依赖步骤明确说明缺失前置条件。
4. 旧 Pipeline 不自动改写、不注入隐藏动作；运行前提示需要显式添加启动动作。
5. 登录前检查负责原生登录进程的辅助功能权限，显示明确修复指引；用户自行授权后重试。不要以 Cloud 改动掩盖权限失败。
6. 不登录表示不执行登录或退出登录，也不清除既有 Session；干净登录态通过单独重置动作控制。

本工程不直接修改或部署 Cloud。账号指定功能的最终验收须等待 Cloud 契约交付。
