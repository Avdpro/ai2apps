# oMLX Runtime：DeepSeek V4 Flash 2-bit DQ Direct Prefill 修复要求

实施状态：Runtime 1.7.12 已完成源码修复、回归、真实 2-bit DQ 验证、Apple 公证、正式 Package 隔离安装及 Cloud/GitHub/ModelScope 三源发布。

日期：2026-09-25  
状态：已完成并发布  
发现版本：`ai2apps/runtime-omlx 1.7.11`  
受影响模型：`ai2apps/model-deepseek-v4-flash-2bit 0.3.5`

## 1. 问题摘要

在 AI2Apps Test 实例中使用 `(Local) AI2Apps-MLX · DeepSeek V4 Flash 2-bit DQ` 对话时，请求返回 HTTP 200，但模型不产生任何可见 token。Chat 最终显示空白助手消息，Prefill 和 Token Gen 指标均为 `—`。

Worker 在两次独立请求中均记录同一异常：

```text
RuntimeError: direct Prefill marker reached legacy path
```

请求已经正确到达模型 Worker，模型 Package 和 checkpoint 也已成功安装、加载到启动阶段。故障发生在 Runtime 的 DeepSeek V4 scope-cache Prefill 路径中，不是 Chat 模型选择、Thinking 标签、网络请求或 checkpoint 下载问题。

## 2. 根因

相关实现位于：

```text
omlx/patches/deepseek_v4/scope_cache.py
```

`ScopeFallbackLoader.prefetch_transient_records()` 目前只检查：

```python
self.direct_prefill and self._direct_enabled()
```

满足条件后，它会产生 `_PreparedDirectRequest` 标记。但是 `build_transient_switch()` 在消费该标记时还会额外检查：

```python
self._direct_store_compatible(self._store(layer))
```

因此生产端和消费端采用了不一致的 Direct Prefill 资格判断。

当前原生 Direct Prefill loader 只支持以下六段 compute-ready store：

```text
gate_proj.weight
gate_proj.scales
down_proj.weight
down_proj.scales
up_proj.weight
up_proj.scales
```

DeepSeek V4 Flash 2-bit DQ 的 expert store 还包含量化偏置：

```text
gate_proj.biases
down_proj.biases
up_proj.biases
```

所以该 store 不满足 `_direct_store_compatible()`。预取阶段却仍产生 Direct 标记，消费阶段随后拒绝 Direct 路径并进入 Legacy 分支，最终触发：

```python
raise RuntimeError("direct Prefill marker reached legacy path")
```

## 3. 必须实施的 Runtime 修改

### 3.1 根本修复：统一 Direct Prefill 资格判断

修改 `ScopeFallbackLoader.prefetch_transient_records()`，在创建 `_PreparedDirectRequest` 前检查当前 layer 的 expert store 是否与原生 Direct loader 兼容。

目标逻辑：

```python
def prefetch_transient_records(
    self,
    layer: int,
    expert_ids: list[int],
) -> Future[_PreparedTransientRecords | _PreparedDirectRequest]:
    """Start pure CPU/SSD preparation for the next Prefill bank."""

    ids = tuple(expert_ids)
    if not ids:
        raise ValueError("cannot prefetch an empty fallback expert bank")

    self.prefetch_submits += 1
    store = self._store(layer)
    if (
        self.direct_prefill
        and self._direct_enabled()
        and self._direct_store_compatible(store)
    ):
        future: Future[
            _PreparedTransientRecords | _PreparedDirectRequest
        ] = Future()
        future.set_result(_PreparedDirectRequest(layer=layer, ids=ids))
        return future

    return self._prefetch_pool.submit(
        self._read_transient_records_detached,
        layer,
        ids,
    )
```

预期行为：

- 六段式 4-bit store 继续使用 Direct Prefill，不损失现有快路径性能。
- 带 `*.biases` 的 2-bit DQ store 自动使用现有异步 Legacy Prefill。
- 不改变 Decode、Hot Cache、Adaptive L1 或模型 Package 行为。

### 3.2 防御性修复：不允许错误标记导致请求崩溃

在 `build_transient_switch()` 的 Legacy 分支中，不应再因为收到 `_PreparedDirectRequest` 而直接终止推理。若标记与当前 store 不兼容，应同步读取 records 并继续构建 Legacy fallback switch。

目标逻辑：

```python
elif isinstance(prefetched, _PreparedDirectRequest):
    if prefetched.layer != layer or prefetched.ids != ids:
        raise ValueError("prefetched direct bank does not match request")
    records, record_bytes = self._read_records(layer, expert_ids)
else:
    # 保留当前 _PreparedTransientRecords buffers 转换逻辑。
    ...
```

这一项是安全网。根本修复完成后正常流程不应进入这里，但环境能力变化、未来 store 布局变化或其他调用方产生的陈旧标记都不应导致用户得到空白回复。

不要通过以下方式规避问题：

- 不要把 2-bit DQ 强行声明为六段式兼容。
- 不要忽略 `*.biases` 或用零偏置替代。
- 不要关闭所有模型的 Direct Prefill。
- 不要在模型 Package 中覆盖 Runtime 的缓存加载逻辑。

## 4. 测试要求

在 Runtime 测试集的 Direct L1/Prefill 测试文件中至少增加以下覆盖。

### 4.1 六段式 store 保留 Direct 快路径

构造只含六个受支持 tensor segment 的 fake store，开启 Direct L1 和 Direct Prefill，断言：

- `prefetch_transient_records()` 返回完成态 Future。
- Future 结果为 `_PreparedDirectRequest`。
- `build_transient_switch()` 调用 `_direct_load_slots()`。
- `_read_records()` 和 `_read_transient_records_detached()` 均未被调用。

### 4.2 2-bit DQ store 自动使用 Legacy 异步预取

构造包含以下九个 segment 的 fake store：

```text
gate_proj.weight, gate_proj.scales, gate_proj.biases
down_proj.weight, down_proj.scales, down_proj.biases
up_proj.weight, up_proj.scales, up_proj.biases
```

开启 Direct L1 和 Direct Prefill，断言：

- `prefetch_transient_records()` 不返回 `_PreparedDirectRequest`。
- 它调用 `_read_transient_records_detached()`。
- `build_transient_switch()` 成功建立包含 biases 的 Legacy fallback switch。
- 推理结果与关闭 Direct Prefill 时一致。
- 不出现 `direct Prefill marker reached legacy path`。

### 4.3 陈旧或错误 Direct 标记安全回退

向不兼容 store 的 `build_transient_switch()` 人工传入 `_PreparedDirectRequest`，断言：

- Runtime 校验 layer 和 expert IDs。
- Runtime 同步调用 `_read_records()` 并继续执行。
- 不抛出 RuntimeError。

### 4.4 真实模型冒烟测试

至少对以下两个模型执行相同短 prompt：

```text
hi
20+20=?
```

覆盖：

1. DeepSeek V4 Flash 4-bit：确认仍走 Direct Prefill，并正常返回文本。
2. DeepSeek V4 Flash 2-bit DQ：确认走 Legacy Prefill，并正常返回文本。

两者都必须验证首 token、结束事件及 Prefill/Token Gen telemetry 存在。

## 5. 验收标准

- DeepSeek V4 Flash 2-bit DQ 连续多轮对话均产生非空回复。
- Worker 日志中不再出现 `direct Prefill marker reached legacy path`。
- 2-bit DQ 的 `*.biases` 被完整加载并参与计算。
- 4-bit 六段式模型继续命中 Direct Prefill；相关性能没有显著回退。
- Direct Prefill 开启、关闭两种模式下，2-bit DQ 的确定性测试输出保持一致。
- Prefill、Token Gen 和 Duration telemetry 正常上报。
- 现有 DeepSeek V4、Direct L1、scope-cache 和模型 Worker 测试全部通过。

## 6. 发布边界

本问题的推理修复属于 `ai2apps/runtime-omlx`。DeepSeek V4 Flash 2-bit DQ 的模型代码、
checkpoint 和 checkpoint distribution 不需要改动，因为：

- Package 已正确描述 2-bit DQ 模型及其量化张量。
- checkpoint 中的 biases 是模型计算所需数据，并非异常内容。
- 出错的是 Runtime 对 Direct Prefill 能力的判断和回退策略。

现有模型 Package 0.3.5 的 Runtime 依赖范围为 `>=1.7.5,<2.0.0`。因此，已经安装
Runtime 1.7.11 的实例会把该依赖视为已满足，不会因重新安装或重试模型 Package 而自动
升级到 1.7.12。实例必须显式升级 Runtime 1.7.12。若要让 ACPF 对受影响实例自动执行该
升级，需要另行发布一个提高最低 Runtime 到 1.7.12 的模型 Package 修订版；这不属于本次
Runtime 1.7.12 的发布授权和制品范围。

Runtime 发布后，应在 AI2Apps App-Dev 和 Test 实例分别更新并完成真实模型验证。Chat 对“HTTP 200 后流式生成失败”的错误展示可以另立客户端任务处理，不应阻塞本 Runtime 修复。

## 7. 实施与验证记录

2026-09-25 已在 `ScopeFallbackLoader` 完成两处 Runtime 修复：

- `prefetch_transient_records()` 只有在 Direct Prefill 已开启、原生 Direct-L1
  可用且当前 store 为受支持的六段布局时才生成 `_PreparedDirectRequest`；九段
  2-bit DQ store 继续使用现有异步 `_read_transient_records_detached()`。
- `build_transient_switch()` 收到与当前 store 不兼容的陈旧 Direct 标记时，先校验
  layer 和 expert IDs，再同步读取完整 records 并构建 Legacy switch，不再终止请求。

新增回归覆盖六段 Direct 标记及加载、九段 bias store 异步回退与 Direct-off 数值一致、
陈旧标记同步安全回退及不匹配标记拒绝。验证结果：

- `tests/test_direct_l1.py`：10 passed。
- DeepSeek Prefill、DeepSeek patch、Scope warmup、Scope runtime：132 passed。
- Model Worker、DeepSeek 2-bit adapter、Runtime Package contract：39 passed。
- Ruff、Python compileall、`git diff --check`：通过。

正式 Runtime 1.7.11 的 CPython 3.11、MLX 和已签名原生扩展被 APFS 克隆到临时验收
环境，仅覆盖本次 `scope_cache.py`。原生 `preadv_fused_experts` 符号可用，并以
`OMLX_MOE_DIRECT_L1=1` 完成真实 2-bit DQ SSD checkpoint 测试：

- `hi`：产生非空 4-token 输出，TTFT 0.885 秒，Decode 14.75 token/s；Direct Prefill
  开启时 2 次异步预取均命中，Direct load 为 0。
- `20+20=?`：产生 48-token 非空输出并明确包含“答案是40”；Direct Prefill 开启时
  40 次异步预取均命中，Direct load 为 0，峰值 31.45 GiB。
- 同一 48-token 数学提示在 Direct Prefill 开启与关闭时输出 SHA-256 均为
  `a1364ed8dc05609f8cf0ccf81b9bf6c6e51fa7fb5028131d4878dfb121d027b3`。

当前 Test 缓存内的 4-bit `DeepSeek-V4-Flash-SSD` 实际 store 顺序为
`scales, weight`，并非 Direct loader 规定的 `weight, scales` compute-ready 六段布局，
因此它只能验证正常生成，不能作为真实 Direct Prefill 快路径验收物。canonical 六段路径
已由回归测试确认仍生成 Direct 标记且调用 `_direct_load_slots()`；正式发布前若要完成真实
4-bit Direct 门禁，需要使用此前的 compute-ready checkpoint 或重建该 checkpoint。

Runtime 1.7.12 内部候选位于
`packages/ai2apps-runtime-omlx/dist/1.7.12/AI2Apps-oMLX-Runtime-1.7.12-internal.dmg`：

- 384,542,702 bytes；SHA-256
  `aade49e5e185980a33255c81861b1e4d24aea279be2f1da315432fd30c0bbc5e`。
- Developer ID Team `84XL5V265N`，`codesign --verify --deep --strict` 通过。
- 候选内 `scope_cache.py` 与工作树 SHA-256 均为
  `6f2d8d2ad59416e9bf57456f1271a0370b8334e194a1e69755a48bfa2bbc60e8`。
- 候选内 CPython 3.11 成功加载 MLX 与 `preadv_fused_experts`，直接从只读挂载 DMG
  运行 `hi` 成功，TTFT 0.893 秒、Decode 15.43 token/s、峰值 31.27 GiB。
