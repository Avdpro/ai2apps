# DS4F 官方4bit与DS4.1F当前引擎实测（2026-09-14）

## 结论

同一2048-token纯文本输入、首token后128步greedy Decode，两轮独立进程测试：

| 路径 | Prefill TPS（两轮） | Decode TPS（两轮） | 平均 Prefill / Decode | MLX峰值 GB |
|---|---|---|---|---|
| DS4F 官方4bit，FleshEngine | 116.80 / 139.30 | 8.62 / 8.65 | 128.05 / 8.64 | 58.70 |
| DS4.1F 原精度，MLX runner | 107.07 / 111.07 | 7.36 / 6.95 | 109.07 / 7.15 | 51.69 |

本例DS4F平均Decode快20.7%，Prefill快17.4%。Prefill轮间波动明显，仅两个样本，不代表通用性能上限或模型质量对比。

## 实际配置

- 当前HEAD `8ff6faf966d56ae92d21bf2d36d9512da5745784` + dirty workspace。相关源码SHA256已保存summary.json；没有改动推理代码或构建发布制品。
- DS4F：官方snapshot `60d8d70770c6776ff598c94bb586a859a38244f1`，专家FP4/其余混合精度，expert store `artifacts/moe-expert-major`，record_bytes=13,369,344；不是2bit-DQ。
- DS4F最终入口是DeepseekV4FleshEngine，自动选择science_engineering Scope，L1 Top60、L0 Hot8，Direct-L1=1、Direct Prefill=1。动态L1启用，本例没有触发晋升；Natural精确路由，无Boost/MTP。
- DS4.1F：已上传SSD checkpoint；Main40/Hot8，动态L1，Prefill双缓冲64，Hot交接不重读，完整Top6，无Burst/Block/MTP。
- 两边允许系统文件缓存（DS4F NOCACHE=0），不声明物理SSD冷读。GLM两个上传进程测量期间暂停、finally恢复；没有清空系统page cache，也没有停止其他用户App。
- DS4F使用现有CPython3.11 Runtime环境，DS4.1F使用CPython3.13实验环境，均使用各自匹配的native扩展。比较当前可用引擎，非相同调度器/算子隔离实验。
- 固定fixture `experiments/dsv41_analysis/fixtures/prefill2048.json` 是重复科普文本；两边均2048输入，不是正式多轮对话。自由生成内容不同，不做跨模型token/logits一致性要求。
- DS4F生成129 tokens，其中首token归Prefill，后128步归Decode；统一Decode按1000/tpot_ms计算，避免原benchmark gen_tps将首token计入分子造成约0.8%偏差。DS4.1F按128/sum(step_seconds[1:])计算；runner日志/保存logits在逐步计时之外，而DS4F含服务调度开销。
- 表中内存统一为MLX allocator峰值，不是整个进程/系统占用。DS4.1F另测physical footprint峰值57.26GB；本轮DS4F未采physical footprint。

## 诊断对照与旧记录修正

最初复用旧脚本（BatchedEngine、固定general Scope）运行：DS4F NOCACHE=1 Decode为4.29/4.20 TPS，允许系统文件缓存后为8.30/8.35 TPS。可见该用例对文件缓存高度敏感，不能拿NOCACHE结果直接与DS4.1F默认结果比较。这四次保留为诊断，不纳入上表。

此前聊天把Direct-L1历史9.7–11.1 TPS整体归入2bit，不够可靠：旧checkpoint说明写2bit，但实际记录命令使用官方source和13,369,344-byte记录。此次明确使用官方原版4bit，纠正该口径；没有把旧数字当成本轮实测。

## 原始证据与复现

目录 `artifacts/ds4-vs-ds41-20260914/`：
- 正式：ds4-5.json、ds4-6.json、ds41-1/manifest.json、ds41-2/manifest.json。
- 诊断：ds4-1..4.json；全部log保留。
- summary.json记录统一指标和源码SHA；bench_ds4_flesh.py、run_flesh.py、run_pair.py、run_buffered.py记录实际命令/环境。运行器包含临时暂停本任务GLM上传、finally恢复的流程。
- DS4.1F逐步logits保留用于后续分析。本次测试不是SSD checkpoint发布验收或正式Package升级。
