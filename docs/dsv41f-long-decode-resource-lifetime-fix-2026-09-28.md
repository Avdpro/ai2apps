# DeepSeek V4.1 Flash 长 Decode Metal 资源生命周期修复

日期：2026-09-28

状态：已实现并完成 12K 真机回归，待纳入新版 Runtime/Desktop

## 结论

故障根因已经定位，不是 KV cache 的正常长度增长。DeepSeek V4.1 的每个 routed-expert
resident bank 都维护 `pending` 列表，`bank.track(out)` 在每层 Decode 后把输出 lazy graph
加入该列表；此前只有 SSD reload/slot mutation 触发 `_fence()` 时才清空。连续 cache hit
期间没有 fence，因此每个 token 会留下最多 40 个跨 token 输出根引用，每个根又会固定其
整段 MLX graph 和 Metal buffers，最终撞到 499000 resource limit。

同一路径还有两个需要一起截断的函数式状态：`cache_counters` 和每层 `ages`。它们在每个
token 更新，若只 materialize logits，旧状态 graph 不保证在 token 边界释放。

修复在原有 `mx.eval(logits)` 的 token 完成边界执行以下操作：

1. 同一次 `mx.eval` materialize logits、cache counters 和所有已建立的 ages；
2. eval 返回后清空各 bank 的 `pending` 输出引用；
3. slot reload 之前的 `_fence()` 语义保持不变。

因此没有增加 GPU→CPU 同步次数，没有把 all-hit router indices 搬回 CPU，也没有调用
`mx.clear_cache()` 掩盖问题。

## 真机结果

使用 AI2Apps 共享目录中的 475GB DeepSeek V4.1 SSD checkpoint、Runtime 1.7.12 的正式
CPython 3.11/MLX 0.32.0 和已签名 Direct-L1 extension。测试使用固定非 EOS token，确保
完成 12,000 次 Decode；每 512 token 采样一次，结束后重置序列并完成第二个短请求。

| 指标 | 结果 |
|---|---:|
| completion tokens | 12,000 |
| Decode 时间（不含首次 Prefill） | 1,157.792 s |
| 0–512 token cold TPS | 8.845 token/s |
| 512–12K steady TPS | 10.445 token/s |
| 全程资源回归吞吐 | 10.365 token/s |
| 起始 Metal active | 50,113,648,298 bytes |
| 12K Metal active | 50,116,749,110 bytes |
| active 增量 | 3,100,812 bytes |
| 采样最大 `pending_outputs` | 0 |
| layer Decode 次数 | 480,000 |
| all-hit layer 次数 | 430,983（89.788%） |
| 非 all-hit layer 次数 | 49,017 |
| 第二个短请求 | 完成 |

测试同时覆盖了大量 all-hit 和非 all-hit/cache 更新层。12K 处没有 Metal resource limit；
active memory 在 warm-up 后保持水平，peak 的约 24.6MB 缓慢增长属于长序列状态/工作区，
不再出现按 layer × token 累积的常驻输出 graph。

MLX 0.32.0 Python API 只公开 active/cache/peak memory，没有导出 allocator
`num_resources_`。本次以具体 Python 引用链、每 token pending=0、稳定 active memory、越过原
故障时长并完成 12K 以及第二次请求共同验收。完整逐点数据在
`artifacts/dsv41-long-decode-resource-20260928/report.json`，复现入口为
`scripts/diagnose_dsv41_long_decode.py`。这次 10.365 TPS 是固定-token 资源回归数据，不替代
标准对话质量/吞吐 benchmark。

基准源 commit 为 `de405d2371d61f85fda19da583b5d9fa1000849a`，工作树包含本次修复；
实际加载的四个关键源码 SHA-256 和脱敏复现命令已写入 report 的 `benchmark` 字段。

## 流式失败语义

Model Worker 现在只在完整消费生成流后标记 `succeeded`。生成器异常会：

- 写入包含 request ID、operation、model、code 和 message 的结构化错误；
- 将 operation 标记为 `failed` 并记录 traceback；
- 对 SSE 发送错误帧，不发送伪造的 `[DONE]`；
- 在 `finally` 中释放 invocation lock 并清理 request root。

客户端取消标记为 `cancelled`。Chat 会识别结构化错误，并要求流出现合法 `[DONE]`；异常
EOF 保存为 `failed`，保留已经生成的正文和 reasoning，用户主动停止保存为 `cancelled`。
DeepSeek V4.1 在达到 max_tokens 时的最终输出也已修正为 `finish_reason=length`。

## 其它模型审计

| 模型路径 | 生命周期机制 | 同构风险结论 |
|---|---|---|
| DeepSeek V4 Flash | 每次 model forward 调用 `_materialize_cache_arrays(cache)`，递归 materialize CacheList 叶子 | 未发现跨 token 输出列表 |
| GLM 5.3 | Prefill pending 固定为双 scratch bank，复用前及尾部逐项 eval；Scope pending 在 drain 后 clear；L1 promotion 每层最多保存 8 个整数专家 ID | 未发现同构无界 graph |
| Qwen3.8 Next | 继承 GLM 的 bounded cache executor；pending promotion 按层覆盖/弹出，值为有界专家 ID | 未发现同构无界 graph |
| Qwen3.6 35B | Scope collector 只在单次有固定 expected-layers 的 probe 中存放 router arrays，finish 后对象释放；profile collector drain 后 clear | 未发现同构无界 graph |

全仓搜索中，只有 DeepSeek V4.1 同时存在长期 `MetalBank.pending`、逐 token
`bank.track(out)` 和“仅在未来 miss/reload 才清理”的组合。GLM/Qwen/DS4F 仍会因 KV cache
随 context 增长而增加设计内存，但没有这次的同构 Metal resource 泄露。21 项 GLM/Qwen
cache/Scope 定向测试和 2 项 DS4F cache materialization 测试通过；该审计不冒充每个模型
都已完成独立 32K 真机压力测试。

## 验证

- DeepSeek V4.1、Worker、adapter、Chat：78 passed。
- GLM/Qwen cache/Scope：21 passed。
- DeepSeek V4 cache materialization：2 passed。
- 真实 DeepSeek V4.1 12K Decode + 后续短请求：通过。
- Ruff（本次 Python 文件）、JSON locale 解析、`git diff --check`：通过。

## 发布边界

引擎和 Model Worker 修复已随 `ai2apps/runtime-omlx 1.7.13` 发布，Cloud、GitHub 和
ModelScope 三源均已激活；发布收据见
`docs/ai2apps-mlx-runtime-1.7.13-deepseek-v41-long-decode-release.md`。Chat 的异常 EOF 防御属于
Desktop Host 静态前端，需要纳入下一版 Desktop。checkpoint 和 DeepSeek V4.1 模型算法/权重
均不变。为确保已经安装旧 Runtime 的设备自动升级，后续还需提高 DeepSeek V4.1 模型
Package 的 Runtime 最低版本。
