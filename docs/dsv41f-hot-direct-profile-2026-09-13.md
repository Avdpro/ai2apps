# DS4.1F 消除Hot重读与Prefill分项profile

基于Tag `dsv41f-mlx-baseline-v2-20260913` 的后续实验。旧Tag未改动。

## Hot交接

原双缓冲先在scratch读取并计算全部冷专家，再为Decode重读最后Hot8。
新路径将最后8个冷专家从scratch分组排除，在所有Main/scratch消费者结束后，
一次读入Hot并计算其贡献。输出按原expert-ID顺序恢复；保留相同Hot工作集和
LRU专家身份顺序，物理slot编号不是身份约束。仍使用原native loader安全栅栏。
双缓冲启用时默认使用新交接；`--prefill-hot-reread` 恢复旧对照。总默认
`--prefill-slots 0` 没有变化。SSD原始仓库、权重和Decode前向未改。

2048输入、32步固定参考Decode，Main40/Hot8，完整Top6、64-slot双缓冲：

| 配置 | Prefill TPS | 全run专家逻辑读取GB | 峰值GB |
| --- | ---: | ---: | ---: |
| 同轮旧交接对照 | 109.93 | 122.298 | 57.304 |
| 直接Hot首轮 | 109.51 | 116.282 | 57.302 |
| 直接Hot复测 | 110.33 | 116.282 | 57.297 |
| 最终版含轻量计时 | 108.38 | 116.282 | 57.298 |

读取固定减少 **6,016,204,800 bytes**（6.016十进制GB），即40层×8专家×18,800,640。
这些是API逻辑读取量，未清空系统page cache，不是物理SSD冷读字节。
所有候选的Prefill及32步Decode logits逐值一致，逐层cache hit/miss计数也一致。
独立代码短输入同样通过；双阶段Top2与原对应Top2参考也逐值一致、计数一致，
本轮133.16 Prefill TPS。该一致性不把Burst变成相对完整模型的无损算法。

没有显著TPS改善：候选结果在对照附近波动。专家compute分组从原117增至149，
因为独立增加Hot终组；额外调度可能抵消部分收益，当前不能定量归因。不要仅因
减少6GB读取就宣称加速成立。所有运行输出有限、无Torch、峰值低于65GB。

## 同步分项profile

`profile_prefill.py` 在方法输入准备和输出完成处显式求值并同步，按调用栈记录
逐层inclusive/exclusive时间；独占时间可加，包含子调用的时间不能重复相加。
输入延迟求值计入父调用。记录函数墙钟时间，不是Metal GPU硬件计数器测量。
Storage raw包含读取、CPU字节准备和上传/数组求值，不能全部视为物理SSD耗时。

固定2048、Decode=0的诊断forward为 **20.372秒**，与不带profile的TPS分开报告：

| 顶层部分 | 包含子调用的秒数 | 占诊断forward |
| --- | ---: | ---: |
| MoE | 13.004 | 63.8% |
| Attention | 5.137 | 25.2% |
| Engram | 0.347 | 1.7% |
| 其余主干、归一化、输入输出等 | 1.885 | 9.3% |

MoE内部另有以下**包含关系**：

- 专家native I/O计数器合计6.448秒，其中scratch读取3.966秒。
- routed expert计算调用合计4.331秒，包含其三投影、量化及激活。
- shared expert合计0.569秒。
- cache bank load+fence方法合计2.485秒，已包含在MoE及native I/O关联路径中。

这些不能与13.004秒相加。attention的5.137秒包含相关投影、压缩、index等，
没有重复计入主干其它类别。递归expert_linear的inclusive总和也不可直接作为
三投影独占GPU时间。完整原始调用表保存在profile.json。

验证所有exclusive之和恰为20.372秒，profile的Prefill末位logits与原完整参考
逐值一致。同步会改变计算/读取重叠，因此该分解用于定位，不用来预测异步TPS。

## 正常异步路径轻量计时

最终完整Top6运行的40层dispatch合计8.091秒（不覆盖整个MoE/forward），其中：

| 字段 | 秒数 | 含义 |
| --- | ---: | --- |
| submit_seconds | 2.187 | Python分组、建图与async_eval提交，不是GPU计算时间 |
| scratch_wait_seconds | 0.00023 | 覆盖scratch前等其消费者完成 |
| drain_wait_seconds | 0.766 | Main/scratch末尾和Hot计算末尾求值等待 |
| hot_handoff_seconds | 0.449 | 原bank.prepare，包含读取和安全栅栏 |
| assembly_seconds | 0.243 | 输出位置恢复及求值 |

未列余项包含scratch读取、路由metadata、初始化等。读取时GPU可以计算，以上
墙钟项不能用于推导GPU利用率或把native I/O与GPU时间简单相减。scratch重用
等待很小，当前证据不支持把主要问题归因于双缓冲被反复覆盖阻塞。

当前结论：Hot重读已消除且数值/缓存身份保持；吞吐尚无显著改善。下一步应关注
MoE中读取/调度的重叠和attention成本，而不是继续盲目融合gate/up投影。

## 复现与产物

```sh
# 无profile性能路径
.venv/bin/python experiments/dsv41_mlx/run.py \
  --prompt-json experiments/dsv41_analysis/fixtures/prefill2048.json \
  --decode 32 --prefill-slots 64 --output <fresh-output>
# 旧交接对照额外加 --prefill-hot-reread

# 独立同步诊断，不能把其TPS当性能gate
.venv/bin/python experiments/dsv41_analysis/profile_prefill.py \
  --prompt-json experiments/dsv41_analysis/fixtures/prefill2048.json \
  --decode 0 --prefill-slots 64 --output <fresh-profile-output>
```

对照脚本 `bench_hot_direct.py`、校验脚本 `compare_hot_direct.py`。
`artifacts/dsv41-hot-direct-{first,control,repeat,profile,final,code,both}-20260913`
保存manifest和trace；同步profile在profile目录的profile.json，记录诊断脚本哈希。
`artifacts/dsv41-hot-direct-comparisons-20260913.json` 保存逐步比较、计数校验及
正常异步计时汇总。所有旧产物保留。本轮没有生产Runtime集成。
