# DS4.1F 官方源码与 Qwen/GLM 缓存优化对照

日期：2026-09-13。仅源码审查、safetensors header 统计与文件完整性复核；未运行 DS4.1 推理，未修改运行时。HEAD：`11b5b9ac537e42b1029d1f0148bbbe6a33307f8e`，当前工作树另有其他工作。

## 下载与证据

ModelScope `deepseek-ai/DeepSeek-V4.1-Flash` 已于北京时间 2026-09-12 18:54:25 完成：89 个非空文件、48 个 safetensors 分片、510,313,354,155 bytes。本日再次逐文件比对下载前文件清单，大小均匹配。分片索引检查已完成；未声称本次重读全部 510 GB 做 SHA-256 校验。

路径：`artifacts/dsv41-download/DeepSeek-V4.1-Flash/`。
实际张量统计及四个关键配置/源码文件 SHA-256：`artifacts/dsv41-download/tensor-inventory.json`。统计只读取 header，没有实例化大模型。

对照资料：

- `docs/qwen38-next-cached-moe-checkpoint-2026-08-28.md`
- `docs/glm5-3-cached-moe-optimization-2026-08-28.md`
- 下载中的 `inference/model.py`、`inference/engram.py`、`inference/kernel.py`、`inference/convert.py` 与两个 config。

## 结论

首选 **原始精度 Engram SSD 行读取 + 原生 FP4 专家固定槽位存储 + GLM Main/Hot 管理 + Qwen canonical Prefill 思路 + DS4.1 独立计算与 KV 状态**。

不先做 2-bit。现有 DS4F SwitchGLU 已有 group32 MXFP4、U32 packed weight、U8 scales 的执行路径，可以调查复用；但其激活、加权和归约不能未经验证视为官方等价。GLM/Qwen 的 affine Q4 store wrapper 不可直接读取原始 FP4。

## 1. 真正占空间的是哪些部分

48 个分片共 96,085 个张量，按实际 data_offsets 统计（GiB = 2^30 bytes）：

| 部分 | 实际存储 GiB | 优化方向 |
|---|---:|---|
| 主干 routed experts | 268.945 | 磁盘完整保存；Main/Hot 只驻留少量专家 |
| 两层 Engram 表（含 scale） | 188.833 | 原生 FP8 按行读，不整表驻留 |
| 其他主干参数 | 9.170 | 优先常驻；展开/重排后内存需重新统计 |
| MTP | 7.388 | 首轮文本参考不加载、不执行 |
| 视觉及 aligner | 0.904 | 首轮纯文本不加载；后续独立接入 |

所以“510 GB 文件意味着先要 512 GB RAM”不成立。大头适合分别按专家、按行访问。这里的 9.170 GiB 是 checkpoint packed 大小，不是实现后的 dense resident 内存保证。

主干共有 40×384=15,360 个专家。每个专家原始三组 weight/scale 合计 **18,800,640 bytes（17.930 MiB）**。无需反量化就能按原始六段组织 expert-major store；是否能直接进入当前 MXFP4 kernel，要验证低/高 nibble 顺序、scale 格式、行宽、目标形状及 activation 语义。

原生 FP4 下，40 层每层总槽位 40/56/72/88，专家 bank 分别约 28.02/39.22/50.43/61.63 GiB。总槽位包括 Main 和 Hot，不包括 scratch、dense、Engram cache、KV 和激活。它们是容量算术，不是机器适配或峰值承诺。

若另做 affine group64 且 scale/bias 各 2 bytes，则专家记录 Q2 为 10.547 MiB，Q4 为 18.984 MiB。Q4 affine 甚至比源 FP4 记录更大，不能把重新量化当作无代价重打包。

## 2. 优先级最高的语义差异：先权重，再 down projection

官方 `model.py:841`：

1. w1/w3 投影；FP32 SiLU 和截断；
2. 中间激活乘 router weight；
3. cast 回输入 dtype；
4. w2；对 FP4 权重，`linear:181` 还会先做 FP8 activation quantization；
5. `MoE:889` 按专家 ID 遍历，在 FP32 输出上逐专家累加，最后加 shared expert。

因此 `w2(weight*h)` 与 `weight*w2(h)` 在这里不保证相同：中间存在舍入和动态激活量化。PipeNetwork/现有通用缓存的 projection 后加权不能直接宣称数值等价。即使只保留 Top6 路由顺序也不等于官方单 rank 的专家 ID 累加顺序。

应提供 DS4.1 专用专家计算入口，把已选专家权重传到 down 前；原始参考分支保留量化点与累加顺序。融合/重排分支逐层测误差、argmax 和长链路输出。CPU/MLX 移植与官方 CUDA 不保证 bitwise 一致，必须明确误差标准。

## 3. 专家存储：GLM 的机制，V4.1 的布局

复用固定容量 Main/Hot、SLRU batch pin、物理写完才 publish tag、原生 Direct-L1、命中计算与 miss I/O 重叠。确保槽位最后一个 GPU 使用者结束后才能覆盖；I/O 失败应终止当前计算并使受损槽位失效，不继续用旧 tag 掩盖部分写入。

不要复制 GLM Main80/Hot16 或 Qwen Top160/Hot10 数值。V4.1 单专家更大，必须按字节预算扫描。起步可比较 Main32/48/64 + Hot8，再在同总预算下换 Hot6/8/12；这些只是待测档位。

动态全命中仍有 miss-count `.item()` 同步，不能称 no-sync。先让缓存路径正确并测出 host sync 占比，再优化 native route planner。不要先写丢掉动态 miss 检查的快路径。

最坏全部 miss 的 decode 每 token 读 40×6×18,800,640 = **4.512 GB** 原生专家数据。若实际专家 miss 比例为 m，近似数据量为 4.512×m GB/token，另加 promotion/预热等。真实 TPS 还受随机读取、计算与同步影响；这是成本模型，不是 TPS 预测。

## 4. Engram：保留原始表，优化访问

官方 `model.py:296` 已是“索引后只解量化选中行”，但整表作为 parameter 存在。用磁盘行 reader 替代这一存储，不改 Engram 门控。

两层每 token 共 48 行，每行 256 FP8 bytes + 8 scale bytes，逻辑读取量 12,672 bytes。实际页读取放大须测。相对于专家 miss 的 MB 级记录，Engram 首要问题是随机请求延迟和同步，不是逻辑字节吞吐。

执行策略：token 一旦已知，统一计算两层 hash IDs → 去重/按页合并 → 批量读取 → 小型限额行 cache → 恢复原行序 → 官方 FP32 解码及 scale 乘法 → BF16 → wkv/gate。

第 1 层可与 embedding/第 0 层计算重叠，第 14 层可更早预取。Prefill 输入 chunk 已知，可以提前安排整块读。不同类型的 I/O 需联合限流，防止专家队列挡住 Engram 小读。

必须保留 `engram.py:160` 的 compressed vocabulary、序列起点和 DEAD image-span 规则。顺序生成可将完整历史改为最后 3 个 compressed IDs 加位置；支持回滚/恢复时必须保存对应边界历史，不能复用未来 token。Qwen mmap 只有按行读，没有这些 DS 特有语义和完整预取/限额缓存。

Qwen 文档的 PLE-off 实验反而增加专家 SSD 读取 12.2%、降低长 decode TPS 2.2%，进一步支持“优化表访问，而非跳过表计算”；这不是 DS Engram 的性能实测。

## 5. Prefill：不能只调 chunk 参数

官方 minimal reference 只有 `start_pos==0` 的整块 prefill 与后续单 token 分支：`Compressor:458`、`Attention._window_kv:703` 使用 squeeze/单 slot 写入。不能直接把非零 offset 的多 token chunk 传入并假设支持。

第一步补任意 chunk 的 compressor remainder、SWA ring、可见性 mask、位置和 Engram 历史，覆盖奇数/偶数边界。再采用 Qwen canonical grouping + L1 reuse + retain-L1，避免因为命中层级不同而改变计算形状。GLM resident-first 和双缓冲保留为 A/B，不能依据 GLM 成功就默认适合 DS。

分组工作区按 bytes 限额。GLM 208-expert bucket 在 V4.1 原生 FP4 下单 bank 约 3.64 GiB，双 bank 约 7.28 GiB，尚未计激活。phase 结束及时释放 scratch。增加 chunk 可减少重复专家读取，但中间 attention/indexer 内存可能上升，需联合扫描。

## 6. KV/attention：官方参考也不是 packed KV serving 实现

owner 层为 2/8/14/20，index source 为 2/8/14/20/24/28/32/36；其余层复用。保留 owner 状态一次，通过请求内引用连接消费者。

官方 `kernel.py:184` 的 `fp4_act_quant(..., inplace=True)` 把反量化值写回原 tensor；`model.py` 将其放入普通缓存 buffer。它本身也不能代表官方产品 packed KV 的 bytes/token。

另有两处值得后续优化：

- `Attention.forward:765` 每层 cat(window, compressed cache)，可研究 sparse attention 双源读取，消除长 cache 拼接与复制。
- `Indexer:527` 先生成所有位置的 scores，再 mask candidate；可研究在后续 index source 只 gather candidate positions 并分块评分，避免大中间张量。保留负权重、mask、top-k ties 和位置排序语义。

需要先明确 source 选择：当前官方 `Indexer` 仅在 latent 非空时更新全局 `shared_attn.index_k`。ratio2 未成组的 decode 步可能仍指向上一轮末尾 owner 的 keys。这是应复现和隔离的参考实现疑点；不能直接用“修复后参考”作独立真值，需保存原版/owner-explicit 的差异证据。

共享状态必须 request/model-owned，不能把官方 one-model-per-process 全局对象直接搬进多会话 engine。完整快照包含 SWA、compressed/index owner、partial groups、offset、Engram 边界历史；MTP 以后再补接受/拒绝回滚。

### CED：Prefill 与 Decode 的阶段差异（技术报告核对后修订）

官方技术报告第 9 页 §2.2、第 20 页 §3.2.2 明确区分完整参考与生产执行：每个主干 MoE 层仍是 384 选 6，并非 Prefill Top3、Decode Top6。长 prompt 的完整序列主要经过前 20 层 causal encoder；后 20 层 decoder 的 global KV 由 encoder 最终 hidden states 投影得到。每个 decode token 仍经过完整 40 层。这是官方 Prefill 约 8B、Decode 约 16B 激活参数的来源。

Decoder 本地 SWA 仍需要各层 hidden states。官方 Decoder SWA Bounded Replay 在每次 Prefill 时把末尾 `n_win=128` 个 prompt token 的 encoder 输出送过 decoder，截断回放段之外的 SWA，建立 decode 所需状态。因此不能完全跳过 decoder，也不能只保留 encoder 权重。报告明确指出该状态**不与完整 decoder forward 数学等价**；其“质量影响很小”是官方实验结论，需在我们的路径上单独验证。报告给出的精确恢复范围是 `(L/2) × n_win`，不能把 128-token bounded replay 标作无损优化。

本地官方最小 `Transformer.forward:1242` 对 prefill/decode 均遍历 40 层，适合作为简单 SSD 按需加载参考；它没有实现上述生产阶段优化。此前将 CED 仅列为远期研究，优先级偏低：建立正确参考后，应优先实现、独立评估 encoder 全序列 + decoder 尾段回放，再做一般 Prefill 微调。不能提前计入未经实测的 TPS 收益。

缓存调度应区分 encoder Prefill、decoder 尾部回放、完整 Decode 三阶段，分别记录 expert trace、working set、读盘量和切换开销。Prefill 可向 encoder 倾斜预算，并预热 decoder 所需专家；进入 Decode 后恢复 40 层预算。这里减少的是主要 prompt 部分的专家层调用，不保证专家唯一集合、SSD 字节数或峰值内存恰好减半。近似 bounded replay 与完整参考分别报告数值/质量结果，不混入 exact parity 的存储优化验收。

来源：[官方技术报告](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/blob/main/DeepSeek_V41_Tech_Report.pdf)，本地副本 `artifacts/dsv41-download/DeepSeek-V4.1-Flash/DeepSeek_V41_Tech_Report.pdf`。

## 7. Scope、promotion、MTP 的选择

- GLM static Scope online 为 -2.04%，dynamic+Hot16+promote1 更有效；Qwen Scope 在其测试中有效，但全局 Top224 离线覆盖略高于独立 Scope。结论：新模型先动态/轻量 global bootstrap，采集轨迹后决定 Scope，不先套十类 profile。
- Qwen 长回答 promotion4 增速 31.8%，短回答却不划算；DS 先统计 repeated miss 和晋升开销，再比较延迟或复用驱动 promotion，不照抄 128-token 阈值。
- GLM MTP 接受率不错仍未通过 exact-logit rollback，且端到端速度无收益。DSpark 首轮关闭；未来目标层 37/38/39、3 个 MTP stage、block5 都需独立验证，不由模型携带 MTP 权重推断加速成立。
- Boost/REAP/2-bit 单独评价质量，不混入原始精度存储优化收益。

## 8. 可在当前机器执行的基线与验收

遵循用户已明确的约束：**不要求全模型驻留，不使用全驻留 85% TPS 作为门槛**。

1. 原始精度、简单 SSD 按需加载参考：Engram 按行读，专家只取本次需要的完整原始参数，必要时 dense 也按层读。先支持短文本生成，允许很慢。
2. 独立小配置官方语义测试，以及真实单层/单专家驻留对照。原始 expert 单层 packed 约 6.72 GiB，单 Top6 packed 约 107.58 MiB；比全模型对照可行得多。展开参考仍需按 tile 控制峰值。
3. 对同权重缓存路径验证路由、逐层输出、logits 与固定生成；覆盖全 hit、混合 miss、全 miss、失败、取消、跨请求与 chunk。
4. 固定内存预算比较 simple SSD / Main+Hot / Engram cache / overlap，记录 cold/warm、TTFT、Prefill、steady TPS、SSD request/bytes、CPU同步、MLX active/peak、RSS 和文件页缓存。
5. 优先单独评估 CED 分阶段 Prefill 与 Decoder SWA Bounded Replay：记录长短 prompt、首 token logits、生成质量与 Prefill/阶段切换性能；近似恢复不要求冒充 exact parity。再独立比较 packed KV、候选索引、双源 attention、promotion、2-bit。任何未通过对应检查的变化回退到前一参考路径。

本次产物是实施优先级与语义约束，未声称 DS4.1 的实际 TPS 或内存峰值已验证。

实施进展：首版 SSD CPU 数值参考和短序列数据已完成，见 [SSD 精度参考基准](dsv41f-ssd-reference-baseline-2026-09-13.md)。它复用官方模型代码，但 CPU 算子移植尚未通过 CUDA parity；不得将可重复性误记为 GPU 数值验证。
