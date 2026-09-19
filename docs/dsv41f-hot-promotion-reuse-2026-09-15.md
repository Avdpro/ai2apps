# DS4.1F Hot晋升数据复用

## 已实现

**Hot已有专家晋升到Main时，默认复用内存数据，不再从SSD读取。** Natural与Burst的晋升入口共用实现；尚未在Hot中的专家继续调用原GLM/Qwen preadv加载器。L1容量、晋升选择、频率衰减、Hot淘汰及Router/专家计算均不改变。

使用原生memcpy直接复制同一MLX bank的六段uint8专家记录，不经过NumPy/PyTorch，不进行解量化或新建整层bank。它是CPU执行的统一内存字节搬运，不是CPU模型前向，也不是新增Metal计算kernel。

复制和SSD写入前统一求值pending GPU消费者并同步；Hot源与Main目标分离，先检查全部原生复制参数。一次混合晋升仅做一次现有安全等待，全部读取/复制成功后才发布映射。原生操作失败向上传播，不用旧映射继续推理。旧native缺少复制接口时明确要求重建，不回退SSD重读。

## 验证

- 4项复制测试：源文件截空仍可完成纯Hot晋升且SSD调用为零；混合晋升只读非驻留专家；lazy消费者保留旧值；非法复制不写入；旧native拒绝且不读SSD。原LRU安全测试也通过。
- 128步完整logits和逐层事件诊断：460个Hot晋升均复制，Hot晋升SSD读取为零；路由、生成、全部logits摘要、计数、晋升名单、目标slot与旧路径一致。
- 短输入128步及2048左右输入512步各AB/BA两轮，共8次自然路径测试；每对输出完全一致，SSD读取减少字节数恰好等于复制字节数。
- Burst Top2/Block1与Top4/Block4各旧/新32步：输出、缓存及事务统计一致，分别复用96/113条专家记录。

## 性能与读取

| 用例 | 旧路径两轮TPS | 复用两轮TPS | 均值变化 | 每次少读SSD | 复用峰值GB |
|---|---:|---:|---:|---:|---:|
| coding-en-train-18 | 4.473/4.486 | 4.452/4.479 | -0.30% | 9.006GB | 55.210 |
| long-math_logic-zh-test | 4.767/4.919 | 4.761/4.708 | -2.23% | 34.706GB | 57.334 |

| 用例 | 旧native Decode I/O秒 | 新native Decode I/O秒 | 内存复制秒 |
|---|---:|---:|---:|
| coding-en-train-18 | 9.433 | 9.184 | 0.323 |
| long-math_logic-zh-test | 36.371 | 35.778 | 0.816 |

**本次没有测出TPS提升。** 内存复制本身有成本，部分native读取耗时节省被抵消；两个用例也不足以证明稳定的吞吐变化。实现的确定收益是消除已有Hot数据的重复SSD请求，不将少读字节量宣称为SSD设备物理流量或同比例加速。小样本最大峰值仍低于65GB，未检验多模态或更长上下文峰值。

## 默认与兼容

- 默认启用复用；`--promotion-reread`仅为显式旧路径诊断开关。
- `adaptive_l1.promotion_reuse`记录复制专家数、字节数、耗时与逐层统计；`expert_total_read_bytes`继续只记录SSD加载请求。
- route collector分开记录`reads`和`copies`。旧离线回放以SSD重读为基线，旧冻结trace保持有效；新复制事件用本次专用事件审计验证，不把复制算入SSD读取。
- 必须重建`artifacts/dsv41-native-build`中的扩展；本次仅实验引擎已完成，未发布Runtime或Package。

## 产物

- [汇总](/Users/avdpropang/sdk/omlx-moe-cache/artifacts/dsv41-promotion-reuse-20260915/summary.json)
- [逐层事件检查](/Users/avdpropang/sdk/omlx-moe-cache/artifacts/dsv41-promotion-reuse-20260915/diagnostic-check.json)
- [Burst回归](/Users/avdpropang/sdk/omlx-moe-cache/artifacts/dsv41-promotion-reuse-20260915/burst-check.json)
- native构建：`cmake --build artifacts/dsv41-native-build -j 2`。
- 自然路径对照：`experiments/dsv41_analysis/promotion_reuse.py`；Burst：`promotion_reuse_burst.py`。
