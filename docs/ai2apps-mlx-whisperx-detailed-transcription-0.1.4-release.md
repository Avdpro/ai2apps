# MLX WhisperX Detailed Transcription 0.1.4 发布回执

日期：2026-09-23

## 发布身份

- Package：`ai2apps/model-detailed-transcription-mlx`
- Version：`0.1.4`
- Submission：`cb49e7b6-eb88-4597-9715-ade6dcb71688`
- Publisher ID：`229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher public-key fingerprint：
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`
- Repository Snapshot：`194`
- Submission created at：`2026-09-23T06:42:04.175Z`

## 不可变发布物

- Artifact：`ai2apps-model-detailed-transcription-mlx-0.1.4-production.ai2service`
- Size：`32,289` bytes
- SHA-256：`6ab0086aaec6ef30e6aa56f0bb6568235a9beff0b97608b74c9bdd64cab81bf8`
- Runtime dependency：`ai2apps/runtime-omlx >=1.6.0,<2.0.0`

0.1.4 修复 forced alignment 丢失标点和大小写的问题。Qwen3-ASR 原始 transcript
继续作为显示文本；Qwen3 ForcedAligner 只提供 `words[].start/end` 和 segment timing。
当规范化后的对齐文本覆盖原文不足 65% 时，才允许沿用原有的严重幻觉裁剪保护。
Runtime 与 checkpoint 分发均未变化。

## 发布与验证

- 英文 `Come on, Joey!` 和中文 `你好，世界！` 的标点/大小写回归已覆盖，同时验证
  aligned words 和时间戳仍被保留，既有 hallucination trimming 测试继续通过。
- 185 项 Pipeline、Package、provisioning、Worker 和 Studio 测试通过；正式与实验
  aligner 源码逐字节一致，Ruff 和 diff whitespace 检查通过。
- 0.1.4 source 携带签名覆盖的 discovery、model profile 和 install metadata；为兼容
  当前 Cloud，正式构建仅省略可选的外层 `modelInstall` catalog projection。
- 初次使用不匹配的历史 Keychain 记录时，Cloud 在验签阶段拒绝请求，未创建 submission。
  随后使用已注册且指纹匹配的现有 Publisher key 完成 candidate、review、approved、
  published 全流程；没有创建替代 Publisher、key、Package ID 或版本。
- Dev 实例 Cookie 只通过标准 live publication 脚本用于本次 Package；没有复制、输出或
  写入发布物。发布及公开验证完成后，该 Cookie 授权失效。
- 匿名 Registry 验证返回 Snapshot 194；artifact 完整字节和 envelope JSON 均与本地
  正式制品一致。

## App-Dev 验收状态

本次已完成代码、Package、发布流程与匿名 Registry 一致性验证。App-Dev Local 重启并
加载 0.1.4 版本上限的安装映射后，Discover 不再显示“不可信安装计划”，卡片可进入
`Install model`；对应 catalog/install compatibility 测试 40 项通过。真实媒体推理回归
仍需把已安装 Package 升级到 0.1.4，并使用本机已授权的 Qwen3 ASR、ForcedAligner 与
Sortformer checkpoint 处理测试媒体；这一步不需要新 Runtime 或 checkpoint 分发。
