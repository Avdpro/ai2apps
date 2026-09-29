# oMLX Runtime：DeepSeek V4.1 长 Decode 耗尽 Metal Resource 的修复要求

日期：2026-09-28

状态：已定位并修复，12K 真机回归通过，待发布

发现版本：`ai2apps/runtime-omlx 1.7.12`

受影响模型：`ai2apps/model-deepseek-v41-flash 0.1.1`

发现环境：AI2Apps App-Dev，Apple Silicon，Chat 本地推理

实施回执：[`docs/dsv41f-long-decode-resource-lifetime-fix-2026-09-28.md`](../../docs/dsv41f-long-decode-resource-lifetime-fix-2026-09-28.md)。

## 1. 结论

这次对话不是达到 `max_tokens` 后正常结束，也不是 Chat 主动停止。DeepSeek V4.1
在长时间 Decode 中触发了 MLX Metal allocator 的资源数量上限：

```text
RuntimeError: [metal::malloc] Resource limit (499000) exceeded.
```

请求的 HTTP/SSE headers 已经返回，所以 Host 记录到 HTTP 200；但 Worker 在生成下一个
token 时异常退出，流中没有最终 `finish_reason`、usage 或 `[DONE]`。Chat 把 EOF 当成正常
完成，因而保存了一条只有 Thinking、没有最终回答、状态却为 `completed` 的助手消息。

这里可以将故障归类为 **Decode 期间的 Metal resource 生命周期泄露/无界累积**。更准确地说，
当前证据证明 allocator 管理的 Metal buffer 对象数在故障时已达到 499000；结合长 Decode
才触发的特征，它与逐 token resource 累积高度一致，但尚不能仅凭异常位置断言是哪一个
Python 变量“忘记 free”。最可能的机制是逐 token 创建的 MLX lazy graph、KV/cache 状态或
函数式更新返回值仍被引用，导致旧 buffer 无法回收；具体引用链必须由 instrumentation 证实。

## 2. 复现与证据

### 2.1 用户可见现象

- 模型：`(Local) AI2Apps-MLX · DeepSeek V4.1 Flash`。
- Thinking 持续约 `527.5s`，请求总时长约 `559.8s`。
- Thinking 内容生成到一半后停止，没有最终 answer。
- Prefill/Token Gen 与 token 统计没有最终值，因为流没有正常结束。
- Chat 将助手消息错误保存为 `completed`。

对应会话：

```text
session_id = ses_12a7d823b75c4385977954ca3b02560b
assistant_message_id = msg_0d802eee4d2b4c89b1de1b2b86c9d75b
```

持久化元数据记录：

```text
thinking_time = 527.5
total_time = 559.79
prompt_tokens = 0
total_tokens = 0
status = completed
```

这些 token 零值不是“生成了零 token”，而是终止 usage 缺失后客户端写入的回退值；数据库中
实际保存了约 5.3K 字符的 `_thinking`。

### 2.2 时间线

Host 日志：

```text
2026-09-28 00:23:04.698 +08:00
POST http://127.0.0.1:50232/v1/chat/completions -> HTTP/1.1 200 OK
```

Worker service log：

```text
2026-09-27T16:32:17.799716Z
RuntimeError: [metal::malloc] Resource limit (499000) exceeded.
```

两者为同一时区换算后的请求。HTTP 200 只表示流式响应 headers 已发出，不表示生成成功。

### 2.3 完整关键调用栈

```text
ai2apps/model_worker/server.py:575       serialized_chunks
ai2apps/model_worker/omlx_chat.py:407    _chat_stream
omlx/patches/deepseek_v41/engine.py:400  stream_chat
omlx/patches/deepseek_v41/engine.py:290  _decode_sync
omlx/patches/deepseek_v41/adaptive.py:93 __call__
omlx/patches/deepseek_v41/model.py:321   __call__
omlx/patches/deepseek_v41/adaptive.py:87 moe
omlx/patches/deepseek_v41/model.py:278   moe
omlx/patches/deepseek_v41/model.py:219   routes_all_hit
    return bool(mx.all(mapped >= 0).item())
RuntimeError: [metal::malloc] Resource limit (499000) exceeded.
```

`routes_all_hit()` 是下一次 Metal 分配碰到上限的位置，不应在没有资源曲线与引用分析的情况
下被直接认定为泄露源。

## 3. 为什么不是输出 token 上限

Host 的全局默认输出上限为 `32768`；该会话没有单独设置 `modelSettings.max_tokens`，Package
请求会由 Host 的 `_apply_package_max_tokens()` 将有效上限写入 Worker payload。

更关键的是 DeepSeek V4.1 的生成控制流：

```python
if index + 1 < int(max_tokens):
    logits = await loop.run_in_executor(
        executor,
        self._decode_sync,
        token,
        len(prompt_ids) + index,
    )
```

本次异常正是从这次 `_decode_sync()` 调用内部抛出。因此当时必然满足
`index + 1 < max_tokens`。如果已经达到上限，这次 Decode 根本不会执行，生成器会以
`finish_reason="length"` 正常结束。

本次流里没有 `finish_reason="length"`、没有其他最终 `finish_reason`、没有 usage、也没有
`[DONE]`，所以不能把它归因于正常输出截断。

## 4. Metal 错误的准确含义

MLX 的 Metal allocator 分开管理内存字节数和 Metal resource 数量。MLX 源码在创建新 buffer
前检查 `num_resources_ >= resource_limit_`；即使系统还有可用统一内存，也可能先因 Metal
buffer 对象数达到上限而失败。这里的 `499000` 是 resource/buffer 数量门槛，不是 499000
字节，也不是 token 数。

allocator 会优先释放可回收的 cached buffers；释放后仍达到 499000，说明大量 buffer 当时
仍是 active，或没有进入可回收 cache。`mx.clear_cache()` 只能清理已经可回收的缓存，不能
释放仍被 graph、array、KV/cache state 或其他 Python/C++ 对象引用的 buffer，因此不能把
周期调用 `mx.clear_cache()` 作为根本修复。

上游已有高度相似的 DeepSeek V4 长生成报告：逐 token 的函数式 cache 更新若丢弃返回的新
state、同时旧 lazy graph 仍挂在长期存活对象上，会表现为每层每 token 增加 Metal buffer，
最终稳定撞到相同的 resource-count 上限。它是本问题的重要排查方向，但仍需在 oMLX 当前
DeepSeek V4.1 实现中用 instrumentation 证实。

参考：

- [MLX Metal allocator 实现](https://github.com/ml-explore/mlx/blob/main/mlx/backend/metal/allocator.cpp)
- [mlx-lm #1332：DeepSeek V4 长 Decode 的 Metal residency 增长](https://github.com/ml-explore/mlx-lm/issues/1332)
- [mlx-lm #1662：丢弃 `update_and_fetch` 返回 state 导致逐层逐 token buffer 泄露](https://github.com/ml-explore/mlx-lm/issues/1662)

## 5. Runtime 必须完成的根因修复

### 5.1 先建立 resource-count 观测，不以异常行猜根因

为长 Decode 增加仅用于测试/诊断的采样，至少记录：

- completion token index；
- Metal active、cache、peak memory；
- Metal resource/buffer count；
- 每 N 个 token 的 resource-count 增量；
- 各层 KV cache、router lookup、age/counter state 的 shape 与对象替换情况；
- graph materialization/`mx.eval` 边界。

如果当前 MLX Python API 没有导出 `num_resources_`，在 Runtime 测试构建中添加最小诊断
hook，或在 allocator/Metal 工具层采样。只看内存 GB 曲线不足以验收本问题。

### 5.2 审计所有跨 token 存活的 MLX state

重点审计 DeepSeek V4.1 Decode 中下列状态及其调用链：

- attention KV cache 的 `update_and_fetch()` 或等价函数：必须使用并保存函数返回的新
  keys/values，不能只依赖副作用后丢弃返回值；
- `lookups`、`ages`、`cache_counters`、ticks 与路由命中判定；
- `self.ages[l][slots] = ...` 等更新是否形成串联的 lazy graph；
- `self.cache_counters[l] = self.cache_counters[l] + ...` 是否保留上一 token 的计算链；
- `bank.track(out)` 或其他长期容器是否持有每个 token 的输出/中间 array；
- Decode 后传给下一 token 的 logits、hidden state、attention state 是否已 materialize，并与
  不再需要的 graph 断开；
- miss、all-hit、Adaptive 及普通 cache 路径是否都具有相同的有界生命周期。

修复应确保跨 token state 只保留当前必需值，旧 graph 能在下一轮前释放，同时继续遵守以下
现有性能约束：router indices 在 all-hit 路径留在设备端，不得为规避泄露而增加逐 token
CPU round-trip，也不得关闭 cache-aware MoE 快路径。

### 5.3 不接受的规避方式

- 仅降低默认 `max_tokens`，让崩溃更晚或更难触发；
- 仅周期调用 `mx.clear_cache()`；
- 捕获异常后静默返回空答案或伪造 `finish_reason="stop"`；
- 将 all-hit router indices 每 token 搬到 CPU；
- 关闭 DeepSeek V4.1 Thinking、MoE cache、Adaptive 或 SSD cache 来绕过；
- 只提高 Metal resource limit；这会推迟故障，不会消除无界增长。

## 6. Worker 流式失败传播必须同时修正

当前 `ai2apps/model_worker/server.py` 的 `serialized_chunks()` 在 `finally` 中无条件执行：

```python
record["status"] = "succeeded"
```

因此 `result.chunks` 抛异常时，内部 operation 状态仍可能被标记成功。这与实际结果不一致。
应改为：

1. 正常消费完整流后才标记 `succeeded`。
2. `GeneratorExit`/客户端取消标记为 cancelled/aborted（按现有状态模型映射）。
3. 其他异常标记 `failed`，保留结构化错误 code、message 和 request/model 上下文。
4. 无论成功失败都在 `finally` 中释放 lock、清理 request root。
5. headers 已发送后的异常必须通过既定流式错误协议通知 Host；若协议无法发送错误帧，Host
   至少必须能将“无合法终止事件的 EOF”识别为失败，不能视为成功。

这项修复不能替代 Metal 生命周期修复，但能避免同类引擎错误再次显示为空白成功回复。

## 7. Chat/Host 的独立防御任务

当前 Chat 在 `reader.read()` 返回 `done` 后直接进入保存流程。它虽然记录了
`finishReason` 和 `lastUsage`，却没有验证流是否收到合法终止事件；随后即使最终内容为空，
也会保存 `status=completed` 的助手消息。

Chat/Host 应另行实现：

- 对本地 Package 流明确跟踪 `[DONE]` 或等价的协议终止事件；
- EOF 前既无终止事件又无最终 `finish_reason` 时，显示“本地推理中断”，保留已有 Thinking
  供诊断，但将消息标记为 `failed`；
- 展示 Worker 的结构化错误，不把 HTTP 200 当作流式生成成功；
- 不用缺失的 usage 伪造 0 token/0 TPS；
- 对用户主动停止与引擎异常使用不同状态和提示。

这是客户端容错，不属于引擎根因修复；实施时需单独更新 Desktop NXR 台账。

## 8. 测试要求

### 8.1 引擎级长 Decode 回归

为 DeepSeek V4.1 建立可重复的长生成测试，固定 prompt、sampling、seed、cache 模式和
checkpoint，避免过早 EOS，并运行到至少 12K completion tokens；正式验收应覆盖有效上限
`32768` 或模型 context 允许的最大长度。

每隔固定 token 数采样 resource count。允许 KV cache 所需内存随序列长度按设计增长，但：

- Metal resource count 在 warm-up 后必须有界，不能近似按 layer × token 线性增长；
- 12K 与 32K 目标处不得出现 `[metal::malloc] Resource limit`；
- 生成必须返回合法 `finish_reason`、usage 和 `[DONE]`；
- 进程完成一次长请求后，应能继续完成第二个短请求；
- 请求结束或取消后，非模型常驻资源应回落到稳定基线。

### 8.2 路径覆盖

至少覆盖：

1. all-hit Decode；
2. 有 cache miss/promote 的 Decode；
3. Adaptive 开启与关闭；
4. Thinking `Auto` 与 `On (Unlimited)`；
5. 正常 EOS、`finish_reason=length`、用户取消、引擎异常；
6. 连续两次长请求及长请求后短请求。

### 8.3 正确性与性能门禁

- 修复前后固定短 prompt 的 token、Top-10 logits/router 结果保持既定精度标准；
- all-hit 路径保持 router indices device-resident；
- steady-state TPS 不得因强制同步或 CPU round-trip 显著回退；
- Prefill、Token Gen、Thinking、Duration telemetry 在成功和失败场景均语义正确。

### 8.4 Worker/Host 协议回归

构造一个在输出若干 reasoning chunks 后抛异常的 fake Worker stream，断言：

- operation 最终不是 `succeeded`；
- lock 与临时目录被清理；
- Host 收到结构化失败或可识别的非正常 EOF；
- Chat 不保存空白 `completed` 助手消息；
- 已有 reasoning 可保留用于诊断，但不会冒充最终回答。

## 9. 验收标准

- DeepSeek V4.1 在真实 Apple Silicon 上完成至少 12K-token 长 Decode，不触发 Metal
  resource limit；正式门禁覆盖 32768 或 context 上限。
- Metal resource count 不再随 generated token 持续线性增长，并提供修复前后曲线。
- 找到并记录具体引用链或状态更新缺陷；不能只以 `mx.clear_cache()` 通过短测。
- 短输出正确性、Top-10/router parity 与 all-hit 性能保持现有门禁。
- 成功流具有最终 `finish_reason`、usage、`[DONE]`。
- 引擎异常会完整传播为失败，Worker operation 不再误标 `succeeded`。
- Chat 不再把异常 EOF 保存为 `completed` 空回答。
- Runtime 单元测试、DeepSeek V4.1 真机长测、Model Worker 流式异常测试全部通过。

## 10. 发布边界

根因位于 `ai2apps/runtime-omlx` 所携带的 DeepSeek V4.1 引擎/MLX 状态生命周期，以及
Runtime 内 Model Worker 的流式失败传播。现有模型 Package 只提供模型声明与适配入口；当前
证据不要求修改 checkpoint，也不应把 native 或引擎级资源管理逻辑下放到模型 Package。

如果修复发布为新的 Runtime 版本，而现有模型 Package 的 Runtime 依赖下限仍低于该版本，
已经安装旧 Runtime 的实例不会自动升级。发布负责人需要决定是否另发仅提高最低 Runtime
版本的模型 Package 修订版，以确保 ACPF 能把受影响实例升级到修复版本。

## 11. 处理结果（2026-09-28）

根因修复与 Model Worker 失败传播已随 `ai2apps/runtime-omlx 1.7.13` 发布。Apple 公证、
隔离安装、12K 真实 SSD Decode、Cloud/GitHub/ModelScope 三源和匿名完整字节/Publisher
签名验证均通过。完整结果与不可变来源标识见
`docs/ai2apps-mlx-runtime-1.7.13-deepseek-v41-long-decode-release.md`。checkpoint 不变；Chat
异常 EOF 的 UI 防御仍等待下一版 Desktop Release。
