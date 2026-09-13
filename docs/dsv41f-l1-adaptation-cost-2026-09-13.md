# 动态 L1 原型与四层全驻留成本

后续决定：动态 L1 已提升为 `experiments/dsv41_mlx/run.py` 的默认策略，
`--static-l1` 保留固定 L1 对照。实现位于 `experiments/dsv41_mlx/adaptive.py`；
原实验入口作为兼容转发保留。固定全量层方案不启用，仍为 Main40/Hot8、65 GB
文本预算。冻结 v1 归档未改动。下文数据是提升为默认前的实验记录。

默认入口回归：`artifacts/dsv41-default-dynamic128-20260913` 的 129 份 logits
与原动态实验逐值一致，发生 46 次专家晋升，采样峰值 54.904 GB。
单 token `Hello` 输入 + 17 步 Decode 已跨过首次晋升，动态与 `--static-l1`
开关运行的 18 份 logits 逐值一致。分别保存于
`artifacts/dsv41-default-single17-20260913` 和
`artifacts/dsv41-static-switch17-20260913`。固定开关无动态维护或晋升。

冻结 v1 保持不变。本轮新增实验入口
`experiments/dsv41_analysis/run_dynamic_l1.py`，通过子类接入策略，未修改模型前向。

## 四层全驻留

每个原始 packed 专家记录为 18,800,640 bytes。每层 384 个专家，目前 Main40
+ Hot8 占 48 个槽位。若将 0/1/19/39 层替换为完整 384 个槽位，取消其冗余 Hot：

`4 × (384 − 48) × 18,800,640 = 25,268,060,160 bytes`

即额外 **25.27 GB / 23.53 GiB**；四层专家总量从 3.61 GB 变为 28.88 GB。
按冻结运行峰值 54.895 GB 粗估，总峰值 **80.16 GB**。如果仍保留四层 Hot8，
额外量为 25.87 GB。此处是权重容量计算和峰值外推，没有执行 80 GB 实验。
即使仅全驻留一层，也额外约 6.32 GB；两层额外 12.63 GB，已超过现有余量。

## 读取收益估算

2048+32 原样本中四层贡献 206/929 = 22.17% 的 miss。本轮补测 128 Decode：

- 固定 L1 共 30,720 次专家请求，miss 3,630；四层 miss 779，占 21.46%。
- Decode 总时间 18.4487 秒；四层 native 读取调用计时合计 0.5573 秒。
- 若只消除此项且其他成本不变，128/(18.4487−0.5573) = **7.15 TPS**，
  相对本轮静态 6.94 TPS 提升 **3.12%**。

这不是全驻留实测，也不是总收益上限：native 的 `io_seconds` 不含其前置
GPU fence，其他 miss 调度和同步成本没有独立拆分。反之，增加驻留内存、
全量首次加载及带宽竞争可能增加成本。系统文件缓存未清除，计时不等于物理
SSD 延迟。因此目前证据不足以把四层全驻留描述为大幅加速，更不能许诺 10 TPS。

## 动态 L1 首版

- 不增加 Main40/Hot8 容量，不修改权重和路由。
- Prefill 频率仅作为相当于 12 token 的初始先验，避免长输入压制后续 Decode。
- GPU 累加 Decode 频次；每 16 步检查一次并衰减历史频次至 0.5。
- 每层最多替换 4 个 Main 专家；候选频次至少 3，且超过被替换者 2。
- 在原 native loader 的消费者 fence 后读取并发布新映射；维护周期才读取
  完整频次到 CPU。普通 Decode 仍沿用冻结版 all-hit 路径。
- 原实验针对多 token 初始输入；提升为默认时补齐单 token 初始输入的频次
  初始化。尚未接入 Scope，未做自适应维护周期。

```sh
.venv/bin/python experiments/dsv41_analysis/run_dynamic_l1.py --static-l1 \
  --prompt-json artifacts/dsv41-benchmark2048-prompt.json --decode 128 \
  --output artifacts/dsv41-l1-static128-20260913
.venv/bin/python experiments/dsv41_analysis/run_dynamic_l1.py \
  --prompt-json artifacts/dsv41-benchmark2048-prompt.json --decode 128 \
  --output artifacts/dsv41-l1-dynamic128-20260913
```

| 指标 | 固定 L1 | 动态 L1 |
| --- | ---: | ---: |
| Decode TPS | 6.94 | 7.32 |
| 合计命中率 | 88.184% | 88.356% |
| 晋升次数（专家数） | 0 | 46 |
| Decode native I/O 秒（含晋升读取） | 3.032 | 3.056 |
| 采样峰值 GB | 54.897 | 54.861 |

129 个输出 ID 全部相同，129 份 logits 最大绝对差 **0**，所有输出有限。
这是相对固定 MLX 的缓存策略一致性验证，并未改变既有 CPU 对齐的限制。
wrapper 自身哈希另存 `adaptive-l1.json`；主 manifest 的源码哈希仅覆盖基模型。

单次吞吐差约 +5.6%，但命中率只增加 0.17 个百分点，且晋升计入后直接 I/O
并未下降，因此不能将全部加速归因于策略，也不能声称已证实长 Decode 显著
提升。重复输入的路由分布变化少；下一步需用更长、多样化且遵守 EOS 的生成
验证收益，并优化晋升成本。当前保存为实验候选，冻结基准不被替换。
