# Owner Mobile：有效账户登录自动恢复设备访问

状态：Local / iOS 已准备能力协商与恢复客户端；Cloud 尚未实现或部署本协议，完整无感恢复不得宣称上线。日期：2026-10-16。

## 产品规则

App 与网页使用同一规则：账户登录有效、仍为目标设备 Owner、设备访问未被撤销时，短设备会话到期应重新取得；不得将 8 小时绝对期限、30 分钟闲置期限、60 秒租约等同于账户登录期限。保留短会话、租约和所有权限校验，不通过延长 JWT 或忽略过期达成体验。

网络中断、后台挂起、Local 重启导致的会话丢失应恢复；设备离线显示等待上线，不提示退出登录。真正登录失效进入正常登录流程。Owner 改变、账号禁用、设备撤销、用户明确退出该连接不得静默重新授权。恢复不重发任何生成、聊天、发布、支付、上传等业务操作。

原生主 WebView 为持久化 WKWebView，沿用 Cloud 网页登录。通知 OAuth 是另一套凭据/范围，不能因为它有效就自动当作设备 Owner 授权。如未来支持原生账户凭据交换，需另行定义受限、账户一致的交换协议，禁止把通知 token 或浏览器 Cookie 交给 Local。

## Cloud 最小接入契约

在既有 `PUT /v1/internal/spaces/owner-home/device` 响应新增可选字段：

```json
{"ownerLoginResumeProtocol":"owner-login-resume-v1"}
```

仅在相应生产入口及安全矩阵全部可用后返回。缺失或其他值代表未就绪，Local 不启用自动恢复。原有 ownerAuthorizationUrl 及旧流程保留。

新增同一账户入口的恢复模式（不新增 Local 公网 API）：

```
GET https://coder.ai2apps.com/u/{ownerUserId}?entry=owner-home&resume=1&device_origin={URL编码的原Desktop HTTPS origin}
```

Local 根据受信任注册设备/安装身份构造该 URL，在已授权的 `GET /v1/mobile/owner-home/status` 响应中返回可选 `ownerResumeUrl`。URL 是非敏感导航提示，不是凭据，不包含 token、handoff、签名或任意 return URL。原生与网页只接受 coder 精确主机、UUID 账户路径、唯一的三个参数、与当前 Desktop 一致的设备 origin。

Cloud 必须：

1. 通过自身 HttpOnly 账户登录会话及既有刷新机制确认当前账户。不能信任 query、User-Agent 或调用的是 App API。
2. 将 device_origin 精确解析为注册设备；检查当前账户与路径 Owner 相同、设备属于该 Owner、安装/组织/成员/credential/access epoch 均有效、设备启用且允许 Owner Home。不得跳到其他主设备、同账号的另一个实例或 App-Dev。
3. 登录有效且权限未撤销时，签发新的独立一次性交接，走原有受限 handoff/交换及 Local 短租约流程。由同一个浏览器会话完成跳转，保留现有跨站、CSRF、回跳目标校验，不能允许第三方任意发起跨账户绑定。
4. 登录无效时进入 Cloud 登录页面；成功后只恢复同一合法目标。403/撤销不自动创建替代会话；显示明确原因。
5. 离线设备显示等待/重试状态，不能发无限 handoff 或重定向循环。无缓存、no-referrer；日志不泄露交接或刷新凭据。
6. 区分自然到期/重启与主动退出/撤销。主动退出应在 Cloud 的账户登录会话与目标设备维度记住阻断状态，直到用户明确选择再次进入；不得靠 Local 的临时页面标记作为唯一撤销保护。账号登出/封禁、Owner 变化、设备撤销使已有短会话和后续恢复均不可用。
7. `entry=owner-home` 普通入口继续兼容，已登录的 Owner 可直接恢复自身有效访问；首次安全确认（若有）和明确退出后的重新进入不能由静默恢复绕过。

## 已实现的客户端

- 网页 Owner 状态检查加 10 秒超时与并发抑制；网络异常/429/5xx 不清空页面、不宣称登录失效，继续只读探测。
- 401 与 403 分开：401 仅在 Cloud 能力已声明且收到有效原设备恢复 URL 时发起恢复；403 不自动恢复。主动退出清除 hint 并标记阻止原生恢复。
- 网页只在前台进行自动导航，每 tab 每 5 分钟最多一次；storage 不可用时不自动导航，以避免循环。
- iOS 401 文案改为“连接需要恢复”，使用同样的能力入口及每连接 5 分钟预算；非秘密 hint 与选择的连接绑定，冷启动可复用。只加载新 GET，不重发业务。
- iOS 不读 Cookie/不转发 token，恢复仍由 Cloud 检查持久化 WebView 登录；实际手机需安装更新版本后验收。
- 自管 VPN/隧道保持独立配对策略，不使用 Cloud 账户恢复能力。

## 必须通过的验收

- 同一用户：网页和 iOS，前台 >8 小时、后台 >30 分钟、短租约过期、断网/网络切换、Desktop Local 重启后，账户仍有效则自动恢复同一设备。
- 失效/撤销：账户登录过期、账号退出/禁用、Owner 变更、device/credential/access epoch 撤销、明确退出该连接，都不被自动恢复绕过。
- 恶意参数：其他用户 UUID、其他实例 origin、重复参数、伪造 App 标识、外域/端口/凭据/fragment/任意 return URL 被拒绝。
- 防循环：Cloud 离线、Desktop 离线、交接失败、恢复后仍 401，不产生重定向风暴，不自动重发生成等操作。
- 回归：匿名访客空间、普通网页登录、通知 OAuth、Package sandbox / Bridge 范围、受限资源路由不变。

Cloud 项目完成实现、部署和回执后，Local 再重载并确认 capability、iOS 安装新构建，执行真实 Chrome/iPhone Safari/App 长会话验收。不要提前打开能力声明。
