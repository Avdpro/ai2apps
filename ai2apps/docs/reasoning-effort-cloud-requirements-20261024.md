# 托管 Cloud reasoning_effort 支持需求

状态：待 Cloud 项目确认合同、实现和部署。本仓库未修改 Cloud 后端。仅适用于托管 `/v1/ai/responses`；BYOK 已在 Local Provider 适配。

## 请求与能力协商

建议为 `/v1/ai/responses` 增加可选 `reasoningEffort`，规范值 `none / minimal / low / medium / high / xhigh / max / ultra`。缺省保持现有行为。具体字段名须以 Cloud 对接回执为准，Local 不预先假设该字段已上线。

`/v1/ai/models` 对每个模型公开明确的 reasoning 控制能力、可用规范档位和是否允许关闭。Cloud 自己维护上游映射，不让 Local 猜测上游型号。能力声明必须能区分“无思考模型”“支持力度控制”“不支持力度控制”；旧响应无声明不代表支持。

## 行为

- Local 按能力协商传入规范意图；Cloud 在 Provider 适配层映射原生参数。DeepSeek low 对应启用思考加 low；其他模型按官方能力映射。
- 非法档位返回稳定 400 错误；模型不支持请求档位也返回明确错误。不得忽略参数、提高力度、换模型或换 Provider。
- 同一请求的重试、幂等和异步恢复必须保持力度。幂等输入校验包括该字段；不得重用另一力度的旧结果。
- 流式与非流式都支持；保持工具调用、隐私、权限、限额、收费和 token 用量合同。
- 回执/使用记录保留规范请求力度和实际原生力度，便于诊断默认高思考耗费；不暴露思考内容。
- Model Package 无思考能力时可以不向 Worker 发送参数，但必须明确回执不可应用，而不能声称实际启用了 low。

## 验收与回执

覆盖省略参数的旧客户端、DeepSeek low/none、其他 Provider 的映射、非法/不支持档位、流式、工具调用、幂等冲突和预算/计费不变。回执请包含实际字段名、模型能力 schema、错误码、部署版本和示例。Local 之后按已发布合同增加托管 Cloud 映射与集成测试。

当前 Local 对托管 Cloud 显式 effort 返回不支持错误，防止看似生效。未传参数的旧请求不变。搜索摘要现在显式 low，选用托管模型需先完成本需求；DeepSeek BYOK 路径已支持。
