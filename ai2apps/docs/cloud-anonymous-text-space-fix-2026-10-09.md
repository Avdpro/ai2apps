# Cloud 匿名访客：纯文字空间被误判未发布

读取生产回执 visitor-space-production-2026-10-09.md 及 src/spaces/service.ts 后确认：匿名 resolver 使用 publishedAppCount == 0 判定 unpublished。已发布的纯文字/链接空间没有 App，因此永远不能匿名访问。这与 MVP 允许先发布文字/链接冲突。

请增加明确的发布标记（如 published=true），或明确独立 publishedContentCount 并冻结兼容合同。不要让 Local 虚报 publishedAppCount；该字段仍应是已发布且未隐藏的 App 卡片数量。只有 App 数量为零，不能推断未发布。

状态验收：未发布 => unpublished；已发布且开启的文字/链接空间 => online；关闭 => closed；设备离线 => offline。旧协议/Owner Home/匿名断言验证保持不变。新字段的接收、单调代次、清空内容、零可见卡片行为应在回执中明确。

Local 本轮已实现匿名验证/交接及访客声明，未启用就绪标志或改变开关。协议声明使用本地持久 epoch/revision + 1（本地从 0 开始，Cloud 最小为 1），保证首次发布及开关变化严格递增；发布 App 数量按真实卡片统计。请确认继续兼容这套映射。

## 已解决
Cloud anonymous-text-space-20261009-v1 增加 published boolean；Local 已接入，Dev 真实零 App 文字空间匿名访问通过。详见 anonymous-visitor-local-integration-2026-10-09.md。
