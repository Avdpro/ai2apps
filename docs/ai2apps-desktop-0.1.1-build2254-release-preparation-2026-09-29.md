# AI2Apps Desktop 0.1.1 Build 2254 发布准备

状态：`source_ready`

用户已在当前发布任务明确要求构建并发布新 Release；目标为 stable 频道 100% rollout。
生产匿名清单基线为 0.1.1 / Build 2253，因此本次分配 0.1.1 / Build 2254。Build 2254
的本地发布目录和 GitHub tag 在分配时均不存在。

## 候选范围

本次 Desktop 汇总 2253 之后已经实现或已发布 Runtime、但仍需要 Desktop Host/UI 承载的
改动：

- ACPF：Package lifecycle、更新后的聊天模型推荐、共享 Checkpoint 验证收据与
  verification/materialization/activation 阶段进度。
- Chat：单击式 Rush、32K 上下文合同、流式 Thinking/Prefill/Token Gen 指标、整轮 SSD
  平均、Worker physical footprint 与峰值、流异常失败状态、Composer 模式栏。
- Models/Worker：SSD 激活状态、严格的本地 Checkpoint sidecar 复用。
- Video Composer：聚光遮罩和文本特殊层、Gallery 只预览、中文 Artifact 下载、插入静帧、
  连续变速/20x 上限、可靠保存/另存为与新建项目。
- Voice Studio：已生成 Audiobook Line 音频拖入 Gallery。
- 构建工具：App-Dev 专用录屏窗口命令。该能力受 Development、`app-dev` instance 与
  App-Dev bundle 三重约束；生产构建不得包含 Shell 变换或显示菜单入口。
- Runtime 源码与 Package 描述对齐已发布的 `ai2apps/runtime-omlx 1.8.5`，以及
  Ornith 1.5 Package 0.1.5。它们本轮不重复发布独立 Package。

详细行为、实机证据和回退说明以 `docs/ai2apps-desktop-next-release.md` 中对应 NXR 为准。
个人参考音频 `ai2apps-test-system/assets/voice-1.wav` 明确排除，不提交、不打包、不上传。

## 发布约束

- Bundle ID `com.ai2apps.desktop`，instance `default`，`arm64`，`RUNTIME_PROFILE=cloud`，
  `SANDBOX_MODE=0`。
- Developer ID `Developer ID Application: Avdpro Pang (84XL5V265N)`；Apple 公证 profile
  `ai2apps-notary`。
- GitHub `Avdpro/ai2apps`；ModelScope `ai2apps/desktop-releases`；ModelScope 为第一下载源。
- 正式制品只能从已提交、已推送且 clean 的 main commit 构建。
- Cloud 先按 0% 原子登记并完成双源预检，再以同一 rollout id `build2254-test` 扩至
  10000 basis points；不直接改生产 stable.json。

## 门禁进度

- 生产 stable 基线匿名核对：通过，0.1.1 / 2253 / 10000 basis points。
- GitHub 身份：`Avdpro`；ModelScope SDK 身份：`ai2apps`。
- Developer ID 与 Apple 公证 profile：可用。
- `node --test tests/*.cjs`：16/16 文件通过。
- `swift test --package-path apps/ai2apps-acefox`：77 项 Swift Testing + 2 项 XCTest 通过。
- JavaScript 语法、JSON、`git diff --check`：通过。
- 完整 Python 首轮发现并修正两处过期合同：新增聊天推荐文案缺少 ACPF 中英文翻译、
  视频 Runtime 同步测试仍固定 1.8.0；定向复验 7/7 通过。
- 完整 Python 修正后复验：10287 passed、68 skipped、74 deselected，742.17 秒，无失败；
  JUnit `/private/tmp/ai2apps-2254-full-final2.xml`。

## 尚待完成

1. 提交并推送候选源码，合并到 main，从 clean main commit 构建。
2. Developer ID 构建、DMG、公证、staple、Gatekeeper 和 2253→2254 候选验证。
3. GitHub/ModelScope 双源上传、匿名完整摘要和 Range 验证。
4. Cloud 0% 登记、验收、100% rollout 及生产清单/健康检查。
5. 目标 Mac 实际升级与新 Build 启动属于发布后的端到端验收；Cloud 访问日志不能替代。
