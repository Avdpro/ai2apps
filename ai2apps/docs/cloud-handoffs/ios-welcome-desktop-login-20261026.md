# iOS 欢迎页与账户 Desktop 入口对接 — 2026-10-26

## 目标与现有实现
首次启动显示欢迎页、登录 AI2Apps、扫码和 Mac 设置指南；登录后原生展示账户设备。用户可回到设备首页，不依赖扫码、复制 UUID 或审核专用授权后门。

当前客户端复用持久 WKWebView 登录：`https://home.ai2apps.com/signin`。Build 8 修正：在官网同源通过固定 `https://home.ai2apps.com/v1/auth/me` 读取 user.id（不使用通知 OAuth token 授予 Desktop 权限），通过官网同源代理读取 `GET /v1/remote/devices` 和 `GET /v1/spaces/{accountId}/owner-home`。只有 resolve 返回 available 且 deviceOrigin 与设备卡片严格匹配时，开放该卡片的进入按钮，导航到 `/u/{accountId}?entry=owner-home`，由现有网页及 Local 完成交换。通常仅主设备可直接进入；其他设备保留扫码，不伪造可用入口。

现有主设备在选择后发生变更仍可能导致入口重新解析不同目标：客户端不得声称绑定任意目标；首版按钮明确标为“进入主 Desktop”，Cloud 完成下述绑定合同后才能提供所有设备的独立进入。

## 请 Cloud 实现 / 确认
1. 提供通用登录入口，例如 `/mobile/account`：已登录直接进入账户设备页面，未登录完成认证后回到同一固定入口。不要依赖通知模块命名的 account/web；不接受任意 return URL。支持注册、找回密码和真实退出。确认 home 与 coder 的登录会话能在同一 WKWebsiteDataStore 中复用，不要求导出 Cookie。
2. 提供账户绑定的设备目录（建议 `GET /v1/mobile/desktops`，正式字段以最终手册为准）：协议版本、账户 ID/显示名、设备 ID/名称、在线状态、可访问能力、不可用原因、主设备标识、精确稳定授权入口。目录只包含当前账户可见设备，不返回连接 secret、FRP 凭据、handoff 或 token。401 与无设备区分，Cache-Control no-store。
3. 每个稳定入口必须绑定目标设备与 Installation。点击时重新验证浏览器账户、实际 Owner、成员/设备/能力代次、代理可用性与额度。授权入口不是授权凭据。目标变更或离线时返回明确原因，不自动改到另一台 Desktop。
4. 使用现有 owner-mobile-unified-v1 / exchange-v1：独立代次、持久 exchangeRequestId、幂等 exchange、成功提交后才激活/按用户意愿撤销；普通登录默认不撤销其他客户端。不得使用通知 token 或仅凭设备 URL 授权。
5. 返回稳定原因枚举：offline / remote_disabled / quota_exceeded / upgrade_required / revoked / account_forbidden 等。不要把所有错误解释成未登录。
6. 退出仍走现有持久撤销机制，失败可见且不能静默恢复。设备列表和登录提示不得跨账号缓存。公开访客空间与 Owner 私有权限保持独立。

## 验收矩阵
- 全新 iPhone：登录 → 设备 → Apps/Chat/Agent，全程无需扫码或人工点击 Desktop 确认（已有合法 Owner 登录合同内）。
- 未登录401、取消登录、无设备、单台、多台、离线、权限撤销、额度耗尽、客户端升级要求。
- A/B账号切换：清除旧账号投影，B无法进入A设备；用户篡改URL/设备ID均不得赋权。
- 点击到交换期间主设备/Installation/代次变化：拒绝或重新选择，不静默切换。
- Desktop重启及iOS前后台：恢复合法会话，不重发聊天/任务。
- WebKit、Safari与原生同一合同；实际Owner/新设备/多设备验收区别于fixture。

## 边界
本次仅编写对接要求，不修改或部署Cloud。现有主设备入口可先使用；新设备目录协议未部署前不得默认开启。审核账号与真实用户走同一链路，审核Mac须隔离数据并保持在线。


## 2026-10-26 真机发现：官网与 coder 登录域隔离
用户已在 home 登录，但 coder account/web 未登录。Cloud Cookie未声明Domain；共享WKWebsiteDataStore不等于跨域共享Cookie。Build 8 已改为官网同源登录确认/目录读取。
**需要Cloud配合的阻塞点**：用户点击官网/原生“进入我的应用”跳向 coder Owner入口时，需要正式、短时、单次、浏览器绑定且目标设备绑定的登录衔接或统一认证入口。不得复制Cookie、扩大Domain、将密码二次提交或让原生合成会话。请验证现有官网相同链接是否也要求重复登录；若需要，应交付正式SSO协议及跨账号、重放、过期、取消测试。在此之前不能宣称官网登录后完整无感进入Desktop已验收。


## 最终合同接入（Build 9）
Cloud 已部署1.79.0；上述提议以Cloud最终手册 `mobile-account-desktops-client-handoff-2026-10-26.md` 为准。
原生已迁移到home /mobile/account与 /v1/mobile/desktops；不再使用原生登录轮询与coder个人空间入口。
精确绑定设备入口支持非主设备；重复登录问题的正式解决路径现已接入，真实iPhone完整交换待用户验收。
