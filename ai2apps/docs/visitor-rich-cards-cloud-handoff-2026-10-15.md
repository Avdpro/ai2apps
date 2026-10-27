# 访客空间富内容卡片：Cloud 交接（visitor-content-v1）

## 当前状态

Local 已实现编辑、草稿、共享预览、发布校验、图片/视频/HTML 素材副本、稿件及轮播展示。没有修改 Cloud 源码、生产配置或用户已发布空间。新素材通道默认关闭；含素材的发布会明确提示 Cloud 尚未就绪，文字/链接/无封面稿件和对应轮播仍兼容既有发布流程。

## Edge 精确资源通道

仅新增 `GET` / `HEAD /mobile/space/media/{revision}/{asset_id}`。

- `revision` 为非负十进制整数；`asset_id` 为 64 位小写十六进制标识，不接受后缀、子路径、编码斜杠或路径遍历。
- 沿用现有匿名/访客空间 Cookie、设备绑定、会话租约；不能把本路径当作无身份静态资源。保留当前 8 小时绝对时限、30 分钟闲置、最长 120 秒短租约与撤销机制。
- Local 每次验证租约、设备、当前发布版本、公开快照中明确引用的素材标识；包含轮播子卡片，隐藏卡片不发布。素材目录按 Installation 隔离；不暴露 Gallery 路径或其它资产。
- 放行 Range / If-Range，透传 200/206/416、Content-Type、Content-Length、Content-Range、Accept-Ranges；HEAD 无响应体。视频最大 100 MiB，禁止代理把完整文件读进小型 JSON 缓冲区。
- 保留 `Cache-Control: no-store`、`Referrer-Policy: no-referrer`、`X-Content-Type-Options: nosniff`，不跨用户共享缓存。
- 绝不放行 `/v1/platform/remote/visitor-space/**` 或 Gallery 管理/内容路由，它们仍只属于设备 Owner Local。

## CSP

空间页面新增 `media-src 'self'; frame-src 'self'`。已有图片源为 `'self'` 与精确 Cloud 头像源，不增加任意外部源。

HTML 素材响应必须保留：

```
sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'
```

iframe 同时带 `sandbox="allow-scripts"`，无 allow-same-origin、表单、弹窗、下载、顶层导航或 Bridge。HTML 必须用户点击才运行，离开可视区停止。Data URL 仅作为编辑导入形式，会解码成 UTF-8 文件；不是信任证明。该隔离保护父页面与私有能力，不宣称可以消灭任意脚本 CPU 消耗或 iframe 自身导航，不能把它升级为有权限的 App。

## 数据与限制

保持 bootstrap、JWT、会话协议不变。`space.cards` 新增：

- image: `assetId`, `fit: contain|cover`；上传 ≤20 MiB，解码 ≤4000 万像素，重编码 PNG、移除元数据、最长边 2560。
- video: `assetId`, 可选 `coverId`；≤100 MiB、≤300 秒、最长边1920且短边1080；MP4/WebM，H.264/VP8/VP9/AV1。不自动播放。
- html: `assetId`, `height:160..800`；UTF-8 ≤10 MiB；自包含 CSS/JS 和内联素材。
- article: `body` ≤1 MiB，基础 Markdown、可选 `coverId`；raw HTML 仅显示为文字。没有开放任意附件 URL。
- link: 既有 HTTPS URL，增加可选 `coverId`。YouTube/B站作为来源卡片打开外部网页，不嵌入第三方播放器，不自动抓取 URL。
- carousel: `cards` 最多8张、禁止嵌套、`autoplay` 默认false、`interval` 默认5秒（3–30）。发布至少一张可见子卡片。

所有素材只保存不透明标识，bootstrap 不承载 HTML 或媒体二进制。顶层最多30张卡片；既有 `text/link/app` 继续兼容。Cloud 若有卡片类型白名单/计数校验，需要兼容这些字段并递归计数 app；不得扩大应用权限。

## 激活与验收

Cloud 回执确认通道与 CSP 后，Local 通过实例 config/visitor-content-gateway.json 设置：

```json
{"enabled": true, "protocol": "visitor-content-v1"}
```

或隔离测试使用 `AI2APPS_VISITOR_CONTENT_GATEWAY_READY=1`。本次未开启任何实例配置。

验收：图片与视频 Range、10 MiB HTML 边界；无 Cookie、撤销/过期、错误设备/Installation、旧 revision、未发布/隐藏/已删除素材均拒绝；HTML 无父 DOM/Bridge/私有 API；轮播嵌套素材与跨卡片播放；Chrome 与 iPhone Safari 真匿名会话。

## Local 验证

36 项 Python（包含既有空间/租约回归、新素材发布与权限、实际短 MP4 ffprobe）、11 项 Node 通过。隔离浏览器验证了轮播 dot 切换、稿件展开、HTML 运行/离屏停止及390px布局。未宣称完成生产公网或真实 iPhone Safari 验收；未替用户发布内容。
