# 简单 Task 音频提示词预处理 502：Cloud 排查交接

状态：生产故障已定位到 Cloud → AI provider 边界，底层原因未确认。此仓库未修改 Cloud 代码。

## 已确认事实

- 2026-10-06 18:06:24.747 Asia/Shanghai（10:06:24.747 UTC），Dev server.log 记录 `POST https://coder.ai2apps.com/v1/ai/responses` → 502。
- 下一层 `/v1/chat/completions` 返回 `AI_PROVIDER_ERROR`，message `AI provider request failed`，retryable=false。
- 简单 Task 设置：`work_simple = cloud/openai/gpt-5.6-luna`；Cloud 模型名为 `openai/gpt-5.6-luna`。
- 用户输入“雷鸣般的掌声”，音效 10 秒。请求在文本预处理阶段失败，Stable Audio 未收到此次生成调用。右侧成功音频为先前输出，不能用作本次成功证据。
- 本地请求含 system 翻译/润色说明及 user JSON（task=audio.sound_effects_generation、description=雷鸣般的掌声），stream=false、maxOutputTokens=512、temperature=0。未传 tools。
- Local 流程为 mount 授权 → work_simple 解析 → 内部 Chat Completions → Cloud Responses → 英文 JSON prompt → Stable Audio → Host 共享输出。

## Cloud 项目需要排查

1. 按上述时间和模型检索生产 provider 请求日志/堆栈，确认实际 provider、实际模型、上游 HTTP 状态与脱敏错误原因；不要仅返回包装后的 AI_PROVIDER_ERROR。
2. 对比省略 temperature 与 temperature=0 的请求。推理模型参数兼容是待验证假设，不是已确认根因；同时排查令牌上限、供应商可用性/超时及模型路由。
3. 若为参数兼容，按模型能力构造 provider 请求，保留严格校验；若为外部故障，返回可靠的 retryable 与关联 request ID。客户端不应看到原始供应商凭证、头或敏感响应。
4. 用原始“雷鸣般的掌声”复测，要求返回非空英文 JSON prompt，含热烈掌声语义而非天气雷声；之后在客户端验证完整音效生成。

## 已完成的本地修正

- 简单 Task 文本调用省略不必要的 temperature，使用模型默认采样；没有更换用户选定模型，没有静默跳过翻译。
- 错误信息展示所选模型、HTTP 状态和经过格式白名单过滤的上游 code，不暴露任意上游 message。
- 增加真实 ASGI 路由合同回归，覆盖请求参数与 AI_PROVIDER_ERROR 的安全传递。此测试的 Cloud 响应为模拟，不代表生产已修复。
- 尚未部署此轮修正到正在运行的 Dev Local；运行中的 Python 需要重启才能加载。没有读取 Cookie 或生产 token，没有修改默认模型，没有重新发布 Package。

验收要求：Cloud 生产日志给出根因与修复/恢复证据；本地重启后原始提示词能完成翻译与音效生成，失败时不产生伪成功输出。
