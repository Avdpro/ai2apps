# DS4.1F Prefill：GLM/Qwen 实现对照与 Burst 方案

本轮为源码审查，尚未实现或测量新的 Prefill 调度/Burst。现有 Burst 只影响
Decode，Prefill 保留完整 Top6。最近相同2048输入基线为106.60 TPS
（`artifacts/dsv41-tail-128-zero-control-20260913/manifest.json`），不是300TPS。

## 直接可迁移的优化

DS 当前 `experiments/dsv41_mlx/model.py::moe` 已按专家聚合token，Main先算，
冷专家每Hot8个一组，每组prepare后计算并mx.eval。底层
`experiments/dsv41_reference/metal_bank.py::_load` 每次写入先等待pending并
mx.synchronize。已采用GLM native preadv直写统一内存；缺口是调度，并非换一个
更快的文件读取API。最多344个非Main专家意味着43个冷组，加1个Main组/层。

GLM `omlx/patches/glm5_next_cache/dynamic_cache.py::_prefill_direct_locked`
使用独立scratch bank，提交当前计算mx.async_eval后加载下一个bank；重用bank
前等待该bank消费者。根据resident/direct组数选方案，避免为节省读取而增加
kernel次数。建议DS先做独立双缓冲32/64/96 slots A/B，保持Decode Main40/Hot8。
以18,800,640 bytes/专家计，双缓冲分别约1.203/2.406/3.610 GB，全模型顺序层
共用一对scratch，不是每层分配。还要计入输出和工作空间，不能仅凭静态算式
保证65GB峰值。Prefill结束释放scratch。不可直接删掉旧bank的全局同步；必须
证明加载目标没有尚未完成的GPU消费者并保持owner存活、写完再发布身份。

Qwen `omlx/patches/qwen38_next_cache/runtime.py` 默认canonical reuse和retain L1，
resident-first默认关闭：在保持原始QMM分组的前提下从Main/Hot复制现有专家，
减少重复SSD读取。3861token记录233.74→295.25 TPS；不能跨模型套用该收益。
其resident-first及过大scratch实验曾出现生成差异，因此DS变更分组、矩阵阈值
都要单独做数值验收。DS当前整块2048 Prefill已经复用Main，尚无跨chunk路径，
不能宣称迁移Qwen两个开关就有相同增益。

DS `expert_linear` 每专家>=128rows走matrix QMM，小批走gather；gate/up/down
分别做量化、排序/逆排及组装。后续可复用gate/up输入量化和dispatch元数据，
减少重复排序，再评估融合及阈值。必须保留权重进入激活量化前的DS数学位置，
不能照搬GLM在专家输出后加权的实现。先profile真实GPU时间和SSD等待，再定优先级。

## Prefill Burst

可增加独立的Prefill Top2/Top4开关，Decode策略保持独立，默认关闭。
建议按每层整块路由先规划，而非按SSD读取先后决定尾部去留：

1. 每token保留原始biased router TopN；权重仍来自原始Top6的unbiased分数。
2. 收集全批必保专家并集U，与进入该层的resident集合R。
3. 只加载U中未resident的专家；原始尾部若属于R或U则保留，否则置零。
4. 不重新归一化，不补选其它专家；省去被置零route的实际QMM行，并按原始
   expert-ID顺序归并。保留用于动态L1的完整路由统计。

这样尾部结果不会依赖分组顺序，也能复用因其它token必保而已经加载的专家。
2048个token的Top2并集可能仍覆盖多数384专家；I/O收益取决于unique expert
数，计算收益取决于实际删除route数，均不等于Top2/Top6的比例。GLM的有损
Prefill正式记录约+6.4%/+11.7%，Qwen约+3%～4%，仅作为先例，不是DS预测。

精度影响会写入整个prompt的hidden/KV/压缩状态，后续精确Decode也不会自动
消除。需对完整Prefill+完整Decode、Burst Prefill+完整Decode、完整Prefill+
Burst Decode、两阶段Burst分别验收，避免把两类误差混在一起。

## 验收顺序

先做完整Top6的双缓冲/批处理，再独立测Prefill Burst Top4/Top2，均固定2048
输入，加入非重复代码/中文样本。记录每层unique必保/加载专家数、保留route
比例、SSD字节、组数、等待、Prefill TPS、65十进制GB采样峰值；数值比较末位
Prefill logits及固定参考token的后续Decode KL/Top1，必要时逐层hidden定位。
不得用自由生成分叉后的logits作为相同上下文比较。

另有DS专属CED/decoder bounded replay路线，见已有官方实现审查文档；它属于
单独的阶段执行改造，128尾段回放不与完整40层Prefill数学等价，不混入上述
存储调度优化，也不预先计入加速承诺。
