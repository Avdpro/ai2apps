# MiniMax H3 MLX 0.9.1 发布记录

状态：已正式发布并完成匿名公网回读；待用户在 App-Dev 升级后重试原 OpenVDN 图生视频 Run。

## 修复

`ai2apps/model-minimax-h3 0.9.0` 的 Worker 适配器只接受 Python 原生布尔值。视频请求携带首帧、尾帧或参考素材时，Host 按 Worker multipart 协议把标量字段编码为文本，因此 `fast=false` 到达适配器时是规范字符串 `"false"`，旧版在模型加载前返回 `fast must be a boolean`。

0.9.1 在 Package 适配器边界把精确的 `"true"` / `"false"` 还原为布尔值，仍拒绝 `"yes"` 等模糊输入。通用 Host multipart 协议、模型 ID、Checkpoint Distribution、Runtime 依赖、权重和各 H3 变体推荐步数均不变。

## 验证

- H3 Worker 适配器定向回归：18 passed。
- 新增 multipart `fast` / `fast_max` 的四组规范布尔值回归；既有非规范值拒绝回归保留。
- Contract v1 未签名候选包构建通过：`ai2apps/model-minimax-h3 0.9.1`，142,381 bytes。
- 完整 MLX 测试集在当前无 Metal 的子进程中于收集阶段中止；这不是测试断言失败。正式发布后需在 App-Dev 安装 0.9.1，重试原 OpenVDN DMD8 图生视频任务。

## 正式发布回执

沿用已发布 0.9.0 的身份：Publisher `229d6350-cd0e-408a-9905-41367385ae5c`，Publisher key `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`，公钥指纹 `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`。本地签名记录的派生指纹与 Cloud 精确匹配，没有新建或替换 Publisher/key。

- Artifact：`/Users/avdpropang/sdk/minimaxh3/ai2apps-package/dist/ai2apps-model-minimax-h3-0.9.1-production.ai2service`
- SHA-256：`4a3e137db64db3da0d8fdb29d63e3dbca344229f006e4f95095541e2ff114b47`
- Size：142,381 bytes
- Submission：`08272d73-8099-4cab-ab24-28caced7e6d5`
- Review：`62e799da-5025-4b5c-9320-fc4e30436557`，approved
- Release status：`published`
- Repository metadata version：228
- 匿名公网回读：`artifactExactBytes: true`，`envelopeExactJson: true`

发布时仅在 Installation 会话不足后使用了用户对精确 Package/version 授权的 Dev scoped Cookie；Cookie、Cloud token 和私钥均未输出或落盘。正式发布完成后，本次 Cookie 使用授权已终止。

## App-Dev 升级入口修正

App-Dev Discover 首次点击“安装模型”时返回 `This Package does not declare a trusted model installation plan`。签名后的 0.9.1 制品实际包含完整 `modelInstall`；问题是当前 Cloud catalog 投影没有回传该字段，而 Local 的显式可信兼容记录仅覆盖到 0.9.0。

Local 的 MiniMax H3 可信安装记录现已精确扩展到已发布且逐字节验证的 0.9.1；0.9.2 及未来版本仍不会被该兼容记录放行。Discover 分类与安装计划测试通过：66 passed。Python 改动需重启固定 `app-dev` Local 后生效。

固定 `app-dev` Helper 已通过认证控制通道仅重启 App-Dev Local，端口由 `55230` 切换为 `59998`。重启后重新打开 Discover，原安装计划错误提示已消失，MiniMax H3 仍正确显示本地 0.9.0 / 服务器 0.9.1；按用户要求未代为点击安装。
