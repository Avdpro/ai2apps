# Desktop 0.1.8 / Build 2269 Cloud 发布交接

日期：2026-11-21（Asia/Shanghai）。用户已明确要求先发布当前版，后续变更下一版。
当前生产基线：0.1.8 / 2268，10000 basis points。目标：2269，先 0% 登记验收，再同 rollout ID 扩到 100%。

## 固定工件

- 源码：a29bfd9232a6198e81aad725ea31bd85426edc3f；构建时工作区 clean，已推送 origin/codex/desktop-2269。
- GitHub：https://github.com/Avdpro/ai2apps/releases/tag/v0.1.8-build2269
- ModelScope：ai2apps/desktop-releases，revision a35543d9452f94d4e0375ce2736475a5424e7fb6。
- Apple Accepted submission：45a36f0e-48d5-4b8a-b834-f7a31f6afc39；stapled、Gatekeeper、递归验签及最终 metadata 验证通过。
- Bundle com.ai2apps.desktop；instance default；arm64；Runtime cloud；无完整模型 Runtime 或权重。
- 工件目录：`/Users/avdpropang/sdk/omlx-moe-cache/apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.8-build2269`
- 0% 清单：`/Users/avdpropang/sdk/omlx-moe-cache/apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.8-build2269/stable-zero.json`
- 100% 目标参考：`/Users/avdpropang/sdk/omlx-moe-cache/apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.8-build2269/stable.json`
- rollout ID：`build2269-test`，扩灰不得更换。

- `/Users/avdpropang/sdk/omlx-moe-cache/apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.8-build2269/AI2Apps-0.1.8-build2269-macos-arm64.dmg`：270054639 bytes；SHA-256 `b883e3dacc666e6a9efc8897a7c0cdd6a087a5e09817a69a11e902c41b42cfa8`。
- `/Users/avdpropang/sdk/omlx-moe-cache/apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.8-build2269/AI2Apps-0.1.8-build2269-macos-arm64.release.json`：1011 bytes；SHA-256 `04dca80d26e3e9394721ee46b6788288e57b9f9e7c2ceba5316883601cf2b3ef`。

## Cloud 执行要求

请按 Cloud 的 desktop-update-production-runbook 执行：schema、双源匿名完整下载、正确 206 Range/Content-Range、大小/SHA-256/notarization 预检；使用真实 operator/approver 和用户发布批准记录先原子登记 0%，验收后通过 rollout 操作扩至 10000。不得直接覆盖 stable.json，不得伪造独立审批身份。

记录 GET/HEAD 200、正确 Content-Type/Length/Cache-Control、无 Set-Cookie、条件 ETag 304、清单摘要、健康状态和日志；预检失败保持 2268。

## Desktop 验证与限制

原生 Swift 检查、图片所有权/传输修复专项、翻译/导航/Todo/情报夹具专项、17 项发布工作流隔离测试通过。正式 App 临时空数据冷启动通过，schema 123，内嵌源码和服务资源字节匹配。2268→2269 只读升级资格验证 eligible。

用户确认手机 Bot、BYOK 图片及商品图实机验收，并明确要求发布阶段不重复耗时 Bot 完整回归。已中断的全量 Host/AaAT 及旧 Bot UI 测试失败保留，不标为全量通过，未批量放宽 Bot 测试。

独立 Package 不在本任务重新发布。Cloud 原子发布及目标 Mac 真实下载/安装/重启尚待执行；本交接不声明自动更新已上线。完成后请回传 Cloud 发布回执，随后记录目标 Mac E2E 升级结果并推进 Desktop 台账基线。

双源最终本地预检：GitHub 与 ModelScope 的 DMG/metadata 匿名完整下载 size/SHA-256 全部匹配；Range bytes=1024-2047 均为 206 且 Content-Range/字节匹配。PyPI/Homebrew 两个 GitHub release 工作流均 skipped。
