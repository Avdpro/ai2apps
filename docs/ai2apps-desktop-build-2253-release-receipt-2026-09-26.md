# AI2Apps 0.1.1 Build 2253 发布记录（进行中）

双源制品发布和匿名字节验证已完成；尚未完成 Cloud 生产发布或目标 Mac 升级，不能视为完整发布回执。

## 来源与范围

- 产品提交：`de405d23`；主分支合并及正式构建来源：`ecb64006311317d65f7794148d9a209a6989a82a`，已推送至 `Avdpro/ai2apps` 的 main。
- 构建工作树：`/private/tmp/ai2apps-sync-main-20260926`，构建前后 Git 工作树为空。个人 `assets/voice-1.wav` 保留在原工作区且未提交。
- 版本唯一来源 `ai2apps/_version.py` 为 0.1.1；Build 参数 2253。固定 com.ai2apps.desktop / default / arm64 / cloud / SANDBOX_MODE=0。
- 候选范围见 `ai2apps-desktop-0.1.1-release-preparation-2026-09-26.md` 与台账 `NXR-RELEASE-011-2253-20260926`。2251/2252 历史能力不重复宣称新交付；独立 Runtime/Package 不重发，L2/ICB 研究不开启。
- 主分支源码不包含外部 AceFox 工程的完整历史：浏览器依赖使用该工程正式 mach build faster / mach package 产物，基线 HEAD 为 `06e98acfcb1e853da0783ab3c5591e2f7dc91e62` 加既有 AI2Apps 工作区补丁。不能把主分支 tag 单独描述为可重建完整浏览器。未向 Mozilla upstream 推送。
- 新纳入的文档/第三方源在 staged diff 检查中出现 Markdown 硬换行和上游 EOF 空行提示；未改变许可证或第三方字节来消除格式提示。产品构建工作树的 diff check 为空；此格式提示不代表代码回归失败。

## 测试和用户验收

- 完整 Python：10231 passed、67 skipped、74 deselected，727.61 秒；默认排除 slow/integration。
- Swift：77 Swift Testing + 2 XCTest 通过；Node：16 个测试文件通过。
- 版本调整后产品版本/更新脚本/Schema 迁移：36 passed。
- 修改密码、Imagine 新功能、原生托盘/启动页双语、中文登录流程由用户确认现场验收；Agent 未重复输入密码、付费生成或代填 UI 测试。
- 证据归档：本次 Release 目录下 `evidence/`。不将历史 Run 或每个模型未执行的主观质量验收算作本轮已通过。

## 构建与基线差异

- 制品目录：`apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.1-build2253/`。
- 标准 build-release-app.sh 和 build-release-dmg.sh 已成功；Developer ID 签名、verify-release-app、DMG 完整性及 App 匹配校验通过，App CDHash `5edadd423ef2fcaa718a610d2e7893dbe6688975`。
- 只读挂载 2252 最终 DMG，与候选内嵌 app/ 比较：43 新增、67 字节变化、7 删除。包内文本源码与已提交源码无不一致。两份 FRP 因重新签名字节变化但 CDHash 相同；删除项均为旧 `.DS_Store`。
- 其余新增/变化对应本轮 Voice、Imagine、Account、媒体 Host、下载、语言、版本及 IndexTTS adapter/vendor 范围。Schema 72–77 为增量迁移；不执行数据库降级。
- 正式 browser/omni.ja 中 shell.mjs 与 shell.xhtml 与本轮源文件完全一致，未使用 Development overlay。

## 公证与发布

- Apple submission：`e25001c2-7c2b-472c-ac6a-89cfac36941f`，Accepted；staple、Gatekeeper、verify-notarized-release 通过。
- 2252 正式 DMG 中的 App → 2253 候选资格验证为 `eligible`；未执行实际升级。
- 最终 DMG：267655808 bytes，SHA-256 `9fd7798dc22dbb27224d26caf6de6b8168937f584b19b29fcc14ab9e7d862fad`。
- 最终 metadata：1011 bytes，SHA-256 `f3a2f44dd02a8fac42c9094d3010d8b1fb5561e30134c2c2474c0c1eb8f7d11a`，notarization.status=stapled。
- GitHub Release `v0.1.1-build2253` 已正式发布（非 draft、非 prerelease）：<https://github.com/Avdpro/ai2apps/releases/tag/v0.1.1-build2253>。两个资产经匿名完整回读，大小和 SHA-256 与本地一致；DMG 首部、中部、尾部 Range 均为标准 `206` 且字节一致。
- ModelScope SDK 身份已确认为 `ai2apps`，目标仓库为公开的 `ai2apps/desktop-releases`。先上传 metadata、再上传 DMG，最终同时包含两份制品的 immutable revision 为 `b18618ac138fef2c5e0ef30d9f9d2e614d2c2626`。固定 revision 匿名完整下载的大小和 SHA-256 与本地一致；DMG 首部、中部、尾部 Range 均为受支持的 `200 + Content-Range` 且字节一致。未读取、打印或记录 token/Cookie/临时签名参数。
- 已生成 Cloud 交接清单：`stable-zero.json` 为 `0` basis points，SHA-256 `8b2311f60b63549e50a2b680ea7bc47e3082ed9ad7ad115d5951503a5a5852d1`；`stable.json` 为 `10000` basis points，SHA-256 `c89a9cdcae55d6f03241ceb36118974cac973ae3e9dee844fb654d2cd37585f8`。两者 rollout ID 均为 `build2253-test`，ModelScope 固定 revision 为第一源、GitHub 固定 tag 为第二源，只差灰度值。
- Cloud 已部署限定的 ModelScope `200 + 精确 Content-Range` 预检兼容修复，生产镜像为 `ai2apps-cloud:desktop-preflight-ms-20260926`，Image ID `sha256:d21b0f1c4cc0a38e5337e3ae0693ce25369cf97dfddf0cf94c61b11a99c3a6db`。例外仅适用于白名单仓库的 40 位固定 revision，GitHub 及其他源仍要求 206；完整 size/SHA-256、metadata 与 stapled 门禁保留。专项 13 项、镜像全量 357 passed / 0 failed / 2 skipped；旁路候选和切换后的生产 CLI 均对原始 `stable-zero.json` 完成双源完整预检。Cloud 回执：`/Users/avdpropang/sdk/ai2apps-cloud/docs/desktop-preflight-modelscope-production-2026-09-26.md`。
- 工作区所有者随后在 Cloud 任务直接批准按既有自动化＋owner 先例发布，审计记录 operator=`codex-release-automation`、approver=`workspace-owner-explicit-approval`，并明确说明这不是两个独立人类审批身份。Cloud 于 2026-09-26T12:07:29.612Z 完成 0% 原子登记，正式规范化摘要 `9b543a9fbb12d06c957307d45562b43a5c67a0159055b8e12726ee11f3c1b43a`；验收后保持 rollout `build2253-test`，于 12:12:54.790Z 扩至 10000 basis points。最终生产清单 SHA-256 `9c6438fe1802d3d4581cb7441f14fd259033a7e6c57256cb7636de14c8970cff`，ETag `"sha256-9c6438fe1802d3d4581cb7441f14fd259033a7e6c57256cb7636de14c8970cff"`。
- Cloud 审计由 15 行追加为 17 行（publish、rollout），两份 history 字节摘要验证通过；两次正式写入前均完成双源完整预检。0%/100% 的 GET、HEAD、304、服务器和本机公网摘要、健康、既有 API、restart count 0、error/fatal 0 均通过。完整回执：`/Users/avdpropang/sdk/ai2apps-cloud/docs/desktop-build-2253-production-publication-2026-09-26.md`。尚未执行四网络探针，且 Cloud 发布不能代替目标 Mac 的 2252 → 2253 实际升级与启动验收。
