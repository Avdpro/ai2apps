# 匿名访客会话续租 Local 接入（2026-10-09）

依据 Cloud OpenAPI 1.65.0 / personal-space-anonymous-session-v1。Local 代码已接入，Dev 真实 Chromium 持续浏览10分27秒验收通过。

## 实现
- 完成页 /mobile/space/session/complete 读取并立即清除 fragment，经 Local 兑换。长期 refresh proof 仅保留在 Local 内存，不进入 Cookie、bootstrap、URL 或日志。
- 独立会话和短租约：Cookie 最多覆盖签名绝对截止；租约过期不删除仍可续租的身份，但不给过期租约放行。Local 重启需重新从固定入口进入。
- 验证 Ed25519、准确协议/audience、匿名身份、session/jti、lease version、Owner/device/installation/credential/access/mapping/capability/space/published 绑定，120 秒租约与8小时/30分钟边界。旧协议不升级。
- 逐会话异步锁合并续租；剩余60秒或前台活动触发，至少30秒间隔。超时保留同一 requestId/body 重试，过期幂等缓存使用服务端当前版本和新 requestId。拒绝版本回退和关闭期间迟到的响应。
- 401/永久错误终止；429/5xx/网络错误保留身份、有界退避（含 Retry-After），有效租约之外暂停资源。关闭/发布先撤销 Local 身份，再同步 Cloud。
- GET bootstrap 只检查/续租，POST 才报告前台阅读活动，严格 Origin/Host/Cookie。前台每60秒报告，后台不推进闲置；pageshow/恢复先验证，初次交接完成前不抢先检查 Cookie。
- 页面续租不重绘相同发布版本、不导航、不重载 iframe；网络异常显示连接恢复中，租约截止隐藏内容，恢复后显示。绝对/闲置截止或撤销后提供固定入口。
- 既有 Dev 就绪配置不变，在完整能力声明增加 visitorSessionProtocol；用户开关、内容与真实 App 数量不变。

## 自动验证
76 项 Python 回归通过，包含6项新会话并发/后台恢复/活动/关闭竞态/网络失败/旧版本拒绝测试；8 项 Node 通过，覆盖前后台活动、同版本不重绘、交接与 pageshow 竞态。JS 语法和 scoped diff 检查通过。最终 Retry-After 日期解析改动后6项会话测试再通过。

## 验收边界
不修改 Cloud。未将 iPhone Safari 或 opaque sandbox App Cookie 推断为通过。真实关闭/重开会影响用户已开放空间，本轮不更改用户开关；撤销与竞态先由隔离测试覆盖。8小时/30分钟完整墙钟验收未执行。

## Dev 实机记录
最终 Local：dev / PID 80116 / 端口 60039。通过标准 Helper 控制通道重启，未改访客开关或内容，未重启 App-Dev/Test。

内置 Chromium 浏览器从固定个人 URL 建立新协议会话。首轮发现 pageshow 在兑换前触发 bootstrap 的401竞态，已修正为交接完成后再检查，并新增回归测试。最终版本持续阅读从 UTC 2026-10-08 21:26:54 开始计时（页面更早已完成兑换），无手动刷新、点击或重新授权。后台核对同一 session 的 Cloud refresh 200 和单次 exchange；无敏感凭据写入验收记录。

新增 HTTP 层专项测试通过：POST bootstrap Origin 约束、Secure/HttpOnly/SameSite Cookie、8小时 Cookie 上限、响应无 refresh proof。会话专项共7项、前端8项通过；既有70项后端回归此前通过（与首6项会话专项合计76）。

最终结果：UTC 21:37:21 结束，连续观察 10分27秒；同一 session 成功续租10次、失败0次、仅1次exchange。最终浏览器仍在 /mobile/space/home，visibility=visible，visitor-root 未隐藏，status为空，标题和文字卡片正常。通过本轮真实 Chromium 前台持续阅读验收；不是 iPhone 或8小时墙钟验收。
