# MLX WhisperX Detailed Transcription 0.1.3 发布回执

日期：2026-09-23

## 发布身份

- Package：`ai2apps/model-detailed-transcription-mlx`
- Version：`0.1.3`
- Submission：`4a4cb7c0-dcfd-4a33-92b8-488bb09bdc6f`
- Publisher ID：`229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher public-key fingerprint：
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`
- Repository Snapshot：`193`
- Published at：`2026-09-23T01:46:31.044Z`

## 不可变发布物

- Artifact：`ai2apps-model-detailed-transcription-mlx-0.1.3-production.ai2service`
- Size：`31,382` bytes
- SHA-256：`44ab6c4ab6d9b9ed9fa6c27186edbf06750680e34bba1f70acb66cc9380999c2`
- Runtime dependency：`ai2apps/runtime-omlx >=1.6.0,<2.0.0`

0.1.3 修复 ASR 返回完整语言名或 locale tag 时的 forced-alignment 失败。Pipeline
在调用 Qwen3 ForcedAligner 前把 `English`、`Chinese`、`en-US`、`zh-CN` 等值规范化为
aligner 支持的语言代码；aligner 边界也接受规范全名。Checkpoint、Runtime 和模型能力
声明均未变化。

## 发布与验证

- 61 项 MLX WhisperX 测试和 75 项 Package/provisioning 测试通过；覆盖现场错误形态：
  ASR 返回 `English` 后进入 forced alignment。
- 正式与实验 Pipeline/Aligner 源码保持逐字节一致；Ruff 和 diff whitespace 检查通过。
- 注册 Publisher 公钥离线验签通过，指纹与 Cloud 当前 active key 完全一致。
- Dev 实例 Cookie 只通过标准 live publication 脚本用于本次 Package；没有复制、输出或
  写入发布物。发布完成后该 Cookie 授权失效。
- Cloud submission 完成 candidate、review、approved、published 全流程。
- 匿名 Registry 下载返回 Snapshot 193；artifact 完整字节和 envelope JSON 均与本地
  正式制品一致。

## App-Dev 验收状态

App-Dev 已通过 Discover 发起 0.1.2 → 0.1.3 升级。Compact profile 缺少本地
Qwen3 ASR checkpoint，Models 正确进入 checkpoint 安装；其中 Sortformer 需要用户确认
NVIDIA Open Model License。首次确认界面因动态 Tailwind `z-[10000]` 未进入构建样式而
落在模型配置弹窗后方，表现为 `Starting…` 卡住。Dashboard 已改为显式 DOM z-index，
并增加源回归断言；刷新静态页面即可生效，无需重建 App。

许可必须由用户本人确认。Compact checkpoint 下载完成后的真实 Voice Studio 英文转写
回归仍待执行，因此该项 Desktop NXR 状态保持 `in_progress`，不把 Package 已发布误记为
端到端验收完成。
