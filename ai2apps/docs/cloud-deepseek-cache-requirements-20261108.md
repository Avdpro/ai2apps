# Cloud DeepSeek 缓存用量核查与请求前缀合同

交付对象：AI2Apps Cloud 项目。本仓库不改 Cloud 代码。本轮本地投影修复与本要求可独立实施，不切换用户模型或账户。

## 已确认边界

2026-11-08 通过 Dev 标准 Installation 身份调用托管模型 `deepseek/deepseek-v4-flash`，相同 1,916 Tokens 合成输入重复三次，Cloud 原始 usage 均为零命中，且声称上游报告。请求 ID：

- `d79e440a-a18e-4589-825c-ead277e79a18`
- `bc10c8b4-a43a-434d-b294-996e6a5e52ef`
- `f282a7ad-9e5a-4fc1-8a4d-1c28749086e4`

Dev 自有 Key 对 DeepSeek 官方接口的同类输入重复调用正常命中。不同 Key、路由/模型及上游服务不能假定共享缓存，所以这些数据不是 Cloud 归一化错误的最终证明。需要用上述 Cloud 请求关联真实供应商请求，检查原始返回。

## 核查要求

1. 在受限服务端日志中对照实际供应商/model/endpoint、供应商 request ID 和原始 usage；不记录密钥，不向客户端公开上游凭据或用户正文。
2. 保留并校验原生 `prompt_cache_hit_tokens`、`prompt_cache_miss_tokens` 与 OpenAI 风格 `prompt_tokens_details.cached_tokens`。如使用 Responses API，对照 `input_tokens_details.cached_tokens`。缺失保持 null/unreported；不能用默认零宣称 upstream-reported。冲突或越界应标记不可信并可诊断，不能静默选择错误字段。
3. 非流式和流式终态使用同一归一化规则；公开输入总量、命中量、未命中量及观测来源，确保命中+未命中与输入一致。计费数据单独校验，不根据估算价格倒推缓存。
4. 检查是否按请求轮换模型/账户/端点，注入时间戳、随机 ID 或前置模板，或把晚到的系统声明合并到请求头部。Local 当前托管协议会把所有 system/developer 片段聚合到顶层 system；请评估按原顺序保留消息角色的版本化协议，避免追加审阅声明重写早期前缀，不能直接丢失系统指令优先级。
5. 用同一受控服务端路由做冷/重复/尾追加/头修改/流式对照，并与供应商原始 usage、Cloud 响应、本地持久指标逐字段核验。固定上游调用条件，避免把不同账户的首次请求误当缓存失败。

## 验收

缺失、明确零、正命中、原生/标准字段冲突分别有覆盖；可用 request ID 追踪，不泄露用户内容。线上受控重复请求若仍真实为零，明确报告路由/供应商限制和原始证据，不承诺供应商必须命中。交付核查结果后再决定是否需要 Cloud 修复和部署。
