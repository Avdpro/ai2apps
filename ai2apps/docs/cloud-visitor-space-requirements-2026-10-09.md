# Cloud 访客空间 MVP 对接需求

本仓库不修改 Cloud。沿用固定 /u/{owner}。2026-10-09 产品修订：访客空间必须支持未登录 AI2Apps 的匿名访问；Cloud 登录仅用于 Owner 私有入口。现有 personal-space-v1 交接仍绑定登录账户，不能视为已支持匿名访问。

## 新通道
- GET /mobile/space/app/{revision}/{app_key}/{resource:path}：Local 每次校验 space Cookie、设备绑定、空间开启、发布版本与 App 清单，且校验资源摘要。Cloud 不按 App ID 手工审批。保留 Local sandbox CSP，禁止注入 allow-same-origin。
- GET /mobile/space/assets/space.js 与 space.css、GET /v1/mobile/space/bootstrap 沿用；无新增公开管理 API。
- 未知路径/方法拒绝；禁止将请求重写到 Owner App、管理 API 或 Package bridge。

## 长会话
现有断言最多 120 秒，Local 不延长。建议独立 visitor 会话/短租约协议（用户、Owner、设备、access_epoch、空间发布/撤销代次绑定），明确刷新、撤销、绝对/闲置上限和错误码；需 Cloud 发布正式合同后客户端接入。Owner 的 8 小时租约不能用于 visitor。

## 验收与就绪
非 Owner/Owner 访客模式均只能看已发布内容；关闭空间立即阻止新交接，Local 拒绝已有 Cookie；跨用户/设备、过期、撤销、旧发布版本均拒绝。iframe 资源在 sandbox opaque origin 下验证 Cookie 实际行为（Chrome/Safari）。部署回执前本地 AI2APPS_VISITOR_APP_GATEWAY_READY 不开启。Cloud 返回原有用户 URL 用于过期后重新进入，不自动升级 Owner 权限。

## 部署顺序与客户端验收接口
1. 先部署精确资源路由与保留 CSP；不要等待长会话 v2 才允许静态主页 MVP。
2. 回执注明已支持的 protocol、精确 method/path、CSP、无 Cookie/错误 Cookie/过期/撤销/跨设备矩阵。
3. 客户端在指定实例设置 AI2APPS_VISITOR_APP_GATEWAY_READY=1 并重启；当前环境保持关闭。之后在本机发布具有 Open-Entry 声明的 App 卡片，完成账号 B 访客实机验收。
4. 访客长会话另行冻结接口合同并发布；现行 v1 仍严格 120 秒，不将测试通过的短会话描述为长期可用。

关闭空间由 Local epoch 与会话撤销立即执行，现有 Cloud 入口可能仍允许登录，但 Local 会拒绝 handoff exchange。若要让 Cloud 入口同步显示“空间已关闭”，请给现有 capability 声明增加独立 visitorEnabled 字段（不能复用影响 Owner Home 的 enabled 字段），并给出兼容性回执，再由客户端接入。

## 必须补充：匿名访客访问（2026-10-09）

### 入口体验
- 未登录浏览器打开 /u/{owner}，空间开启且已有发布内容时，直接进入公开空间，不先显示登录表单。
- 已登录的非 Owner 同样进入公开空间；Owner 可选择“进入我的应用”或“访问访客空间”。entry=owner-home 继续走现有 Owner 登录/授权，不降级为匿名私有入口。
- 空间关闭、未发布、设备离线分别显示准确状态；保留固定用户 URL 重试，禁止回退到 coder.ai2apps.com 根路径。
- 默认匿名可访问是“开启访客空间”的含义，不要求主人额外配置第二个匿名开关。管理页开启前说明“任何持有链接的人都可访问已发布内容”。

### Cloud / Local 协议边界
- 匿名访客不创建 AI2Apps 用户、不使用 Owner/member Cookie、不转换为 Local principal。
- Cloud 发行一次性交接码，使用独立、明确版本的匿名访客断言；不得用伪造用户 ID 或 account_session_epoch 冒充登录用户以兼容旧协议。
- 正式合同需明确 issuer/audience/scope、匿名访问模式、唯一 jti、owner/device/installation 绑定、access_epoch、mapping/capability revision、空间撤销代次以及签发/过期时间。Local 在合同冻结后实现严格校验；旧断言校验保持不变。
- 公开内容 bootstrap 与 sandbox 资源继续逐次验证空间开启、发布快照及撤销状态。匿名身份不能进入 Owner Mobile、管理 API、私有 App、模型调用、文件或 Package Bridge。
- 交接码短时、单次、限制重复兑换；匿名会话使用 Secure/HttpOnly Cookie。Cloud 实施匿名请求限流与会话配额，返回可展示的错误码，避免无登录访问耗尽设备资源。
- 匿名会话期限/续租由新合同明确，不延用账户 session epoch，不私自扩大现有 120 秒断言寿命。关闭立即拒绝新访问并撤销已有访问，重开旧凭证不可复活。

### 交付与验收
Cloud 项目先实现并给出匿名协议/路由/CSP/错误码回执，客户端随后接入。请同步 visitorEnabled 和发布状态，不能复用 Owner Home 开关。
验收：全新无 Cookie 浏览器、退出 AI2Apps 后、iPhone Safari 无痕均能查看公开内容；关闭/未发布/离线状态正确；匿名跨设备、篡改断言、重放、过期、撤销及管理 API 访问均拒绝；Owner 私有流程无回归。真实匿名访问通过前不得宣称上线。

## 生产合同接入进展
2026-10-09 已读取 Cloud/Edge 生产回执，匿名合同本地实现和测试见 anonymous-visitor-local-integration-2026-10-09.md。发现纯文字空间被 publishedAppCount=0 阻断，补充需求见 cloud-anonymous-text-space-fix-2026-10-09.md。匿名公网访问仍待实测。

## 持续浏览需求（用户已批准）
120 秒固定会话需要替换为独立匿名会话加短租约。完整合同需求与 Local 落地/验收清单：cloud-anonymous-visitor-session-lease-requirements-2026-10-09.md。当前 v1 仍按 120 秒执行，等待 Cloud 正式接口后接入，不能仅修改本地超时。
