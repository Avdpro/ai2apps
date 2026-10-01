# AI2Apps Desktop 0.1.2 Build 2256 发布准备

日期：2026-10-01

状态：已发布，目标 Mac 实机升级验收待完成

## 发布身份

- 产品版本：`0.1.2`
- Build：`2256`
- Bundle ID：`com.ai2apps.desktop`
- Instance：`default`
- 架构：`arm64`
- Runtime profile：`cloud`
- Sandbox：`0`
- 更新通道：`stable`
- Rollout ID：`build2256-test`
- 生产基线：`0.1.1 / Build 2254`
- Build 2255：双源资产存在但未进入 Cloud stable，由 2256 取代

## 纳入范围

- `NXR-AVATAR-SLOTS-20261001`
- `NXR-AVATAR-MINIAPP-20261001` 的 Desktop Host、ACPF、任务与共享输出合同
- `NXR-FLASHHEAD-PACKAGE-20261001` 的已发布源码与客户端协商记录
- `NXR-VIDEO-COMPOSER-SPECIAL-LAYERS-20260929` 及其 2026-10-01 增量
- 视频字幕提取、人工校对、字幕文件生成及视频烧录流程
- multipart list/dict/bool 字段的受控 JSON 编码
- 新增 ACPF Profile 的中英文文案

## 延期与排除

- AVTR-1、MuseTalk、InfiniteTalk、Ex-Omni 移植源码与 parity 测试：仍在实验阶段
- `scripts/prepare_avatar_weights.py`：仅供上述实验移植使用
- `docs/ai2apps-avatar-model-port-status.md`：随实验工作保留，未纳入候选
- `ai2apps-test-system/assets/voice-1.wav`：个人测试素材
- Avatar Studio Suite 的 Registry App Package 发布：在 Desktop Host 2256 可用后独立完成

## 源码提交

- 功能候选：`b97bc0f8`（avatar workflows and video studio fixes）
- 本地化修复：`fff39864`（avatar provisioning profile localization）
- 正式 main 提交：`23ba608fe86a692c418fc815a24e2c0c1e76645a`
- Homebrew formula 自动更新：`c5c5e3e8`

## 已完成门禁

- 定向 Python：165 passed
- Video Studio + FlashHead：22 passed
- ACPF 本地化修复：3 passed
- Node 专项：5 passed
- Node 全部文件：18/18 passed
- Swift：77 项 Swift Testing + 2 项 XCTest passed
- JavaScript syntax：passed
- 限定 Ruff：passed
- `git diff --check`：passed
- 完整 Python 首轮：10316 passed、68 skipped、74 deselected、1 failed；唯一失败为新增
  Avatar ACPF Profile 缺少 9 组中英文映射，已修复并由本地化专项 3/3 复验。该轮不作为
  发布通过证据；JUnit：`/private/tmp/ai2apps-2256-full.xml`
- 修复后的完整 Python 最终门禁：10317 passed、68 skipped、74 deselected；JUnit：
  `/private/tmp/ai2apps-2256-full-final2.xml`
- Dev、App-Dev、Test 固定实例均已重建并通过身份与深层签名验证。
- 正式 App 为 `0.1.2 / 2256`、`com.ai2apps.desktop`、`default`、`arm64`、`cloud`；
  Developer ID 深层签名通过，App 约 700 MiB。
- Apple 公证 Accepted，Submission ID `9dc11d31-20bd-4f3a-804a-df983e146815`；staple、
  Gatekeeper、DMG 与 metadata 最终验证通过。
- GitHub 与 ModelScope 匿名完整下载 size/SHA-256 相同；GitHub Range 为 `206`，ModelScope
  为已支持的 `200 + 精确区间字节` 兼容行为。
- Cloud 已先以 0% 原子登记，再使用同一 `build2256-test` rollout 扩到 100%；生产
  GET/HEAD/ETag 304、双源预检、健康、既有 API 和审计链验证通过。

## 发布后待完成验收

- 目标 Mac 从低 Build 升级、启动和旧备份清理验收

完整发布回执：`docs/ai2apps-desktop-0.1.2-build2256-release-2026-10-01.md`。
