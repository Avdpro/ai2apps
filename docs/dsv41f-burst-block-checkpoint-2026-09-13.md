# Burst Top2/Top4 与首次 miss 层回退

实现入口：`experiments/dsv41_mlx/run.py`，策略：`burst.py`。
默认仍为动态 L1 + 完整专家逐层执行；Burst 与 block 均不默认启用。
冻结 v1 归档哈希已重新核对，未修改。此改动仅为研究 runner，未接入生产 runtime。

## Burst 语义

- Prefill 完整执行原始 Top-6，Burst 仅对 Decode 生效。
- Top-N 按原始 `sqrtsoftplus(router_logits) + bias` 的 Top-6 顺序确定。
  N=2/4 的专家必须正确加载和执行；不是按 expert ID 或缓存可用性排序。
- 其余 Top-6 中，已驻留者仍执行，缺失者贡献置零；不重归一化 routing weights。
  共享专家始终执行。为了保留现有专家算子，当前仍构建 6 槽 GPU 调用，并将
  缺失位置的安全占位结果屏蔽为零。因此不是只计算 N 个专家的专用内核。
- “正确”指相对于 Burst 当前输入状态的真实 Router；不保证与完整模型的
  未来路由或最终输出一致。
- 默认 `--block-layers 1` 是逐层 Burst 对照。2/4 仅与 `--burst-top` 配合。
  不带 Burst 请求 block>1，或 Burst 与 `--static-l1` 组合，会明确报错。

## 分段状态机

块内每层入口保留 h、mHC mix，以及 `states/shared` 的快照，保留共享数组
别名关系。MLX array 使用独立句柄，后续 functional update 不污染恢复点。
当前为简单、完整的状态树快照；尚未做只保存本块受影响状态的精简版本。

每层投机计算只写 GPU required-miss 标记，不读取 `.item()`。块末 materialize
候选输出与所有标记后检查第一次 miss：

1. 全命中：提交整块。
2. 第 j 层首次 miss：提交 j 前的前缀；恢复 j 入口及其后的模型状态。
3. 只补读 j 层必需的缺失专家，并 pin 该层已驻留尾部，避免替换改变 Burst
   近似规则。完成 j 层后，从 j+1 开始重新组成 2/4 层块。
4. j 之后的投机状态、路由统计不提交；下一次计算重新产生真实路由。

Engram hash 在每个 token 进入分段循环前只更新一次。动态 L1 维护在 token
开始、任何块执行前进行，使用前面已提交 token 的频次；频次、LRU 与 cache
计数只在层提交时更新。native bank 写入前的消费者 eval/synchronize 保留。
投机块完成后才允许恢复读盘，不能边读边覆盖 in-flight GPU 的数组。

`replayed_layers` 统计直接恢复执行的失败层次数；`discarded_layers` 统计
失败尝试中没有提交的全部层数，是本次额外层计算量的更合适指标。

## 测试配置与复现

M5 Max / 128 GiB；原始权重；Main40/Hot8；动态 L1 默认；MLX 空闲缓存 2 GiB，
65 decimal GB 采样预算。相同 2048-token 输入，128 步 Decode（共129输出）。
GPU 运行依次进行，不同时启动多模型。固定长度 benchmark 不因 EOS 提前停止。

```sh
.venv/bin/python experiments/dsv41_analysis/bench_burst_blocks.py
.venv/bin/python experiments/dsv41_analysis/compare_burst_blocks.py
.venv/bin/python experiments/dsv41_analysis/test_burst_snapshot.py
```

单组运行，例如：

```sh
.venv/bin/python experiments/dsv41_mlx/run.py \
  --burst-top 4 --block-layers 2 \
  --prompt-json artifacts/dsv41-benchmark2048-prompt.json \
  --decode 128 --output artifacts/my-burst-top4-block2
```

## 性能结果

| Burst | Block | Decode TPS | 相对同 Top-N 逐层 | 块一次通过率 | 额外层计算比例 | 峰值 GB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Top2 | 1（对照） | 10.11 | — | — | 0% | 54.96 |
| Top2 | 2 | 9.55 | −5.5% | 86.2% | 10.0% | 54.90 |
| Top2 | 4 | 9.37 | −7.3% | 74.2% | 15.6% | 55.00 |
| Top4 | 1（对照） | 9.08 | — | — | 0% | 54.90 |
| Top4 | 2 | 7.25 | −20.2% | 58.6% | 35.6% | 54.90 |
| Top4 | 4 | 6.32 | −30.4% | 35.0% | 64.2% | 54.90 |

Top2 Block2/4 均触发 366 次恢复，Top4 均触发1199次。更大块减少检查次数，
但首次 miss 后丢弃的后缀更多。Top4 Block4 保存并提交的正确前缀共1406层，
仍额外计算3286层；说明确实恢复到内部失败层，而不是全部回退到块首。
Block4 的首次 miss 偏移0/1/2/3均被实际覆盖。

检查计数：逐层5120，Top2 Block2/4为3017/1786，Top4 Block2/4为4098/3045。
这是显式 required-miss 检查次数，不包括 native 读盘 fence、Engram 地址读取、
预算采样等其他边界。分段不等于整个进程完全无主机同步。

这些是每格一次的微基准，不是多输入/多轮统计保证。逐层对照和分段都不执行
普通 runner 的 Decode 层末日志回调，彼此对比一致；与历史精确模式 TPS 的
差异还包含回调路径差异，不能全部归因于 Burst。

## 正确性与近似边界

- 四组分段运行，各129份 logits 与相同Top-N的逐层Burst **逐值一致**；
  每层必需加载量、尾部省略量也一致。
- Top2累计加载411个必需缺失专家，省略3056次冷尾部贡献；Top4为1556/1848。
  上述计数不包括动态L1预热/晋升读取。
- 对完整精确MLX基线，两种Burst的129个生成ID在本输入中相同，但logits不同。
  同上下文最大KL：Top2约0.00360，Top4约0.00114。重复输入结果不能作为整体
  质量等价证据；短 hot/cold 输入也说明Burst会改变生成。
- Top2短输入17步强制触发块内miss，18份logits与逐层对照一致。
- 独立 snapshot 测试验证旧值保持和shared别名关系。
- 默认不开Burst的France短输入回归，4份logits与此前完整MLX逐值一致。
- 所有运行记录 `torch_imported=false`，最大采样峰值约55GB，未超65GB。

Artifacts：`artifacts/dsv41-burst128-t{2,4}-b{1,2,4}-20260913`，包含
manifest、logits、`burst.json`、`adaptive-l1.json`；汇总为
`artifacts/dsv41-burst128-matrix-20260913.json` 和
`artifacts/dsv41-burst128-comparisons-20260913.json`。

## 结论

机制已实现并通过对应Burst策略的逐值回归，但当前没有预测L2时分段仍是负收益。
保持显式开关，默认精确路径不变。下一步优化应先降低状态快照开销、提高块的
完整必需专家命中率，再评价L2联合收益；不能据此把Burst成绩称为无损10TPS。
