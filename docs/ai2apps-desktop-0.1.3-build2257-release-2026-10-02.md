# AI2Apps Desktop 0.1.3 Build 2257 发布回执

日期：2026-10-02

状态：已发布至生产 100%；目标 Mac 实机升级验收待完成。

## 发布身份

- 版本 / Build：`0.1.3 / 2257`
- Bundle / Instance：`com.ai2apps.desktop / default`
- 架构 / Runtime：`arm64 / cloud`
- Sandbox：`0`
- 源码提交：`f7dacc9c06550ac2bbba85d849ffe819aa88f243`
- GitHub tag：`v0.1.3-build2257`
- Rollout ID：`build2257-test`
- Apple Submission ID：`6efb70b8-d9fa-4562-bdca-6803941e1621`（Accepted）

## 本版内容

- Discover 为存在较新目录版本的已安装 Package 提供升级入口，并确保模型升级继续走
  Package 安装操作。
- Imagine Studio 新增内置 2× 图片放大；Video Studio 新增内置 2× 视频放大、长片分段、
  重叠融合、取消/重试与音轨保留。
- Host 纳入 Runtime 1.8.8 的图片/视频放大、视频分割能力与按真实输入尺寸计算的资源估计。
- Video Composer 纳入 SAM 2.1 / Apple Vision 动态人物蒙版和签名的
  `ai2apps-person-mask` 原生辅助程序。
- Release 组装排除仓库 `.build`、pytest/ruff cache，并使用 `PYTHONSAFEPATH=1`
  验证内嵌 Python。
- Encore、AVTR-1、MuseTalk、InfiniteTalk、Ex-Omni 研究代码及个人测试音频未纳入。

## 工件与 Apple 验收

- DMG：`AI2Apps-0.1.3-build2257-macos-arm64.dmg`
  - size：`267983236`
  - SHA-256：`96f907c60c42912fa5131e9877e293b8d4d67d8b1736f66ab0e3ebd0b6efebc9`
- metadata：`AI2Apps-0.1.3-build2257-macos-arm64.release.json`
  - size：`1011`
  - SHA-256：`aa4a47c85515ad597fc1d00dfee73742517d9d1ce7658b4e0f31fb03bc996c8f`
- 本地目录：
  `apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.3-build2257/`
- App Developer ID 深层签名验证、DMG 完整性、Apple 公证、staple、Gatekeeper 与
  metadata 配对验证通过。CDHash：`fb3228d77125d08e0f924d01be6e148734bc576b`，
  Team ID：`84XL5V265N`。

## 双源

- GitHub Release：
  `https://github.com/Avdpro/ai2apps/releases/tag/v0.1.3-build2257`
- ModelScope：`ai2apps/desktop-releases`
- ModelScope immutable revision：
  `26d04b3dd2b107446a2a05603b3cffe49cc02b49`

两个源的 DMG 与 metadata 均按最终 size/SHA-256 验证一致。生产清单保持 ModelScope、
GitHub 顺序，只含不可变、无凭据 URL；未写入 Cookie、token 或临时重定向地址。

## Cloud 生产发布

- 发布前：0.1.2 / Build 2256 / 100%，digest
  `23e9030ceed409f4cdb9bba908182f2adbaa1a63f5137b3c83113fedec0cb8f8`，audit 21。
- 0% 原子登记：`2026-10-02T04:07:51.133Z`
  - digest：`3fd0e1e2d5cfdaf5a8f49f247eac285385708e6523be707970a99ad9845705d1`
  - ETag：`"sha256-3fd0e1e2d5cfdaf5a8f49f247eac285385708e6523be707970a99ad9845705d1"`
  - audit：22
- 100% rollout：`2026-10-02T04:08:21.241Z`
  - digest：`13b983e758483c30ebfd0e422ff5fe289e426f06526a2b469704fb610de7861e`
  - ETag：`"sha256-13b983e758483c30ebfd0e422ff5fe289e426f06526a2b469704fb610de7861e"`
  - audit：23
- operator：`codex-release-automation`
- approver：`workspace-owner-explicit-approval`

本次用户直接授权覆盖 0% 登记、验收及扩至 100%。审计如实记录自动化执行与单一 owner
批准，不冒充两名独立认证的人类。只读预检、publish 与 rollout 的双源预检通过；两阶段
GET/HEAD/ETag 304、history 和六个既有 API 验证通过。最终容器 `healthy`、restart `0`、
最近 15 分钟 JSON error/fatal `0`。Build 2256 的 audited history 保留为频道回滚点；回滚
频道不代表向已经安装 2257 的客户端自动降级。

服务器证据目录：`/srv/ai2apps-cloud/desktop-release-2257-20261002`。本机独立生产探针确认
Build 2257、`build2257-test`、10000 basis points 及最终 digest 一致。发布过程未使用
Dev Cookie。

## 验证结果

- 完整 Python：`10437 passed, 68 skipped, 74 deselected`。
- Node：全部 16 个测试文件通过。
- Swift：77 项 Swift Testing + 2 项 XCTest 通过。
- 限定 Ruff 与 `git diff --check` 通过。
- GitHub `main` 已推送源码提交，正式 App/DMG 已签名、公证并完成双源与生产发布。

GitHub Release 触发的 Homebrew formula 工作流通过，并把 formula 更新为
`0.1.3-build2257`。另外两个工作流沿用既有失败模式：PyPI 工作流因 Desktop tag
`v0.1.3-build2257` 不等于 Python Package 版本 `0.1.3`，在版本门禁处按设计停止；CI 的
Python 3.11/3.12/3.13 runner 均未安装 `av`，在测试收集阶段报
`ModuleNotFoundError: No module named 'av'`。本地完整环境回归通过；这两项不改变已经签名并
按摘要发布的 Desktop 工件，但工作流 tag 过滤和 CI 依赖仍应单独修复。

## 尚未声称完成

- 未配齐中国电信、中国联通、中国移动及海外四网络独立探针。
- 尚未在低于 2257 的目标 Mac 上完成发现更新、断点下载、安装、首次启动，以及成功启动后
  清理 `AI2Apps.previous.app` 的端到端验收；Cloud 访问或清单探针不能替代这项验收。
