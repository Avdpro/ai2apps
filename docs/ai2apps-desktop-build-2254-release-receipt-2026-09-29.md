# AI2Apps 0.1.1 Build 2254 发布记录（已发布，待目标 Mac 升级验收）

Build 2254 已完成源码门禁、正式构建、Developer ID 签名、Apple 公证、GitHub/ModelScope
双源发布和 Cloud stable 频道 100% rollout。目标 Mac 的自动发现、下载、安装、启动和旧版本
清理仍须单独验收；Cloud 发布成功不等同于客户端安装成功。

## 来源与范围

- 产品提交为 `aba3ba93`；正式 main 合并及构建来源为
  `7850b8ab6edfa701504badb2788ecf4307e85e01`，已推送至 `Avdpro/ai2apps`。
- 正式 clean 工作树为 `/private/tmp/ai2apps-sync-main-20260926`。个人参考音频
  `ai2apps-test-system/assets/voice-1.wav` 未纳入提交或制品。
- 版本为 0.1.1 / Build 2254；固定身份为 `com.ai2apps.desktop` / `default` / arm64 /
  cloud Runtime / `SANDBOX_MODE=0`。
- 本轮范围和已知边界见
  `docs/ai2apps-desktop-0.1.1-build2254-release-preparation-2026-09-29.md` 与台账
  `NXR-RELEASE-011-2254-20260929`。

## 测试与构建

- 完整 Python：10287 passed、68 skipped、74 deselected，742.17 秒；JUnit 为
  `/private/tmp/ai2apps-2254-full-final2.xml`。
- Swift：77 项 Swift Testing 与 2 项 XCTest 通过；Node：16 个测试文件通过；JavaScript
  语法、JSON 和 diff whitespace 检查通过。
- 正式 App 约 700 MiB，与 2253 基线相当，未误打包完整 MLX Runtime。
- Developer ID 深层签名、DMG 完整性、App 匹配、Gatekeeper 和 stapling 检查通过。
  App CDHash 为 `d5375322462eb324b18a86fd2d69399a47c9cd7c`。
- Apple submission `ad40bfe6-e4b6-431c-974a-4b730d086235` 状态为 Accepted。
- 2253 正式 App 到 2254 候选的更新资格检查结果为 `eligible`；该结果不是实际升级验收。

## 制品与双源

- DMG：`AI2Apps-0.1.1-build2254-macos-arm64.dmg`，267817602 bytes，SHA-256
  `2059b724a2fd1ae3fd9a23762d0df879580ad663dbfcc57b6b58a23bcb578630`。
- metadata：`AI2Apps-0.1.1-build2254-macos-arm64.release.json`，1011 bytes，SHA-256
  `1bead7dbf64aae371ade039fe0a8f9adce8113a3781834929b7d1e9cb322d97c`。
- GitHub Release `v0.1.1-build2254` 已正式发布，非 draft、非 prerelease：
  <https://github.com/Avdpro/ai2apps/releases/tag/v0.1.1-build2254>。
- ModelScope 目标为 `ai2apps/desktop-releases`；同时包含 DMG 和 metadata 的 immutable
  revision 为 `8262b99c08aad0b171842f4bac187b8a63ebf4c5`。
- 两源均完成匿名完整下载，文件大小及 SHA-256 与本地一致。DMG 首部、中部和尾部 Range
  字节均一致；GitHub 返回 206，ModelScope 返回其受 Cloud 白名单约束的 200 兼容响应。
  发布过程未读取 Dev Cookie。

## Cloud 生产发布

- rollout ID 为 `build2254-test`。Cloud 在每次写入前均完成 Schema、metadata、公证元数据、
  双源完整 size/SHA-256 与 Range 预检。
- 0% 原子登记于 2026-09-29T10:46:47.935Z 完成，规范化清单摘要为
  `b4b19ee701956fc20f93fb1e85026e1da7c857838d51b5e65f63353ff7298cef`，审计第 18 条。
- 验收后以同一 rollout ID 于 2026-09-29T10:48:05.895Z 扩至 10000 basis points，最终
  生产清单 SHA-256 为
  `e743e9a5e018e5535d4ebaae6717d3492ab01c0bd865943109035e21b34d40c9`，ETag 为
  `"sha256-e743e9a5e018e5535d4ebaae6717d3492ab01c0bd865943109035e21b34d40c9"`，审计第 19 条。
- operator=`codex-release-automation`、approver=`workspace-owner-explicit-approval`，如实记录
  单 owner 自动化审批，不声称存在两个独立人类审批身份。
- 0%/100% 的 GET、HEAD、ETag 304、history 摘要、健康状态和六项既有 API 均通过；最终
  healthy、restart count 0、最近 15 分钟 error/fatal 0。旧 2253 history 可用于服务端清单
  回滚。Cloud 完整回执：
  `/Users/avdpropang/sdk/ai2apps-cloud/docs/desktop-build-2254-production-publication-2026-09-29.md`。
- 产品任务随后从公网独立读取 `https://coder.ai2apps.com/updates/stable.json`：HTTP 200、
  Content-Length 1822，正文 SHA-256 和 ETag 均与最终生产摘要一致，内容为 Build 2254 /
  `build2254-test` / 10000 basis points。

## 尚待验收

- 至少一台目标 Mac 从旧 Build 自动发现 2254，确认实际下载源、进度、SHA 校验、安装替换、
  新 Build 首次启动以及 `AI2Apps.previous.app` 成功启动后的清理。
- 中国境内、境外、代理和断网恢复四网络矩阵尚未在本轮全部执行。

因此本记录确认“分发发布完成”，但在目标 Mac 闭环完成前不把本台账项标记为 `included`。
