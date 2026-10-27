# Mobile App 专属 Agent Chat：Cloud / iOS / Local 交接契约

日期：2026-10-21
状态：已被 Desktop 批准的连接方案替代；保留为历史提案。当前实现见 [Desktop/Mobile v1](desktop-approved-mobile-agent-20261021.md)。Cloud 1.74.0 允许浏览器与原生 App 申请，不再要求 App-only。

## 目标与当前缺口

仅经过验证的原生 Mobile App 会话可使用 Agent Chat。普通浏览器 Owner 入口继续只支持 Chat。App 内仍按用户、Installation、App、Tool、确认策略执行，不授予全局 Local 管理权限。

当前 `remote/owner_home.py` 验证 Cloud 的 `owner-home:apps` 短租约，签名字段包含用户、Desktop 设备、Installation、Session 及撤销代次；没有原生客户端身份或 Agent 授权。`web/templates/mobile_chat.html` 在 Owner 入口隐藏 Agent；`web/owner_home_gateway.py` 拒绝 Agent API。这是现有授权边界，不可只改按钮或白名单。

iOS 在 `ai2apps-ios/AI2Apps/WebSession.swift` 用 WKWebView 加载相同入口。已有 `NotificationInstallationProof` 和通知 OAuth 仅证明通知客户端安装绑定，作用域是 notifications；不能直接用于 Agent。不得把通知令牌转成 Agent 权限。

User-Agent、自报 bundle ID、URL 参数、HTTP Header、JS Bridge 是否存在均不是可信客户端证明。Desktop `device_id` 也不是手机客户端安装身份。

## Cloud 项目所需变更

以下为待确认的协议设计，不是当前已存在 API 或字段。Cloud 项目应回传最终 OpenAPI、签名样例和错误语义，Local/iOS 再对接。

1. 新增版本化原生 Agent 授权能力协商。旧版本、字段缺失、未知协议一律仅 Chat。
2. 复用现有 Cloud 登录账户，新增明确的 Agent Chat 授权 scope；不要扩大 `notifications` 或旧 `owner-home:apps` 的含义。用户授权绑定当前 Owner、目标 Desktop Installation 和手机客户端安装。
3. 原生客户端通过受支持的应用身份验证流程注册安装公钥。iOS 正式环境优先 App Attest 等服务端可验证的应用证明；开发环境走独立登记/允许列表，不将开发身份放入生产。bundle ID、team ID、公钥自报不能单独作为 App 身份证据。
4. 原生授权采用一次性 challenge、PKCE/state、安装私钥持有证明。明确 audience、有效期、nonce 重放缓存和密钥轮换/撤销规则。
5. 由 Cloud 签名授权同时绑定 actor/owner、Desktop device/installation、mobile client installation、client key thumbprint、session、授权 scopes、协议版本、授权代次及到期时间。
6. 浏览器 Owner 登录不能申请原生 Agent grant；浏览器自报 client_kind、复制 App URL、换 User-Agent 均无效。没有证明的普通 OAuth 公共客户端不应获此权限。
7. 一次性交接到 Local 后不将 grant 变成可复制到浏览器即用的普通 Cookie 权限。Local 需要验证原生持有证明：例如独立原生传输签名请求，或经原生签名 challenge 建立与该密钥绑定的受限通道。最终选择须在 Cloud/iOS/Local 联调前固定。
8. 续租保持客户端、密钥、目标 Desktop、scope 与会话绑定不变；若变更则结束旧授权并重新授权。退出/撤销/设备停用/账户切换/手机安装密钥轮换使旧通道失效。
9. Cloud 不可用时不能增加或延长权限。既有短租约仅在原有有效窗口使用。
10. 返回可展示的能力与不可用原因；错误至少区分未支持、未授权、客户端证明失效、租约过期、目标设备离线。不得通过调试字段返回密钥、Cookie 或签名原文。

## iOS 交接

- 在 Keychain 管理专用或明确分域的安装密钥；通知权限与 Agent 权限分开授权、分开 audience 和签名上下文。
- 原生只为精确允许的 Cloud/Local origin、已验证的顶层会话签名。Package iframe、普通外部网页和任意 JS 输入不能调用通用签名器。
- 手机安全地向 Local 提供绑定请求的方法、目标路径、body digest、nonce、有效期与会话身份；精确编码规范须由最终协议定义。签名不能移用于另一接口、另一设备或改写参数。
- 私钥、Cloud refresh token 和 Desktop API key 不进入 JS。原生桥接只提供具体授权的调用功能，不提供任意 HTTP 代理。
- 同步网页模式状态；能力过期立即禁用 Agent 控件并提示恢复，不自动重放任务或表单提交。

## Local 与 Mobile Chat 后续实现

在最终 Cloud 协议获确认前，保持现有 Agent 入口失败关闭，不接受猜测的签名字段。

- 校验签名及持有证明后，产生服务端会话能力描述；模板和 API 使用同一描述。普通网页看到不可切换的 Chat 标签和清楚说明，App grant 有效才显示 Chat / Agent。
- 通过受限、主体绑定的网关连接既有 Agent API，不把 Owner 访问转成 Local API key。覆盖 Agent 发现、创建 Run、状态读取、取消、持久交互读取/确认/取消、预算继续确认、按需结果读取。
- 所有读写验证 Run/Session 所有权与安装绑定，效应请求携带幂等键和既有版本/确认守卫。取消、未知结果和断线不自动换 Tool 重试。
- 复用现有 AaAT 声明/Context、任务进度、结果图文契约。Shopping、Intelligence 等业务不进入共享 AS 或客户端权限判断。
- 模型选择复用桌面的能力声明策略；Agent 无显式选择时需要至少中等复杂度、可靠工具调用。用户显式选择不得静默换型号。
- 复用共享 `aaat_result_views.js/css`；通过受限授权的图片读取能力展示缩略图/新闻封面，保留原始来源链接，不开放任意代理。
- 历史及重连只读取持久 Run/消息/交互，不创建任务，不重放效应。处理中重新打开页面仍能看见确认表单、进度和真实最终状态。

## 必须通过的验收

1. 同一 Owner：App grant + 有效持有证明可发现 Agent、执行只读任务；普通 Safari/Chrome 只有 Chat，直接调用 Agent API 拒绝。
2. 伪造 UA/Header/URL/Bridge、复制 App Cookie、复用 nonce、修改 body/path/method、错误公钥、跨设备/安装/用户/Run 均拒绝。证明失败前无业务提交。
3. Cloud 续租不得悄悄新增 scopes 或更换 client key；过期、撤销、退出、账户切换及设备停用阻止新调用和未确认交互。
4. Todo 只读查询与匿名/任意 Provider 契约用例验证通用调用；Shopping 生成推荐需确认，新闻采集保留实际 partial。AS 无 App 特例。
5. 补齐参数、确认、拒绝、取消、预算继续、断线重连、App 后台恢复、Local 重启均遵守既有 durable guards；不重复提交。
6. 手机真机验证购物缩略图表格、新闻标题图卡片、逐步进度与历史恢复。390px 浏览器 fixture 不代替真机/完整网关验收。
7. 必跑 AaAT 架构门禁、Owner gateway/lease/隔离测试、Mobile 交互/幂等/历史测试；保留普通网页拒绝回归，不删旧安全断言以通过检查。

## 仓库边界与交付顺序

本仓库 AGENTS.md 的 “AI2Apps Cloud change boundary” 要求：涉及 Cloud API/行为，先写需求交由 Cloud 项目实现、部署和升级，不从本仓库修改 Cloud 代码。

建议顺序：Cloud 确认协议与身份验证方案 → Cloud + iOS 安装证明及 scope → Local 受限网关与 Mobile 交互 → 隔离端到端 → Dev + 真机验收。没有前置协议不能承诺 App-only Agent 已可用；本轮未扩大权限或部署。
