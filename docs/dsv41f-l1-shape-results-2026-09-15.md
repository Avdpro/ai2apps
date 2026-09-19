# DS4.1F 逐层L1形状执行报告

## 结论

按用户要求完成采样、回放、形状求解和接入验证。性能验收由原60例×4次缩减为5例×4次；候选与Main40逐步输出完全一致。小样本宏平均Decode为 **4.471 → 4.434 TPS（-0.82%）**。保留Main40默认；本轮不宣称通过完整统计采用门槛。

## 完成范围

| 项目 | 结果 |
|---|---|
| 1. 数据清单与冻结 | 300条：180训练、60验证、60封存测试；10任务组、中英文 |
| 2. 路由采样与因果回放 | 300条Main40采集；20例×32/40/48共60次真实校准；五档容量回放 |
| 3. 初始L1形状 | 40层各32/36/40/44/48，总Main1600；Hot每层8；验证集选择后冻结 |
| 4. 接入与检查 | opt-in形状加载、长Decode精度、持续对话、20次缩减性能测试；默认未改变 |

原240次运行主要用于跨任务性能稳定性与回退统计，并非精度检查所必需。用户指出成本偏高后，停止大批次，保留11次完成结果，补齐1次短任务和8次长输入对照。被用户主动中断的1次运行单独归档，不计作推理故障。未查看性能成绩来挑选新增用例：从未覆盖任务组中按固定ID哈希选择中英文各一个2048输入，选择理由与SHA已落盘。没有在测试后重新拟合候选。

## 候选形状与回放

```json
[48, 44, 44, 44, 44, 44, 36, 40, 40, 36, 36, 40, 40, 48, 40, 48, 36, 40, 44, 48, 36, 40, 44, 48, 36, 32, 32, 36, 32, 32, 32, 32, 36, 36, 36, 40, 40, 44, 48, 48]
```

总Main槽位1600，Hot320槽，专家有效载荷约36.098GB；该数不包含主干、KV、scratch等。专家身份继续根据当前Prefill初始化并动态晋升，容量固定。未引入机动池、预测L2、Burst或Block。

验证集每token加载量变化 **-0.399%**，含miss的layer-step变化 **+0.480%**。减少少量读取不代表减少GPU到CPU等待，这也是不能仅靠命中率判断吞吐的原因。

![容量与训练集读取取舍](/Users/avdpropang/sdk/omlx-moe-cache/artifacts/dsv41-l1-shape-20260915/candidate/allocation.png)

## 精度与内存

60次校准覆盖307,200个layer-step，真实计数、读取专家和物理slot与因果回放完全一致；三档容量的路由和全部logits摘要一致。中英文各4096左右输入、512步Decode，Main40/候选共4次，保留全部logits并通过一致性检查；再完成8次F_NOCACHE控制。

中英文四轮持续会话各验证Main40/候选：同Model保留KV、Engram和bank，跨过128-token注意力窗口，每步输出与缓存事件一致。这是实验引擎逐token追加验证，尚不是Runtime服务或chunked incremental Prefill验收。

20次性能运行共核对4,116份logits摘要，生成token全部相同。采样峰值58.631GB，20次性能运行两种方案最大峰值57.352GB，均低于65十进制GB。

## 小样本配对性能

每个用例两轮AB/BA，表中TPS为两轮均值。所有完整运行保留；没有挑选最快成绩。总体按五例等权平均，仅作初步判断。

| 用例 | 输入/Decode | Main40 TPS | 候选TPS | 变化 |
|---|---:|---:|---:|---:|
| general / zh | 27 / 128 | 5.020 | 4.996 | -0.49% |
| coding / en | 32 / 128 | 4.145 | 4.162 | +0.42% |
| medical_health / en | 68 / 128 | 4.377 | 3.873 | -11.52% |
| math_logic / zh | 2083 / 512 | 4.720 | 5.059 | +7.18% |
| science_engineering / en | 2087 / 128 | 4.094 | 4.083 | -0.27% |

**重复运行波动：** medical_health基线两轮约3.999/4.756TPS，math_logic基线约5.077/4.363TPS。相同方案内部已出现明显波动，因此表中的−11.52%和+7.18%不应被解释为稳定回退或提升；现有native I/O计时与OS读取量不足以解释全部差异。按用户缩减要求不继续扩测，不给因果归因或置信区间。五例−0.82%也只是本批描述值。

本表使用实验runner的自然完整Top6路径、Prefill bank64、Main40/分层容量、Hot8，其他参数一致。它是此组真实题材fixture的缓存容量对照，不代表Burst或重复提示fixture下的最高TPS。

| 五例宏平均指标 | Main40 | 候选 |
|---|---:|---:|
| 前16步Decode TPS | 2.7085 | 2.6310 |
| 尾段Decode TPS | 4.9152 | 4.9444 |
| 路由命中率% | 70.9036 | 71.0435 |
| 全命中layer-step% | 18.3633 | 18.0020 |
| 每例晋升读取专家数 | 1317.2000 | 1325.0000 |
| 每例路由miss数 | 14100.2000 | 14049.6000 |
| 每例native Decode读取秒数 | 15.0793 | 15.0367 |
| 每例OS记账Decode读取GB | 138.2204 | 137.9785 |

尾段：128步取后64步，512步取后128步。native读取时间含miss与晋升I/O，不是完整GPU/CPU同步成本；不与其他wall时间直接相加。Darwin磁盘读计数是OS记账流量，不代表SSD设备总物理字节。

### 2048输入Prefill与长Decode

| 用例 | Main40 Prefill TPS | 候选Prefill TPS | Main40 Decode TPS | 候选Decode TPS |
|---|---:|---:|---:|---:|
| math_logic / zh | 65.109 | 65.016 | 4.720 | 5.059 |
| science_engineering / en | 65.503 | 65.819 | 4.094 | 4.083 |

### F_NOCACHE控制

仅对专家文件描述符设置Darwin F_NOCACHE，不清全局文件缓存；不能保证所有读取都是物理SSD读取。每个用例每方案两次，结果与正常路径输出一致。

| 用例 | Main40 Decode TPS | 候选Decode TPS |
|---|---:|---:|
| long-general-en-validation | 3.893 | 4.083 |
| long-general-zh-validation | 4.410 | 4.443 |

## 局限与后续

240条原生短输入21～74tokens；60条长输入为不同编号事实记录组成的合成证据审查任务，约2048/4096tokens，不能代表真实长代码、完整生产业务或多模态。300条采样均无提前EOS。原740条中排除140条跨题材组合题，按中英文主题家族重分，避免父任务泄漏；模板仍有共性。旧ID保留原split字样，冻结manifest中的split字段才是最终划分。

当前只做5个封存用例的初步测速，没有完成60用例统计验收，不给置信区间、不声称跨任务稳定提升。保持统一Main40默认，候选仅可显式加载。若未来要改默认，再使用新的独立数据确认收益；本轮不再扩测来追逐微小差异。

机动L1需要独立的共享内存池设计；本轮静态配额的读取改善较小，尚不足以证明它值得优先实现。没有发布Runtime或模型Package。

## 产物与复现

- [冻结数据清单](/Users/avdpropang/sdk/omlx-moe-cache/artifacts/dsv41-l1-shape-20260915/dataset/dataset-manifest.json)
- [候选及SHA](/Users/avdpropang/sdk/omlx-moe-cache/artifacts/dsv41-l1-shape-20260915/candidate/frozen.json)
- [完整20次性能指标](/Users/avdpropang/sdk/omlx-moe-cache/artifacts/dsv41-l1-shape-20260915/limited-results.json)
- [最终审计](/Users/avdpropang/sdk/omlx-moe-cache/artifacts/dsv41-l1-shape-20260915/final-audit.json)
- [缩减理由与选样规则](/Users/avdpropang/sdk/omlx-moe-cache/artifacts/dsv41-l1-shape-20260915/limited-selection.json)
- [校准](/Users/avdpropang/sdk/omlx-moe-cache/artifacts/dsv41-l1-shape-20260915/calibration.json)、[长精度](/Users/avdpropang/sdk/omlx-moe-cache/artifacts/dsv41-l1-shape-20260915/qualification.json)、[持续会话](/Users/avdpropang/sdk/omlx-moe-cache/artifacts/dsv41-l1-shape-20260915/persistent-qualification.json)
- [源码快照](/Users/avdpropang/sdk/omlx-moe-cache/artifacts/dsv41-l1-shape-20260915/source-snapshot/manifest.json)

运行入口：`experiments/dsv41_analysis/l1_shape/limited.py`复用完成结果并补齐缩减测试；`limited_report.py`生成本报告。原`pipeline.py`保留完整240次方案，不应为复现本次小样本结果直接重启它。
