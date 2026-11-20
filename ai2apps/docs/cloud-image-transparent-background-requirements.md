# Cloud 图像透明背景契约需求（2026-11-20）

Sticker Workshop 新增白底/透明选项。BYOK 已直接透传原生 `background=transparent`，输出 PNG；Cloud 后端需要由 Cloud 项目单独实现并部署。

- `/v1/ai/models` 对实际支持的模型在 `imageOptions.background` 发布 `auto`、`opaque`、`transparent` 的真实支持集合，不按模型前缀猜测。未发布时客户端拒绝透明请求，不切换路由。
- 图像 generations/edits 请求允许可选 `background`，严格校验枚举与 PNG/WebP 格式约束；原样传给 Provider。省略时保留现有行为，透明请求不能静默转成白底或 JPEG。
- 原始输出字节及 MIME 保留 Alpha。适配层、结果存储、缩略图与下载链路不得把透明输出压平到白色。
- 客户端执行前重查当前模型目录，仅声明支持后才向 Cloud 提交此字段。返回不透明结果时客户端报错，不重试、不换模型或 Provider、不用抠图伪造成功。
- 验收 generations、双参考 edits、PNG/WebP、JPEG 拒绝、未支持模型拒绝、输出 Alpha、原始尺寸、计费/请求标识与幂等；需要 Cloud 真实调用验收。当前客户端验收仅使用夹具。
