# AI2Apps WebDriver BiDi 与 AceFox 实例隔离安全整改需求

状态：待 WebAgent / AceFox / Desktop Shell 团队跟进  
日期：2026-09-02  
范围：AI2Apps Desktop、AceFox、Helper、WebDriver BiDi Gateway、WebAgent  
不涉及：AI2Apps Cloud API 或 Cloud 侧代码变更

## 1. 目的

本文记录对当前 AI2Apps WebDriver BiDi 链路的安全审查结果，并定义整改要求。

必须建立以下安全边界：

> WebAgent 的 WebDriver BiDi 上游只能是由 AI2Apps Helper 启动并认证的 AceFox 网页浏览器实例，不能是承载 AI2Apps Shell、App Entry、Mini-Entry、Account 登录页或其他 Local WebUI 的 App 浏览器实例。

仅验证端口位于 loopback、持有 bearer token 或进程名为 AceFox，不足以满足该边界。实例身份、Profile、App/mount、browsing context 和 capability 必须由可信 Host 绑定并在 Gateway 服务端强制执行。

本整改不得引入第二套语义浏览器 REST、WebSocket、Python 或 JavaScript API。WebDriver BiDi 仍是唯一浏览器控制协议；Gateway 继续使用原生 BiDi 方法和消息结构，只承担认证、授权、实例/Profile/context 绑定、生命周期和审计。

## 2. 当前实现拓扑

当前 Shell BiDi 链路为：

```text
System App / Mini-Entry JavaScript
        |
        | Local Session -> one-use ticket
        v
/v1/platform/browser/webdriver-bidi
        |
        | read AI2APPS_SHELL_AUTOMATION_PATH
        v
shell-automation.json
        |
        | loopback WebSocket + bearer
        v
AceFox app-shell BiDi listener
```

当前独立 Browser Agent 是另一条链路：

```text
Helper browser control
        |
        v
BrowserAgentLaunchPlan
        |
        | profile: browserProfiles/agents/<profile-id>
        | role: agent
        v
independent AceFox process + independent BiDi endpoint
```

两条链路目前没有形成“WebAgent 只能使用独立 AceFox 网页浏览器实例”的统一强制边界。

## 3. 已发现的问题

### 3.1 Gateway 当前连接的是 `app-shell` 实例

AI2Apps Launcher 创建 `browserProfiles/app-shell` Profile，并使用以下环境启动 AceFox：

- `AI2APPS_APP_SHELL=1`；
- `AI2APPS_BROWSER_ROLE=shell`；
- `--remote-debugging-port`；
- `AI2APPS_REMOTE_AGENT_TOKEN`。

随后 Launcher 将该进程的 PID、端口和 token 写入 `shell-automation.json`。Local runtime 通过 `AI2APPS_SHELL_AUTOMATION_PATH` 读取这个 descriptor。

因此，按当前代码语义，`ShellBiDiGateway` 的上游就是 AI2Apps `app-shell` AceFox 实例，而不是专门承载普通网页的独立 AceFox Browser/Agent 实例。

证据：

- `apps/ai2apps-acefox/Sources/AI2AppsLauncher/main.swift`：`launchAceFox` 创建 `app-shell` Profile、设置 `role=shell` 并发布 `shell-automation.json`；
- `apps/ai2apps-acefox/Sources/AI2AppsSupervisorCore/LaunchPlan.swift`：向 Local runtime 注入 `AI2APPS_SHELL_AUTOMATION_PATH`；
- `ai2apps/browser/shell_bidi_gateway.py`：只从该环境变量加载上游 endpoint。

### 3.2 只有 endpoint 形状校验，没有可信实例身份校验

`ShellBiDiEndpoint.load` 当前主要校验：

- descriptor schema version；
- host 必须是 `127.0.0.1`；
- 端口范围；
- 256-bit token 格式；
- PID 为正且进程仍存活。

当前没有校验或绑定：

- descriptor 的 `instance_id` 是否等于当前 Installation/boot；
- PID 对应的实际 executable、bundle ID、Team ID、代码签名或 designated requirement；
- 进程是否由当前 Helper 本次启动；
- `AI2APPS_BROWSER_ROLE` 是否为允许 WebAgent 使用的网页浏览器角色；
- Profile ID、Profile 根目录和 Profile 所有者；
- descriptor 发布时间、boot ID、启动 nonce 或撤销 epoch；
- endpoint 是否属于预期 AceFox browser instance，而非 Shell 或其他本机进程。

仅 `os.kill(pid, 0)` 只能证明 PID 存在，不能证明它是被授权的 AceFox 网页浏览器实例。

### 3.3 Gateway 没有在服务端限制 browsing context

当前 Gateway 只虚拟化 `session.status`、`session.new` 和 `session.end`。其他客户端消息原样转发至上游。

因此，获得连接的客户端可以自行调用：

- `browsingContext.getTree` 枚举 Session 内全部 context；
- `script.evaluate` / `script.callFunction` 指定任意可见 context；
- `browsingContext.navigate`、截图、输入等方法指定其他 context；
- `storage.*` 或 browser/network 级的非 context 命令。

Chat、Knowledge 和 Agent 当前会在前端 SDK 中根据 Sidebar 提供的 `bidi_context` 选择页面。这是正常客户端行为，但不是安全边界。调用者可以绕过 SDK，直接发送原生 BiDi 命令。

### 3.4 ticket 未绑定 App、mount、Profile 和 context

当前 ticket 的主要条件为：

- 请求具有 Local Session principal；
- principal 具有 `APP_CHAT_USE`；
- ticket 随机、一次性、30 秒有效；
- WebSocket Origin 与 Local origin 完全一致。

ticket 没有绑定：

- `app_id` / `app_instance_id`；
- Entry/Mini-Entry `mount_id`；
- AceFox `browser_instance_id` / `profile_id`；
- window ID / top-level browsing-context ID；
- requested/granted browser capability；
- grant epoch、mount epoch 或撤销状态。

路由注释中的“authenticated first-party Mini-Entry”目前不是由服务端 mount attestation 强制证明的。

### 3.5 完整 BiDi 权限与普通 Chat 使用权限混用

当前 `APP_CHAT_USE` 即可申请透明 BiDi ticket。该权限粒度不足以表达以下差异：

- 读取当前网页；
- 截图当前网页；
- 在当前网页交互；
- 新建/关闭网页 Tab；
- 访问整个 Profile；
- 读取 Cookie/storage 或认证相关网络数据；
- 获得完整 `browser.webdriver-bidi`。

完整 BiDi 是高权限能力，不应由普通 Chat 可用权限隐式推出。

### 3.6 当前自动化测试没有证明实例和 context 隔离

现有测试覆盖了 loopback、token、descriptor 基本格式、同源 WebSocket、ticket 一次性和共享 Session 生命周期，但没有证明：

- Shell/App 实例不能作为 WebAgent 上游；
- AI2Apps Local WebUI context 不会出现在授权树中；
- 对未授权 context 的命令会被 Gateway 拒绝；
- `storage.getCookies` 等全局命令在低权限 grant 下会失败；
- descriptor 替换、PID 复用、错误 role/Profile 或跨 Installation 会失败。

## 4. 风险评估

### 4.1 主要资产

- AI2Apps Local Session 和 Cloud-browser 映射会话；
- Account 登录页中的密码、OTP 和管理员验证流程；
- System App、Entry、Mini-Entry 和 Chat 内容；
- AceFox Profile 中已登录网站的 Cookie、storage 和页面数据；
- 本地管理 API 的 ambient authority；
- 用户当前打开但未授权给 WebAgent 的其他页面。

### 4.2 攻击场景

1. 一个被注入恶意 JavaScript 的同源 System App 申请 BiDi ticket，枚举全部 context，并读取 AI2Apps Account 或其他 System App 页面。
2. WebAgent 绕过共享客户端 SDK，直接向 Gateway 发送指定其他 context 的原生 BiDi 命令。
3. 错误或被替换的 descriptor 把 Gateway 指向另一个 loopback listener；当前 loader 未验证进程代码身份和 browser role。
4. 低权限 Chat grant 被用于执行完整 Profile 级 BiDi 命令，包括 Cookie/storage 操作。
5. 一个 mount 已关闭或切换页面后，旧连接继续持有之前的 Profile/context 权限。

### 4.3 严重性

在“可信 System App 永不被攻破”的假设下，风险可能被掩盖；但该假设不能覆盖 XSS、供应链、错误 Patch、插件或未来第三方扩展。由于暴露面可能包含登录凭据和整个本地账户权限，本问题应按高优先级安全边界缺失处理。

## 5. 必须满足的安全不变量

以下要求使用规范术语：MUST/必须、MUST NOT/禁止、SHOULD/应当。

### 5.1 实例隔离

1. WebAgent BiDi Gateway 的上游必须是 Helper 启动并登记的独立 AceFox 网页浏览器实例。
2. AI2Apps `app-shell`、Local WebUI、Account、Entry 和 Mini-Entry 所在实例禁止开启供 WebAgent 使用的 BiDi listener。
3. WebAgent 禁止直接提供或选择 `ws://host:port`、PID、Profile 路径或 bearer token。
4. Gateway 禁止回退到 `shell-automation.json` 或任何未携带可信 browser role 的 legacy descriptor。
5. Helper 必须是 browser instance lease、endpoint 和 bearer 的唯一签发者；WebAgent 永远不能获得上游 raw endpoint 或 bearer。
6. 同一个 App bundle 可用于启动不同角色，但角色必须通过 Helper 的启动记录和不可伪造的 instance identity 区分，不能仅信任子进程环境变量自报。

### 5.2 Profile 隔离

1. AceFox 网页浏览器必须使用独立的、Installation + actor + browser-instance scoped Profile。
2. `app-shell` Profile 与 WebAgent browser Profile 禁止共用 Cookie jar、storage、service worker、下载状态或 session restore 数据。
3. Profile 根目录必须由 Helper 选择和创建；WebAgent/App 不得提交任意路径。
4. 一个 browser instance 的 Gateway session 禁止跨 Profile 操作。

### 5.3 context 隔离

1. 每个 Gateway grant 必须绑定一个或一组明确的 top-level browsing context。
2. 被授权 context 必须由 AceFox/Helper 发布的可信 active-tab/window binding 产生，禁止信任 App JavaScript 自报的 context ID。
3. Gateway 必须验证所有命令中显式或嵌套的 context、realm、navigation、intercept 和 subscription scope。
4. 未授权 context、其 realm 和其事件必须不可见且不可操作。
5. `browsingContext.getTree` 只能返回 grant 内的 context 及其允许的子 frame，同时保持原生 BiDi payload shape。
6. AI2Apps Local origin、privileged UI、extension/chrome context、Account/Shell/App context 必须 fail closed。URL denylist 只能作为防御纵深，不能替代可信 context classification。
7. 当 selected tab、window、Profile、mount 或 top-level context 变化时，旧 binding 必须撤销；需要访问新页面时签发新 grant 或执行受控 rebind。

### 5.4 capability 隔离

最少区分：

- `browser.read`：限定 context 的 URL/title、DOM 读取、selection 和截图；
- `browser.interact`：限定 context 的导航、输入、滚动和对话框；
- `browser.automation`：经授权的 Tab/window/download/network 自动化；
- `browser.webdriver-bidi`：指定 Profile 范围内的完整原生协议；
- 建议新增独立的 credentials/storage 高风险 grant，或者明确把它只包含在完整 Profile 级权限中。

要求：

1. `APP_CHAT_USE` 不能自动等价于 `browser.webdriver-bidi`。
2. context-bound `browser.read/interact` 必须拒绝无安全 context 作用域的 `storage.*`、敏感 network header、跨 Tab 和 browser-global 命令。
3. 完整 Profile 级权限必须在 UI 中明确说明它可访问已登录页面及 Cookie/storage，并经过显式用户或管理员授权。
4. Gateway 的协议授权层可以拒绝命令、约束目标和过滤不可见 context，但不得重新命名 BiDi 方法或发明语义替代 API。

### 5.5 ticket 和 session 绑定

ticket/grant 至少包含并由服务端验证：

```text
installation_id
boot_id
actor_user_id
app_id
app_instance_id
mount_id
mount_epoch
browser_instance_id
browser_role
profile_id
window_id
top_level_context_id
granted_capabilities
grant_epoch
issued_at / expires_at
nonce
```

要求：

1. ticket 必须一次性且短期有效；当前 30 秒可保留。
2. WebSocket 建立后，授权状态必须成为 server-side session state，不能继续依赖客户端参数。
3. App suspend/close、mount unmount、logout、grant revoke、AceFox restart、Profile change 和 Helper lease expiry 必须立即撤销连接。
4. Gateway 必须验证 exact source origin、mount identity 和 actor，不得只验证同源 Local Session。

### 5.6 descriptor 与进程身份

建议用新的 Helper-owned browser instance descriptor/lease 取代 Shell descriptor。至少包含：

```json
{
  "schema_version": 2,
  "installation_id": "...",
  "boot_id": "...",
  "browser_instance_id": "...",
  "browser_role": "acefox-web",
  "profile_id": "...",
  "pid": 123,
  "executable_path": "...",
  "bundle_id": "...",
  "code_identity": "...",
  "host": "127.0.0.1",
  "port": 49152,
  "endpoint_epoch": 1,
  "published_at": "...",
  "expires_at": "..."
}
```

具体 bearer 不应进入 App 可读 descriptor。可由 Helper 与 Gateway 通过受保护控制通道交换，或保存在仅 Host 可读的短期文件中。

加载时必须验证：

- Installation、boot、browser instance、role 和 Profile 全部匹配请求；
- PID 属于 Helper 记录的 launch transaction；
- executable、bundle ID、Team ID/代码签名符合当前发布配置；
- endpoint epoch 未撤销且未过期；
- listener 完成 bearer challenge，且返回预期的 vendor capability/instance nonce；
- PID 复用、旧 descriptor 和跨 Installation descriptor 全部失败。

## 6. 推荐目标拓扑

```text
AI2Apps App / Mini-Entry
        |
        | mount-bound capability request
        v
Trusted Host / Helper
        |
        | create or resolve AceFox browser lease
        | bind profile + window + browsing context
        v
BiDi Gateway
        |
        | native BiDi, authenticated and scope-enforced
        | raw upstream endpoint/token never disclosed
        v
Dedicated AceFox web browser instance
        |
        `-- web-content contexts only

AI2Apps app-shell instance
        `-- no WebAgent BiDi listener / never an upstream candidate
```

如果产品形态要求浏览页面和 Sidebar 仍位于同一个 AceFox 前台 App 中，则必须至少将 AI2Apps Local App surface 与网页内容放入不同、可由 AceFox 可信标记的 browser instance/Profile 边界，并在 Gateway 强制 context allowlist。仅靠前端 SDK 选择 context 不可接受。

## 7. 分阶段实施建议

### 阶段 0：立即 fail closed

1. 给现有 Gateway 增加 server-side descriptor role 检查。
2. 新逻辑拒绝 `role=shell`、缺少 role、缺少 Installation/boot binding 的 endpoint。
3. 禁止 Gateway 在新版本回退到 legacy Shell descriptor。
4. 在独立 AceFox browser endpoint 未准备好时返回明确的 `browser_instance_unavailable`，不要降级连接 App Shell。
5. 将完整 BiDi ticket 从 `APP_CHAT_USE` 中拆出。

该阶段可能暂时关闭部分 WebAgent 功能，但不能为了保持功能而继续越过实例边界。

### 阶段 1：独立 AceFox browser lease

1. Helper 提供 create/focus/renew/release browser instance lease。
2. 复用现有 `BrowserAgentLaunchPlan` 的独立 Profile 与进程基础，但冻结新的 `acefox-web` role 和 descriptor v2。
3. Local runtime/Gateway 只通过 Helper 控制通道解析 lease，不读取 Shell descriptor。
4. App Shell 启动路径删除供 WebAgent 使用的 remote debugging 参数和 token 发布。

### 阶段 2：mount/context-bound Gateway

1. ticket API 接收 Host 解析的 mount identity，不信任任意客户端 `appId`/`mountId`。
2. AceFox/Helper 发布 active window + top-level context binding。
3. Gateway 保存 grant scope，验证命令目标、过滤 context tree/events，并处理 rebind/revoke。
4. 共享客户端 SDK 继续提供 Readability、稳定等待、截图和输入 helper，但不再承担安全判断。

### 阶段 3：能力拆分与敏感操作保护

1. 实现 `browser.read/interact/automation/webdriver-bidi` 的服务端授权映射。
2. 默认拒绝 Cookie/storage、认证 header、密码/OTP/支付字段读取。
3. 完整 Profile 权限加入明确的 Setup/Trust Center 展示、审计和撤销入口。

### 阶段 4：删除旧路径

1. 删除 `AI2APPS_SHELL_AUTOMATION_PATH` 对 WebAgent Gateway 的用途。
2. 删除 Shell App 为 WebAgent 发布 `shell-automation.json` 的逻辑。
3. 删除依赖前端 `getTree` 自行保证安全边界的兼容代码；前端仍可用于重连 UX，但服务端必须独立验证。

## 8. 协议级实现注意事项

为了保持协议透明性，Gateway 应解析原生 BiDi envelope 做授权，但不创建新方法目录。

至少审查以下命令类别：

- `browsingContext.*`：context、parent/child、navigation、截图、prompt；
- `script.*`：target context、realm、sandbox；
- `input.*`：context；
- `network.*`：contexts、intercepts、认证和 headers；
- `storage.*`：partition/global scope、Cookie/storage；
- `browser.*`：user context、client window；
- `session.subscribe`：事件和 contexts；
- 所有返回 context、realm、navigation、userContext 或 clientWindow 标识的事件和结果。

处理原则：

1. 未识别的新 BiDi 方法在非完整协议 grant 下默认拒绝。
2. 对已授权原生方法保持 method 名称、参数和响应 shape。
3. 对越权请求返回标准 BiDi error envelope，不返回 AI2Apps 私有语义响应。
4. 事件必须按同一 grant scope 过滤，避免通过事件旁路泄露 URL、realm 或网络数据。
5. 不记录页面正文、Cookie、header、截图或输入值；仅审计 actor、App、mount、Profile、context、method、结果类别和拒绝原因。

## 9. 验收测试

### 9.1 实例隔离

- [ ] Gateway 接受 Helper 启动且 role 为 `acefox-web` 的当前 browser instance。
- [ ] Gateway 拒绝 `app-shell`、`agent`（若未授权）、未知 role 和缺失 role。
- [ ] Gateway 拒绝跨 Installation、旧 boot、过期 epoch 和已撤销 lease。
- [ ] 修改 descriptor 指向另一个存活 PID 后仍被拒绝。
- [ ] PID 复用后旧 descriptor 不可恢复权限。
- [ ] WebAgent 无法提交自定义 endpoint、token、PID 或 Profile 路径。

### 9.2 Profile/context 隔离

- [ ] `getTree` 只返回授权网页 context 和允许的子 frame。
- [ ] AI2Apps Shell、Account、Local App、Entry、Mini-Entry context 不可见。
- [ ] 对未授权 context 执行 `script.callFunction`、截图、导航和输入均返回 BiDi 权限错误。
- [ ] 使用未授权 realm、navigation ID、window ID 或 userContext 的旁路请求失败。
- [ ] 切换 Tab 后旧 grant 失效或按设计完成受控 rebind。
- [ ] mount 关闭、logout、权限撤销和 AceFox restart 后连接立即失效。

### 9.3 敏感能力

- [ ] `browser.read` 无法调用 `storage.getCookies`。
- [ ] `browser.interact` 无法读取认证 header 或跨 Tab 数据。
- [ ] 只有显式完整 Profile grant 才能执行允许的 browser-global 命令。
- [ ] 密码、OTP、Cookie、token 和支付字段不进入模型、日志、Source、Evidence 或 audit。

### 9.4 回归

- [ ] Chat 可读取绑定网页的渲染文本和 selection。
- [ ] 用户启用后可截取绑定网页的 viewport。
- [ ] Knowledge 可导入需要登录的当前网页，但不能读取其他 Tab。
- [ ] Agent 可在授权网页中 click/input/scroll/navigate。
- [ ] 原生 BiDi 方法和 payload shape 保持兼容，未新增语义浏览器 API。
- [ ] 多个 Mini-Entry 不会互相继承 context、Profile 或 grant。

## 10. 完成标准

只有同时满足以下条件才能认为整改完成：

1. 代码路径上不存在 WebAgent -> `app-shell` BiDi endpoint 的连接或 fallback。
2. Helper 能证明上游是当前 Installation、当前 boot、当前 lease 下的独立 AceFox 网页浏览器实例。
3. Gateway 在服务端强制 Profile/context/capability scope，前端 SDK 不再是安全边界。
4. AI2Apps Shell、Account 和所有 Local App context 对 WebAgent 不可见且不可操作。
5. 自动化测试覆盖实例替换、PID 复用、跨 Profile、跨 context、storage/Cookie 和撤销场景。
6. Trust Center/Setup UI 对完整 Profile 级 BiDi 权限给出明确说明并允许撤销。
7. 安全审计确认日志和诊断不包含页面内容或凭据。

## 11. 相关文件

- `docs/ai2apps-browser-control-architecture.md`
- `docs/ai2apps-platform-architecture.md`
- `docs/ai2apps-browser-agent-sidebar-builder-plan.md`
- `ai2apps/browser/shell_bidi_gateway.py`
- `ai2apps/api/browser.py`
- `ai2apps/web/static/js/browser_bidi_client.js`
- `ai2apps/web/static/js/chat_mini.js`
- `apps/ai2apps-acefox/Sources/AI2AppsLauncher/main.swift`
- `apps/ai2apps-acefox/Sources/AI2AppsSupervisorCore/LaunchPlan.swift`
- `apps/ai2apps-acefox/Sources/AI2AppsSupervisorCore/BrowserAgentLaunchPlan.swift`
- `apps/ai2apps-acefox/Sources/AI2AppsContracts/ShellAutomationDescriptor.swift`
- `apps/ai2apps-acefox/Sources/AI2AppsHelper/main.swift`
- `tests/test_ai2apps_browser.py`

