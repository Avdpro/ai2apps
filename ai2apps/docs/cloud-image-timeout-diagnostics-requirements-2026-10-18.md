# Cloud 图片请求超时排查与错误诊断需求

日期：2026-10-18（Asia/Shanghai）  
交接对象：AI2Apps Cloud 项目  
范围：检查现网日志、定位本次图片编辑 504，完善 Cloud 错误协议与追踪信息。本文不包含 Cloud 代码修改或部署。

## 1. 问题与本地已核实证据

用户在 App-Dev 的 Agent Chat 上传两张人物图片，要求生成天安门背景合影。AaAT 成功进入 `ai2apps.imagine.group-photo`，请求已提交 Cloud；不是本地参数校验失败，也不是 Agent 上下文字节超限。

| 项目 | 已核实值 |
| --- | --- |
| 接口 | `POST https://coder.ai2apps.com/v1/ai/images/edits` |
| Local Studio Job | `stjob_65391de37df94c338aecb92ec04a5e8b` |
| Local 幂等键 | `agent-image-tinv_e3d9e473d0d94a5d97d3405b6b457ba6` |
| Mini-App | `ai2apps.imagine.group-photo` |
| 模型标识 | `cloud/ai2apps/openai/gpt-image-2` |
| 输出参数 | `1536x1024`，quality=`auto` |
| Job 创建（UTC） | `2026-10-18T06:24:40.454979Z` |
| Job 失败更新（UTC） | `2026-10-18T06:25:41.335733Z` |
| 对应北京时间 | 14:24:40.455 → 14:25:41.336 |
| 本地收到 HTTP 响应 | `2026-10-18 14:25:41,334`，`504 Gateway Time-out` |
| Job 总耗时 | 约 60.88 秒（不是精确的上游推理耗时） |

本地日志：

```text
2026-10-18 14:25:41,334 - httpx - INFO - HTTP Request: POST https://coder.ai2apps.com/v1/ai/images/edits "HTTP/1.1 504 Gateway Time-out"
```

本地最终保存的错误：

```json
{"code":"AI2APPS_CLOUD_IMAGE_REQUEST_FAILED","message":"AI2Apps Cloud image request failed","retryable":false}
```

**证据边界：**上面 JSON 是 Local 解析后的错误，不是原始 Cloud 响应正文。Local 当前只提取响应的 `error.code/message/retryable`；字段缺失时填通用错误及 `retryable=false`。因此不能据此确认 Cloud 明确禁止重试，也不能判断原响应是 HTML、其他 JSON 结构或空正文。本地未捕获原始响应头/body，也没有本次 Cloud request ID。

约 61 秒提示存在某一层约 60 秒的截止时间，但这是待验证假设，不能直接认定为反向代理超时。Local 收到了 HTTP 504 响应，没有进入本地 HTTP 客户端 TimeoutException 分支。

## 2. 请 Cloud 项目检查日志并交付结论

1. 按 UTC 06:24:30–06:26:00（北京时间 14:24:30–14:26:00）检索上述接口；必要时扩展到前后五分钟。
2. 关联入口代理/CDN/LB、Cloud API、排队/任务层和模型供应商调用记录。若存在多条同时间请求，用模型、尺寸和幂等关联信息进一步定位。
3. 本地幂等键不等同于已核实的 HTTP `Idempotency-Key`：Local 图片桥接用任务执行的 request_id 设置该请求头。请查询实际收到的值，并给出其与任务/供应商请求的映射，不要凭 Local key 猜测。
4. 确认是谁生成 504：入口网关、Cloud 总截止时间、连接池等待、连接建立、上传写入、等待响应头/首字节、响应读取、任务排队，还是供应商主动返回 504。若依赖链还有代理，请继续追到首次产生错误的一层。
5. 列出这条路径各层实际 timeout 配置、实际耗时与触发条件，解释约 60 秒截止来自哪里。不要仅提高单个客户端 timeout 后就判定解决。
6. 检查超时后上游是否仍在执行、是否最终产图、结果是否可恢复、是否计费/退款，以及同一幂等键再次提交是否会重复生成或扣费。
7. 确认 Cloud 实际返回的 HTTP 状态、Content-Type、错误结构与追踪响应头。原始正文只在受控内部日志中查看，交付脱敏摘要。

请回传：根因、证据关联 ID、超时配置链、上游最终状态、账务结果、修复方案、部署版本及验收结果。若日志已无法定位，应明确缺失哪些记录和补充措施，不能把猜测写作根因。

## 3. 结构化错误协议

建议 `/v1/ai/images/edits` 与 `/generations` 使用一致的 JSON envelope，兼容现有 `error.code/message/retryable`。字段命名可由 Cloud 统一，但必须表达以下语义。

| 字段 | 要求 |
| --- | --- |
| `code` | 稳定机器码，区分网关截止、Cloud 截止、供应商连接/读取超时、供应商返回 504等；不能全部压成同一通用码 |
| `message` | 可直接展示的简短信息，说明已知超时层；未知时明确未知 |
| `request_id` / `trace_id` | 用户报障和跨层日志关联 ID，响应头同步提供 |
| `origin` | `edge_gateway`、`cloud_api`、`cloud_worker`、`provider` 或 `unknown` |
| `phase` | `queue`、`pool`、`connect`、`write`、`first_byte`、`read`、`overall` 或 `unknown` |
| `timeout_ms` / `elapsed_ms` | 触发层配置与该层实测耗时；未知用 null，不用 0 冒充 |
| `upstream_status` | 仅在实际收到供应商 HTTP 响应时填写；不要把 Cloud 自己的 504填成供应商状态 |
| `upstream_request_id` | 供应商支持时记录，面向客户端只返回适合公开的标识 |
| `operation_id` | 已建立持久化任务时返回，支持恢复查询 |
| `execution_state` | `not_submitted`、`submitted`、`running`、`succeeded`、`failed`、`unknown`；只报告有证据的状态 |
| `retryable` | 临时错误分类，允许 null 表示未知；不代表可以无条件创建新请求 |
| `retry_strategy` | `same_idempotency_key`、`poll_operation`、`manual`、`none`、`unknown` |
| `retry_after_ms` | 适用时返回，并与 HTTP Retry-After 保持一致 |
| `billing_state` | `not_charged`、`reserved`、`charged`、`refunded`、`unknown`，按实际账务记录填写 |

示例仅为协议示意，不代表本次根因：

```json
{
  "error": {
    "code": "CLOUD_IMAGE_UPSTREAM_READ_TIMEOUT",
    "message": "等待图片供应商返回结果超时，任务最终状态尚未确认。",
    "request_id": "req_example",
    "trace_id": "trace_example",
    "origin": "cloud_api",
    "phase": "read",
    "timeout_ms": 60000,
    "elapsed_ms": 60012,
    "upstream_status": null,
    "upstream_request_id": null,
    "operation_id": "op_example",
    "execution_state": "unknown",
    "retryable": null,
    "retry_strategy": "poll_operation",
    "retry_after_ms": 3000,
    "billing_state": "unknown"
  }
}
```

## 4. 网关、日志与恢复要求

- 应用捕获的超时统一输出上述结构；入口代理产生的 502/504也应尽可能提供结构化错误和关联 ID。无法控制的外部网关错误应明确标为未知来源，不伪造供应商错误。
- 记录请求入站、排队、供应商提交、首字节、完成/超时的时间和耗时。用同一 trace 关联，记录脱敏的模型路由与 timeout 配置。
- 不记录图片 Base64、完整图片、鉴权头、Cookie、密钥或完整用户提示词。诊断只需图片数量/字节数、模型/尺寸、脱敏标识和阶段数据。
- 请求已提交后的超时不能被当成“肯定未生成”。若支持状态查询，明确查询接口及鉴权/归属校验；不支持则交付最小新增接口方案。
- 明确幂等作用域、保留期、相同 key 不同请求内容的冲突处理、并发重复请求处理。只有可以证明不会重复执行/扣费时，才允许客户端自动按原 key 重试。
- 若根因是长耗时生成超过网关生命周期，应评估持久化异步任务与查询/通知返回，不只无限增大同步超时。

## 5. Local 配套交接

Cloud 协议确认后，Local 需配套保留结构化字段，不再把缺失的 retryable 强制转为 false；非 JSON 错误显示 HTTP 状态和可用的 request ID，将来源标为未知。Chat/Studio 显示简短原因，展开显示阶段、耗时和排查 ID，避免展示嵌套 Python 异常字符串。

上述 Local 配套属于后续联调事项，本次仅提交需求文档，尚未实现。Cloud 不应假设当前 Local 会自动透传新增字段。请回传字段契约、示例响应及兼容策略，供 Local 项目接入。

## 6. 验收标准

- 分别模拟连接池、连接、写入、读取、Cloud 总截止、入口代理截止和供应商主动 504；可准确区分 origin/phase，无法识别的明确 unknown。
- 测试 JSON、HTML、空正文及缺少字段的错误，客户端不崩溃、不误报为确定不可重试。
- 跨层 request/trace ID 可串起一次请求的全过程；验证日志不含图片或凭据。
- 模拟超时后供应商继续成功，能查询/恢复产物并正确显示账务；重复提交原 key 不重复生成/扣费。
- 验证相同 key 不同 payload 被明确拒绝、不同用户不能查询他人 operation。
- 用正常耗时及超过 60 秒的真实图片编辑请求验证改造效果，并说明各层截止与恢复行为。
- 对本次 Job 给出可审计的排查结论；若无法恢复原结果，说明原因及费用处理。
