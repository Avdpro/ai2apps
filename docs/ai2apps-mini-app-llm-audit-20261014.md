# Mini-App LLM 调用扫描（2026-10-14）

扫描范围：packages 全部 app.yaml 与 web JS、ai2apps/studio、api、browser、agent_builder 的模型选择及 completion 调用。以下区分本轮已迁移与建议升级，未声称已迁移所有工作流。

| Mini-App / 工作流 | 发现 | 建议复杂度 | 状态 |
|---|---|---|---|
| 歌曲创作 | 风格翻译曾在 Host 内 | simple | 已迁入 Package prompt.js；默认勾选，可取消 |
| 音乐生成、音效生成 | 同一 Host 音频翻译路径 | simple | 已迁入同一 Package helper |
| 视频字幕与翻译 | 原 subtitle.refine 与翻译提示词在 Host | standard | 已迁移：润色批次/提示词及翻译提示词由 Media Voice Suite 持有；润色走 llm.complete，翻译经同一 mount-bound llm.text 路由；Host 保留时间轴与译文数量校验。旧 subtitle.refine 接口已删除，待开发实例端到端验收。 |
| 视频音轨翻译 | 原翻译、时长约束缩写提示词在 Host | standard，短句压缩 simple | 已迁移：Package 持有翻译与缩写策略，Host 经统一 llm.text 路由执行并保留媒体流水线、对齐和重试；待开发实例端到端验收。 |
| 有声书制作 | readaloud.py 源文本分析直接 resolve work_standard | standard | 已迁移：audiobook_source.js + 内置 Mini-App 通用 LLM 入口；旧 source/analyze 删除，保留确认写入校验 |
| Search All | app.yaml 已声明排序/摘要翻译 Agent 步骤 | standard | 已是 Package 提示词；Agent executor 应与通用接口共享系统隐私优先规则，不重复前端 LLM 调用 |
| Shopping Pro / Gift Recommendations | background_planner 与 agent_builder 已按等级/profile 选模型 | standard/complex | 保留声明式 Agent 流程，补接未来系统隐私开关的同一约束 |
| 其他 ASR、分离、换声、快速朗读、角色管理 | 核心是专用模型推理而非通用 LLM | 不适用 | 不应替换为 llm.complete |

相邻但不是普通 Package Mini-App：Todo、Agent Builder、Agent Mini 使用自己的任务路由；后续系统隐私开关上线应一并审计。此轮不更改这些独立流程。

平台接口是一次性主 App 能力升级；安装新套件仍需要含该通用接口的平台版本。之后改变套件翻译提示词、开关和校验不再要求更新 Host。
