# DS4.1F Burst 连续窗口优化（2026-09-16）

状态：完成。独立实验后端；auto 默认仍为 packet，未发布 Runtime。

## 实现

1. 原 guarded 每层保存全部 40 层状态并作为 Gate 依赖。现在按层保存本层状态与频次/年龄；共享 attention 状态与小型全局计数单独保留。miss 时保留完成前缀和当前层 attention，恢复未完成后缀。前一层缓存更新通过显式依赖串入下一 Gate。
2. 删除 ICB 每算子额外无条件全局 barrier，保留 MLX 原生依赖 barrier；Gate 后显式 barrier 发布停止标记。使用 concurrent encoder。原有 donation 限制仍在 guarded 后缀生效。
3. 每窗口中首次 Gate 前使用原生调度，包括已修复 MoE 和下一次路由检查前的计算。GPU 停止保护从首次 Gate 后才生效。
4. 显式跨层执行在 miss 后继续重组窗口，不再把整个 token 的余下层直接降为 packet。
5. 增加原生推测窗口对照：窗口内保留原生 Metal dispatch；Gate 只记第一个 miss，安全槽暂算后缀，丢弃无效结果；从首个 miss 的 MoE 恢复。该方式减少同步但不在 GPU 上跳过后缀，不能称为 GPU 提前停止。仅支持 Burst 的安全槽路径。

原专家、路由、attention、权重与 SSD loader 不变。Burst 保留 Top2/Top4 必需专家及原 zero-tail 策略；“精确”指与相同 Burst 参考一致，不指与自然 Top6 一致。

## 测试与复现

- 工具：`experiments/dsv41_analysis/miss_resume/benchmark_guard_optimized.py`。
- 输出：`artifacts/dsv41-burst-guard-opt-20260916/`。
- `correctness`：旧版、guarded Block2/4/40，Top2/Top4；8 Decode，逐 token logits、KV/shared/频次/年龄/计数的 safetensors 对照。
- `correctness-v2`：首次 Gate 前原生调度，以及 native window Block2/4；同一逐步状态对照。
- `performance-v2`：历史 2048 输入、128 Decode，Main40/Hot8、eviction_dual、Prefill64；顺序运行 old/native/guarded，检查全部 logits 哈希、SSD 字节、晋升、计数和 bank fence。
- 独立 MLX 0.32.0 固定源版本，继续使用 wheel 原始 metallib；无 wheel 安装变更。
- 实验开关：`DSV41_LOCAL_CHECKPOINTS=0` 可恢复全量 checkpoint；`DSV41_NATIVE_PREFIX=0` 可恢复全窗口 guarded；`DSV41_NATIVE_WINDOW=1` 选择原生推测窗口（通过实验 entry 的 guarded 控制器入口）。环境开关记录于 manifest。

## 正式 CLI 结果

后端 ABI 更新后，hit/miss、四阶段 GPU 停止恢复、自然 Top6 完整模型回归均通过。累计15组候选逐步状态对照全部精确一致。正式入口选择的5项 CPU 测试通过。验证收据：`artifacts/dsv41-burst-guard-opt-20260916/final-verification.json`。

同一历史 2048-token 输入、128-token Decode，Main40/Hot8，eviction_dual，Prefill64，原生 zero-tail Burst。完整 TPS 包含第一个 Decode；尾段单列后112步。Top2 按旧→新→新→旧顺序执行。没有清理 OS 文件缓存，也未停用其他用户进程。

| 模式 | 完整 Decode TPS | 后112步 TPS | 边界检查 |
|---|---:|---:|---:|
| Top2 legacy A | 8.479 | 9.586 | 5120 |
| Top2 window2 A | 9.304 | 10.698 | 2873 |
| Top2 window2 B | 9.309 | 10.771 | 2873 |
| Top2 legacy B | 9.158 | 10.583 | 5120 |
| Top4 legacy | 8.077 | 9.271 | 5120 |
| Top4 window2 | 7.568 | 8.525 | 3523 |

表中5120仅指逐层路由判断边界，不包含旧版 miss 元数据的额外回读或公共 token/head 同步；2873为新窗口提交数。

Top2 两轮合并为 8.805→9.307 TPS（+5.69%），但旧版两轮相差约8%，新模式仅比最快旧版高约1.6%。因此只能认定该高命中案例有小幅正收益，不能声称已经得到稳定的大幅加速。Top4 下降约6.3%，不推荐此配置。

Top2 共5120层，349层需要必需专家加载（6.82%），平均2.73层/token。window2 把边界检查减少43.89%，其中2429个提交完成两层；没有 attention 重放。Top2 的完整层图共构建5285层，比5120多165层；此外每次 miss 的当前 MoE 也曾暂算，不能把3.2%的额外完整层构建量当作全部额外 GPU 工作。SSD 读取字节、每层命中统计、晋升、bank fence 与旧版完全一致。

所有正式对照的129份 logits 哈希均精确一致；峰值约57.3 GB（十进制），低于65 GB。这里的精确比较对象是相同 TopN/zero-tail Burst。

## 其他方案与限制

- 原生固定 window4：Top2 8.868 TPS，Top4 6.644 TPS。同步更少，但推测后缀和恢复成本更大。
- 按本请求已观察到的 miss 分布划分窗口（无离线提示先验）：减少推测浪费，但未胜过固定 window2；保持实验开关，不作为默认。
- 真正 GPU 提前停止的 guarded window4：本轮高命中 Top2 为6.060 TPS。即使删除全量状态保存和无条件逐算子 barrier，其逐算子 ICB 仍明显拖慢。原生 window 获得的小收益不能当作 guarded 已通过性能验收。
- 统计计数与路由统计移出窗口控制依赖，在 runner 已有的每 token 结束 `mx.eval(logits, cache_counters, ages)` 中结算，仍计入 Decode 计时；close 再汇总报告。此前“延至 close”的表述不准确。只提交本窗口修改的状态，避免重复遍历40层。没有增加模型的主机同步边界。
- 单次主机检查观察到其他后台 CPU 活动与既有 swap，但没有热限制警告；没有证据把波动归因于某个特定进程或 swap，亦未修改系统服务。
- auto 仍是 packet；没有自动启用 window 或 guarded。没有发布 Runtime/Package，也没有改变 L0/L1 大小。

## 使用

```sh
.venv/bin/python experiments/dsv41_analysis/miss_resume/build.py
.venv/bin/python experiments/dsv41_mlx/run.py \
  --inference-mode window --burst-top 2 --resume-block 2 \
  --prompt-json artifacts/dsv41-tps-anchor-20260916/prompt.json \
  --prefill-slots 64 --decode 128 --logits-mode hash \
  --output artifacts/my-burst-window2
```

`window` 仅支持当前标准文本、eviction_dual、Main40、zero-tail Burst 配置；不支持的组合明确报错。原有图像/其他策略继续走默认 packet。

复测须使用新目录：`DSV41_WINDOW_BENCH_DIR=artifacts/my-burst-window-abba .venv/bin/python experiments/dsv41_analysis/miss_resume/benchmark_guard_final.py`。
源提交 `8ff6faf966d56ae92d21bf2d36d9512da5745784`（脏工作树）；每次 manifest 记录实验源文件哈希。后续唯一二进制调整为 ABI 标记改为 `icb-gate-barrier-v2-mlx0320`：防止新的 Gate-barrier 后端与旧 bridge 混用；计算逻辑不变。后端与 bridge 必须成对重建。

短输入高 miss 场景不能作为历史高命中吞吐的替代数字。
