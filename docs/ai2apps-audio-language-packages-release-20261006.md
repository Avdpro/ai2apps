# 音频提示词语言策略 Package 发布回执

2026-10-06：两个 Package 已发布，Repository metadata **263**；匿名完整下载、Repository/Publisher 签名及 size/SHA-256 验证通过。Dev Discover 已确认两项服务器版本。

| Package | 版本 | bytes | SHA-256 | submission |
| --- | --- | --- | --- | --- |
| `ai2apps/model-stable-audio-mlx` | 0.1.1 | 199781 | `851860542afed55237213c18c3f245685c4305f31c45fa208430017a7b101983` | `b16a0038-f1b3-4ef0-84c6-c9268ba6b59d` |
| `ai2apps/audio-generation-suite` | 0.2.1 | 22552 | `63e62bf03e7eb29a1fd1380fad022ec6b4d0c62b3195da3e2f7b94224358b409` | `b6569221-2c7a-4b47-a1fa-b1477e45336e` |

## 变化

Stable Audio 0.1.1 在音乐和音效声明中新增 `metadata.audio_generation.preferred_prompt_language: en`。全部 `src/` 推理载荷与 0.1.0 完全一致，权重及许可未变化。

音频套件 0.2.1 根据 Host 返回的 `preferredPromptLanguage` 显示自动翻译提示，保留原始输入，成功后显示实际生成描述。音乐、音效、歌曲仍同包，输出归 Host 共享 Preview & Output。App 使用标准 `--omit-mini-app-catalog` 兼容构建；签名 app.yaml 三入口声明完整保留。

Runtime 无新发布；隔离验收使用已发布 1.8.10，原依赖范围不变。ACE-Step 与 YuE2 无 Package 变化。

## 多源与验收

小型代码 Package 使用 Cloud 源。权重沿用已发布 HF/ModelScope distributions，匿名 Index 115 回读与 envelope 完全一致：

- `dist_ai2apps_stable_audio3_small_music_mlx_v1`：`sha256:8a4b8f6e336f00e5d49156913e3eb795eee9dd899046f37ed3e16038939796af`。
- `dist_ai2apps_stable_audio3_small_sfx_mlx_v1`：`sha256:f5e4095cd7176aea33960639228e29758e9cd20e2eb683d186a7676d8eacc00f`。

既有完整双源校验见 `artifacts/music-packages-0.1.0/`，本次未重发 distribution 或更换文件。

103 项 Python 回归通过；18 项歌曲交互、16 项安装菜单、Host 取消消息链和 Quick Read 输出作用域检查通过。隔离实例安装签名 Runtime/模型后，音乐与音效分别生成 2 秒 stereo WAV，取消均返回 499，重启 running、卸载通过。音频套件真实安装 0.2.0 后升级 0.2.1，三个入口挂载及卸载通过。QA 许可 fixture 仅限隔离验收，不改用户许可状态。

## 交付边界

条件翻译由 Host 执行，不在模型或 Mini-App Package 中。Host 源码已实现语言策略和简单 Task 参数兼容修正；本次没有重启 Dev、重建或发布 Desktop，也未证明运行中的 Host 已加载最新 Python。需要对应客户端代码交付后才能获得完整策略。

Dev Discover 当前显示 Stable Audio 本地 0.1.0、服务器 0.1.1，套件服务器 0.2.1；本次是发布，没有替用户在 Dev 中安装新版或接受许可。此前 Cloud Task `AI_PROVIDER_ERROR` 未经生产端到端复测，不能以 Package 发布成功宣称 502 已修复。

源码 HEAD `fa377dcb62875d5c82fc8177afd4277cd2357db9`，工作树有未提交改动，以制品摘要为准。原 Publisher `229d6350-cd0e-408a-9905-41367385ae5c`、key `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`，派生公钥指纹与 Cloud 匹配。标准构建/发布脚本执行；本次 Dev Cookie 授权使用结束，无 Cookie/token/私钥输出或落盘。

证据：`artifacts/audio-language-release-20261006/` 的构建、发布、匿名下载、签名验收及测试收据。机器回执：`docs/ai2apps-audio-language-packages-release-20261006.json`。
