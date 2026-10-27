# 富内容访客空间 Local 启用回执

2026-10-15，接入 Cloud `visitor-content-20261015-v2`。

## 已完成

- 已核对 Cloud 生产回执，精确 GET/HEAD 素材通道、Range/If-Range 与 CSP 一致。
- Dev、App-Dev 的 App 和 Helper 源码根均为 `/Users/avdpropang/sdk/omlx-moe-cache`。
- 重载前只读统计两个实例的任务状态，未发现活跃任务。
- 两实例 `config/visitor-content-gateway.json` 设置为 `{"enabled":true,"protocol":"visitor-content-v1"}`，通过标准 Helper 重启 Local；没有复制源码、修改签名包或混用实例数据。
- App-Dev：PID 23797，端口 61781；Dev：PID 23812，端口 62006。
- 重载日志确认 `ai2apps.web.space_routes` 从当前 checkout 导入；实际服务的 space.js、visitor_space_editor.js、space.css SHA-256 与源码一致。
- 真实 Device 公网素材路径无 Cookie 请求返回 403、Cache-Control no-store。
- 使用独立浏览器从固定用户 URL 进入，匿名交接成功并显示现有公开文字空间；没有读取 Cookie、发布/修改用户内容。

- 匿名页面跨越 120 秒短租约后仍正常；再次整页刷新成功恢复公开内容，无需重新登录。该检查不等同于30分钟闲置或8小时验收。

## 验收边界

本次仅启用通道与验证已有内容。真实图片/视频/HTML 尚未发布，因此不能宣称已完成公网媒体、Range、沙箱与轮播端到端验收。相关隔离测试此前为36项 Python、11项 Node通过。

物理 iPhone Safari、真实媒体发布后的权限矩阵及30分钟闲置/8小时绝对时限仍待验收。现有公开内容保持不变，新增卡片由用户编辑并明确发布后生效。

回滚：将目标实例配置 enabled 设为 false（默认关闭）；不要回滚或覆盖用户空间数据库。
