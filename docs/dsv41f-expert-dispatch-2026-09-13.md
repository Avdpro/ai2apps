# DS4.1F Prefill专家计算调度复用

上一轮双缓冲没有实现此项。本轮新增 `experiments/dsv41_mlx/expert_dispatch.py`，
由 `--shared-dispatch` 显式启用，仅影响带segments的Prefill专家计算，Decode不变。

- gate/up共用一次输入quant及BF16转换。
- gate/up/down共用matrix/gather分区、slot排序、逆排序、gather索引与输出恢复排列。
- down仍对其独立的加权激活做quant；不改变权重进入激活量化前的位置。
- 保留每专家128行的matrix阈值、全部原Top6路由、投影顺序和累加顺序。
- 对小分区复用已经量化的对应行，避免旧混合路径再次量化小分区。

## 实测

固定2048输入、完整Top6、双缓冲64、Main40/Hot8、32步固定参考Decode。
新进程顺序运行，未控制系统page cache；不能认为小差异具有统计显著性。

| 配置 | Prefill TPS | 峰值GB | Prefill及32步logits最大绝对差 |
| --- | ---: | ---: | ---: |
| 同轮关闭共享调度 | 111.52 | 57.300 | 0 |
| 开启，第一次 | 115.53 | 57.302 | 0 |
| 开启，复测 | 112.46 | 57.381 | 0 |

相对本轮对照约+3.6%和+0.8%，收益较小、存在波动，不能作为显著加速结论。
上一轮116.19也在此波动范围附近，不能跨轮择优拼接加速比例。
独立Python短输入的Prefill+32步也逐值一致。真实专家权重下三个分支分别测试：
全小批gather（16/32行）、混合matrix/gather（128/32行）、全matrix（128/128行），
输出均逐值一致。所有模型运行输出有限、无Torch、采样峰值低于65GB。

复用减少源码层面的重复准备，但不能假定MLX原先一定重复执行每个相同GPU表达式；
当前未测得每个kernel的独立耗时。完整Prefill还包括SSD、attention、dense和Engram，
因此不把这项改动当作300TPS目标的主要解决方案。目前保留opt-in，不改变默认值。
后续独立候选是gate/up融合投影或分组kernel，但尚未实施，也不能提前计入收益。

## 复现

```sh
.venv/bin/python experiments/dsv41_analysis/test_shared_dispatch.py
.venv/bin/python experiments/dsv41_analysis/bench_shared_dispatch.py
.venv/bin/python experiments/dsv41_analysis/compare_shared_dispatch.py
```

实际推理可加 `--prefill-slots 64 --shared-dispatch`。
产物：`artifacts/dsv41-dispatch-{shared,control,repeat,code}-20260913`；每份manifest
记录源码SHA256、checkpoint哈希及HEAD、计时、峰值和逐步logits哈希。
汇总 `artifacts/dsv41-dispatch-comparisons-20260913.json` 和
`artifacts/dsv41-dispatch-kernel-check-20260913.json`。旧产物未覆盖，无生产集成。

后续gate/up融合已测试，端到端约回退7%～9%，未默认启用；见
[dsv41f-fused-gate-up-2026-09-13.md](dsv41f-fused-gate-up-2026-09-13.md)。
