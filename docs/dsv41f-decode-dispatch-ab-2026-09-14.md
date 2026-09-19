# DS4.1F Decode 排序/量化复用实验（2026-09-14）

## 结果与默认选择

三条路径均通过完整模型数值对照，但本组测试无可确认吞吐收益，保留legacy默认。

| 路径 | 两轮Decode TPS | 平均TPS | 对legacy |
|---|---|---:|---:|
| legacy | 7.3656 / 7.3626 | 7.3641 | +0.00% |
| shared | 7.2675 / 7.3961 | 7.3318 | -0.44% |
| unsorted | 7.3693 / 7.3737 | 7.3715 | +0.10% |

- legacy：原三个投影分别建立排序并量化。
- shared：一套排序/逆序/lhs/rhs供三个投影复用，gate/up只量化一次输入；down仍单独量化激活结果。
- unsorted：共享gate/up量化，不排序，使用sorted_indices=False直接按原路由顺序执行gather_qmm。

实现位于`experiments/dsv41_mlx/expert_dispatch.py::decode_expert`，仅当segments=None且route数不超过原TopK时使用；Prefill算法不变。Model构造器和runner新增`decode_dispatch`/`--decode-dispatch {legacy,shared,unsorted}`，manifest记录选项。

原激活量化、FP32受限SwiGLU和路由权重施加位置、BF16转换、三投影权重、完整Top6及缓存覆写栅栏均保留。已有Prefill shared-dispatch开关与本开关独立。

## 验证条件

固定2048-token科普fixture + 128步Decode（共129份logits），Main40/Hot8、动态L1、64槽Prefill双缓冲；关闭逐层回调；允许系统文件缓存。顺序legacy/shared/unsorted/unsorted/shared/legacy，各独立进程。GLM上传期间暂停，finally已恢复。不把本组与早前6.96/7.20 TPS的跨时间变化当作本修改收益。

六次运行每次129份完整logits与legacy1逐值一致，max_abs=0；input/generated IDs、cache counters、promotion记录一致。进程footprint峰值均低于57.281GB，满足65GB约束。

另运行6项真实Metal小尺寸校验：非连续独立槽位、重复槽位（Burst占位形态）、单路和零权重，shared/unsorted均与legacy输出逐值一致。仅覆盖Burst所需索引形态，不代表完成所有Burst模式端到端验收。

Prefill没有改动，但各run实测仍有约102–111 TPS波动；不能据此推导Decode策略影响Prefill。排序/量化在源码层面减少，不自动等价于端到端变快，未用GPU计数器定位抵消来源。该实验不支持将重复排序视为当前主要性能差距。

## 复现

```sh
.venv/bin/python experiments/dsv41_mlx/run.py \
  --prompt-json experiments/dsv41_analysis/fixtures/prefill2048.json \
  --decode 128 --prefill-slots 64 --decode-dispatch unsorted \
  --output artifacts/<fresh-output>
```

将unsorted换为shared/legacy进行对照。默认legacy，不因约0.1%的差异切换。下一步仍可独立研究compiled router/激活小算子及attention/indexer；本轮未实现这些方向。

原始收据、源码SHA、全部logits、比较脚本和小尺寸校验：`artifacts/dsv41-decode-dispatch-ab-20260914/`。源码py_compile与改动文件diff检查通过。仅实验代码，未发布Runtime或Package。
