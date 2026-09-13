# DS4.1F Prefill gate/up融合投影实验

2026-09-13。结论：当前MLX MXFP4在线拼接融合没有端到端收益，保持默认关闭。

## 实现与边界

`--fused-gate-up` 隐含启用shared dispatch，仅用于Prefill。按输出行维度拼接
原gate/up的packed权重和scale，执行一次投影，然后拆开gate/up继续原clamp、
SiLU、路由权重和down量化路径。没有反量化重编码或改变原始权重值，也没有
改写SSD专家仓库。Decode仍使用原路径。

第一版对整bank拼接。第二版仅取本组最大使用slot之前的前缀，排除未使用的
尾部slot；不重映射中间空洞。当前代码为第二版，manifest记
`gate_up_pack=used-prefix-v2`。旧测试源码哈希保存在各自manifest，未覆盖产物。
临时拼接成本计入Prefill计时和进程内存，不以预处理方式从总耗时中扣除。

## 完整模型A/B

2048-token固定输入、32步固定完整参考Decode，Main40/Hot8、双缓冲64、完整Top6。
控制组已启用shared dispatch。每组新进程、串行运行，系统page cache未主动清空。

| 配置 | Prefill TPS | 相对同轮对照 | 峰值GB | Prefill+32步logits最大差 |
| --- | ---: | ---: | ---: | ---: |
| 分离gate/up对照 | 111.79 | — | 57.218 | 0 |
| 整bank融合 | 102.46 | −8.35% | 57.302 | 0 |
| 整bank融合复测 | 101.67 | −9.06% | 57.300 | 0 |
| 使用前缀融合 | 103.43 | −7.48% | 57.141 | 0 |

整bank融合的独立代码短输入Prefill+32步也逐值一致。所有运行输出有限、无Torch、
采样峰值低于65十进制GB。融合开关没有成为默认，未进行生产集成。

## 排除在线拼接的小规模投影诊断

使用layer0的8个真实专家，gate/up拼接权重和输入量化在计时前完成。交替运行
两种投影，每种预热2次后采样10次；计时含Python提交、排列及输出形成，不是
Metal硬件计数器的纯kernel时间，不含SSD、在线拼接、down或其它模型模块。

| 每专家行数 | 分离投影ms | 融合投影ms | 解释 |
| --- | ---: | ---: | --- |
| 16，gather | 1.920 | 2.022 | 融合约慢5.3% |
| 128，matrix | 1.720 | 1.670 | 融合约快2.9% |
| 256，matrix | 2.607 | 2.591 | 差异约0.6% |

三种输出逐值一致。这只是单层小规模诊断，但没有显示足以覆盖在线拼接成本的
明显优势；不能由此宣称重建预拼接SSD仓库会显著加速。当前不推进整仓重建。

另外用4-slot bank、只访问前2个专家，覆盖全gather、混合matrix/gather、全matrix
三个分支，验证第二版裁掉尾部槽位后仍逐值一致。

## 产物与复现

- `experiments/dsv41_analysis/bench_fused_gate_up.py`：控制、融合、复测、代码对照。
- `experiments/dsv41_analysis/compare_fused_gate_up.py`：逐步logits/KL/Top1检查。
- `experiments/dsv41_analysis/test_fused_gate_up.py`、`test_fused_compact.py`：真实权重分支验证。
- `experiments/dsv41_analysis/bench_fused_projection.py`：预拼接投影诊断。
- `artifacts/dsv41-fused-{control,fused,repeat,code,compact}-20260913`。
- `artifacts/dsv41-fused-comparisons-20260913.json`、
  `artifacts/dsv41-fused-projection-diagnostic-20260913.json`。

当前源码重新运行benchmark会使用第二版；第一版以对应manifest源码哈希和保存的
逐步结果为准。第二版完整模型复现：

```sh
.venv/bin/python experiments/dsv41_analysis/run_prefill_probe.py \
  --reference artifacts/dsv41-default-dynamic128-20260913 \
  --prompt-json artifacts/dsv41-benchmark2048-prompt.json --decode 32 \
  --prefill-slots 64 --fused-gate-up --output <fresh-output>
```

接下来更合理的候选是消除已确认的Hot交接重复读取，或根据整模型分项profile
定位其它瓶颈；本实验没有实现这些后续候选。
