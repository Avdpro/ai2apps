# DS4.1F Prefill 双缓冲与独立 Burst 实测

2026-09-13。纯文本、原始MXFP4专家权重、Main40/Hot8、动态L1，65十进制GB预算。
新能力目前显式开启；默认仍为原完整Top6串行Prefill，Decode Burst与block默认关闭。

## 实现

`experiments/dsv41_mlx/prefill.py` 提供全模型共用的一对scratch，32/64/96槽。
沿用原GLM/Qwen native preadv，直接填充MLX数组；mx.async_eval提交当前组计算，
下一次读取填充另一bank。覆盖前仅等待该bank的消费者；不删改原L0/L1 loader的
全局安全栅栏。每层完成后结果按原expert-ID顺序恢复，route权重进入激活量化前
的数学位置不变。Main初始化、Decode Hot容量与原完整Top6频率统计不变。

为保持旧Hot初始化，当前实现最后重读旧算法最终Hot组；首轮完整Top6因此比
基线多读取约3.57GB专家数据（跨40层总计）。这是明确的额外成本，尚未做
scratch到Hot的无重复读取交接。以独立计数报告scratch I/O，不能漏算总读取量。
每组输出同步结束后才复用scratch；Prefill结束和model.close都会释放scratch。

Prefill Burst由 `--prefill-top 2/4` 独立开启，要求非零scratch。每token的
原始TopN按biased router排序；保留原始Top6中属于入层resident集合或全批必保
专家并集的route，其他项不执行QMM并置零。不归一化、不补选其它专家。顺序不
依赖SSD组加载先后。Decode保持完整Top6，除非同时指定 `--burst-top`。

## 首轮2048输入性能

固定 `artifacts/dsv41-benchmark2048-prompt.json`，8步Decode；各自新进程，串行
运行，没有主动清空系统page cache，不称作物理SSD冷读。Prefill计时包含首轮
按需权重载入，但不含进程启动和tokenizer准备。

| 配置 | Prefill TPS | 峰值GB | Prefill scratch读取GB | 保留route比例 |
| --- | ---: | ---: | ---: | ---: |
| 原版串行完整Top6 | 103.33 | 54.897 | — | 100% |
| 双缓冲32完整Top6 | 110.78 | 56.087 | 68.622 | 100% |
| 双缓冲64完整Top6 | 112.69 | 57.304 | 68.622 | 100% |
| 双缓冲96完整Top6 | 107.49 | 58.502 | 68.622 | 100% |
| 双缓冲64 Prefill Top4 | 118.56 | 57.301 | 44.840 | 98.42% |
| 双缓冲64 Prefill Top2 | 134.79 | 57.288 | 17.955 | 93.71% |

64完整Top6比同轮基线约+9.1%；Top2比原版约+30.4%、比64完整Top6约+19.6%。
这些不是稳定排名或300TPS达标证明。Top2减少很多冷专家读取，但仍计算93.7%
的route，不能按Top2/Top6估算FLOPs。96槽更多内存却更慢，不能盲目扩容。

## 数值验证

完整Top6的32/64/96在长输入的Prefill及后续8步logits均与旧完整参考逐值一致。
64完整Top6在独立代码/中文短输入的Prefill+32步Decode也逐值一致。
所有比较验证trace哈希与有限值，运行进程无Torch，均低于65GB。

Prefill Burst先改变状态，后续固定喂入完整参考token，Decode本身仍完整：

| 输入 | 策略 | Prefill末位KL | Prefill首个预测一致 | 后续Decode平均KL | Decode Top1一致 |
| --- | --- | ---: | --- | ---: | ---: |
| 2048重复输入 | Top4 | 见JSON逐步记录 | 是 | 0.0000764 | 8/8 |
| 2048重复输入 | Top2 | 见JSON逐步记录 | 是 | 0.0002788 | 8/8 |
| Python短输入 | Top4 | 0.060889 | **否** | 0.0007357 | 32/32 |
| Python短输入 | Top2 | 0.025717 | 是 | 0.0007859 | 32/32 |
| 中文短输入 | Top4/Top2 | 0 | 是 | 0 | 32/32 |

中文输入太短，resident覆盖导致该样本没有形成有效的近似误差压力；不能当作
通用中文质量无损证据。Python Top4的第一个预测已经变化，后续32/32是在固定
参考token条件下的结果，不是自由生成全文一致。该组只提供有限数值证据，不能
替代长且多样的质量评估。Prefill和Decode误差需分别记录。

## 复现与产物

- `experiments/dsv41_analysis/bench_prefill.py`：首轮容量/TopN/短输入矩阵。
- `experiments/dsv41_analysis/bench_prefill_repeat.py`：32步复测与双阶段Burst。
- `experiments/dsv41_analysis/run_prefill_probe.py`：完整参考token重放，manifest记录实际输入。
- `experiments/dsv41_analysis/compare_prefill.py`：逐步KL、Top1、Prefill误差及总读取量。
- `artifacts/dsv41-prefill-matrix-20260913.json`、`artifacts/dsv41-prefill-comparisons-20260913.json`。

每个输出目录包含manifest源码SHA256、HEAD、checkpoint哈希、峰值、耗时及
逐步logits；旧冻结版本和旧测试产物未覆盖。本轮只改独立实验代码，无生产集成。

## 复测及最终Hot交接修正

32步固定参考Decode的复测：基线104.54 Prefill TPS，64完整Top6为111.04，
64 Prefill Top2为136.12。仅Prefill Burst仍留下非零后续Decode误差。

首版只seed最后一个Hot组，最后一组不足8个时遗漏了前组应保留的专家。
最终改为seed完整最后8个冷专家，保持旧路径的Hot工作集及LRU身份次序。
最终完整Top6与同轮基线的逐层L1/L0/miss计数全部一致，33份logits逐值一致。
虽然物理slot编号可不同，但专家身份、LRU顺序和已测计算结果一致。

| 最终交接修正版，2048+32 | Prefill TPS | Decode TPS（含首步） | 峰值GB | 后续Decode平均KL |
| --- | ---: | ---: | ---: | ---: |
| 64完整Top6 | 116.19 | 6.25 | 57.441 | 0 |
| 64 Prefill Top2 + Decode Top2 | 136.79 | 8.75 | 57.291 | 0.0003791 |

双阶段Top2的Prefill末位KL为0.00003398，该重复输入的33次Top1均与参考一致；
不代表通用生成质量无损。旧首版双阶段试跑出现146.91 Prefill TPS，本轮修正后
为136.79，因此不选择146.91作为最终交付数字。不同运行热状态存在波动；
完整Top6多次结果111～116，比复测基线104.54高约6%～11%。

最终seed完整Hot8的额外专家读取为6.016GB（2048用例40层合计），已计入
`expert_total_read_bytes`，不是隐藏的额外内存驻留。下一步可将最后Hot8直接
作为终组计算或做经验证的scratch→Hot交接，消除重复SSD读取；尚未实现。

最终产物：`artifacts/dsv41-prefill-final64-20260913`、
`artifacts/dsv41-prefill-final-both-top2-20260913`。最终源码SHA以这些manifest为准。
复现最终两组：

```sh
.venv/bin/python experiments/dsv41_analysis/run_prefill_probe.py \
  --reference artifacts/dsv41-default-dynamic128-20260913 \
  --prompt-json artifacts/dsv41-benchmark2048-prompt.json --decode 32 \
  --prefill-slots 64 --output <fresh-output>
# 第二组额外添加：--prefill-top 2 --burst-top 2
```

目前保留显式开关，不修改默认的完整Top6原路径。推荐下一轮精确性能实验使用
`--prefill-slots 64`；有损组合独立设置。尚未达到300 Prefill TPS，不能把Qwen的
吞吐直接外推；进一步重点是消除Hot交接重读、复用gate/up量化及dispatch元数据，
然后依据分项profile定位计算瓶颈。CED bounded replay仍是另一个独立近似路线。

专家调度后续已单独实现并测量：见
[dsv41f-expert-dispatch-2026-09-13.md](dsv41f-expert-dispatch-2026-09-13.md)。
共享gate/up量化及三投影dispatch元数据在本轮约+0.8%～3.6%，仍为显式实验选项。
