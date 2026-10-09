# Owner Open-Home：Cloud 授权入口与会话续期需求

日期：2026-10-07
状态：待 Cloud 项目确认、实现与部署；本仓库不修改 Cloud 代码。

## 目标与现状

用户希望用账户固定 `/u/<ownerUserId>` 链接，在 Cloud 完成登录，Owner 可进入自己的 Mobile Home、查看并使用已有 App；访客仅进入发布的 Open-Entry。

当前 personal-space-v1 断言有效 120 秒，Local 个人空间会话也严格止于该期限。Owner 同样受限。这是访问授权断言，不能转换为成员/管理员凭证。单纯放宽 Local 时间或拉长 JWT 不能实现可撤销的持续授权。

已有 Cloud 成员交接 API：

- `POST /v1/installations/:installationId/member-handoffs`，登录用户自身的 Cloud Session 授权。
- `POST /v1/internal/installations/:installationId/member-handoffs/exchange`，Device 身份兑换。
- 成员 JWT audience：`ai2apps-installation-member-v1`；与个人空间访问凭证分离。

但当前 `remote_mobile` 返回 `/mobile/complete#handoff=...`，Local 旧页面会将其发给 **Remote Mobile pairing exchange**，两种 handoff 所属协议不一致。不要混用或尝试多个兑换端点。

Local 新接收入口已准备（源码及隔离测试完成，未因本次准备重启运行实例）：

- `GET /mobile/member/complete`：复用 Mobile Home 模板。
- `POST /v1/mobile/member-session/exchange`：只走 Installation member exchange，验证设备/Owner/installation，创建独立 HttpOnly Mobile Cookie。
- 成功进入 `/mobile`，复用 Mobile Ready App 目录、实例、Dock、打开/切换/关闭。
- Owner 不匹配、设备停止、epoch 变化时拒绝，撤销临时 Local 会话。
- 当前仍用既有 Mobile 15 分钟会话，不能宣称长会话问题已解决。

## Cloud 需求一：Owner 授权入口

建议在 `/u/<ownerUserId>` 的 Cloud 页面提供“进入我的应用”，通过服务器当前登录身份核对：

1. 访问者确为该空间/主设备的 Owner，installation、membership、设备、权益均有效。
2. 普通访客不能请求或获取 Owner 授权；不能相信客户端传入 role、ownerUserId 或 installationId 就直接放行。
3. 以访问者自己的 Cloud Session 创建成员 handoff；不使用 Device 安装会话或后台 Owner Session 代替浏览器访问者。
4. 兼容旧客户端：建议新增明确 target（拟 `remote_open_home`）或版本化能力协商，跳转到精确的 `https://device-<slug>.<remoteDomain>/mobile/member/complete#handoff=...`。旧 `remote_mobile` 不能无协商更改回调。
5. 只有声明支持成员回调的新客户端才展示可用授权入口。Cloud 部署前请回传最终 capability、target、回调和错误码合同，Local 再接声明与按钮。
6. 复用 Cloud 已登录会话，除非策略要求重新认证，否则不要求用户再次输入密码。所有密码、Cloud Cookie 均留在 Cloud 域名。
7. 如果要从设备 Open-Home 点击跳回 Cloud 授权，请提供由 Cloud 返回的稳定 owner-authorization URL；不接受任意 return URL，Local 不猜测不存在的 Cloud 页面地址。

## Cloud 需求二：短期交接与持续会话分离

保留一次性 handoff 和短时 JWT。新增或明确 **可撤销的设备端使用会话授权合同**，允许 Local 在短期断言到期后，按 Cloud 授权的租约继续服务和续期；不要仅把 JWT exp 改大。

建议初始策略（待产品/Cloud 确认）：最长 8 小时、闲置 30 分钟、每 60 秒重新校验；敏感管理动作另行提升授权。Cloud 应返回策略，Local 不硬编码为永久身份。

合同至少需要：

- 明确会话创建/刷新/撤销 API、认证主体、返回 schema 和签名 audience。
- 绑定 actor、owner、device、installation、organization、role、membership_epoch、access_epoch、account_session_epoch、local_session_epoch、scope、session ID；个人空间续期还须考虑 mapping/capability revision。
- 刷新凭据只保存在 Local 服务器；浏览器仅持有 Secure/HttpOnly 的不透明 Cookie，不接收 Cloud bearer/refresh token/Device secret。
- 每次刷新验证 Cloud 当前身份、成员状态、主设备/能力映射、设备状态和权益；禁止凭过期断言无限续期。
- 成员撤销、Owner 变化、退出所有会话、设备停止/撤销/epoch 轮换即时或在明确的短窗口内使会话失效；长连接/流式请求也需执行有界撤销。
- Cloud 不可用时只允许已有租约的明确定义窗口，不延长权限，过期后关闭受保护操作。
- 明确 401/403/409/503 错误语义；恢复登录后保留安全的 App 导航/草稿引用，不恢复被撤销的权限或跨用户实例。
- Owner 和访客可采用不同策略，但访问者不能借 Owner 身份标签升级为成员会话。

## 验收

1. 已登录 Owner：固定链接 → Cloud Owner 授权 → 独立成员交接 → Mobile Home → 列表 → 打开并完成一次真实 App 操作。
2. 使用超过 120 秒不掉线；超过旧 Mobile 15 分钟时按新合同续期，而非无条件延长 Local 会话。
3. 访客、过期/重放/wrong-device handoff、错误 audience、非 Owner 成员不能进入 Owner 专用接收入口。
4. 修改 role/member/account/device epochs、撤销与 Cloud 故障按合同收敛；并发请求不能越过停止/撤销。
5. Owner App Session 不授予任意 `/admin`、`/v1/platform`、模型 API、MCP 访问；具体 App 仍使用其授权能力与数据隔离。
6. 返回 Cloud 部署版本、合同、验收证据和回滚方式；Local 随后接入正式按钮、续期和端到端验证。

## Local 后续

Cloud 确认后增加能力协商和“我的应用”入口，接入续期/重新认证、Mobile Home 状态与错误反馈。若具体 App 尚不能通过公网受限 API 完成操作，应增加逐能力授权的 App 接口，不能把整个内部平台 API 加入公网白名单。
