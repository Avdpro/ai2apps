# DS4.1F GPU miss/resume 方案评审

参考：`/Users/avdpropang/sdk/dmoe/docs/cached-moe-gpu-miss-resume-v1.md`（状态为待实现，不是已经完成的运行时）。本轮仅阅读并评审，不修改兄弟DMoE仓库，不复制其Runtime模块。

## 判断

值得采用其执行模型：GPU连续执行命中层，在首次真正需要的专家缺失处保存continuation，结束本轮提交，由CPU处理缺失并从当前层MoE恢复。这与oracle/L2预取互补，不能由已有miss通知或普通MLX的where自动获得。高命中下主要减少逐层主机命中检查；低命中时仍可能接近逐层交接。

当前Natural路径在`model.py::moe`每层执行`mx.all(mapped>=0).item()`，全命中也读回；miss再取ID/age/评分、加载和更新映射。当前Burst的block=1同样每层检查，block=2/4整段执行后读flags，首次miss则丢弃后缀状态并从失败层的attention开始重算。新方案会把恢复点推进到Router之后，避免失败层attention/router重算及后续实质计算；但已编码的跳过命令仍可能产生尾延迟。

## DS4.1F的具体continuation

从现有layer流程保存GPU引用：当前MoE输入x、原Router expert IDs/权重（需要尾部替补时也保留原分数）、attention完成后的residual、ffn_post/ffn_comb以及供下一层使用的ffn_pre。DS4.1F有4路HC残差，不能只保存一个5120维x。当前shared expert在routed expert之后执行，第一版明确延后到恢复后的MoE尾部；不得漏算或重复。

当前层attention及压缩/index KV状态已更新，应保留并仅执行一次。恢复直接运行专家与HC post，然后进入下一层。后续层的states/shared别名、compressor缓冲、KV写入必须尚未提交；Python预先构图可能已经改字典、offset等元数据，需要暂存并按GPU完成前缀提交，不能只用GPU标志约束GPU写入。

Engram token/hash cache目前在每token入口更新一次，跨恢复复用，不能再次推进。L1 fast/slow频次、ages/ticks、统计同样要有一次性提交标志：不能每次恢复重复observe Router。miss维护所需的年龄/评分可以并入这次状态读回，避免再次逐层取host元数据。

## Natural与Burst语义

- Natural：全部Top6都驻留才继续；同层缺失一次上报，加载时保护本层全部选中专家。
- Burst Top2/4：只把required TopN缺失作为暂停条件；其余尾部沿用当前zero/zero-renorm/fixed-top/renorm定义。不能为保证尾部全部驻留而偷偷改变Burst行为。
- Burst加载时仍保护当前会参与计算的驻留尾部，与现有requested集合一致。尾部替补及归一化在映射就绪后按原语义计算。
- Natural验收对齐原无损路径；Burst验收对齐相同TopN/尾部策略的旧Burst路径，而非宣称与完整Top6相同。

## 执行与预取约束

GPU状态应是有依赖关系的执行输入/输出：RUNNING/MISS/DONE、首个miss层、resume阶段、去重缺失列表。continuation保留设备张量，CPU只接收有界状态/必要调度元数据。不能靠裸共享标志、原子写或busy spin等SSD；CPU在工作完成后发布完整权重映射，再重新提交。

全链所有算子需要条件调度/受状态保护，尤其attention、量化、gather_qmm、HC、KV写入以及logits/采样。当前Python层MX算子链没有这份文档描述的整链门控；不能把addCompletedHandler或一个检查kernel当作它的替代。应先在本仓库独立实验原生执行模块中验证，尽量复用原数学和已有kernel，避免为性能重写改变数值的前向。

本轮GPU提交引用的映射与槽位须保持稳定。后台预取可写独立、未被当前提交引用的L2缓冲；不能把此前oracle直接预写未来L0/L1槽位的技巧无条件移入这里。新权重映射在明确安全边界发布，或实现并证明更细的生产者/消费者依赖。真实L2命中若尚未发布，仍可能需要一次交接。

全命中理想情况只需末尾完成检查；若遇到M个需要CPU处理的miss断点，逻辑上为M次MISS处理加最终DONE。实际交接还受分段提交、预取发布及其它host操作影响，不能承诺整个token只有M+1次所有类型CPU/GPU交互。

## 分阶段验收

1. 单请求/单token，2–4个真实层，Prefill保留现有实现；显式选定执行模块与张量生命周期，不先实现40层。
2. 人为构造全命中、中间层单/多专家miss、恢复后第二次miss；验证在首个miss处后续attention/专家/KV没有实质执行或提交。
3. 检查HC残差、压缩/index KV、Engram、计数器/频次/年龄与旧路径一致；失败层attention/router只执行一次；读失败和容量错误显式失败。
4. 验证同一Burst配置的语义；检查尾部策略和回滚次数不混作Natural精度承诺。
5. 记录完整token延迟、主机状态交接数、实际计算/跳过命令尾延迟、SSD读取及重复计算。通过后扩展40层，再与oracle预取结合。

建议先验证此执行机制，保持L2训练暂停。不承诺减少同步后的TPS；此前oracle约6.0–6.4TPS仍保留原同步，这只是存在进一步空间的依据。
