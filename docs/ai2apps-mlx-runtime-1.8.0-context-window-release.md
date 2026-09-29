# AI2Apps oMLX Runtime 1.8.0 发布收据

状态：Cloud 已发布；Cloud、GitHub、ModelScope 三源均已激活，匿名完整制品、Repository
Snapshot、Publisher 签名与外部源 Range 验证通过。

- Package：`ai2apps/runtime-omlx 1.8.0`
- 修复：按模型 Package 声明的上下文窗口限制通用文本、VLM 与 DeepSeek V4.1 的实际
  Decode 上限；旧对话 Package 缺省按 32K 兼容，抵达边界时返回
  `finish_reason=length`。
- Apple 公证：`ee64d9b1-ef34-4df4-9341-b6a6acd99b40`，`Accepted`。
- 正式 DMG：386,283,391 bytes，SHA-256
  `3ae1a46a7203f5b151715caa0e4008bafc162a8b3926093e2c2c7e3dda70419d`。
- 正式 Package：383,523,578 bytes，SHA-256
  `f1aeebaf3386c4a7c4a66d17fcb0de58f067319114bf12504197c0f39e608892`。

## 实现与验证

Worker 从签名模型声明读取 `context_window`，未声明的旧 `llm`/`vlm` Package 使用 32768
token 兼容值。四种 Chat Completions/Responses 流式与非流式入口都把有效窗口传给引擎；
引擎根据格式化后的实际 Prompt token 数计算剩余容量，并裁剪请求的输出上限。DeepSeek
V4.1 专用引擎的缺省窗口同步由 4096 调整为 32768，边界终止不会额外执行一次 Decode。

- 115 项 Model Provider、Worker、通用文本/VLM、DeepSeek V4.1、Package 与 Runtime
  定向回归通过；关键错误 Ruff 检查和 `git diff --check` 通过。
- 正式签名 Package 在全新隔离 Platform 根目录安装成功；DeepSeek V4.1 模型 Package
  0.1.0 精确锁定 Runtime 1.8.0，managed Worker 状态为 `running`。
- DMG 深层签名、staple、Gatekeeper、CPython 3.11.10、MLX 0.32.0 与原生
  `preadv_fused_experts` 探针通过。
- 本次没有修改 checkpoint 或模型 Package；既有对话 Package 可直接获得 32K 兼容默认值。

## Registry 与多源

- Cloud submission：`0492a1f9-bfc7-436c-8364-a62cf95a2925`，`published`。
- GitHub tag：`package-runtime-omlx-v1.8.0`；Source
  `src_365c3769-0314-4b50-a9cb-d051c3c4453a`，validation
  `val_ddfa6766-a28d-41ec-bf0d-6911c061e1e0`，digest
  `6b39c86015adab824d1d99e92ab8ba1ceea669d2b25cfd0188c280fd7f544e49`。
- ModelScope revision：`b56315c1c40cbcb4562d17caeed8db3967df7348`；Source
  `src_67a30f98-366e-4ed7-9c03-2d3ddfa1887d`，validation
  `val_f6c10cf2-ecb4-433f-865a-f39ab6c076bf`，digest
  `7d6b0f486635ac1cc81efe49a871a1042cbb6181c5c2c25f908b0d55daf21519`。
- Cloud 对两个外部源分别完成完整 SHA/size、46-piece manifest 与 49 次 Range 校验。
  GitHub 使用 HTTP 206；ModelScope 使用严格 HTTP 200 加精确 `Content-Range`。
- 最终 Source revision / ETag：6 / `"sources-6"`；Repository metadata：211；Snapshot
  digest：`8bd0639ff4dbb91604e404b47b15d93d2f790ddf5b7643801acb9fa6b6ea86a2`。
- 独立匿名缓存回读得到 `artifactExactBytes=true`、`envelopeExactJson=true`；对两个公开
  外部 URL 的首个 1024-byte Range 也与本地正式制品逐字节一致。

## 发布边界

这次发布只更新 Runtime。Desktop/Host 对 Package 上下文声明的归一化与展示改动仍由下一版
Desktop Release 纳入。已安装且固定到旧 Runtime digest 的模型不会仅因 Registry 出现 1.8.0
自动重锁；新的安装或后续模型 Package 最低版本升级可选择 1.8.0。
