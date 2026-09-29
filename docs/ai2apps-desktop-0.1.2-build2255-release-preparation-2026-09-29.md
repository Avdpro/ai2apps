# AI2Apps Desktop 0.1.2 Build 2255 发布准备

## 基线与目标

- 生产基线：0.1.1 / Build 2254，rollout `build2254-test`，10000 basis points。
- 候选版本：0.1.2 / Build 2255，rollout `build2255-test`。
- 固定合同：`com.ai2apps.desktop` / `default` / arm64 / cloud Runtime /
  `SANDBOX_MODE=0`。
- 正式候选必须来自 clean、已推送 main；个人文件
  `ai2apps-test-system/assets/voice-1.wav` 明确排除。

## 相对 Build 2254 的产品变化

- `NXR-VIDEO-COMPOSER-PROJECT-SAVE-NEW-20260929`：Video Composer 打开工程时，若
  AceFox 文件对象没有可用的 `mozAI2AppsFullPath`，改为将不超过 4 MiB 的 `.ai2video`
  或 JSON 文件流上传至同源 Local 解析。文件流不会伪造可持久化原路径，后续保存进入
  原生“另存为”，避免误写其它位置。
- 产品版本由 0.1.1 提升为 0.1.2；Build 由生产 2254 严格递增为 2255。
- 不更新独立 Runtime、模型 Package、checkpoint、Cloud API 或数据库结构。

## 已完成验证

- Video Composer 定向回归：14 passed。
- `video_studio.js` JavaScript 语法检查通过。
- 相关 Python Ruff 与 `git diff --check` 通过。
- 用户已在固定 Dev 实例中用系统文件选择器打开真实 `.ai2video` 工程，项目名、1080p
  画布、5 条轨道和 149.27 秒时间线均恢复正确。

## 正式发布门禁

1. 完整 Python、Swift 和 Node 回归通过。
2. Dev、App-Dev、Test 固定实例通过各自规定脚本重建及身份/签名验证。
3. clean main 正式构建、签名、公证、staple、Gatekeeper 和 2254→2255 资格检查通过。
4. GitHub/ModelScope 不可变双源完成匿名完整摘要与 Range 字节验证。
5. Cloud 先 0% 原子登记并验收，再以同一 rollout ID 扩至 10000 basis points。
6. 至少一台目标 Mac 完成自动发现、下载、安装、启动及旧备份清理后，才能将发布标记为
   完整成功。
