# Owner Open-Home 客户端接入状态（Cloud OpenAPI 1.62.0）

状态：implemented_dev_e2e_verified。用户明确批准后启用就绪标志，仅重启公网主设备 dev；App-Dev 与生产未升级。

## 已实现的接入基础

- 独立 `oh1` handoff 接收，严格 EdDSA、issuer、audience、scope、Owner/设备/Installation/组织以及 epoch/revision 验证。
- 浏览器仅获得不透明 Secure/HttpOnly/SameSite Cookie；refreshToken 仅保存在 Local 内存，不创建通用 Local 成员会话。
- 60 秒签名租约、30 秒后台刷新、8 小时绝对期限和 30 分钟闲置上限。后台刷新不制造前台活动；离线不延长当前租约。
- 撤销、设备关闭或 epoch 变化会终止租约。续租与退出竞争时不允许恢复已撤销会话。
- ASGI 响应护栏取消超时的活动请求和静默流，发送内容前再次检查租约。
- Home 中“进入我的应用”只接受 Cloud 生成的固定授权 URL；未完成能力声明前不返回/显示该链接。
- 模块 READY 默认 false，完整服务端注册公网边界与独立 Chat 适配后才置 true；不完整的运行时仍拒绝新交换。

## 已完成的运行时连接与验收范围

`omlx/admin/routes.py` 的 Mobile 授权识别进程内租约；Chat 数据路由放入独立 FastAPI 实例，只显式导出模型目录与对话回调。通用认证依赖没有 Owner 绕过逻辑。

实现范围及后续实机验收：

1. Mobile 授权入口识别已通过公网边界检查的进程内租约记录，每次读取都检查当前租约；不从请求 Header 接收身份。
2. 首批只开放内置 Chat 的目录、挂载、线程和对话操作。禁止其它 App、管理界面、MCP、平台任意路径和后台 Agent 任务；实例/挂载也必须绑定到 Chat 与当前主体。
3. Chat 内部调用使用独立、明确路由与 HTTP 方法的受限适配层。不得回退到服务端 API Key，不给通用管理依赖增加 Owner Home 绕过条件。现有通用认证和旧 Mobile 协议保持独立。
4. UI 只在真实交互时报告活动；状态轮询不续闲置期限。过期/撤销后停止流并回到 Cloud 独立授权入口。
5. 完成未授权/访客/跨设备/跨主体/跨 App/方法绕过与流式撤销测试后，才设置 READY 并声明 enabled=true。
6. 当前公网主设备是通用 dev，本次按用户明确批准仅重启该实例进行实机验收。App-Dev 未升级；以后激活 App-Dev 时仍须通过固定构建脚本重建。真实断网/30分钟闲置/8小时边界本轮未等待执行，相关失败关闭和边界行为由隔离测试覆盖。

## 验证与激活

- 114 项相关 Python 测试通过：租约/流19、受限网关与真实数据库17、个人空间12、Remote42、Mobile/相关路由9、Chat15。4 项前端状态/活动/锁定/模型能力格式测试通过；JS/Python 语法和 scoped diff 检查通过。
- 扩大筛选额外发现桌面麦克风旧源码断言失败，位于未由本次修改的 shell.js；不属于 Owner 链路，未擅自修改。
- 两次启用动作曾被自动审批拒绝；用户随后明确批准“启用并进行实机验收”，再执行成功。用户批准范围和工具边界保留。
- 通过标准 HelperControlClient 仅重启 dev。新 PID 88485、端口 53256、boot 2d6c17fa-a503-41a7-b9a9-7a19f01f3023；health 200。公网 Host 未授权 /admin 与 owner status 均403。App-Dev boot 24d29c59-f2e2-45b6-9733-b17b3b15fa02 未变。
- 原生 Dev Home 的公网状态仍“已连接”，账户二维码仍是固定 /u/<owner>。从链接打开 Cloud 已显示“已登录，可进入自己的应用或公开空间”，存在独立“进入我的应用”按钮。
- 真实 Owner 链路通过：固定账户 URL → Cloud 当前访问者会话 → “进入我的应用” → 设备 /mobile → Chat。新浏览器授权后能读取同一 Owner 的既有测试线程；刷新及 Home/Chat 切换后历史保留。
- 真实模型调用通过：显式选择 DeepSeek V4.1 Flash，返回 Connected.；同一 Chrome 会话在首次续租 05:15:19 后，于 05:30:46 再次成功对话并返回 Long session OK.（北京时间 2026-10-07；从首次续租计算已超过15分钟，期间无重登）。
- Chrome 会话后续续租至05:31:17，全部200；首个 AI2Apps 浏览器会话也持续续租超过20分钟。只记录时间与结果，不保存 Cookie、handoff、refreshToken 或签名 JWT。
- 流式退出实测：在页面出现 Streaming from this Mac 时点击退出；05:31:44 Cloud revoke返回200，Chat iframe被移除，页面显示 Owner 会话已结束/重新授权。重新加载不能恢复旧会话。只撤销了用于此项测试的Chrome会话，不退出用户的Cloud账号。
- 390×844 手机视口核对：正文与输入框无横向溢出，顶部退出按钮可见；恢复了测试前默认视口。
- 普通公网内部账户API在带Owner Cookie浏览器中仍由边缘404拒绝；Agent API浏览器导航显示ERR_BLOCKED_BY_CLIENT，不能将该结果当作服务端401证据（客户端隔离测试另有覆盖）。
- 实机修正：模型能力同时支持列表与对象；明确非聊天声明优先于旧model_type，默认要求选择模型；隐藏未开放Agent/附件按钮，修正被主内容遮住的退出入口。旧原始Local模型中仍有被上游标为llm的语音模型，本次未修改模型发现器，显式选择避免自动误用。
- AI2Apps原生浏览器下拉菜单操作后出现可访问性控件树异常，实际对话与长会话在Chrome完成；没有因此复制浏览器Cookie或改用后台Owner会话。

未修改 Cloud 项目，未发布 Desktop，未重建 App-Dev。首批仅支持文本 Chat，附件和 Agent 后台任务隐藏并被服务端拒绝。
