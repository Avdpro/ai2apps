# Burst Top2 驻留尾部替补与权重调整

当前默认保持 `--burst-tail zero`；Block 默认关闭（1）。本轮新增两个显式
实验选项，只允许 Burst + Block1。主文件 `tail_policy.py`、调用点 `burst.py`。
没有改变精确模式和冻结 v1。

## 两种策略

先执行原始真实 Router Top-6 选择，保证 Top2 在缓存中（必要时补读）。保留
原 Top-6 中已驻留的专家，剩余位置从当前 L1/L0 中按 `score+bias` 最高者补齐，
排除重复专家。原始 Top2 不允许被替换。只为必需原始专家读取 SSD，不为替补
专家读取 SSD；状态变化仍可能改变未来 token 的路由和总 I/O。

- `fixed-top`：保留原 Top2 权重，将原 Top3～6 权重总量按最终尾部四专家的
  unbiased score 比例分配。
- `renorm`：按最终六专家的 unbiased score 整体归一化，再乘 route_scale=1.5。
  这会改变 Top2 的贡献权重。

无须替补时两种策略直接保留原权重，避免不必要的舍入差异。最终仍按专家 ID
顺序汇总。预测 L2 未启用。动态 L1 统计原始真实 Top-6，LRU 记录实际执行槽。

```sh
.venv/bin/python experiments/dsv41_mlx/run.py \
  --burst-top 2 --burst-tail fixed-top --block-layers 1 \
  --prompt-json artifacts/dsv41-benchmark2048-prompt.json \
  --decode 128 --output artifacts/my-top2-fixed-tail
```

将 `fixed-top` 换成 `renorm` 或 `zero` 可比较另外两种策略。

## 性能：2048 输入、128 步自由生成

| Top2 尾部策略 | Decode TPS | 相对置零 | 峰值 GB | 替补专家次数 |
| --- | ---: | ---: | ---: | ---: |
| 置零 | 10.11 | — | 54.900 | 0 |
| 固定 Top2 权重 | 9.38 | −7.2% | 54.901 | 3118 |
| 六专家整体归一化 | 9.42 | −6.8% | 54.895 | 3154 |

三者129个生成ID在本重复输入上均与完整模型相同，但logits不同。每个配置
测量一次，按顺序运行，没有同时占用GPU；不能将细微差异视为稳定排名。
额外驻留候选排序、选取与权重运算有成本，当前没有用专用融合kernel优化。

## 数值对照：KL 越小越接近完整模型

完整参考为同一纯MLX模型的全Top-6路径。2048输入自由生成序列一致，可以
比较全部128步；另两条独立短输入使用完整模型的固定生成token逐步喂入所有
候选，确保32步一直是相同文本上下文。这里的teacher-forced argmax序列不是
候选的自由生成结果。

| 输入 | 置零平均 KL | 固定 Top2 平均 KL | 整体归一化平均 KL |
| --- | ---: | ---: | ---: |
| 2048 重复文本，128步 | 0.0000990 | **0.0000723** | 0.0000996 |
| Python 二分查找补全，32步 | 0.003594 | 0.002279 | **0.001865** |
| 中文“人工智能模型中的过拟合是指”，32步 | 0.21404 | 0.19528 | **0.16194** |

平均误差改善不代表每步都改善：

| 输入 | 置零最大 KL | 固定 Top2 最大 KL | 整体归一化最大 KL |
| --- | ---: | ---: | ---: |
| 2048 | 0.003602 | 0.002572 | 0.005520 |
| Python | 0.01096 | 0.01989 | 0.02167 |
| 中文 | 2.15366 | 2.26006 | 1.43403 |

2048与Python的三种策略Top1均与参考一致。中文32步Top1一致数为：
置零29/32，固定Top2为28/32，整体归一化29/32。特别是中文KL仍明显，不能
称为质量无损；只有三条输入，不能外推为通用质量提升。

固定Top2在三条输入的平均KL都降低（约27%、37%、9%）；整体归一化在两个
短输入下降约48%、24%，但长输入没有改善。没有足够证据选出统一默认赢家。

## 验证与记录

- GPU 小算子测试验证：保持Top2、只选resident、按biased分数挑替补、unbiased
  分数加权、权重总量以及无替补时逐值不变。
- 新代码默认zero策略的129份logits与上一版Top2逐值一致。
- 所有策略Prefill logits与各自完整参考逐值一致。
- 所有输出有限，模型进程未加载Torch，采样峰值未超过65GB。

复现脚本：

```sh
.venv/bin/python experiments/dsv41_analysis/test_tail_policy.py
.venv/bin/python experiments/dsv41_analysis/bench_tail_policies.py
.venv/bin/python experiments/dsv41_analysis/compare_tail_policies.py
```

结果目录：`artifacts/dsv41-tail-{128,code,zh}-{zero,fixed-top,renorm}-20260913`；
短输入完整参考为对应 `*-exact-*` 目录。汇总：
`artifacts/dsv41-tail-matrix-20260913.json`、
`artifacts/dsv41-tail-comparisons-20260913.json`。
Teacher-forced runner 在manifest明确记录实际Decode输入、参考路径和执行模式，
不将它混同为自由生成测试。全部实验为原始completion，不使用聊天模板。

结论：驻留高分专家替补值得保留，部分样本平均误差下降，但存在吞吐成本和
局部退化。两个选项均保留为实验，暂不替换zero默认策略。

## 补充对照：尾部置零，仅重新归一化保留权重

新增 `--burst-top 2 --burst-tail zero-renorm`，Block1。缺失尾部仍为零，
没有替补专家；保留项按 `w_i / sum(w_retained) * 1.5` 调整，包括Top2。
全部命中时直接返回原权重，避免额外舍入。默认仍为zero。

同轮2048输入、128步自由生成：zero对照 **9.994 TPS**，zero-renorm
**9.881 TPS**（约−1.14%，单次顺序运行，不足以判断稳定速度差异）；采样
峰值分别54.974GB、54.923GB。新策略三个用例替补次数均为0。

完整参考、相同上下文协议沿用上文：

| 输入 | zero平均KL | zero-renorm平均KL | zero最大KL | zero-renorm最大KL | Top1一致数 zero → zero-renorm |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2048重复文本，128步 | 0.0000990 | 0.0012132 | 0.003602 | 0.048773 | 128/128 → 128/128 |
| Python，32步 | 0.003594 | 0.004938 | 0.010957 | 0.038719 | 32/32 → 31/32 |
| 中文，32步 | 0.214043 | 0.138563 | 2.153659 | 0.909601 | 29/32 → 30/32 |

长输入生成ID仍与完整参考相同，128步均可比较；短输入使用固定参考token
逐步喂入，Top1统计是逐步预测的一致性，不代表自由生成质量。
中文平均KL下降35.3%，但长输入增至约12.3倍，代码增加37.4%。补回权重
总量不等于补回缺失专家的向量方向，不能保证MoE输出范数或最终隐藏状态
恢复；这组结果不支持将单纯归一化设为统一默认。

验证：保留权重总量、缺失项为零、全命中逐值不变的小算子测试通过；本轮
zero对照129份logits与上一轮zero逐值一致。所有候选Prefill与完整参考
逐值一致，输出有限，峰值低于65GB。

复现入口：`experiments/dsv41_analysis/test_retained_renorm.py`、
`experiments/dsv41_analysis/bench_retained_renorm.py`；数值比较复用
`compare_tail_policies.comparison()`。新结果保存在
`artifacts/dsv41-tail-{128,code,zh}-zero-renorm-20260913`，本轮zero对照为
`artifacts/dsv41-tail-128-zero-control-20260913`；汇总为
`artifacts/dsv41-retained-renorm-matrix-20260913.json` 和
`artifacts/dsv41-retained-renorm-comparisons-20260913.json`。
