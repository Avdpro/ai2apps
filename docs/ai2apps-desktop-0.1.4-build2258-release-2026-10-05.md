# AI2Apps Desktop 0.1.4 Build 2258 发布回执

日期：2026-10-05

状态：`released_pending_target_mac`。已公证、双源发布并完成 Cloud 100% 生产验收；目标 Mac 实机升级待验收。

## 发布身份

- 版本 / Build：`0.1.4 / 2258`
- Bundle / Instance：`com.ai2apps.desktop / default`
- 架构 / Runtime / Sandbox：`arm64 / cloud / 0`
- 源码：`51d30e440d942eb04d254f1e5a796a29d39f13ac`，独立 clean worktree 构建，已推送 GitHub main。
- GitHub tag：`v0.1.4-build2258`；rollout ID：`build2258-test`。
- Apple Submission：`bf996bef-3cb3-4cdb-ade3-7fc1d99c886c`（Accepted）。
- Team：`84XL5V265N`；App CDHash：`f0d0ddf61178207509ec1e5704cce81564284638`。

## 本版内容与台账归档

以下条目实现已纳入 2258；历史条目中的实机验收限制仍有效，不因发布而自动关闭：

- `NXR-TODO-MVP-20261003`：Todo 项目树、优先级/高亮、状态/进度、调度与 FIFO 队列、
  导入导出、Gallery/附件、Codex 连接和 Terminal 联动。
- `NXR-HARNESS-RELIABILITY-20261004`、`NXR-HARNESS-RESULT-REFERENCES-20261004`、
  `NXR-HARNESS-CONTROL-SEARCH-20261004`、`NXR-HARNESS-CONTEXT-CHECKPOINT-20261004`、
  `NXR-HARNESS-CHECKPOINT-COVERAGE-20261005`、`NXR-HARNESS-CONTEXT-PYTHON-PORT-20261005`、
  `NXR-HARNESS-SESSION-MEMORY-20261005`：长任务上下文、来源回读、计划/提问、循环保护、
  检查点及跨 Run 会话记忆。包含工具失败恢复、原生 App/Mini-App 开发 Harness、Coding
  sub-Agent、附件与 Gallery Picker；详细验收记录见本次提交的对应 acceptance JSON。
- `NXR-AGENT-REVIEW-PROGRESS-20261003`、`NXR-AGENT-REVIEW-TEST-POSITION-20261003`、
  `NXR-AGENT-PARAMETER-VISIBILITY-20261003`、`NXR-AGENT-PARAMETERS-20261003`：
  Agent Review、参数提取/编辑/运行与结果反馈。
- `NXR-AGENT-NAVIGATION-BOUNDARY-20261003`、`NXR-AGENT-SEARCH-CONFIRMATION-20261003`、
  `NXR-AGENT-PRESENTATION-RECOVERY-20261003`、`NXR-AGENT-MENTIONED-SITE-20261003`、
  `NXR-AGENT-NEWTAB-SCOPE-20261003`、`NXR-BIDI-NATIVE-RECOVERY-20261003`、
  `NXR-BROWSER-LAUNCH-SPINNER-20261003`：浏览器导航/输入/展示、BiDi 恢复与 Sidebar 刷新。
- `NXR-SHELL-STARTUP-NAVIGATION-20261005`、`NXR-ALL-INSTANCES-RECORDING-20261004`：
  区分普通刷新、Helper 重启、Runtime 重连；全部实例的准备录屏入口。
- `NXR-AUDIOBOOK-SELECTED-DIALOGUE-20261002`、`NXR-AUDIOBOOK-EDIT-SAVE-RACE-20261005`：
  勾选片段合并和重生成采用最新编辑文本。
- `NXR-MEDIA-VOICE-I18N-20261005`、`NXR-SUBTITLE-LLM-CORRECTION-20261003`：Studio
  Package 多语言 Host 桥接与字幕校对能力；包含 Avatar 录音/预览桥接及 Imagine Portrait 主题。

开发实例启用记录属于验收证据，不能替代本次 Release 目标 Mac 升级验收。
`NXR-H3-16X9-RESOLUTIONS-20261003`、后续视频放大工作、Encore/AVTR-1/MuseTalk/
InfiniteTalk/Ex-Omni 实验源码及个人参考音频延期，不进入本次源码提交或制品。

## 工件

- DMG：`AI2Apps-0.1.4-build2258-macos-arm64.dmg`
  - 字节数：`268084435`（约 256 MiB）
  - SHA-256：`efdfccc10f3f0c1475cdc2faf9dc0c94e947d00bdbc7a88852e01dc7c0777875`
- Metadata：`AI2Apps-0.1.4-build2258-macos-arm64.release.json`
  - 字节数：`1011`
  - SHA-256：`a616f065c35b63420636b59fb805ad2d845321450a30ffc0bc44fe101d837b6d`
- 持久本地目录：
  `/Users/avdpropang/sdk/omlx-moe-cache/apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.4-build2258/`
- 构建 worktree：`/private/tmp/ai2apps-release-2258`。
- App 深层签名、DMG 完整性、公证、staple、Gatekeeper 与 metadata 配对通过。
- 以上一版留存的 2257 App 做只读升级资格验证，结果为 `eligible`；未代替真实安装。
- 2257→2258 控制平面文件比较：新增 46、变更 63、删除 0；新增仅在 `ai2apps/`，
  未发现明确延期的实验目录。精简 Cloud Runtime 保留，未内嵌完整模型推理 Runtime。

## 双源与 Cloud

- GitHub：[v0.1.4-build2258](https://github.com/Avdpro/ai2apps/releases/tag/v0.1.4-build2258)
- ModelScope：`ai2apps/desktop-releases`
- 最终不可变 revision：`feb3dd54e5d8daf9c4ec8ede754238fd013d766f`
- 两个源返回的 DMG/metadata 字节数及摘要与本地一致；Cloud 完整下载/Range/公证元数据
  预检通过，零灰度发布再次预检通过。
- 发布前生产：Build 2257，100%，digest
  `13b983e758483c30ebfd0e422ff5fe289e426f06526a2b469704fb610de7861e`。
- operator：`codex-release-automation`；approver：`workspace-owner-explicit-approval`。
  用户直接授权发布并在网络中断后要求继续；记录自动化操作加单一 owner 批准，未虚构独立审批人。
- 0% 登记：`2026-10-05T05:52:34.452Z`，audit 24，digest
  `8291081899ee34b2aed37e3883ca8f4e6d62861c0ce844ae56be85c221f76d71`。
  GET/HEAD 200、条件请求 304、无 Set-Cookie、六个既有 API 200；容器 healthy、restart 0。
- 服务器证据目录：`/srv/ai2apps-cloud/desktop-release-2258-20261005`。
- 100% 扩灰：`2026-10-05T05:57:38.273Z`（北京时间 13:57），audit 25，digest
  `d6aa53c228641e800232e65189d137a7e97236b67ec1c1704140cc28899c731d`。
  rollout ID 保持 `build2258-test`，`percentage_basis_points=10000`。
- 最终 GET/HEAD 200、ETag 条件请求 304、Content-Length 1822、无 Set-Cookie、六个既有 API
  全部 200。容器 healthy、restart 0，最近 15 分钟 JSON error/fatal 0；2257 历史回退点保留。
  本机独立匿名探针确认同一 Build、比例和最终摘要。未使用 Dev Cookie。

Cloud 首次预检下载遇到根分区空间不足：下载前约剩 240 MiB，DMG 需要约 256 MiB。
已删除本次产生的 239 MiB 不完整临时 DMG，重新使用 `/dev/shm/ai2apps-desktop-2258-inputs`
暂存并按相同摘要校验；服务器当时内存可用约 6.3 GiB、内存盘可用 3.9 GiB。
未删除历史版本、审计、Docker 镜像或业务数据。Cloud 需要另行清理或扩容磁盘。
完成生产验收后，本次内存盘 DMG/metadata 临时副本已删除；正式文件可从本地 Release
目录及两个不可变源取得，服务器保留清单、审计、预检日志与执行脚本。

## 验证

- 完整 Python：`10450 passed, 68 skipped, 74 deselected`，分三组完成。
- 新增 Agent/Todo focused Python 与 Node 回归、原有 Node 测试文件通过。
- Swift：77 项 Swift Testing + 2 项 XCTest 通过。
- 本次修改 Python 的关键 Ruff、JavaScript/JSON 语法与 diff 检查通过。
- 修复测试期望中的 Todo/服务/迁移 78–79 合同漂移，并给 SDPA 路由门测试接入已有 provider
  reset fixture，消除早前 Scheduler 留存全局状态引发的顺序污染；最后完整受影响分片全绿。
- 对整个仓库额外扫描时，历史 `ai2apps/docs/ideogram-json-probe-2026-09-11/followup.py`
  仍有 7 项未定义名称诊断；它未在本次修改范围，不将此全库扫描描述为通过。

GitHub Homebrew formula 工作流 `37268964392` 成功。PyPI 工作流 `37268964377` 因
Desktop tag `v0.1.4-build2258` 不等于 Python Package 版本 `0.1.4` 在版本门禁停止；
CI `37268483834` 在 runner 缺少 `av` 的测试收集阶段失败。与 2257 回执记录的原因一致，
本次未修改这些工作流；本地完整环境测试通过，不能据此声称 GitHub CI 已通过。

## 待验收

- 目标 Mac 的发现更新、下载、安装、首次启动及 previous App 清理闭环。
- 新 General Agent 长任务、Todo 多执行器交互等条目保留其已记录的真实模型/UI 验收限制。
- 中国电信/联通/移动与海外四网络独立探针尚未配齐。
