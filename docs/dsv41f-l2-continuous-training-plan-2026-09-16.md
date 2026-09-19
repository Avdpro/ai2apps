# DS4.1F 预测 L2 持续优化计划

用户授权：持续采集、优化和训练，直到降低至少70%的cache miss；训练相关操作无需再次确认。目标仍未达成。

## 验收定义

- 分母使用全40层真实miss，而不是只选容易预测的后35层。原始v1的后35层结果保留为历史参考，不与新分母直接比较。
- 主要预算为全token最多48个预读，64为次级方案；96仅作曲线诊断，不以不断提高预算代替预测改进。明确报告有效读取、无效字节和读取总量。
- 首先达到独立新会话的离线有效覆盖≥70%；离线覆盖假定及时READY，是必要条件，不是实际SSD miss下降或TPS验收。真实调度截止时间与暂存兑现仍需后续实测。
- 仅用训练集拟合、验证集调参；已有v1测试集不再用于选择。最终使用未参与选择的新主题会话holdout。保留主模型原Top6与正确性，不启用Burst凑指标。

## 执行顺序

1. 缺失加权二分类目标：正样本权重16，miss位置额外4倍，保留驻留路由辅助监督；比较rank128/256。
2. 加入当前缓存驻留与上一轮路由输入；比较rank256/512，按验证集48预算的实际miss覆盖选模型，连续5轮无提升早停。
3. 分层、分任务审计剩余不可预测miss；必要时补充上一轮逐层状态/分数、token上下文等在预取时刻已知的特征，严禁使用当前轮未来信息。
4. 补充多样新主题与多轮数据。按family隔离，沿用对齐、文件哈希、miss计数与正确性门槛。
5. 验证集达到门槛后冻结候选，进行新holdout验收；未达到则继续改进，不将任务标记完成。

当前第一轮代码：`experiments/dsv41_analysis/l2_predictor/v2/optimize.py`；输出 `artifacts/dsv41-l2-v2-20260916/optimization-v2/`。训练主模型冻结，原Runtime与默认推理不变。

## 已执行与运行中的阶段

- 验证集全40层平均61.304个miss/token。理想预测的逐token预算上限：48预算最高73.68%，64预算最高88.53%，96预算最高98.95%。70%目标在48预算下要求非常接近理想排序；不隐瞒这个约束。
- 第一轮缺失加权rank128已完成，48预算验证覆盖26.65%，64预算31.01%；rank256及缓存特征对照仍在运行，最终以各自result.json为准。注意这是全40层分母，不能直接同v1后35层百分比比较。
- 已构建v3因果逐层状态采集：保留上一token各层归一化FFN输入[40,5120]，不使用下一轮尚未发生的状态。先精确对照pilot，成功才开始90序列/16512行训练与验证补采。旧测试集不重采、不用于选择。
- v3采集按训练/验证交错排序，自动在8/8序列、24/20序列、完整64/26序列时训练状态预测头；rank128/256/512仅用验证集选择。输出位于 `artifacts/dsv41-l2-state-v3-20260916/`，监督入口 `state_pipeline.py`；阶段完成不自动等于70%目标完成。
- 如逐层状态分类仍不足，将考虑利用冻结原Router权重，对下一轮逐层状态做残差预测与路由监督；当前轮状态只作训练标签，不能进入推理输入。是否采用由验证集证据决定。

## 第一轮消融完成

所有结果均为全40层验证集，不是新会话最终验收。

| 预测头 | 48预算miss覆盖 | 64预算miss覆盖 | 最佳轮 |
|---|---:|---:|---:|
| r128-context0 | 26.65% | 31.01% | 28 |
| r256-context0 | 30.12% | 34.84% | 22 |
| r256-context1 | 29.16% | 33.69% | 22 |
| r512-context1 | 31.74% | 36.52% | 19 |

独立加入缓存输入并未超过同rank无缓存输入；最高容量组合提升至31.74%，仍未达标。继续补充rank512/1024无缓存对照以区分容量与特征作用。另已预留12个新主题、24条中英文三轮历史会话，尚未生成/评测，保存在 `artifacts/dsv41-l2-new-conversation-holdout-20260916/`；候选冻结前不参与选择。

## 定向补采与状态模型初始化

验证集诊断（rank512无缓存）：988/4480个输入token未在训练中出现，miss覆盖19.65%；训练中出现20次以上的token覆盖36.89%。第25–35层中多层覆盖低于约21%。诊断输出 `optimization-capacity-v3/diagnostics-r512.json`。这支持补充训练词汇覆盖、检查深层状态信息，而非单纯反复增加epoch。

状态模型从同rank已完成的全局预测器继承权重：将10240输入矩阵拆为final-hidden和token-embedding两部分，逐层输出重排，新增上一轮局部状态及缓存分支以零初始化。数值迁移检查最大绝对差9.54e-7。部分cohort的状态训练记录会明确标注预训练使用12032行，不能把预训练收益误算成少量新增状态数据的效果。

已排队额外40条/5120行训练序列（10领域×中英文×2），保持原family分组，不挪用验证/测试。当前90序列状态实验完成后，`extend_state.py` 会执行增量采集和rank256/512训练。目标仍未达到；流水线完成标志不触发目标成功标记。

容量对照完成：rank512无缓存48/64预算覆盖32.15%/37.13%；rank1024无缓存33.26%/38.27%。增加容量仍有收益，但不足以达到70%。已转向因果逐层状态与扩充训练数据；不能把不断增大模型当成已解决信息不足。

第一批状态pilot（同一1024行训练/1024行验证，另外继承12032行全局预训练）：全量微调最佳48预算覆盖24.27%，相同会话的迁移前基线24.51%；仅训练局部状态增量（655360可训练参数）也未超过基线，最终选择epoch0，保留原能力。小样本下尚无状态增益，不宣称成功。后续训练已将未微调epoch0纳入候选，防止退化checkpoint被误选。当前状态补采已验证至少3072行，较大cohort训练与后续扩充继续运行。

## 因果结构补充实验

- 固定官方Router权重、学习下一轮FFN状态残差：12条训练和12条验证会话，使用下一行previous_ffn作为当前状态**监督目标**，不作为输入。对齐重算官方Router分数先通过误差门槛，之后训练；小样本约24%的64预算覆盖，尚无优势，不能与全量预训练头直接作公平排名。
- 以新token为query对上一轮40层状态做注意力汇总，冻结原全局预测头：小样本同会话验证没有超过epoch0，保留基线。
- 开始“当前prefix”实验：在当前token第0层归一化FFN输入已经计算完成时，预测尚未执行的后续层。这与token开始前预测属于不同调度时机；禁止把未来层状态输入预测器。第0层miss仍计入总分母，候选禁止选择第0层，后续若有效必须实测缩短后的SSD截止时间窗口。
- prefix实验使用冻结的 `prefix-cohort-1.json`，并以相同会话/相同训练轮数/相同预算训练previous-final对照；不把不同cohort结果混比。代码 `train_prefix.py`，独立新会话holdout仍未使用。

## 滚动预取与attention前探针的实际证据

固定cohort（`prefix-cohort-1.json`）的当前prefix0/4与previous-final对照均未显示明显优势；直接从零学习滚动分类也较弱。改为复用官方未来层Router、对当前层状态做归一化迁移后，提前1层的因果Top6提案在最多64次顺序预读下覆盖48.25%；提前2层39.99%。这不是一次性token头，也不是读取未来真实路由。

提前1层状态修正训练在相同2286行验证上达到51.64%，平均45.60次读取/token、精度64.20%；训练集统计未来储备量的因果补读策略最高53.48%，平均55.55次读取、精度54.59%、无效约474MB/token。文件：`router-lookahead-d1-correction-pilot/result.json`、`policy-tuning.json`。仍未达到70%，未计SSD deadline。

另外已实现pre-attention输入采样（v4）：只使用attention计算前已知的HC残差混合，令attention贡献为零来估算本层FFN输入；实际FFN只作训练目标。两条pilot的token/logits/SSD/fence均精确一致。单条128行验证会话中，零修正覆盖57.96%，训练会话均值修正65.95%（最多64预算，平均59.73次读取，精度68.14%）。这只是单会话探针，不能当作泛化成绩；更不能当作实际70%miss下降。

v4的部署限制必须保留：可用读取窗口只有attention计算，且需在attention前完成GPU预测到SSD工作线程的异步通知。当前没有实现/验证不增加阻塞GPU→CPU同步的通知机制，不能把离线准确率替代可部署验收。现扩展至20训练+20验证会话（5120行），覆盖10领域中英文，并训练均值基线上的状态修正。为避免两个约58GB模型并发，大模型采集按进程序列边界顺序调度；`preattn_pipeline.py` 暂停原collector父进程19953，完成/异常时会恢复。当前控制状态见 `artifacts/dsv41-l2-preattn-v4-20260916/serial-bulk-state.json`。原v3队列和训练扩充未取消。

## 扩大验证与新增因果特征

pre-attention 的 1024 行训练/1024 行验证（各8条会话）在cap64下覆盖64.90%，选择均值修正及0.025补读策略；神经残差训练没有超过epoch0。进一步逐维仿射、正则化、重新归一化未超过各自cohort的均值基线（该cohort63.61%）。预测分数偏置校准在1280训练/1152验证行上仍选择epoch0，覆盖64.13%、读取58.66个/token、其中37.13个有效，无效读取约404.87MB/token。不同cohort不能直接据百分比判定回退。证据分别在 `medium-correction`、`affine-pilot-v1`、`score-calibration-v1`。

已准备v5：用上一token每层attention输出代替零attention，并与当前层已知HC残差组合，估计本层FFN输入。额外保存原始previous_attention[40,5120]，以便研究token开始前预测；后者与需要当前层残差的attention_reuse必须区分。v5两会话pilot排在v4完整40会话之后，由独立监督进程按序执行、结束后恢复v3采集。仍需精确forward对照和离线评估。此特征尚无收益结果，未部署Runtime；attention前异步SSD通知的约束仍未解决。独立新会话holdout保持未使用。

## 因果预算分配首次超过70%（仍仅验证集）

`priority-cohort-v1` 固定cohort，2048行验证：原本顺序Top6在48/64预算覆盖48.91%/64.55%，64预算无效411.48MB/token。新增训练集拟合的分层/名次/分数间隔置信度表，并估计未来层更高置信度候选的数量，在当前层决策时给未来保留预算。仅训练集标签拟合表格，当前token未来层预测/真实路由均不参与当前选择。表格使用32样本平滑；预取候选最多预测Top12，但逐token严格受48/64总预算限制。

在验证集选储备系数：48预算factor1覆盖62.05%，平均47.00次读取、35.01个有效、精度74.48%、无效225.53MB/token；64预算factor1.25覆盖71.50%，平均61.03次读取、40.34个有效、精度66.10%、无效388.93MB/token。factor1和1.5分别71.17%与70.23%。这首次在扩大验证cohort跨过70%，但仍是**同层attention前的离线预取**；没有SSD及时READY证明，48主预算仍未过门槛，独立最终测试未使用，不能标记目标完成。下一步在完整cohort复核、结合previous-attention特征，再冻结候选并解决异步通知/时序部署门槛。

代码：`evaluate_early_budget.py --export-proposals`、`evaluate_priority.py`；结果与可重用置信度/未来分布在 `artifacts/dsv41-l2-preattn-v4-20260916/priority-cohort-v1/`。已修复NPZ循环重复解压，改为一次读入后计算，重复执行结果一致。

## 完整40会话复核与异步通知原型

v4已完成20训练+20验证，共5120行。完整2560行验证上，神经状态修正仍选epoch0（旧补读策略64.46%）。新置信度预算策略在完整cohort复核：cap64/factor1.25覆盖71.35%，平均61.16次读取，40.42有效，精度66.09%，无效389.97MB/token；cap48/factor1覆盖61.94%，无效225.02MB/token。与之前部分cohort接近。证据：`priority-cohort-full/priority-result.json`。仍未开启独立最终验收。

新增隔离原型 `experiments/dsv41_analysis/l2_predictor/async_mailbox/`：GPU将候选ID写入独立shared packet，注册Metal command-buffer完成回调；回调保留packet生命周期并将ID复制至带锁CPU队列，Python读取线程可非阻塞drain。通过 `mx.async_eval(packet)` 交由MLX提交，不在算子内部直接commit、不等待GPU。初版直接commit导致Metal断言，已废弃该方式；第二版尊重MLX调度通过65packet准确性检查，synthetic GPU tail中通知约1.27ms、tail结束约20.98ms，通知在tail前到达。主线程通知等待为0。

此smoke仅证明异步交付可行，不是模型attention窗口或SSD的性能证明；增加提交边界可能有开销，需要后续实际模型A/B以及READY命中验证。native bridge仅链接隔离的既有MLX构建，没有修改活动Runtime、主模型或MLX源码。v5监督正在等待原v3当前512-token序列结束，之后按原定顺序执行pilot；未强杀该采集。

## Previous-attention pilot与真实模型通知窗口

v5两条会话通过精确forward核验；128行验证中直接复用上一token attention的cap64 Top6覆盖68.27%（加0.25均值修正68.28%），精度75.73%、误读253.81MB/token。全均值修正配合训练置信度策略cap64/factor1.25为70.82%、误读339.88MB/token；cap48/factor1为61.71%。这是单会话小样本，不替代完整v4验证结果。v5已排队扩展为与v4相同的20训练+20验证，保存pilot计划，沿用不变源快照与核验门槛。

新增 `async_mailbox/deadline_entry.py` 与 `deadline_pipeline.py`，真实模型baseline/notify/baseline-repeat三组、相同输入16步Decode；通知组在attention前预测Top12并异步交付，在真实Router完成时异步交付Top6，记录CPU观察到的送达窗口。此诊断有每层两个异步提交，不能预设没有开销；暂不读取SSD、不消费L2、不改变真实路由。CPU轮询时戳可能将同批通知压缩为近零窗口，不能视为Metal硬件计时。首次runner缺少冻结采集版本的collection_roots接口而失败，输出保留；补齐roots/complete接口后使用独立 `dsv41-l2-deadline-v2-20260916` 重跑。串行监督finally恢复原v3父进程，v5扩充在此测试成功后开始。

## 真实模型通知窗口核验完成

`dsv41-l2-deadline-v2-20260916/report.json`：16 Decode×40层共640对通知；baseline/notify/baseline-repeat的input IDs、generated IDs、全部logits SHA、cache_stats、expert_read_bytes精确一致。排除前4步后TPS分别5.3831/5.3603/5.3898，通知组约低0.4–0.6%；单次短测不作稳定性能保证。CPU观察的预测送达→真实route送达中位0.619ms、p10 0.464ms、p90 0.892ms，≥1ms仅7.97%。此窗口较短，不能由离线71.35%宣称70%实际READY命中；还未做真实SSD消费。

因此把置信度/未来预算策略迁移至提前1层模型：同一2286行验证cohort，cap64/factor1.25覆盖57.06%（此前因果补读53.48%），平均60.76次读取、32.36有效、误读534.02MB/token。第0层不能预读但仍计入分母。结果 `lookahead-priority-cohort/priority-result.json`。额外因果状态试验：当前层归一化迁移 + 上一token两层之间残差，系数0.5/1.0的64预算分别55.59%/50.92%，未超过已训练修正；不使用未来层真实状态作为输入。批次末尾31/32行对齐问题在执行成功前修正，现整序列drop-last对齐。代码 `export_lookahead_priority.py`。

v5完整40会话补采已经启动；原v3父进程依既有序列边界调度暂停，完成/异常会恢复。下一步仍需改善较早时机的预测，同时验证same-layer预读是否能部分兑现，并用独立新会话作最终验收，目标未完成。

## 提前一层状态模型的结构对照

在固定2413训练/2286验证行上，用当前source FFN与上一token层间残差拟合逐特征二元ridge变换（约60万系数），ridge0.01/0.1/1/10的64预算覆盖51.86%/52.22%/53.64%/54.20%，未超过已训练共享修正+置信度预算的57.06%。模型参数只由训练序列拟合；末token无next-state标签，统一丢弃。文件 `lookahead-affine-fit` 及各 `lookahead-affine-ridge-*`。

进一步实现每层独立rank64状态残差变换，保留token/previous-final输入与冻结真实Router。相同小cohort最佳epoch2，原Top6策略覆盖51.65%；配合置信度预算56.87%，未超过共享变换。增加层间参数独立性本身没有证实收益。代码 `train_router_lookahead.py --per-layer-rank 64`，参数0保持原共享实现。

已冻结当前验证通过的54序列（28train/26validation）为 `lookahead-expanded-cohort.json`，开始顺序训练共享/逐层rank64并自动导出置信度预算评估，输出 `lookahead-expanded-r0`、`lookahead-expanded-r64`。这扩充训练数据，也扩大验证cohort，不能直接把原百分比当作同样本A/B；两个新模型彼此使用相同cohort。独立新会话holdout仍未动用，真实SSD READY门槛仍未通过。

## 扩大cohort与当前路由条件训练

54序列扩大cohort含4454行验证，共享与逐层rank64配合相同置信度预算分别55.0677%/55.0611%；该验证包含更多长会话，不能与旧2286行57.06%直接作退化判断。新增 `RoutedCorrection` 以当前source层已经可计算的Top6专家ID查表并均值聚合为低秩条件输入；不使用下一层路由。由逐层模型热启动，新增专家嵌入为零，数值迁移max-delta=0。冻结原参数、仅训练路由嵌入（lr0.001）的验证未超过epoch0，最终保持55.0611%。输出 `lookahead-expanded-route-only`，不切换默认预测器。

v5完整补采继续；已排队数据完整后的两种均值修正（0/1）+置信度预算评估，入口 `evaluate_reuse_bulk_when_ready.py`。所有模型仍只用训练/验证，未开启独立holdout。

下一项需要验证跨token保留L2有效载荷的价值：此前逐tokenproposal指标没有计入错误预取后来被使用。回放必须有严格专家槽容量与64/token读取上限，包含仅增加同容量缓存、不预测的对照，分开报告即刻命中、延迟复用和最终未使用读取；不能借此无界扩缓存或混淆容量与预测收益，也不代表SSD deadline已通过。

## 跨token L2容量回放

新增 `replay_persistent_l2.py`，在4454行、26条验证会话回放提前一层逐层rank64预测。导出专家ID并逐元素确认scores/eligible/correct/miss与既有评估相同。各会话清空L2，原L0/L1轨迹保持固定，模拟只替换SSD取数来源；cap48/64逐token断言，槽数上限448。当前source层产生下一层候选，不查看未来层真实标签来选择。**所有预读暂按即时READY，是乐观上限，未测deadline。**

重复保留foreground与prediction有效载荷时：64/128/256槽、cap64分别覆盖55.04%/56.19%/57.17%；同容量无预测缓存分别0%/0.011%/0.550%。因已用payload多数同时在L0中，L2重复占用浪费容量。

改为只保存未消费的预测payload、用中即移出L2、foreground不另存后，64/128/256槽cap64覆盖57.07%/58.54%/60.55%；256槽误读350.48MB/token，总SSD记录读取较原trace增加30.39%。这些是用时间隐藏IO的候选，不能描述成SSD总读取减少。

扩展容量与reserve系数的验证诊断：384槽/factor1覆盖62.97%，448槽/factor1覆盖63.66%，后者读取总量增加29.99%；448槽有效载荷约8.423GB，尚未确认实际总footprint低于65GB。factor1.25/448槽覆盖62.52%、读取增加25.22%。大缓存仍未达到70%，不能继续无界增加槽数。结果位于 `replay-expanded-r64/persistent-replay*.json`；输出区分即时命中、跨token预测命中、demand保留命中及最终未用预读。

## 排序训练与泛化差距诊断

当前路由条件模型改用missing-weighted Top6 softmax交叉熵（temperature0.1）+0.02状态回归，训练5轮仍未超过warm-start epoch0，因此不替换原权重。`lookahead-expanded-route-rank/result.json` 保留失败对照。

对逐层rank64同一训练置信度策略做in-sample诊断：train cap64/factor1.25覆盖67.81%，validation55.06%；训练诊断包括同数据拟合的校准表，属于偏乐观in-sample指标，不作泛化证据。这至少表明约12.75个百分点的泛化差距；并不能证明只补数据一定达到目标。新增 `--evaluation-split train` 单独输出，禁止覆盖已有验证结果和部署策略。

在既有90会话采集及40条训练扩充完成后，`train_full_lookahead_when_ready.py` 自动冻结已验证train/validation cohort、检查family不重叠，再顺序训练共享与逐层rank64并评估两种split。等待 `extension-complete.json` 以避免与原大规模训练同时争抢内存；仍不打开独立新会话holdout。

新增 `async_mailbox/ssd_small_batch_pipeline.py`，v5结束后按原collector序列边界暂停，使用原GLM/Qwen native preadv/F_NOCACHE，随机层/专家、1/2/4专家小批、交错worker组合测延迟，独立scratch仅4槽；finally恢复采集。此试验用于核查0.62ms窗口是否现实，不等于已实现L2 SSD消费。

## v5完整结果与SSD时间门槛

v5的40条会话5120行已全部采集并核验，原v3已恢复。2560行验证：原始attention复用+置信度预算cap64/factor1.25为70.70%；混合零attention估计与上一token attention（随后训练均值修正），系数0.25/0.5/0.75覆盖72.39%/72.72%/72.30%。每层单个混合系数由训练集中心化残差MSE拟合，范围0.265–0.711，中位0.484，覆盖72.83%，读取60.90个/token、有效41.26、精度67.75%、误读369.31MB/token。证据 `blend-trained/priority-result.json`。

主题family分组bootstrap（同主题中英文一起采样，10000次）：原v4均值方案71.35%的95%区间为70.68–72.02%；v5固定0.5混合72.72%的区间72.06–73.37%。均为验证集上事后诊断，不是独立验收；模型/策略选择偏差未计入区间，不能宣称泛化达标。

关键否定证据：`dsv41-l2-ssd-small-batch-20260916/result.json`，原native preadv、F_NOCACHE、无大模型同时运行，交错随机层/专家50轮、剔除前5轮。单专家1/4读取worker中位分别1.420/1.418ms，p10约0.85–0.87ms；两专家中位2.702ms，四专家5.224ms。所测小批均没有在0.62ms内完成。此为系统调用实际wall time，不是硬件裸SSD计数器；仍明显长于当前同层通知中位窗口0.619ms。**因此不能把72.83%当作可部署的及时命中率；这条同层路径的主要瓶颈现已转为提前量。**

后续以更早的预测为主，既有完整训练数据扩充继续执行。另可用仅驻留专家的近似前向作为有界的路由预测探针：必须独立保存/恢复KV与Engram状态、精确主前向不变、无预测路径SSD加载、验证输出/缓存/SSD字节完全一致，并测额外GPU工作是否值得；它只是待验证的新预测方式，不得在默认推理启用，也不承诺达到目标。

## 驻留专家近似前向预测探针

新增隔离 `experiments/dsv41_analysis/l2_predictor/resident_probe/`，仅用L0/L1驻留专家进行近似前向，不做预测路径SSD加载；保存/恢复KV、shared与Engram hash状态，再做原精确前向。GPU异步提交预测图，不为预测另加主线程GPU等待；bank.track保留预测消费者，原缓存写入安全栅栏仍有效。16-token数据库说明提示，baseline/zero/renorm/replace/block2/block4/末尾baseline的input/generated IDs、全部logits SHA、cache_stats与expert_read_bytes精确一致。前4步后baseline5.446/5.495TPS。未消费L2，速度不代表预取后的性能。

整40层近似预测：冷专家置零、全局分数间隔cap64覆盖66.57%，约4.04TPS；保留权重归一化64.28%；用较高分驻留专家补齐66.47%、3.97TPS。整轮误差累积且额外计算代价明显，均不能采用。

短块每2/4层重新从精确hidden/KV出发：块内近似预测后恢复再精确计算，候选仅按当前已产生的层顺序cap64，不使用未来块的全局排序。Block2覆盖79.00%，读取52.19个/token、有效49.63、误读48.18MB/token；Block4覆盖74.23%，读取52.50、有效46.63、误读110.45MB/token。稳态3.875/4.132TPS，峰值约54.9GB，额外计算未被SSD重叠抵消。

这些仅单提示16步诊断，不是训练/验证总体成绩，更不是独立新会话验收。下一步需真正连接异步通知、预取和精确前向消费，验证READY率、SSD竞争、内存及TPS；达到79%离线路由覆盖不能标记目标完成。入口从后续replace起保存proposal-source.py及SHA；最初zero/renorm/baseline未单独冻结wrapper，主模型模块仍来自既有冻结v4源快照。

## 真实短块预取与零拷贝消费

新增隔离 `prefetch_probe/`。每层8个额外物理槽（共320槽，payload6.016GB），不进入原逻辑40L1+8L0；按预测Top6、全token最多64个请求、异步Metal完成通知启动原native preadv。真实miss优先，取消已过期尚未读的预测。READY时把备用槽与原定目标槽的物理角色交换，原prepare发布修改后的目的槽，不做memcpy/GPU大块复制；所有原cache写入安全栅栏保留。增加单元核验，确认目的list原位更新、备用槽归属、排队取消和统计。

16 Decode固定提示的实际验收：全部生成ID/logits SHA、每token各层resident membership、真实路由、cache_stats一致，额外物理槽没有改变逻辑缓存行为。峰值约60.9GB。普通fd条件Block2：原1005miss中548及时READY、172晚到、285前台读取；Block4：695及时、33晚到、277前台，即 **69.15%及时覆盖**，不是把72.44%“及时+晚到”冒充目标。Block4后台815次读取、87次未用，误读102.23MB/token，SSD记录总读取比原miss路径增加8.66%。

含token末预取收尾等待的runner计时：Block2/4约5.352/5.500TPS，相同备用槽无预取但有近似计算分别3.906/4.111TPS。历史本提示无近似baseline约5.45–5.49TPS；不同轮次不能作为稳定速度收益。原runner step_seconds不含collection_complete，因此报告额外加上已记录tail_wait；新增timing.json对后续运行直接覆盖模型入口至collection完成（包括诊断复制）。

严格F_NOCACHE复核（`dsv41-l2-prefetch-strict-20260916/report.json`）：无预测baseline5.279/5.171TPS；Block4/5/6及时覆盖68.36%/67.46%/68.16%，加收尾等待runner约5.652/5.663/5.658TPS，误读102.23/110.45/133.95MB/token。仍只有一个短开发提示，未到独立验收，更未证明≥70%。

通知本身每token新增40个**异步GPU→CPU通知**；没有额外阻塞主线程等待预测的GPU边界，但不能声称GPU→CPU事件总次数未增加。最终部署仍要与原miss-resume合并、审计通知/同步次数及额外开销，当前不会改默认Runtime/Package。所有READY统计点在原miss安全fence之后、请求消费前，额外预测计算包含在测量中；独立holdout未打开。

## 完整状态数据与短块策略下一轮

v3原90条会话/16512行全部采集验证完成，full-r256/r512训练开始；40条训练扩充及完整lookahead训练仍按既有依赖顺序执行。新增policy_pipeline.py在lookahead-full-extended-complete.json之后串行运行，避免训练/全模型推理争抢GPU。32 decode开发提示，严格F_NOCACHE，对比baseline两端与block3/4零尾部、block4归一化、block3/4驻留替补。采用显式L2_PROBE_CANONICAL=1对齐正式路由的权重归一化与数值专家ID累加顺序；L2_PROBE_TAIL仅改变近似预测，精确主前向不变。默认实验旧行为保留，运行前冻结脚本及SHA。所有组合均检查精确logits/路由/cache membership，记录真正及时READY、late、误读、完整collection计时及footprint。当前新策略仅完成语法检查并排队，未把它们当作已测收益；独立holdout仍不打开。

## 广覆盖真实预取验证队列

完整v3状态头full-r256/r512均完成，cap64验证覆盖35.35%/37.77%（r512 best epoch7），仍远低于70%，不把扩大神经头当成已解决方案。新增development_pipeline.py：等待短块策略report后，在精确主前向和65GB gate通过者中按及时覆盖选定一个候选，冻结策略，再对现有validation的20条scope会话（10类主题×中英文）逐条baseline/candidate严格F_NOCACHE、128decode比较。报告用sum(timely)/sum(original misses)，记录late、误读MB/token、SSD总量变化、完整计时和逐会话数据；不平均会话百分比、不消费最终holdout。所有模型进程按依赖串行。该队列已启动等待，尚无广覆盖运行结果。额外40/token异步通知问题仍未解决，不能作为默认部署验收完成。

## 合并原有cache-hit回读的实验分支

### 取消预算回收与损失诊断

`analyze_gaps.py` 已运行：严格 Block4 的1005个原miss中，687及时、37晚到、102预测错误、179预测正确但未读入。旧日志不足以把最后一项精确拆成取消和预算耗尽，不能全部归因预算。16个token中6个用完原64请求配额。

隔离 Scheduler 现在回收尚处于 queued、因层截止而取消的读取预算；`L2_RECYCLE_CANCELLED=0` 保留旧行为。loading/ready/consumed不释放，因此累计实际读取与待执行读取合计仍不超过64/token。新增 admitted_requests/cancelled_requests；单元测试覆盖重复关闭不重复释放，以及70次累计入队含6次未读取消时仅有64次有效读取预约。后续尚未启动的实验使用此实现并冻结源代码，尚无覆盖率收益实测。生产Runtime不变。

新增L2_NOTICE_MODE=packed（默认仍async）：在routes_all_hit处将原单标量item读取替换为一次packed tolist，携带当前已构建短块的预测Top6 IDs；不创建额外Metal完成通知，不对未来尚未构建的块取值。线程安全HostMailbox交给同一SSD调度器。每层原cache-hit读取边界保留，预测负载/就绪时间可能使等待更长，不能仅凭次数相同宣称性能等价。packed_readbacks和extra_async_notifications_per_token写入实测产物。

新增packed_pipeline.py排在20会话开发验证之后运行，严格F_NOCACHE、32decode，baseline两端/async block4/packed block4与6；没有与采集或训练同时启动大模型。语法检查、原scheduler槽位交换/取消测试通过；packed真实模型运行尚未执行，不能宣称精确性、无新增同步或速度收益已验收。该实验不改变当前默认运行路径，最终holdout仍未消费。

## Expanded corpus complete

All 130 sequences / 21632 token-state rows are collected and have per-sequence verification receipts. `expanded-corpus-receipt.json` records split totals. Extended rank256 training is running; rank512 and full lookahead training follow serially. No final holdout opened; coverage goal not yet verified.

## Full extended training completed

Extended global-state r256/r512 validation cap64 coverage: 36.285% / 38.802%. Full lookahead shared / per-layer-r64 with train-fitted priority at cap64, factor1.25: 56.440% / 56.845%; average reads60.664 /60.132, useful34.620 /34.868, waste489.65 /474.99 MB/token. Offline, no deadline, final test unopened. Full-training completion receipt is present; strict real-prefetch policy pipeline now running. Further model scaling alone is not established as sufficient.

## 32-token strict policy comparison

`dsv41-l2-prefetch-policy-20260916/report.json`: all candidates exact primary logits/routes/logical-cache parity; footprint about60.9GB. Timely coverage block3zero62.568%, block4zero65.481%, block4renorm64.840%, block4replace65.778%, block3replace62.222%. Block4replace waste98.116MB/token, end-to-end-after4 TPS5.321; block4zero waste91.653MB/token, TPS5.465; baseline endpoints4.971/5.073TPS. Cancelled-budget recycling and canonical ordering are both enabled, so no isolated attribution. Longer32-token result is below prior16-token short-probe coverage; no70% claim. Frozen broad-development candidate=4-block4-replace by predeclared maximum-coverage rule; 20 conversation baseline/candidate validation has started.

## Broad real-prefetch validation complete

20 scope-validation conversations x128decode (2560tokens), strict F_NOCACHE, block4 resident replacement / canonical routing / cancelled-budget recycling / cap64 / 8 staging slots per layer. All exact logits, generated IDs, actual routes and logical cache membership match paired baseline. Original145024 misses:115488 timely (79.6337%),4724late,24812foreground. Background132378 reads,12166unused; waste89.347104MB/token, total decode SSD reads+8.38896%. Every conversation timely coverage73.4492%-88.4899%; peak62.021GB. Equal-length end-to-end-after4 pooled TPS baseline5.08595, candidate5.51510 (+8.44%). Full report: artifacts/dsv41-l2-prefetch-development-20260916/report.json. These are development-validation conversations, not independent final acceptance; extra40 async notifications/token remains. Packed readback comparison has now started.

## Packed delivery negative result and credit-limited early notices

32-token packed delivery passed exact parity but timely coverage block4/6 fell to37.38%/42.52%, end-to-end TPS4.650/4.769 versus baseline4.899/4.796 and async block4 5.441. Delaying prediction publication to exact-main readback loses lead time. Do not deploy this mode.

New isolated L2_NOTICE_MODE=credit keeps early asynchronous notices, but each is paid for by one already-eliminated miss-metadata readback in the same token. Exact cache-hit and miss metadata are packed into one transfer; actual IDs are masked to zeros on all-hit. Per-token credits start0, increment only on actual main miss, decrement before emitting notice; skipped predictions issue no GPU notification. Thus counted route readbacks plus async notices cannot exceed original40+actual-miss-layer count; original bank fences remain. This is a source-level invariant pending actual parity/timing checks, not yet a claim about every diagnostic readback. credit_pipeline.py is running baseline/async4/credit4/credit6/baseline, strict SSD32decode. Final holdout still unopened.

## Credit-limited notice first result

Strict32-token credit block4/6 passed exact parity. Counted route readbacks + async notices fell from baseline2262 to2147/2104. Timely48.94%/48.74%; TPS5.123/5.046 versus baseline5.046/5.039. Coverage insufficient. Added L2_NOTICE_GROUP=2 to pack adjacent predicted layers into one notice (still only spending previously saved per-token readback credits), preserving cap64 actual reads. Scheduler expands bundled messages and retains layer deadlines. credit2_pipeline now running; ordinary slot/budget tests passed. No independent holdout opened.

## Startup route reuse experiment

Two-layer credit batching short32-token results: block4/6 timely55.11%/56.94%, TPS5.360/5.189; baseline5.088/5.022. Exact parity passed, counted route boundaries1827/1797 vs2262.

New opt-in L2_CREDIT_STARTUP reuses layer0 proposal IDs (before any approximate MoE contribution) for its main hit decision, replacing that scalar readback with the existing native notification and allowing the first grouped prefetch immediately. On a layer0 miss, normal metadata readback remains; later layers retain merged hit/metadata reads. Report must verify predicted layer0 IDs equal exact main IDs for every token and exact full logits/routes/cache parity; per-token boundary accounting includes replaced scalar and retained startup metadata. startup_pipeline.py is running strict32-token comparison; no performance or acceptance claim yet. Final holdout unopened.

## Startup short comparison and wider credit validation

Startup layer0 route reuse passed per-token exact-route and full-forward/cache parity. Block4/6 group2 timely57.432%/58.963%, TPS5.412/5.332, route+notification boundaries1846/1816 vs2262 baseline; waste78.728/105.166MB/token. Baseline5.070/4.944TPS. Short coverage remains below target.

credit_development_pipeline.py launched the same20 development conversations x128decode, strict SSD, cap64 and65GB, selecting block6/zero-tail/group2/startup by maximum short timely coverage among candidates whose counted route boundaries do not exceed baseline. All per-token boundary audits, layer0 exact route audits, full logits/cache parity and memory checks remain required. No held-out final conversation used.

## Credit validation complete; independent acceptance started

20x128 validation complete:102205/145024 true misses timely=70.4745%;5608late,37211foreground;119253background reads,11440unused; waste84.01536MB/token and totalSSD+7.88835%. Route+notification boundaries178985 baseline vs147597 candidate; peak61.850GB. Pooled after4 end-to-end TPS4.99064 vs5.41928. Exact logits, generated IDs, full routes/cache membership and startup route audits passed. Margin over70% is small; final success unproven.

Candidate frozen before opening reservation in artifacts/dsv41-l2-final-credit-v1-20260916/frozen-candidate.json: block6/zero tail/credit group2/startup/canonical, cap64 actual reads and320 physical staging slots,65GB. Isolated entry/resident/scheduler/bank source copied and hashed; frozen base model Python sources hashed and checked before every case. Entry resolves its resident predictor relative to its own frozen directory.

Independent24 authored bilingual multi-turn histories /12 new families now run paired exact baseline/candidate, maximum256decode and stop-at-EOS (do not inflate coverage with post-EOS tokens). All cases required; no test-time tuning or exclusions. Final report must aggregate all actual decode misses, separately report late reads, waste, totalSSD, TPS, memory and per-token boundary limits. Driver verifies frozen source and fixture hashes. This consumes the reserved final holdout; it cannot subsequently be used to select improvements. Acceptance running, not complete.

Final aggregate audit helper added: `experiments/dsv41_analysis/l2_predictor/prefetch_probe/audit_final_acceptance.py`. It refuses incomplete evaluations, rechecks frozen sources, fixture hashes, family separation, precision, strict SSD reads, per-token budget/boundaries and memory. Pooled TPS uses actual measured token counts and total elapsed time; uncertainty uses a fixed-seed 10,000-resample family-cluster bootstrap (descriptive only, not a new acceptance threshold). Syntax check passed; actual final audit awaits all24 cases. At this update10 cases are verified and case11 candidate is running. No intermediate coverage inspected or candidate tuning performed.

## Independent acceptance completed

All24 cases /12 unseen families /6144 decode tokens completed; driver exit0 and final audit pass. Timely240503/342075=70.3071%, late12996, foreground88576; unused26806=82.02636MB/token; total expert SSD reads+7.8363%. Full-timing pooled TPS5.13517→5.51728 (+7.4411%), sampled footprint62.97124GB. Exact output/routes/logical-cache parity, cap64 per-token actual reads and counted route-boundary limits passed. Family-bootstrap95% interval69.8120–70.8503%; empirical aggregate meets70%, but margin small and not every conversation meets70%. All cases reached256 despite EOS stop enabled. Full scope, limitations, reproducibility and completion evidence: `docs/dsv41f-l2-independent-acceptance-2026-09-16.md`. Effective candidate is resident-only approximate-forward prediction, not the trained small matrix; production Runtime remains unchanged.
