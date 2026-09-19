# MLX WhisperX Detailed Transcription 0.1.2 发布回执

日期：2026-09-04

## 发布身份

- Package：`ai2apps/model-detailed-transcription-mlx`
- Version：`0.1.2`
- Submission：`ab93f656-e5e9-4360-bdc5-a11d2ccce717`
- Publisher ID：`229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Repository Snapshot：`109`
- Published at：`2026-09-04T13:56:39.604Z`

## 不可变发布物

- Artifact：`ai2apps-model-detailed-transcription-mlx-0.1.2-production.ai2service`
- Size：`31,036` bytes
- SHA-256：`03f00cd9acb9b025c56ff8bb72adce37c5a6313b9b05cc29987420f85d950ea1`
- Runtime dependency：`ai2apps/runtime-omlx >=1.6.0,<2.0.0`

0.1.2 修复 0.1.1 真实 Worker smoke 暴露的 macOS 沙箱问题：Package 不再对 Host
授予的上传文件路径调用 `Path.resolve()`，从而避免 `/tmp` 规范化到 `/private/tmp` 时
遍历未授权父目录。同时，Worker Adapter 接受 multipart 表单常见的 `true`/`false`、
`1`/`0`、`yes`/`no` 和 `on`/`off` 布尔字符串。

## 发布前验证

- 注册 Publisher 公钥离线验签通过。
- Pipeline、Package、Host route、音频能力、Discover mapping 与发布脚本联合回归
  `136/136` 通过。
- Ruff 与 `git diff --check` 通过。
- Runtime 1.6.0 与 Package 0.1.2 在隔离环境完成真实安装、依赖锁定、Worker 启动和
  Metal 推理；实际 Worker Python 为 `3.11`。
- 英文 compact smoke：输出
  `Today we are testing the standalone MLX WhisperX pipeline`，9/9 forced-alignment
  units，coverage `1.0`。
- 中文 compact smoke：输出“今天们测试中文语音识别和逐字时间对齐”，相对参考
  “今天我们测试中文语音识别和逐字时间对齐”遗漏“我”一字；18/19 alignment units，
  coverage `0.9473684210526315`。该结果作为 compact 0.6B 的已知准确率基线记录，不能
  把 forced-alignment coverage 当作 ASR 文本正确率。

## 匿名生产验收

- 公共目录返回 `latestVersion=0.1.2`、`installable=true`、`blockers=[]`。
- 签名 Repository Snapshot v109 验证通过。
- 匿名完整下载大小 `31,036` bytes、SHA-256 与本地不可变发布物一致。
- 公共 envelope 与本地签名 envelope 逐 JSON 相同。
- 直接使用匿名 Registry 下载的 artifact 再次完成 Runtime 1.6.0 中英文真实推理，结果
  与发布前 smoke 一致。
- 四个 checkpoint distribution（compact/quality ASR、ForcedAligner、Sortformer）此前
  已完成 Hugging Face/ModelScope 双源发布及匿名验证；Package 本身不内嵌权重。

本 Package 使用独立 `audio_detailed_transcription` 类型和
`/v1/audio/transcriptions/detailed` 路由，不进入 Chat STT 模型列表。
