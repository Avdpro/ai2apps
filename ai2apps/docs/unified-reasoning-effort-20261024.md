# 统一 reasoning_effort 调用合同

调用方在任务请求中使用可选 `reasoning_effort`；`task_payload(..., reasoning_effort='low')` 会持久保留该意图，隐私路由重新选模型和摘要修复重试均不得丢失。未传参数的旧调用保留原行为。

规范值：`none / minimal / low / medium / high / xhigh / max / ultra`。这些是调用意图，不代表每个模型都支持所有档位。不得把 `low` 静默提升成 `high`，不得将思考力度等同于输出 token 上限。

Provider 目录的 `capabilities.reasoningControl` 声明原生协议：

```json
{"format":"thinking","efforts":["low","high","max"],"can_disable":true,
 "aliases":{"minimal":"low","medium":"high","xhigh":"high","ultra":"max"}}
```

共享适配器不识别 Provider、App、Tool 名称。支持 `openai`（顶层 reasoning_effort）、`thinking`（thinking.type 与 effort）、`responses`（reasoning.effort）、`chat_template`（chat_template_kwargs）、`output_config`（adaptive thinking 与 output_config.effort）以及 `none`（明确无思考能力）。别名必须由 Provider 明确声明；不支持的档位、冲突的原生参数、无效声明均报错。旧 OpenAI 兼容 Provider 未声明控制协议时保持规范字段透传，原有 Responses 端点适配继续生效。

DeepSeek V4 的 BYOK 目录声明原生 `thinking` 协议，`low` 发为 `thinking.type=enabled` 与 `reasoning_effort=low`；`none` 发为 `thinking.type=disabled`。依据：[官方思考模式合同](https://api-docs.deepseek.com/guides/thinking_mode/)。

签名 Model Package 的 `reasoning` v1 可增量声明可选 `effort_control`（同上结构），旧字段不变。required 模型不能声明可关闭思考。无思考模型不发送无意义的力度参数；有思考能力但没有声明映射的 Package 对显式 effort 返回可诊断错误，旧调用不受影响。新声明应与实际 Worker/模型模板能力一致，不能用声明伪造模型不具备的档位。

搜索摘要的初始生成及全部有限修复均显式使用 `low`，现有输出上限 6000 / 10000 / 16000 不变。证据来源与引用校验不变。

托管 AI2Apps Cloud 尚未声明该字段，Local 对显式 effort 明确报错，不会静默丢弃。Cloud 扩展需求见 [Cloud 对接需求](reasoning-effort-cloud-requirements-20261024.md)。这不影响当前 DeepSeek BYOK 搜索摘要。

## 验证与启用

- 针对性回归 119 项通过，之后新增的 Responses 声明端点回归也通过（对应子集 63 项通过）。覆盖真实 Provider 目录到 MockTransport 的 DeepSeek low/none/别名映射、任意 Provider 的 Responses 路由、Package 流式/非流式传参、显式不支持、旧省略参数、隐私重新路由和摘要有限修复。HTTP 和模型均为 fixture，未新增付费模型/搜索执行，尚无真实 token 节省量验收。
- AaAT 完整边界门禁 302 项通过，最终增量架构检查 27 项通过；检查策略没有改动。
- 较大回归集另有 7 个不经过本次行为的失败：两个旧会话权限 fixture、三个模型页/翻译断言、一个 GPT Image 能力集合断言、一个旧 SSD distribution ID 断言。未借本次改动修改这些独立断言或业务路径。
- App-Dev 和 Dev 均在空闲确认后通过各自标准 Helper 重启。最终 App-Dev PID 69258 / 54672，Dev PID 69255 / 54633；App/Helper 元数据源码根、运行中的搜索工作流导入路径及提供的共享静态资源均对应当前 checkout，健康检查 200。没有 App/Runtime/Package 构建或生产发布。
