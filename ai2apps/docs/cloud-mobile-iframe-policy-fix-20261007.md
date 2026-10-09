# Cloud 修改要求：Mobile 非 Chat App 被 iframe 策略拒绝

## 现象及已确认原因

Owner Mobile Home 能显示 Chat、Gallery、Knowledge、Todo 目录，但后三者打开白屏。
2026-10-07 使用真实 Owner 会话，Knowledge iframe 的 src 为 `/mobile/knowledge`，Chrome 显示“拒绝了我们的连接请求”。
对生产设备域名相同路径的无凭证 HEAD 探测（均为 403，不代表授权成功）显示：

- `/mobile/chat`：CSP `frame-ancestors 'self'`。
- `/mobile/knowledge`：CSP `frame-ancestors 'none'`。

只读核对 Cloud 仓库确认：`infrastructure/remote/edge-nginx.conf.template` 和 `edge-nginx-origin.conf.template` 的 iframe location 只匹配 `chat`、`app-content`。其余 Mobile 路径继承顶层 `frame-ancestors 'none'`。同一真实 Owner 会话在顶层直接打开 `/mobile/knowledge` 时正常显示界面、加载 4 项且无错误提示。

这是本次非 Chat 页面不能嵌入的根因，客户端无法覆盖网关 CSP。

## 要求

1. 两份 edge 模板及生产对应配置，都把明确授权的 `/mobile/todo`、`/mobile/knowledge`、`/mobile/gallery` 页面加入同源嵌入分支；严格限定这三个精确路径（可按现有规范处理末尾斜杠）。不要开放整个 `/mobile/*` 或任何管理/API路径。
2. 最终页面响应仅有一致的 `frame-ancestors 'self'` 策略，不得同时残留 `frame-ancestors 'none'` 或 `X-Frame-Options: DENY`。维持现有的租约、认证、Owner App 路由授权和跨源嵌入禁止。
3. 保留 Chat 和 app-content 的既有行为；增加 `test/remote-contract.test.ts` 对三条新页面路径及未授权路径的正反例。
4. 发布时检查 nginx 配置，并部署实际 edge 配置；仅升级 OpenAPI 服务镜像不能视为完成边缘配置变更。

## 验收

- 有效 Owner 会话下，三条页面 GET 返回 200 且只有可同源嵌入的有效策略；在真实 Mobile Shell 内分别打开、返回 Home、再打开均可用。
- 无凭证、非 Owner、过期/撤销租约请求继续被拒绝；跨源 iframe 仍不能嵌入。
- Chat 回归；租约刷新及 API访问范围无扩大。
- iPhone Safari 验证 Gallery/Knowledge/Todo 页面和 API；记录设备域名与生效 edge 配置版本。

## 客户端同时处理

客户端已修正未知 Gallery 图标的兼容映射、恢复损坏的 Gallery/Knowledge CSS，并增加 iframe 被拒绝时的错误提示。Cloud 部署前不能声明白屏问题已完全修复。本轮没有修改 Cloud 文件或生产配置。
