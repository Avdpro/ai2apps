# Desktop 批准的 Mobile Agent：本地实现与验收

日期：2026-10-21。当前协议 `desktop-mobile-agent-v1`，对接 Cloud OpenAPI 1.74.0。

## 产品边界

此方案替代此前 App-only 提案。浏览器与原生 App 均可申请同一 Owner 的逻辑连接；权限来自 Desktop 本机确认和连接私钥，不来自 UA、通知 OAuth、Cookie 或客户端自报身份。旧 Chat 与 Owner Home 授权保持独立。每个 Device 只接受 Cloud active pointer 对应的一个 Agent 连接。

实现默认关闭。没有以本轮代码自动调用 Cloud enabled=true、创建生产 QR 或批准任何手机连接。

## Desktop / Local

- `remote/mobile_agent.py` 使用 SQLite 事务记录 Device/instance/generation/active/pending fence。每次构造生成新 UUID，启动拒绝缓存租约；之前明确开启的配置也必须先以新 instance 与 Cloud 同步，旧连接失效。
- `api/mobile_agent_desktop.py` 仅本机 loopback、本机真实管理员 Cookie、实际 Session 解析与同源 CSRF 确认令牌可用。令牌绑定 Session 摘要；Owner Cookie、API key、Mobile、Package 和 Agent 路由不能调用。
- Desktop 首页沿用原“链接二维码”弹窗，绑定当前 Local connector 的精确 Device，不提供跨设备下拉选择；账户页不另设扫码入口。扫码前 Agent checkbox 禁用且未勾选；收到 Cloud pending 后二维码上覆盖绿色对勾，启用 checkbox 并显示30秒倒计时。用户点击确认并关闭时，勾选发 Agent 决策、未勾选发 Chat 决策；真实终态成功后才关闭。ACK丢失保持弹窗，只允许明确重试同一ACK。取消pending发deny；关闭/重开不保留勾选。点击需 trusted UI event，clientLabel只用textContent显示。
- 待扫码、等待选择、Chat/deny 不撤旧连接。Agent 决策发送前先阻断本地旧租约；新 generation/pending 持久化后再 ACK。ACK 丢失只查询/重试同一连接；35 秒之后不激活，也不恢复旧授权。
- UI 30 秒确认期限与 ACK 硬期限来自 Cloud。使用受信任 Cloud HTTP Date 和单调时钟，Date 的秒精度按提前1秒处理；不能以手机时钟延长期限。
- 新 JWT 固定 Ed25519/JWKS、audience、scope、protocol、身份/安装/代次/instance、jkt/cnf、60秒时间上限。公钥由实际四字段 JWK 计算指纹。续租不允许改变身份绑定。
- Local nonce 为30秒一次性，绑定 connection+jti；签名绑定大写 method、原始 path/query 与原始 body SHA-256。路径规范化别名、复用、改写正文/方法/Run 不能通过。验证在业务调度前完成，保留原 actor 和既有资源所有权/版本/确认/幂等守卫。
- Mobile revoke 必须先验证当前 Cloud challenge 和本机私钥证明，再立即关闭本地能力。无效退出证明不能把别人的连接踢下线；Cloud 故障也不恢复已关闭能力。
- 本机 Core 退出会关闭本地 Agent、持久标记停用；后续启用先清除 Cloud 旧授权，不能通过只读同步复活。

## Mobile / iOS

- `/mobile/home` 接收并立即清除 `agent_pair` / `agent_connection` fragment。Device origin 创建 P-256 key；Cloud 页面负责 Owner 登录、认领与等待 Desktop 确认，回到精确 Device。
- 浏览器私钥是 IndexedDB 中的 non-extractable CryptoKey；公钥只导出 crv/kty/x/y。原生 iOS 使用独立 Keychain 服务保存签名密钥，不复用通知权限。
- 原生 Bridge 仅受信任 Device HTTPS 顶层页面 `/mobile/home` 或 `/mobile/agent-chat` 可用，检查 securityOrigin 与当前顶层 host；Package/子 iframe 不可调用。只有 key/claim/proof/local/delete 等限定操作，无任意 HTTP 或任意字节签名器。
- 连接ID/密钥引用保存本地，稳定连接地址没有 ticket、签名或临时参数。重连使用原密钥重新证明，不自动扫码、不重建 Run。失去密钥需重新配对。退出或已明确撤销后清除连接材料。
- Agent Chat 使用独立签名 transport；租约只在 Local 服务端保管。浏览器只接收 jti、到期描述与能力信息。续租只刷新授权，不重放写请求。
- 复用 Mobile 准备层：参数表单、预算继续/结束、确认/拒绝、取消、任务进度和消息历史；共享 AaAT table/cards。原始正文/链接/业务数据仍归 App，AS 无新增 App 特例。
- 图像从实际已完成 Run 的视图索引解析，通过该 Owner 的可信 Mobile API 描述符与原所有权检查读取，再经签名请求生成短期 blob；不开放任意 URL 图片代理，不放宽 CSP。业务 App 关闭 Mobile 时仍拒绝图片。

## 路由

新公网命名空间仅 `/v1/mobile/agent`，由 PublicDeviceBoundary 对精确已登记 Device Host 分派到隔离 API；不复用 Local API key，不扩大旧 Owner 白名单。

精确路由清单见 `mobile-agent-edge-routes-v1.json`。`/v1/platform/remote/mobile-agent/*` 的本机决策/ACK/开关绝不能放入 Edge、Owner 或 Package 路由。旧未挂载 `mobile_agent_transport.py` 保留作准备层 fixture，不用 enabled=True 回调冒充新签名 guard。

## 验收证据与限制

- 使用 Cloud 交付的公开无私钥向量验证 jkt、claim/lease/revoke/local 字节和 P1363 签名。
- 协议/守卫测试覆盖默认关闭、换代后旧JWT立即失权、Chat保留旧连接、进程重启、ACK丢失、30/35秒期限、nonce过期/重放、method/path/body篡改、无效revoke不能失权、Cloud故障不恢复权限、Local Core退出、错误key/audience/scope/epoch。
- 完整签名 HTTP → Local guard → 真实 General → SQLite 表单 → runtime重启 → 用户确认 → 执行一次 → 视图/引用/历史恢复，用 fixture Cloud/model/业务执行隔离验证；不等同于生产扫码验收。
- 浏览器实际 WebCrypto/IndexedDB、Cloud回跳fixture、lease与Local请求签名互通通过。另有Desktop倒计时/显式选择/ACK重试、Mobile完整表单/预算/图文/历史fixture。
- iOS Debug generic iPhoneOS 构建与原生连接策略测试通过。2026-10-21 使用现有 84XL5V265N 开发签名构建 Build5，codesign deep/strict通过；已覆盖安装至原 iPhone15Pro（com.ai2apps.ios.dev），devicectl读回bundleVersion=5，保留应用数据。首次远程启动因手机锁屏被系统拒绝，未绕过。扫码权限验收仍待人工操作。
- 固定 Dev 已通过 build-dev-app.sh 重建并自动归档旧包，App/Helper源码根均为当前checkout，codesign deep/strict通过。构建输入使用匹配 patched AceFox 的 `dist/firefox/Acefox.app`；初次未打包输入缺omni、plain pkg缺标记均被构建器拒绝，未绕过。
- 用户解锁后 Dev 已恢复运行，原生窗口标题为 `AI2Apps: MacIntel · AI2Apps 127.0.0.1:55906`。账户 → 设备实际显示手机 Agent 区域，未点击启用/生成二维码。启动日志确认 storage/database.py、research/search_workflow.py 从当前 checkout 导入；`/mobile/static/js/mobile_agent_connection.js` 与源码逐字节一致。
- 更新后实际 Device origin 的 `/mobile/home` 和 `/v1/mobile/agent/bootstrap` 均返回200，后者明确 `enabled=false`。证明这两个入口已到当前Local；其余签名路由、真实手机扫码/批准/旧连接即时失权仍待联调，保持能力关闭。
- 更正：此前对热更新 Dev 误用 `verify-release-app.sh`，把发布包 LICENSE/完整 Runtime 要求误报为 Dev 缺陷。Dev 不走发布包验收，不增加许可证打包要求，不修改发布校验；按固定 Dev 的签名、实例隔离、源码绑定、实际模块和服务资源验收。此前 LICENSE 待修结论撤回。

最终结果：AaAT架构/行为回归191 passed；协议、Gateway、Remote、Local auth组合68 passed；Mobile/图文/进度/恢复与浏览器签名、Desktop明确确认共38 passed；Swift原生连接策略检查通过；最新iPhoneOS Debug无签名构建 BUILD SUCCEEDED。测试没有用修改检查范围换取通过。

没有修改Cloud代码、Cloud账户、生产开关或现有用户连接。Build5已安装真机；生产扫码授权验收仍在进行，不能以安装完成代替权限验收。

## 首页扫码交互调整（2026-10-21）

用户确认入口在 Desktop 首页二维码弹窗，已移除账户页重复组件。打开弹窗只准备
enforcer并创建一次性QR，不授予Agent；Agent必须扫码后明确勾选、确认且完成ACK。
使用原Cloud签名协议、30/35秒守卫，不因UI迁移放宽权限。
Cloud当前chat结果页缺少返回Desktop普通Chat的按钮，需求见
[Cloud Chat回跳补齐](desktop-mobile-chat-return-cloud-requirements-20261021.md)。

首页交互回归：真实Shell模板提取的二维码弹窗3项浏览器行为测试通过；完整Mobile/图文/进度/恢复/签名前端40项通过。Dev已通过原生首页点击和刷新加载新Shell；Mobile服务脚本逐字节匹配当前源码。真实扫码/授权/切换仍待人工操作，不能以fixture测试替代。

## 批准后回到 Mobile Home（2026-10-21）

修复 `/mobile/home` 曾使用独立白色连接完成页并要求再点击进入Chat的问题。
现在该页面复用完整 `mobile.html` Shell；先验证原连接密钥与租约，批准后留在Home，
提供显式Agent对话入口，Chat提供返回Home链接。恢复/刷新不自动打开Chat、创建Run
或重放业务操作。首页和应用历史保持 `/mobile/home`，不误改为旧 `/mobile`。
普通App目录继续原Owner/Local授权；仅有Agent连接时Home仍可用，但不会把
agent:invoke转换为通用App访问。Package隔离和原生签名范围不变。

修改仅HTML/CSS/JS，未重启Dev或重装手机；现存批准连接保留。真实公网Home
已返回完整Shell、Agent入口且无旧中转链接；只读fence显示generation2 active、无pending。
这证明扫码/确认的本地激活已发生，不等于已经完成真实模型调用或新旧连接切换验收。
真实Home模板、WebCrypto/IndexedDB、签名请求、批准后停留Home、主动进入Chat与
返回/刷新不重放写请求的浏览器回归通过。完整前端61项通过。

本次Home修复的AaAT架构/行为回归191项再次通过；前端61项通过。

## Home 的标准 Chat 入口复用批准连接（2026-10-21）

修复单独的Agent入口可用、但Home底部Dock/应用列表Chat仍打开Owner-only iframe
导致Agent不可选的问题。只有agentHome且实际原密钥/租约证明成功时，标准Chat
入口才导航至既有 `/mobile/agent-chat`，由顶层页面继续签名与授权验证。未批准或
普通Owner页面仍保留旧Chat路径；没有用UI布尔标记授予后端权限，也没有扩大签名
Bridge给iframe。无需Local重启或手机重装，保留当前批准连接。

测试不再以简化Chat占位页替代：渲染真实Home与mobile_chat.html，实际点Dock的Chat，
签名GET模型/Agent/历史，验证Agent按钮可见可用并自动进入Agent模式，返回Home后
没有新增业务POST。原21项Mobile导航测试通过；手机重新打开连接的真实确认待用户。

标准Chat入口修复：完整前端回归61项通过；Dev服务的mobile.js与当前源码逐字节相同。

## 手机确认与聊天界面精简（2026-10-21）

用户确认重新打开连接后，新的Chat入口已可使用Agent。该证据是人工手机验收，
尚不能替代新旧连接切换的完整验收。聊天控件不再显示“断开Agent”按钮，
连接退出/签名撤销与服务端单一active generation守卫保持；没有放宽权限。
一个Owner可持有不同客户端/不同Desktop的独立连接，不等于创建多个账号身份；
每个Desktop的Agent有效连接仍最多一个。

2026-10-21：按用户要求移除Mobile Home浅绿色独立Agent卡片及对应样式/显隐代码；统一使用应用列表或底部Chat入口，已批准连接仍进入签名Agent聊天。

## 2026-10-21 图片、终态、历史切换及重复扫码修复

真实数据：旧吉卜力熊猫 `art_ff93744f666c4642ab5b4e3c98827737` 已保存约1.9MB，原Run完成。
它使用旧直接图像Provider，没有Studio记录。正常及兼容图像Provider现均委托Imagine
既有Mini-App/Studio Job，业务所有权留在图像owner，无General Agent特例。
后续真实粘土熊猫 `art_683b14f1d15d4b0ea771cd91b9c21719` 已在Studio历史出现。
旧吉卜力图片的恢复接口仍检查原Chat客户端隔离；Desktop无法读取Mobile专属Chat，
因此不能将fixture里的恢复成功外推为这张旧图已恢复。该项真实恢复仍待处理。

Mobile原先只将image_url显示成附件文字，终态progress未设value导致无限动画。
新增精确签名Run/artifact读取，绑定Run已存输出、原Session权限与栅格MIME；终态隐藏进度。
实际公网GET发现双CSP：Local允许img blob，但Edge另有default-src self，二者同时生效
阻止blob图片。测试此前仅渲染模板，未模拟HTTP CSP，覆盖不足。
修复使用已签名获取的Blob，通过createImageBitmap解码并绘制到有role/aria-label的canvas；
未放宽任何CSP、源域或授权。AaAT图文结果resolver复用同一可释放paint资源。
不发起第二次生成；失败显示实际HTTP错误，不再一律要求重连。

运行中切换会话现在停止旧页面观察器，不取消任务；迟到的内容响应不能覆盖当前会话。
同一路径收到新的agent_pair片段会重新进入claim流程，避免WebKit仅触发hashchange而
不重载页面脚本时扫码无反应；保留旧收藏，不删除已批准连接或自动批准新连接。
此项浏览器验证通过，尚待iPhone同连接真实重扫码验收。

仅Agent授权不能访问普通App API。Home fallback现在提供Chat和“连接其他App”入口，
沿原/mobile→Cloud普通授权流程恢复应用访问，不伪造App列表或把Agent租约扩大为Owner授权。
一次扫码同时衔接普通应用访问需Cloud明确提供独立handoff，见现有Cloud交接文档。

Studio输出：跟随最新结果时自动选中新到达的Run；用户主动查看旧结果时保留选择，
显式刷新选择最新。刷新不会生成/计费。

验证：真实模板+WebCrypto签名浏览器在生产双CSP下显示PNG画布、终态进度隐藏，
运行中切换历史、同页面重扫码均无额外业务POST。相关前端53项、Studio输出2项通过。
签名HTTP→真实General/SQLite的Fixture8项及AaAT边界191项在此前通过；本轮边界191项再次通过（85.31秒，退出时另有headless Metal atexit诊断，不影响测试断言结果）。
所有5个修改JS在Dev端口61389与工作区逐字节相同。仅前端更新无需重启/重装。
iPhone最终显示确认、旧图归档及完整新旧连接切换仍待验收，未声明全部完成。

## 一次扫码普通 App + 可选 Agent（2026-10-21，本地准备完成）

对接文档：[desktop-mobile-one-scan-app-agent-handoff-v1.md](desktop-mobile-one-scan-app-agent-handoff-v1.md)。
新增协议 `desktop-mobile-app-handoff-v1` 仅在Cloud GET device精确声明后请求；没有声明时
保留旧请求体，Desktop提示尚未协商组合交接，不冒充已有普通App权限。
Cloud需提供组合扫码返回、绑定的oh1交换元数据与生产部署回执，本仓库未改Cloud。

Local复用既有member-session/exchange与OwnerHome签名租约，只增加绑定校验：connection、
Device、Installation、actor、协议与agent布尔字段；Agent分支要求同Local的ACK active。
缺少绑定字段不能降级为legacy交换。已有Host/Origin、Secure/HttpOnly/Strict Cookie、
单次消费、epoch、重放/撤销/租约守卫保持。新App Cookie不是Local管理员登录或Agent权限。

Mobile删除临时片段后自动交换、读取普通App完整目录；组合授权显示全部可用入口，
普通App分支不会自动恢复旧Agent界面。Owner活动/租约维护复用现有owner_session.js；
一个权限失败不清除另一份有效授权。错误的本次handoff不能以旧Cookie冒充成功。
同页hashchange完成交接后重新载入目录，普通重载不重复交换、不创建业务任务。
无Native签名域、iOS路径或密钥变更，不需要手机重装。

Agent直接复用Desktop的注册表和身份，不以Mobile UI暴露开关裁剪AaAT能力。
新增实际注册表/任意两个Provider调用测试：没有Mobile页面仍可调用；显式Provider禁用拒绝。
无General Agent业务分支，也没有扩大公开API通配范围。

验收：后端Owner/签名协议/Gateway/App范围49项通过；AaAT统一边界193项通过（87.73秒）；
相关前端53项通过。浏览器使用真实模板、WebCrypto、HttpOnly Cookie、生产双CSP，
Cloud签发/目录数据为fixture；Home普通App与App+Agent分支均显示3个授权App（含任意Package），
重载不重复兑换，仅App分支不续Agent租约，错误连接拒绝。不得外推为生产真机已验收。

本轮不重启正在使用的Dev Local，以免在Cloud尚未提供组合协议时撤销手机连接。
后端改动已通过隔离HTTP测试，需在Cloud部署回执后通过对应Helper重启Dev、核验源码根和
运行模块，再一次扫码完成真实Home目录/应用打开/Agent调用/新旧连接切换验收。

## Cloud 1.75.0 对齐与 Dev 激活（2026-10-21）

已读取Cloud客户端手册及生产回执（desktop-mobile-one-scan-client-handoff-2026-10-21.md /
 desktop-mobile-app-handoff-production-2026-10-21.md），此前Cloud依赖已交付。
补齐两项实质差异：Owner JWT必须含签名app_handoff_protocol/connection_id/agent，
accessToken与leaseToken以及后续refresh均不得改变/剥离绑定；布尔值不能冒充整数0/1。
Cloud新协议prepare尚未提交generation时，Local持久pending fence、拒绝旧租约；读到旧
committed state不能恢复旧授权。查询awaiting_ack可恢复丢失prepare结果并重试同次ACK。

定向Owner/协议/Gateway50项通过；AaAT边界194项通过（89.22秒）。新增签名绑定缺失/
刷新变化、prepare高于Cloud committed generation而ACK失败的行为回归。
Home现在显示全部授权Mobile App，超过快捷区数量也不截断；真实模板浏览器使用8个
任意授权App回归，Cloud签发/目录仍是fixture。前一轮完整相关前端53项通过。

通过dev自己的Helper local.restart激活，未碰App-Dev或其它实例；重启前Agent/System/
Browser无运行项、Studio6项均succeeded。新Local PID61378，端口52924，instance=dev。
App与Helper均声明当前Git checkout源根；实际运行模块日志显示当前ai2apps源码路径，
Mobile3个脚本及admin/static Desktop二维码脚本逐字节匹配当前源码。
Desktop原生实际标题为AI2Apps: MacIntel · AI2Apps 127.0.0.1:52924。
生产GET device/POST pairings已成功协商desktop-mobile-app-handoff-v1；原生二维码界面
实际提示“连接已授权App；可额外允许运行Agent”，扫码前Agent禁用且未选中。

已请求用户手机扫码、Desktop明确勾选批准、Cloud返回Desktop并确认Home/各App/Agent。
此时只证明新协议真实协商和界面待确认，尚未声称组合Cookie、手机完整目录、App打开或
新旧连接切换已经实机通过；不打印ticket、二维码URL、cookie、租约或密钥。

## 真机失败定位：配对映射版本0（2026-10-21）

用户手机返回Home但显示Owner Home authorization required。真实Local日志确认：Desktop
Agent decision/ACK成功，member-handoffs/exchange Cloud返回200，Local随后拒绝
`Owner Home assertion rejected: epoch claims`，没有设置Owner Cookie。
只读核对Cloud源码 spaces/owner-home.ts：pairedDeviceId分支签名mapping_revision=0，
表示绑定扫码的具体Device而不使用primary mapping；旧入口仍用正数personalSpaceRevision。
此前客户端合同对齐和fixture漏掉该零值，故生产合法凭据被拒绝。未读取/输出JWT或Cookie。

修复只对签名app_handoff_protocol精确匹配且后续完整App绑定校验通过的mapping_revision
接受0；其余epoch/revision保持正整数，bool/负数、缺少或错误绑定、旧入口mapping=0仍拒绝。
access/lease/refresh绑定比较保持严格。已把真实mapping=0加入全部组合HTTP/Owner fixture，
并测试其它epoch为0、mapping bool/负数以及旧入口不能接受0。
定向52项通过。通过dev Helper重启激活，无运行中任务；本次handoff已被Cloud单次消费，
不能安全重放，需新扫码和Desktop人类批准后重新验收。尚未声明手机Home成功。

本次激活回读：Dev PID70083、端口50217；App/Helper源根均为当前checkout，运行模块日志
11:29显示当前ai2apps路径，Mobile交接/首页脚本逐字节一致。原生标题实际更新为
AI2Apps: MacIntel · AI2Apps 127.0.0.1:50217；生产组合二维码已就绪。
完整AaAT194项再次通过（93.51秒），退出有既有headless Metal atexit诊断。
已说明上次Cloud已消费handoff故不可重放，请求新扫码和Desktop人类批准；真实Home结果待用户。

## 用户真机确认（2026-10-21）

针对“新扫码、Desktop勾选Agent并确认、手机返回Desktop后Home是否出现App列表、能否
打开一个App”的验收问题，用户回复“ok了”。据此记录本次组合扫码后的Home列表和至少
一个App打开已通过用户实机确认。未收集具体App名称，不外推所有卡片逐个打开通过。
Agent实际调用、无Mobile UI能力执行、刷新/历史不重复及新旧连接切换仍需单独验收；
不因勾选Agent或Home成功而将这些项标为完成。

## Mobile Chat 回归 Shell（2026-10-21）

用户真机截图显示Chat离开Shell：没有顶栏/底栏，模型仍停在Loading。根因包含早期为保留
Native主frame签名而使用/mobile/agent-chat顶层跳转，以及组合Owner Home设置body标记后
Chat对Agent可用性的前端判断过宽。不得靠给iframe开放Native签名来修复。

Home的已批准Agent Chat现在是主document内的Shell stage面板，共用mobile_chat_content.html。
保留同一/mobile/home原点、Native main-frame限制、完整Shell顶栏/Dock与历史栈。
Chat第一次打开才初始化；切走暂停观察而不取消任务，回来读取既有消息/Run；未完成的
旧页面响应不重启业务。Composer/status/drawer限制在stage内，不遮挡Dock。
Agent可用性按可信页面描述及后端签名守卫处理，不用Owner Home body外观标记禁用。
Owner-only/未批准连接仍用原有普通Chat路径；未获得Agent授权不会渲染出可调用权限。
旧/mobile/agent-chat链接由前端返回Shell #app=ai2apps.general-chat，避免旧收藏继续脱壳。
普通App路由片段不再被配对脚本清除；仅凭据片段被立即移除。
模型连接失败显示明确错误，避免持续Loading。没有扩大Native签名路径、iframe权限或AS业务规则。

53项相关前端通过：真实Home模板及签名、公网双CSP、8个App目录、Chat↔Home↔任意App、
旧链接迁移、刷新/历史恢复无业务重放、真实像素/卡片、Dock持续可见与输入区不遮挡。
Dev端口50217实际提供4个修改JS/CSS与工作区字节一致；HTML/Jinja为直接热加载，没有
重启Dev或撤销现有手机连接。已请求用户刷新确认实际底栏、模型列表及情报中心往返。
真实iPhone验收结果待用户，不将浏览器fixture当成实机通过。

Shell Chat最终AaAT门禁194项通过（86.60秒）；公开Device Home真实GET200，HTML包含
inline Chat及data-shell-inline=true。仍无手机用户结果，未声称真机模型加载已通过。

## Owner 入口重新进入时恢复 Agent（2026-10-21）

用户截图再次显示完整Shell但Owner普通Chat没有Agent。此前inline修复只覆盖/mobile/home，
Native刷新/重连仍可能进入/mobile；该模板未加载连接恢复代码，最终打开普通Owner Chat。
现在普通Shell也加载同一连接模块，启动时只读取origin内保存的active连接标识和prefer-agent
作为导航提示，转到既有/mobile/home签名边界，再完成原有私钥持有证明及服务端租约校验。
未增加Native签名路径/iframe签名权限；保存标识本身不授予Agent权限。未保存连接、显式
App-only选择或有待消费handoff时不跳转；保留显式App路由，不重放交接或业务请求。

53项相关前端回归通过，包括真实Owner模板重新进入、可见Agent和Dock、无授权/仅App
连接不升级、历史/图片/进度恢复。Dev50217提供的两项JS与工作区逐字节一致；无需重启、
重新扫码或安装。AaAT架构门禁194项通过（86.17秒），退出仍有既有headless Metal atexit诊断。
真机再次刷新结果待用户确认。

### Owner 入口恢复的真机确认

2026-10-21，用户针对“刷新当前页面，再点底部Chat，确认Agent恢复、底栏保留；无需
重新扫码或重装”的验收问题回复“现在好了”。据此记录此次手机入口恢复与Shell底栏验收
通过；不外推Agent实际业务调用或新旧连接切换验收。

## iOS 前后台恢复（2026-10-21）

用户报告从手机App切走再回来丢失Agent。原生didFinish对/mobile/home和旧Agent Chat
未记录可恢复mobileURL；refreshURL及verify也只认/mobile，导致Agent Shell不参与
正常前台探测/页面回收恢复。现在记忆去除query/fragment的/mobile/home，刷新保留同源
App路由并拒绝携带handoff；普通/mobile策略仍兼容。前台只读探测沿用原Owner/App
接口，不扩大Native签名路径或iframe权限。
网页对visibilitychange和BFCache pageshow重新检查已有连接入口；初始化失败的签名Chat
可在回前台重试初始化。只恢复读取与观察，不重放任务或交接。
iOS Debug Build6已构建成功；Swift连接策略和11项probe测试通过。覆盖安装及完整
前端/AaAT回归结果随后记录；实际真机连续切出切回仍待用户验证。

最终验证：相关前端53项通过，AaAT194项通过（88.65秒，既有headless Metal退出诊断）。
Build6签名校验通过并覆盖安装；devicectl读回com.ai2apps.ios.dev bundleVersion=6，
已成功启动原iPhone15Pro。Dev50217两项前台恢复JS与工作区一致。
之前7项前端失败均为boot单元fixture未提供新visibilitychange监听器，补齐真实DOM事件
模型后原导航/非重放断言全部通过；浏览器另测BFCache返回及Agent保持。
真机实际切出切回验收尚待用户，不将成功安装启动记作交互通过。

## Build6 后仍无Agent与状态停留的确诊（2026-10-21）

用户未能进入Agent，并提供Home显示Apps及“正在检查已有应用授权…”的截图。
只读核对原iPhone15Pro保存的入口为正确/mobile/home。精确定位Agent自己的IndexedDB
（数据库名SHA256对应路径，不访问Cookie或Keychain），仅检查active/pending/prefer-agent
三项元数据：active与Desktop当前generation11的active完全一致，但prefer-agent为false。
此前仅App交接将该偏好设false，恢复代码因此跳过仍有效的旧Agent。不是授权消失，
也不能把Build6构建/安装成功当作根因修复完成。

取消仅App交接对已有Agent候选的屏蔽。仅App不授予新Agent，已有独立授权仍由原私钥、
实时Cloud租约、Local connection/generation决定；新的或已撤销客户端不能因UI线索获权。
同时保留Agent恢复失败时的签名Chat入口与具体错误，不再静默换成Owner Chat；前台
检查即使没有Agent也完成Home状态更新，避免停在检查文案。无Cloud/Native权限扩大。
浏览器已验证真实false偏好迁移、仅App交接保留已有授权、无active客户端零Agent请求、
暂时租约失败可见错误及恢复、无业务重放。Dev50217两项JS回读一致；无需重装或扫码。
完整前端与AaAT结果随后记录；已请求用户刷新，不声称手机恢复成功。

最终相关前端53项通过，AaAT194项通过（86.86秒；既有Metal退出诊断）。首轮AaAT
出现一次测试临时SQLite database locked，未更改/放宽实现和断言，完整重跑通过。
诊断用手机偏好/连接元数据临时副本已清理；不保留Cookie或私钥副本。真机刷新待用户。

用户真机确认：针对“右上角刷新，再点底部Chat确认Agent出现；无需扫码或重装”的问题，
用户回复“这次好了”。记录刷新后的Agent恢复通过。未将此答复外推为连续两次后台切换
或旧/新连接切换均通过。

## 移除 Agent 类型选择器（2026-10-21）

按用户要求，Desktop/Mobile均移除General/Research Agent下拉框。Mobile内部选择已启用、
可发现的General Agent；不可用时明确提示，不隐式选中列表里的专用Agent。Desktop保留
已有默认/历史及显式调用处理。执行记录中的真实Agent名称保持可见。
Desktop原生Agent模式已检查，无类型下拉且任务预算仍在；Mobile真实模板浏览器回归
验证不存在选择器，多Agent目录下任务默认发送General Agent。前端53项、AaAT194项
通过（94.74秒，既有Metal退出诊断）。Dev50217脚本回读一致；纯网页热更新无需安装。

## Mobile call owner icons (2026-10-21)

Render deduplicated App/Mini-App badges from recorded Tool output and active status identities. Existing independently authorized App and Mini-App catalogs provide labels, declared ownership and bundled Lucide icon keys. Never infer execution from requested inputs or Tool names. Missing metadata keeps recorded IDs and generic icons; no new permission, AS business branch or server restart. Earlier owners survive later infrastructure calls; async metadata preserves pending forms.

Related frontend55 passed. Actual rendered Mobile browser confirms SVGs during parameter input, completion and history reload without another task POST. Arbitrary provider identities, deduplication and unknown metadata fallback are covered. Dev50217 JS/CSS byte-matches the checkout. AaAT194 passed87.55s, with the existing headless Metal exit diagnostic. Real phone refresh confirmation is not yet claimed.
