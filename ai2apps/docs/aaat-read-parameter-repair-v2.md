# 系统只读参数纠错 v2

状态：已实现，隔离验证通过，空闲检查后已在 App-Dev 激活；真实模型修正、失败停止、预算及原 Agent-Chat 恢复已完成实机验收。现有 Agent-Chat 与 channels/v1 不迁移。

## 接入与边界

新增系统管理端 `POST /v1/platform/channels/read-with-repair`，必须显式提交 `protocol=ai2apps.channels/v2`。身份、权限、Session 和频道选择沿用 v1 的宿主验证，实际业务调用仍经过原 Tool Gateway。普通 `POST /channels/read`、直接 AaAT Router 及 Agent-Chat 不初始化纠错协调器，也不调用新的纠错 AI。

纠错由系统统一协调。新入口默认 `parameter_repair=system`：先确定性修正；必要时在 owner 声明范围内调用一次 AI。调用 App 无需编排模型回合或重试循环。`deterministic` 禁用 AI，`off` 只走原严格只读派发。

Provider 通过原可信注册中的 `read_repair` 声明可修正字段。首批启用：Gallery search、Knowledge search、情报 channels/news 的结果数量 `limit`；显式别名 `max_results` 可迁移为 limit。其他字段不自动启用。

确定性修正仅对声明字段执行：无冲突的明确别名、精确 JSON 数值/布尔字符串、唯一大小写枚举匹配，以及缺失字段的显式 Schema default。不裁剪未知字段、不将冲突字段合并、不截断/舍入超限数值、不把 null 当缺省。

AI 仅接触 owner 启用的、当前已存在但类型无效的数值/布尔字段及其有界 Schema。比如 `limit="a couple"` 可产生 `{ "limit": 2 }` 候选。首批内置 owner 的 AI 数量上限为 20（Schema 更严时取更小值）；显式有效数值仍遵守原 Schema，不因 AI 上限而改变。AI 不修复任意名称拼写，不补造缺失查询、资源 ID、目标、许可或身份，也不改动查询内容/资源范围。语义歧义应拒绝；Schema 与范围校验不宣称能形式化证明任意自然语言语义等价。

新 owner 启用 AI 字段前必须评审其是否仅影响有界只读结果展示，不能把身份、权限、效果目标或查询范围字段作为数量参数开放。业务校验仍由 owner 实施，不进入共享层。

## 请求示例

先从原频道目录选择精确 owner/ref/operation，按当前参数契约提交：

```json
{
  "protocol": "ai2apps.channels/v2",
  "session_id": "<owned-session>",
  "owner": "ai2apps.gallery",
  "local_id": "library",
  "interface_version": "1",
  "provider_id": "<selected-operation.provider>",
  "provider_version": "<selected-operation.provider_version>",
  "role": "search",
  "arguments": {"query": "sample", "max_results": "2"},
  "parameter_repair": "system",
  "max_repair_attempts": 2,
  "total_timeout_ms": 15000,
  "model_max_tokens": 256
}
```

策略上限：最多 2 次候选修正，确定性和 AI 共用；最多一次 AI 请求；整个准备、纠错和实际读取共用最多 15000ms；模型输出请求最多 512 tokens，默认 256；原参数 JSON 上限 16KiB，AI 字段上下文上限 8KiB。不重置计时，不切换备用模型，不为无效模型输出再开循环。

AI 使用当前系统 `work_simple` 模型路由，并遵守系统 privacy profile。缺少配置或模型不可用时，返回明确错误；不回退到当前 Agent-Chat 的模型或借用其模型循环。正常有效参数不需要模型。Cloud 与本地模型均使用已有宿主 ModelInvocationService 身份、计费与调度通道；不存在凭据转发或第二套推理客户端。报告保留实际 usage；未报告的 usage 不推定为零。输入大小/请求次数/输出上限是本版预算边界，不是金额硬上限。

## 执行与失败语义

纠错发生在业务提交前。候选每次重新检查当前可见性、Provider 实例/版本、契约指纹、Schema 及 owner prepare。版本或配置变化、撤销、权限拒绝、交互需求均停止；不会请求新的授权或自动提交确认。

最终派发再次在原 Router 内核对宿主绑定的参数契约指纹。确认/配置型 owner 不走此入口。成功参数只由协调器提交一次 Gateway；Gateway 自身原有读取策略保持不变。handler 内同名 ValidationError、普通失败、断线和超时不进入参数纠错循环；不能据此证明未提交或自动重放。

等待模型/准备阶段的总超时报告 not_started；已进入最终派发后的超时保守报告 unknown。取消传播到当前请求并记录取消，不自动续接或创建新 Run。v2 只覆盖只读能力，不增加效果操作的恢复/幂等承诺。

成功结果仍含原 output/invocation_id，schema 为 v2，并附 repair 报告：纠错 ID、模式、owner policy 摘要、尝试方法/字段名/参数摘要/契约指纹，以及 AI usage。实际有效参数可通过原 invocation 权限接口读取。失败保留当前参数契约、结构化校验路径和停止原因；原输入不被原地修改。

审计使用原 EventStore，绑定原 Session/AppInstance、actor/Installation 和 Provider。事件只保存参数摘要、方法、字段名、版本、停止码与调用引用，不保存原参数值、错误正文或模型建议文本。模型只收到必要的无效字段值；其他参数、查询、资源引用不进入纠错提示。

本版没有创建第二套执行队列，也没有持久 request/attempt 恢复仓储：纠错 ID 是审计关联，不是 HTTP 重试幂等键。重启、刷新或断线不会自动恢复本次纠错；原 Gateway 记录仍可按既有权限查询。任意 App/Package 委托、父 Run 预算继承、写操作和无 Run 确认仍未开放。

## 与既有契约的关系

当前 Agent-Chat 的“宿主不合并冲突参数、不替模型重放、无内层 AI 映射”限制继续适用。v2 只为上述独立入口增加受限系统规范化；不是删改旧限制，也不迁移旧表单、确认认领、Run 键、消息身份或恢复规则。新模块惰性初始化失败不影响 v1 或直接 Agent 调用。

相关代码：`services/parameter_repair.py`、`services/channels.py`；owner 声明保留在内置组合层及情报 owner。新增共享模块作正向架构分类，不添加业务名分支或门禁例外。

验证：完整 AaAT 门禁 752 项、最终定向 63 项及最终纠错套件 25 项通过；模型回复为夹具。App-Dev 激活证据与未执行的真实模型验收范围见 [本轮记录](acceptance/channel-read-repair-20261101/README.md)。

激活后另以真实默认模型完成原 Agent-Chat Gallery 只读冒烟；旧参数契约错误恢复仍走原路径，新协调器在该 Session 中零调用。后续已完成 v2 真实模型实机验收，见下方记录。

真实模型后续验收：[17 个 v2 用例、v1 对照与原 Agent-Chat 执行/恢复](acceptance/channel-read-repair-live-20261101/README.md)通过。本轮无实现变更；验收中观察到的 Local 平滑重启已按启动身份分段记录，没有自动重放。
