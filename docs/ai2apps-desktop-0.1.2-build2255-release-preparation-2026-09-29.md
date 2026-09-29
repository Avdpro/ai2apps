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
- 完整 Python：10287 passed、68 skipped、74 deselected，767.32 秒；JUnit 为
  `/private/tmp/ai2apps-2255-full.xml`。首次受限运行在收集阶段因 Metal 设备不可用中止，
  随后在正常 macOS 宿主环境完整通过，不属于产品测试失败。
- Swift：77 项 Swift Testing 与 2 项 XCTest 通过；Node：16/16 个测试文件通过。
- 固定 Dev、App-Dev、Test 已通过各自规定脚本重建；旧 App 均归档且实例数据保留。
  三者固定 Bundle/instance/Development/Runtime 合同和深层签名检查通过。App-Dev 已启动，
  实例 `app-dev` 的 Local 在 127.0.0.1:51397 返回 healthy；Computer Use 读取窗口标题超时，
  因此没有把标题视觉检查宣称为通过。
- 用户已在固定 Dev 实例中用系统文件选择器打开真实 `.ai2video` 工程，项目名、1080p
  画布、5 条轨道和 149.27 秒时间线均恢复正确。

## 正式发布门禁

1. clean main 正式构建、签名、公证、staple、Gatekeeper 和 2254→2255 资格检查通过。
2. GitHub/ModelScope 不可变双源完成匿名完整摘要与 Range 字节验证。
3. Cloud 先 0% 原子登记并验收，再以同一 rollout ID 扩至 10000 basis points。
4. 至少一台目标 Mac 完成自动发现、下载、安装、启动及旧备份清理后，才能将发布标记为
   完整成功。
