# AI2Apps Desktop 0.1.2 Build 2256 发布回执

日期：2026-10-01

状态：已发布至生产 100%；目标 Mac 实机升级验收待完成。

## 发布身份

- 版本 / Build：`0.1.2 / 2256`
- Bundle / Instance：`com.ai2apps.desktop / default`
- 架构 / Runtime：`arm64 / cloud`
- Sandbox：`0`
- 源码提交：`23ba608fe86a692c418fc815a24e2c0c1e76645a`
- GitHub tag：`v0.1.2-build2256`
- Rollout ID：`build2256-test`
- Apple Submission ID：`9dc11d31-20bd-4f3a-804a-df983e146815`（Accepted）

Build 2255 只存在双源资产，从未进入 Cloud stable。本次生产直接从 Build 2254 升至
Build 2256。

## 最终工件

- DMG：`AI2Apps-0.1.2-build2256-macos-arm64.dmg`
  - size：`267862896`
  - SHA-256：`d18eb406c38186c59a0d5de2b30074c7c3e31dff6528de0dcae35a23a5c3de45`
- metadata：`AI2Apps-0.1.2-build2256-macos-arm64.release.json`
  - size：`1011`
  - SHA-256：`3a22407163d12c388daefd51e23d3cd9f2b1d3fe55e3e4b3d5bcd4ba5e99d2e2`
- 本地目录：
  `apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.2-build2256/`

Developer ID 深层签名、DMG 完整性、Apple 公证、staple、Gatekeeper 和 metadata 配对
验证通过。正式 App 约 700 MiB；最终压缩 DMG 约 255.5 MiB。

## 双源

- GitHub Release：
  `https://github.com/Avdpro/ai2apps/releases/tag/v0.1.2-build2256`
- ModelScope：`ai2apps/desktop-releases`
- ModelScope immutable revision：
  `a0e2a4e75a0f996e346832cf86838d717de7fe68`

两个源的 metadata 与 DMG 均匿名完整下载并与本地 size/SHA-256 一致。GitHub Range 返回
`206`；ModelScope 返回其受支持的 `200` 状态，但响应体严格为请求的 1024 字节区间。
清单按 ModelScope、GitHub 顺序保存，不含 token、Cookie、`auth_key` 或临时 URL。

## Cloud 生产发布

- 发布前：Build 2254，100%，digest
  `e743e9a5e018e5535d4ebaae6717d3492ab01c0bd865943109035e21b34d40c9`，audit 19。
- 0% 原子登记：`2026-10-01T07:12:17.844Z`
  - digest：`b3a156b4b3d1831d43866e1a833aa5a0b8931abd942c407199889ab9e3f007e9`
  - ETag：`"sha256-b3a156b4b3d1831d43866e1a833aa5a0b8931abd942c407199889ab9e3f007e9"`
  - audit：20
- 100% rollout：`2026-10-01T07:13:20.451Z`
  - digest：`23e9030ceed409f4cdb9bba908182f2adbaa1a63f5137b3c83113fedec0cb8f8`
  - ETag：`"sha256-23e9030ceed409f4cdb9bba908182f2adbaa1a63f5137b3c83113fedec0cb8f8"`
  - audit：21
- operator：`codex-release-automation`
- approver：`workspace-owner-explicit-approval`

单 owner 自动化审批如实记录本次用户直接批准，没有伪造两名独立人员。只读 preflight、
正式 publish 与 rollout 三次双源完整预检通过；两阶段 GET/HEAD/ETag 304、history、六个
既有 API、健康和近期错误日志验证通过。最终健康时间 `2026-10-01T07:13:53Z`：
`healthy`、restarts `0`、15 分钟 error/fatal `0`。旧 Build 2254 的回滚 history 摘要有效，
原 19 条 audit 字节前缀未变化。

Cloud 侧完整回执：
`/Users/avdpropang/sdk/ai2apps-cloud/docs/desktop-build-2256-production-publication-2026-10-01.md`。
服务器证据：`/srv/ai2apps-cloud/desktop-release-2256-20261001`。

## 验证结果

- 完整 Python：10317 passed、68 skipped、74 deselected。
- 定向 Python：165 passed；Video Studio + FlashHead：22 passed；ACPF 本地化：3 passed。
- Node：18/18 文件通过，其中专项 5 项通过。
- Swift：77 项 Swift Testing + 2 项 XCTest 通过。
- JavaScript syntax、限定 Ruff、`git diff --check` 通过。
- Dev、App-Dev、Test 固定实例已重建；正式 App 与 DMG 已签名和公证。

GitHub `main` CI 的三个 Python 版本均因 runner 未安装 `av` 而在收集阶段失败；本地完整
环境回归通过。Desktop tag 还触发了 PyPI 工作流，但 `v0.1.2-build2256` 与 Python 包版本
`0.1.2` 不相等，因此在版本门禁处按设计中止。两项均不改变已签名 Desktop 工件，但应
单独修正 CI 依赖与工作流 tag 过滤条件。

## 尚未声称完成

- 四网络独立探针未配齐。
- 本次 Cloud 发布没有执行真实 Mac 安装。
- 仍需在装有更低 Build 的目标 Mac 上验收：发现更新、断点下载、安装、2256 首次启动，
  以及成功启动后清理 `AI2Apps.previous.app`。生产访问日志不能替代这项端到端验收。
