# AI2Apps 0.1.1 / Build 2253 发布交接

交接日期：2026-09-26，续记日期同日。本文件不包含任何凭据。

## 1. 接手结论

**不要重新构建、重新创建 GitHub Release 或重复上传 ModelScope。** 正式 App、DMG 已签名、公证并验证；GitHub 与 ModelScope 双源均已发布并完成匿名完整摘要及 Range 验证。双源 Cloud 交接清单已生成，但尚未执行 Cloud 发布或完成目标 Mac 实际升级，不能宣称端到端发布完成。

用户已批准发布当前全部产品改动，版本为 **0.1.1 / Build 2253**。用户已确认修改密码、Imagine 新功能、原生托盘/启动页双语、中文登录流程现场验收通过；无需重复这些人工验收。

## 2. 仓库、来源和工作树

- 产品根目录：`/Users/avdpropang/sdk/omlx-moe-cache`。
- 当前任务目录：`/Users/avdpropang/sdk/omlx-moe-cache/ai2apps-test-system`。
- 产品准备提交：`de405d23`，`feat: prepare AI2Apps 0.1.1 desktop release`。
- 正式构建来源、main 合并提交：`ecb64006311317d65f7794148d9a209a6989a82a`，已推送 GitHub。
- 原工作树分支：`experiment/moe-cache`；正式 clean 构建工作树：`/private/tmp/ai2apps-sync-main-20260926`，分支 `codex/sync-main-20260926`。
- 发布 tag：`v0.1.1-build2253`。不得移动 tag 或覆盖已发布资产。
- 当前未提交内容：父仓库 `docs/ai2apps-desktop-next-release.md` 的发布进度修改、父仓库新文件 `docs/ai2apps-desktop-build-2253-release-receipt-2026-09-26.md`、本交接文档。
- `ai2apps-test-system/assets/voice-1.wav` 为个人参考音频，用户明确要求不上传、不提交；保留原文件。
- 父仓库发布回执及台账已续记双源完成状态；后续只以生产清单和真实升级证据推进最终状态。

接手必须完整阅读父仓库 `docs/ai2apps-desktop-release-runbook.md`、滚动台账 `docs/ai2apps-desktop-next-release.md` 和相关 AGENTS.md。此次是 Desktop 发布，不是 Package 发布。

## 3. 正式制品（已完成，勿重建）

目录：

`/Users/avdpropang/sdk/omlx-moe-cache/apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.1-build2253`

| 文件 | 大小 | SHA-256 |
| --- | ---: | --- |
| `AI2Apps-0.1.1-build2253-macos-arm64.dmg` | 267655808 bytes | `9fd7798dc22dbb27224d26caf6de6b8168937f584b19b29fcc14ab9e7d862fad` |
| `AI2Apps-0.1.1-build2253-macos-arm64.release.json` | 1011 bytes | `f3a2f44dd02a8fac42c9094d3010d8b1fb5561e30134c2c2474c0c1eb8f7d11a` |

- 同目录 `AI2Apps.app` 为正式 App；`*-internal.*` 是公证前内部制品，**不得上传代替正式文件**。
- 固定合同：`com.ai2apps.desktop`、instance `default`、`arm64`、Runtime `cloud`、`SANDBOX_MODE=0`、最低 macOS 13。
- Developer ID：`Avdpro Pang (84XL5V265N)`。
- App CDHash：`5edadd423ef2fcaa718a610d2e7893dbe6688975`。
- Runtime manifest SHA-256：`6cc94aae34978dc16351a529f5ae6f6fa491e0701280e673aa74947f8d6d6700`。
- Apple Submission ID：`e25001c2-7c2b-472c-ac6a-89cfac36941f`，Accepted。Staple、Gatekeeper、verify-notarized-release 均通过；metadata 为 `stapled`。
- 2252 → 2253 的只读候选升级资格检查为 eligible；**没有实际升级用户 App**。
- 正式构建使用标准脚本和 clean、已推送源码。外部浏览器来自 `/Users/avdpropang/sdk/moz/acefox-firefox-153`，HEAD `06e98acfcb1e853da0783ab3c5591e2f7dc91e62` 加既有 AI2Apps 补丁，经正式 `mach build faster` / `mach package`。未启用 Development overlay，未向 Mozilla upstream 推送。不能声称产品 tag 单独包含完整浏览器源码历史。

## 4. 已完成测试和证据

- 全量 Python：10231 passed、67 skipped、74 deselected，727.61 秒；默认排除 slow/integration。
- Swift：77 Swift Testing + 2 XCTest 通过。
- Node：16 个测试文件通过。
- 版本/更新/Schema 门禁：36 passed。
- 与 2252 最终 App 的内嵌 app/ 比较：43 新增、67 字节变化、7 删除；文本源码符合已提交源码；两份 FRP 重签名字节变化但 CDHash 相同；删除项均为旧 `.DS_Store`。
- 第三方源码/Markdown 提交时存在硬换行及 EOF 空行提示，未修改许可证字节消除提示；不要把该检查描述为完全无提示。

主要证据在正式制品目录 `evidence/`，另有：

- `/private/tmp/ai2apps-2253-full-final.log`、`.xml`
- `/private/tmp/ai2apps-2253-swift.log`
- `/private/tmp/ai2apps-2253-node-final.log`
- `/private/tmp/ai2apps-2253-version-gates.log`
- `/private/tmp/ai2apps-2253-release-build.log`
- `/private/tmp/ai2apps-2253-dmg.log`
- `/private/tmp/ai2apps-2253-notary.log`
- `/private/tmp/ai2apps-2253-update-eligibility.log`
- `/private/tmp/ai2apps-2253-package-comparison.json`
- `/private/tmp/ai2apps-2253-release-notes.md`
- `/private/tmp/ai2apps-2253-github-verification.log`
- `/private/tmp/ai2apps-2253-verify-github.py`（匿名只读校验脚本）

## 5. GitHub 已完成

Release：<https://github.com/Avdpro/ai2apps/releases/tag/v0.1.1-build2253>

正式发布（非 draft，非 prerelease），两个资产 uploaded。匿名完整读取 DMG、metadata 的大小和 SHA-256 均与上表相同。DMG 首部、中间、尾部各 1024 bytes Range 请求均为 206，Content-Range 正确。

无需重复上传；如诊断需要，只读检查即可。

## 6. ModelScope 已完成

- SDK：产品根目录 `.venv/bin/python`、`modelscope_hub` 0.2.0、官方 `HubApi` 缓存认证。
- 上传身份：`ai2apps`；目标公开仓库：`ai2apps/desktop-releases`；repo type：`model`。
- metadata commit：`23fce5904ce96664e3dbc2b4dec33823abeb1642`。
- 最终 immutable revision：`b18618ac138fef2c5e0ef30d9f9d2e614d2c2626`，同时包含 metadata 与 DMG。
- 固定 revision 查询及匿名完整下载确认两文件大小和 SHA-256 与本地一致。
- DMG 首部、中部、尾部各 1024 bytes 均返回 `200 + Content-Range`，范围和字节与本地一致，符合客户端及 Cloud 已支持的 ModelScope 严格兼容合同。
- 未读取、打印或记录 token、Cookie 或重定向临时签名参数。

固定基址：

`https://modelscope.cn/models/ai2apps/desktop-releases/resolve/b18618ac138fef2c5e0ef30d9f9d2e614d2c2626`

## 7. Cloud 清单与待交接事项

已在正式制品目录生成：

| 清单 | 灰度 | SHA-256 |
| --- | ---: | --- |
| `stable-zero.json` | 0 basis points | `8b2311f60b63549e50a2b680ea7bc47e3082ed9ad7ad115d5951503a5a5852d1` |
| `stable.json` | 10000 basis points | `c89a9cdcae55d6f03241ceb36118974cac973ae3e9dee844fb654d2cd37585f8` |

两份清单的 rollout ID 均为 `build2253-test`，Runtime profile 为 `cloud`，ModelScope 固定 revision 第一源，GitHub 固定 tag 第二源。Cloud 已部署严格限定的 ModelScope Range 兼容修复，生产镜像 `ai2apps-cloud:desktop-preflight-ms-20260926` 已使用正式 CLI 对原始 `stable-zero.json` 完成双源完整预检；完整回执为 `/Users/avdpropang/sdk/ai2apps-cloud/docs/desktop-preflight-modelscope-production-2026-09-26.md`。生产 stable 与 publication audit 在修复部署前后摘要未变化。

工作区所有者随后在 Cloud 任务直接批准沿用既有自动化＋owner 先例，审计如实记录 operator=`codex-release-automation`、approver=`workspace-owner-explicit-approval`，并注明不是两个独立人类身份。Cloud 已完成 0% 原子登记及同一 rollout 扩至 10000 basis points；最终生产清单 SHA-256 `9c6438fe1802d3d4581cb7441f14fd259033a7e6c57256cb7636de14c8970cff`，ETag `"sha256-9c6438fe1802d3d4581cb7441f14fd259033a7e6c57256cb7636de14c8970cff"`，审计新增 publish/rollout 两条。完整回执：`/Users/avdpropang/sdk/ai2apps-cloud/docs/desktop-build-2253-production-publication-2026-09-26.md`。

最后只读确认生产仍为 0.1.0 / Build 2252、10000 basis points。Cloud 发布完成后，至少一台目标 Mac 必须完成 2252 → 2253 实际升级并留存旧/新 Build、启动和更新日志。

## 8. 历史故障记录（已解除）

目标固定为 `ai2apps/desktop-releases`，repo_type `model`，上传分支 `master`。使用产品根目录 `.venv/bin/python`（Python 3.13），官方 `modelscope_hub` 版本 **0.2.0**，`HubApi.upload_file`，endpoint `https://modelscope.cn`。缓存目录 `/Users/avdpropang/.modelscope/credentials`。

1. 首次上传 metadata 返回 HTTP 400 `User not logged in`，DMG 未上传。
2. 安全检查确认 SDK 缓存文件存在可读，但其中 session 于 **2026-09-26 09:58:49 UTC / 北京时间 17:58:49** 过期。此时 SDK 不加载凭据。**过期的是缓存 session，不能据此声称用户长期 Token 过期。**
3. 用户在本机通过 getpass 安全登录命令重新登录，明确反馈“登录成功”。随后 `HubApi().whoami()` 成功，用户名 `avdpro`。
4. 新登录后 metadata 上传变为 HTTP **404 / NotExistError**：

   `The project you were looking for could not be found or you don't have permission to view it: models/ai2apps/desktop-releases`

   接口 `POST https://modelscope.cn/api/v1/repos/models/ai2apps/desktop-releases/commit/master`，该次 request_id `6c873dda-3b35-47f6-af7d-accfcbe182ff`。
5. `get_repo('ai2apps/desktop-releases','model')` 成功，返回正确 owner/name；`list_repo_revisions` 显示 master 存在。legacy repo info 的 `IsAccessible=1`。这些只证明可读，不等于证明上传成功。
6. 用相同缓存身份调用标准 SDK `login` 刷新会话后 whoami 仍为 avdpro，metadata 提交仍 404。未切换账号、未创建其他 repo、未使用浏览器 Cookie 或 git-lfs。
7. 用户随后将本地 SDK 登录切换为仓库 owner `ai2apps`。`HubApi().whoami()` 与 repo owner 均确认后，标准 SDK 上传成功；此前的 404 因而作为错误身份下的历史现象保留，不再构成发布阻塞。

此前每次失败重试前均查询过文件列表，未发现 2253 metadata/DMG；切换到正确 SDK 身份后仍先只读确认空缺，再按 metadata、DMG 顺序上传并完成固定 revision 校验。

### 已检查的源码和线索

- 本地 `.venv/lib/python3.13/site-packages/modelscope_hub/config.py`：凭据优先级显式 token → MODELSCOPE_API_TOKEN → SDK 缓存；当时环境无 token 覆盖。load_token 提取缓存 m_session_id，过期返回 None。
- `_legacy_api.py`：legacy 请求将配置 token 放到 Bearer 与 m_session_id；create_commit 路径为 `repos/models/{repo_id}/commit/{revision}`。
- 官方当前 modelscope_hub 源码及旧 modelscope v1.34.0 的 create_commit 路径一致，尚无“URL 拼错”证据。
- `scripts/upload_ssd_checkpoint.py` 也直接用 `HubApi().upload_folder`。`scripts/remote_modelscope_create_then_upload.py` 使用显式 token；不能据此读取其任意 token 文件或切换身份。
- whoami 使用 OpenAPI，上传使用 legacy API；历史上 `avdpro` 的 whoami 成功并不代表具备 `ai2apps` 仓库写权限。最终以正确 owner 身份的实际标准 SDK commit 成功和匿名回读作为结论证据。
- 官方源码参考：<https://github.com/modelscope/modelscope_hub>、<https://github.com/modelscope/modelscope/blob/v1.34.0/modelscope/hub/api.py>。

禁止打印/导出 Token、SDK Cookie 值、浏览器 Cookie、签名下载 URL。没有浏览器 Cookie 访问授权。只能依照发布手册使用官方 SDK 的缓存认证；不要另写发布接口绕过。

## 9. 后续操作顺序

1. 至少一台符合条件的目标 Mac 完成真实升级，记录旧/新 Build、启动和更新日志。只读 eligible 与 Cloud 发布均不是端到端升级证据。
2. 更新父仓库发布回执与滚动台账，提交/同步文档。仅在真实升级完成后归档 included 项并推进生产基线。

本任务最后只读确认生产为 0.1.1 / Build 2253、`build2253-test`、10000 basis points。

## 10. 资源清理与未完成事项

- 本任务为对比而只读挂载了旧 2252 DMG，挂载点 `/Volumes/AI2Apps`，当时设备 `/dev/disk16s1`。尚未卸载；接手用 hdiutil info 核实仍对应旧 DMG 后再 detach，勿按过期设备号误卸载其他卷。
- 不存在需要继续等待的上传进程；ModelScope 两个上传调用均已正常退出并留下固定 revision。
- 不要强制退出或替换用户 default/dev/app-dev 实例，不操作它们的数据。
- 本交接文档是当前状态依据；历史测试 UI 对话、早期登录提示和旧回执进度不能代替最新证据。
