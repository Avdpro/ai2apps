# Local 账户头像接入（2026-10-15）

状态：Local 实现、自动化及隔离 Chromium 裁剪验收完成；固定 App-Dev 已重载。真实账户上传/Gallery 联调与 iPhone Safari 尚待验收，不宣称生产客户端已发布。

## 实现

- Account 身份圆形头像和资料区的「设置头像」入口；替换普通用户的 URL 输入框。无头像/图片失败使用姓名首字母。只显示 Cloud 正式托管头像，旧外链降级。
- 本地 PNG/JPEG/静态 WebP、Gallery 图片单选；1:1 圆形预览、拖动、滑杆及双指缩放、旋转/重置；导出方形 300×300 PNG。原图和 Gallery 内容不修改。取消不上传。
- PUT/DELETE `/v1/platform/cloud/profile/avatar` 使用当前浏览器 Cloud 会话与既有 Core/Origin 保护，转发 `If-Match`、错误状态、ETag、Retry-After。即使 chunked 请求也在 multipart 解析前限制总量；拒绝多余字段、多个文件、query 与 DELETE body。
- 独立头像 CAS，不使用普通资料 PATCH 覆盖头像。409/不确定网络结果后回读；保留裁剪，明确再次保存才替换。缺失合法 avatarRevision 不猜为 0。其它资料未保存草稿保持原样。
- 公开空间已授权 bootstrap 从现有匿名 resolver 取得最小权威 Owner 头像投影，每 Owner 最多缓存 60 秒。只接受正式头像 URL，未改变 JWT claims/会话/正文 revision。仅更新头像 DOM，保留访客应用 iframe。
- 草稿预览显示当前账户头像；Account、访客空间编辑页和公开入口精确允许 coder.ai2apps.com 图片源，未放宽其它 App/script/connect 权限。

## 验证

- Python 49 项通过：上传版本/错误透传、大小/字段/参数拒绝、移除、头像投影缓存/删除、CSP 精确作用域，以及既有匿名租约/公开空间/HTTP 安全回归。
- Node 11 项通过：裁剪边界与旋转几何、非法版本拒绝、公开头像 URL 过滤、匿名租约不重绘、编辑器草稿发布顺序。
- 隔离 Chromium：合成 600×300 图片加载、旋转、缩放、拖动；模拟 409 后保留画面，主动第二次保存收到 `If-Match: "avatar-1"`；输出 PNG 300×300 / 10852 字节。取消关闭窗口。没有向 Cloud 上传测试头像。
- App/Helper `AI2AppsDevelopmentSourceRoot` 均为 `/Users/avdpropang/sdk/omlx-moe-cache`；运行 Local 日志确认 `api/cloud.py`、`web/space_routes.py` 从该 checkout 导入。
- 仅固定 App-Dev Helper 重载：PID 99190，端口 64402。账户 App 可打开；Cloud 账户未登录，实际上传未执行。实际服务的 account_avatar.js/css、account.js、space.js 与 checkout SHA-256 一致。未重建固定 App，未改动 Dev/Test 数据或真实账户头像。

## 待验收

1. App-Dev 登录 Cloud 后，真实本地文件/Gallery 图片选取、上传、移除与跨页显示。
2. iPhone Safari 双指缩放、选图与透明 PNG 视觉验证。
3. 公网 Dev 尚未为本轮 Python 改动重载；在启用该实例前确认空闲，按固定源码合同重载并核验。真实访客 App 运行期间头像更新不重启的端到端验收。
4. Desktop 后续发布纳入台账 `NXR-ACCOUNT-AVATAR-20261015`。没有修改 Cloud 生产或其既有依赖安全告警。
