# DS4F / DS4.1F 当前实现优化差距审查

审查日期2026-09-14。基于当前源码和`artifacts/ds4-vs-ds41-20260914`实测，不新增推理代码或发布变更。

## 判断

差距同时来自模型结构和实现，不能由checkpoint总字节或参数比例解释。当前证据不足以给出两者对21% Decode差距各自的精确贡献。

## 模型固有成本

本地配置：DS4F dim4096、expert intermediate2048、43层、256专家/层；DS4.1F dim5120、expert intermediate2304、40层、384专家/层。当前测试每token完整Top6。

单专家三投影参数按3×dim×intermediate计算，DS4.1F为DS4F的1.40625倍；实际record_bytes=18,800,640 / 13,369,344，亦为1.40625倍。按层数修正，活跃routed-expert矩阵乘加规模约1.308倍。这不等于整模型FLOPs/TPS比例，未包括attention、router、shared experts、mHC、Engram和调度。

384对256增加了专家总库与router维度；不是每token计算所有384专家。DS4.1F Engram是按行读取，不能用510GB/160GB推导3倍推理成本。现有2048同步诊断中Engram占1.7%，仅适用于该样本。

## 当前尚未完全采用的优化

1. 默认runner逐层`mx.eval`、预算检查和日志仍开启，哪怕没有`--trace`。此前`probe_sync.py`移除此回调，保留router和覆写安全等待，129 logits逐值一致，单组6.94→7.56 TPS；尚未成为默认，不能保证每次+9%。
2. DS4 `SwitchGLU`在routes<64时不排序，大batch只建一次排序/逆序和可复用block plan。DS4.1 `expert_linear`每个gate/up/down投影重新排序，即使Decode只有6路；gate/up也各自量化相同输入。已有shared dispatch仅适用带segments的Prefill，并非Decode已复用。优先做Decode小路数不排序、一次计划复用、gate/up输入量化复用。
3. DS4有`@mx.compile` router/受限SwiGLU等，router使用argpartition取TopK。DS4.1当前全384排序，norm/rope/Sinkhorn等由多个MLX算子展开。候选是编译小函数和定制小算子，不是更改数学定义；TopK tie规则、原激活量化与FP32权重施加/归约顺序必须保留或验证。
4. DS4有专用稀疏attention/indexer/topk Metal路径及编译后的exact decode路径。DS4.1 `sparse()`按64 query Python循环、gather KV再调用SDPA，indexer显式score/relu/reduce/sort。可研究减少KV中间复制、原生indexer/topk以及适配原生attention；DS4.1有KV/index跨层共享、不同压缩/候选机制，不可原样替换。当前没有GPU时间线确认每条DS4条件分支在本轮命中，不能把所有可用kernel都称为本轮已执行。
5. DS4.1未实现Scope profile/L2预测；当前Main40由本次Prefill频次初始化，每16步最多4项/层晋升。DS4为自动Scope+Top60/Hot8，动态L1已启用但本次0晋升。二者缓存策略不同，不过本例不能把速度差归因于DS4.1命中更低。

## 实测反证：DS4.1本例并不比DS4更缺专家

DS4.1两轮均30720条Decode路由，L1命中26665、L0命中478、miss3577，总命中率88.36%；动态L1记录44次按层promotion事件（不是44个专家）。DS4正式两轮各记录16709个decode expert loads；不同计数器不直接换算成DS4命中率，但明确显示其实际专家装载次数更多。

DS4.1全run逻辑专家读取约166.82GB，DS4第一正式run计数差约319.13GB（包含Scope切换等），不能视为纯Decode或物理SSD字节。较少逻辑读取而整体更慢，支持继续定位计算/主机调度，而非只扩容L1。

DS4.1的逐层`.item()`主机决策仍在，miss还读取IDs和ages，native覆写前有eval+synchronize。DS4动态路径同样同步miss count，不能宣传DS4完全没有CPU同步。跨层block已实现但默认关闭；无L2时已测回退，不作为现成增速开关。

## 已采用或已试验、不应重复算成新优化

- 原GLM/Qwen native preadv直接写MLX统一内存已采用。
- 动态L1、Hot8、Prefill64槽双缓冲、消除Hot交接重读已采用。
- Prefill shared dispatch已有实验，历史小收益且波动；非全新方案。
- gate/up权重拼接融合历史回退约7–9%，不能直接默认开启。
- 预测L2/Metal event细粒度调度仍属未落地工作，收益未实测。

## 后续建议顺序

先将安全的逐层回调移出性能路径并重新验收；再做Decode不排序/共享量化与投影计划，随后compiled router/小算子、attention/indexer专项。各项分别A/B，继续原checkpoint、完整Top6、2048输入及65GB进程footprint边界。不要把参数比例或单组微基准推导为10TPS保证。

证据入口：
- `experiments/dsv41_mlx/{run,model,kernels,adaptive,expert_dispatch}.py`
- `experiments/dsv41_reference/metal_bank.py`
- `omlx/patches/deepseek_v4/{deepseek_v4_model,switch_layers}.py`
- `docs/dsv41f-metal-synchronization-research-2026-09-13.md`
- `docs/dsv41f-hot-direct-profile-2026-09-13.md`
- `docs/ds4f-vs-ds41f-current-performance-2026-09-14.md`
