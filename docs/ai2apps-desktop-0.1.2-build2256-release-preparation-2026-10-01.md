# AI2Apps Desktop 0.1.2 Build 2256 发布准备

日期：2026-10-01

状态：候选测试中

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
- 正式 main 提交：待 clean main 合并后填写

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

## 待完成门禁

- 最终候选提交上的完整 Python 回归
- Dev、App-Dev、Test 固定实例重建与身份/深层签名验证
- clean main 合并、推送与正式 Release 构建
- Developer ID 签名、DMG、公证、staple、Gatekeeper
- GitHub/ModelScope 同字节不可变双源及完整/Range 验证
- Cloud 0% 原子登记、100% rollout 与生产 GET/HEAD/ETag 验收
- 目标 Mac 从低 Build 升级、启动和旧备份清理验收
