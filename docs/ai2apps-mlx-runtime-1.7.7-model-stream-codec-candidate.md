# AI2Apps oMLX Runtime 1.7.7 模型流式 Codec 候选

日期：2026-09-20
状态：已完成生产发布与匿名精确回读；正式回执见
`docs/ai2apps-mlx-runtime-1.7.7-model-stream-codec-release.md`

## 目标

把模型专属的 token 到文本、特殊 token 保留和 append-only 增量策略放到签名的纯 Python
Model Package Adapter 中，同时把 MLX/oMLX、tokenizer 原生实现、Metal kernel、Worker Host、
协议分流和计量继续留在 Runtime。现有 Model Package 不升级也不改变行为。

## 交付

- Runtime 新增版本化接口 `ai2apps.model-stream-codec/v1`：
  `decode_prefix()` 产生稳定完整前缀，`append_delta()` 只产生新增后缀。
- `OmlxChatAdapter.create_stream_codec()` 是默认返回 `None` 的兼容 hook；旧 Package 继续使用
  Runtime 默认 codec。DeepSeek V4.1 专用引擎已消费该 hook。
- Runtime 提供 `PrefixTextStreamCodec`，默认保留 `<think>` 特殊 token、排除终止 EOS、延迟
  不完整 U+FFFD 后缀并在解码前缀回退时 fail closed。
- Contract v1 构建/验包和旧 Service Archive 验包均禁止
  `ai2apps-model-worker/v1` Package 携带原生载荷；声明 `native_artifacts` 也不能绕过。
- Runtime Package 元数据升至 `ai2apps/runtime-omlx 1.7.7`，新增 capability
  `model-stream-codec-v1`。现有模型 Package 源码与版本均未修改。
- 模型 Package 开发手册新增 Runtime/Package 边界、codec API、兼容规则与发布测试要求。

## 验证

- 69 项定向回归通过：stream codec、DeepSeek V4.1 decoder、Chat Adapter、Cache-MoE Worker、
  Package Contract、旧 Service Archive、Inference Runtime Package 和 Runtime builder；修改文件
  Ruff 检查及 diff whitespace 检查通过。
- 标准 Contract v1 构建器分别拒绝 `.dylib`、`.metallib`、`.node` Model Worker 载荷，错误码为
  `model_worker_native_payload_forbidden`。
- 未修改的 `ai2apps/model-deepseek-v41-flash 0.1.1` 使用标准构建器原样构建成功，证明旧
  Package 不需要为了新扩展点升级。
- 标准 Runtime 构建器已生成本地 ad-hoc 候选
  `/private/tmp/ai2apps-runtime-omlx-1.7.7-development.ai2service`：
  361,684,836 bytes，SHA-256
  `4a4d0d76c03246ca4bb1d7bd84d9aaa7bc452a0d711aa0d0942b9c833a909df8`，Package digest
  `sha256:44b6b30854876e965683d7c6a2cbb3ee1de054ef9fef20453dc92423419f368f`；旧 Service
  Archive inspector 已重新验包并确认 `ai2apps.runtime.omlx 1.7.7` / Runtime protocol。
- 按固定脚本重建 `AI2Apps-app-dev.app`，旧环境归档为
  `AI2Apps-app-dev-20260920-000836.app`；`codesign --verify --deep --strict` 通过，bundle ID
  `com.ai2apps.desktop.appdev`、instance `app-dev` 正确，Bundle 内已确认 codec API 与 adapter
  hook。重启后原生标题为 `AI2Apps-App-Dev: App-Dev 127.0.0.1:51268`，Local `/health`
  返回 `healthy`。

测试结束时 nanobind 在无可用 Metal 的测试进程退出回调中报告环境提示；pytest 本身为
69/69 通过，该提示不来自被测 codec 或 Package 合约。

## 发布结果

- 标准 Runtime 构建器已冻结并完成 Developer ID 签名；Apple Submission
  `b15b7da5-0eec-4afb-aad6-6279e131220d` 为 `Accepted`，staple 与 Gatekeeper 均通过。
- 生产 artifact SHA-256 为
  `f1b8d19e6befcb9c604bf975fd6dbdd3bb055db8a78fa83c17ef3e498dfc9408`，大小
  377,042,056 bytes。
- Cloud Submission `9b85c590-199c-4ec4-80e7-f87d10fc4392` 已发布，Registry metadata
  version 179；匿名回读确认 artifact bytes 与 envelope JSON 完全一致。
- 当前 Dev Cookie 仅通过实时 Shell BiDi 路径用于本次发布，未读取或复制 Cookie SQLite；授权已随
  发布完成失效。
