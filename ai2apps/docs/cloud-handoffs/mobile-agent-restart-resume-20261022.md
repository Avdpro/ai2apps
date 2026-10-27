# Mobile Agent 重启续接需求

日期：2026-10-22。状态：待 Cloud 协议变更；当前客户端不得绕过撤销检查。

## 问题与证据

iPhone 已恢复 Apps，但 Agent 报 `Agent connection is not active`。现有 Cloud `desktop-mobile-agent-v1.md` 明确规定 Desktop 重启/更换 enforcement instance 提升代次并废止旧 Agent。Local 每次启动生成新的 enforcerInstanceId，challenge/proof 前同步 Cloud activeConnectionId，旧连接不再 active 时拒绝；本地重启回归测试也明确断言 activeConnectionId 为空。

此前 iOS 修复解决的是 Owner Apps 登录恢复，并未改变该 Agent 协议，不能宣称完整恢复。

## 所需协议

将长期的 Desktop 批准关系与短期进程租约分离。正常进程重启可续接；停用、主动退出、撤销、替换配对、账户或组织权限变化不能自动恢复。

- 保留已批准关系：用户、Device、Installation、配对连接、公钥指纹、授权范围、批准代次及撤销状态。重启不得把撤销关系重新解释为批准。
- 每次进程仍使用新的 enforcerInstanceId；旧租约、nonce 与请求签名立即失效，不复用旧进程身份。
- 新 Local 用现有设备认证声明新进程后，Cloud 判断原批准关系是否仍可恢复。新协议能力必须显式协商，旧协议行为不变。
- 手机申请一次性挑战并用原配对私钥证明持有；Cloud 重验用户登录/账户会话、Owner 身份、设备与安装绑定、公钥、批准与撤销代次，再发绑定新进程的新短租约。明确登录有效性的验证来源；不能将持有连接 ID 或 Apps Cookie 视为 Agent 授权。
- 需要 Local 确认时采用幂等 prepare/ACK，先持久化新隔离代次再确认；丢响应可恢复同一事务，不能复活旧授权或重复执行业务。
- 旧 Local 回报、并发重启、重放挑战、撤销与续接竞争必须失败关闭。Cloud 不可用时不给权限。
- 返回可区分的原因：可恢复的进程更换、需登录、主动撤销、被替换、停用、权限变化；UI 显示 Apps 与 Agent 的独立状态。
- 续接仅恢复授权与读取已有状态，不重发聊天、创建任务或重试结果未知的写操作。

## 交付与验收

Cloud 请提供新能力字段、精确方法/路径、请求响应、签名输入、有效期、错误码、兼容规则及生产回执。Local 收到合同后接入，不从客户端自行推测字段。

覆盖：批准后重启免扫码恢复；旧进程租约拒绝；无原私钥/跨用户/跨设备拒绝；退出/撤销/停用/替换后拒绝；撤销与恢复竞争；prepare/ACK 丢响应；离线后恢复；Apps-only 不升级 Agent；原 Agent 历史可读且任务不自动重发。最后做真实 iPhone + Desktop 重启闭环。
