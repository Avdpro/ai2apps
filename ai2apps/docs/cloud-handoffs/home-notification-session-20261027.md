# home 登录态与原生通知自动同步

日期：2026-10-27

## 故障与证据

iOS 已通过 `https://home.ai2apps.com/mobile/account` 登录并进入 Desktop，通知面板却显示“请先在 App 中登录 AI2Apps”。

客户端 `NotificationAuth.swift` 的 NotificationWebAccount 固定读取 coder 的 `/api/v1/notifications/account/web`；AutomaticNotificationAuthorization 也固定使用 coder 的 `/api/v1/notifications/session/handoff`。home Cookie 为 host-only，coder 401 无法证明 home 未登录。

Cloud 当前 home Nginx 仅将 /v1/ 等前缀送到 API，/api/v1/notifications/ 未接入 home。不能只修改客户端域名或依赖重定向修复。

## Cloud 所需合同

1. 在 home 精确暴露浏览器身份 GET `/api/v1/notifications/account/web`，使用该域自己的浏览器 Session；响应沿用 account_id 与 notification_session，明确通知交接能力及同源 endpoint。
2. home 精确暴露 GET/POST `/api/v1/notifications/session/handoff`，沿用原安装公钥证明、持久 revision、PKCE、state、单次兑换、scope=notifications 与 callback 来源防护。POST Origin 必须对应 home；不得通配或把 coder Origin 当成 home。
3. 原生 token exchange、refresh、revoke、通知 API 可继续通过 coder 使用现有独立 bearer；home 产生的授权码必须可由同一通知授权服务按既有 PKCE 合同兑换，并绑定实际 home 浏览器 Session。请明确服务是否已有这个共享能力。
4. home 退出应撤销由该 home Session 派生的通知家族/绑定；账户 A/B 切换不复用。不能复制 Cookie、扩大 Cookie Domain、转发密码、用 Device 租约/通知 token 冒充网页登录。
5. 保留旧 coder 登录流程及授权合同；明确双域均登录且账户不同的策略，禁止静默择取另一个账户。
6. home 若只有普通登录而通知能力尚不可用，应明确能力不可用，不能把已登录解释为未登录。

## 客户端将接入

- 通知网页身份、自动 handoff 与回调来源校验迁移至明确声明的 home 同源合同，仍使用持久 WKWebsiteDataStore。
- 同一轮身份/交接/兑换绑定 account 与 origin；兑换前重查同源账户。
- 401 只代表该域登录失效，不从 coder 401 推断 home 退出。
- 继续保留持久撤销、安装证明、账户切换 fencing、最多30条消息及不统计未读。
- 不重放聊天、任务或其他业务请求。

## 验收

仅 home 登录且 coder 未登录：正常同步通知；未登录/未验证/退出/切换账户：正确拒绝且旧通知消失。PKCE错误、跨域POST、来源伪造、重复handoff与安装revision冲突均拒绝。既有coder合同回归。生产提供精确路由/方法、响应和撤销绑定证据后，客户端构建并覆盖安装测试手机，真实 APNs 与消息列表另做实机验收。

本轮未修改 Cloud 源码、未读取 Cookie，也未以 Desktop 连接替代通知授权。
