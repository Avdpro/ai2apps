# DS4.1 Flash阶段基线v2

Tag：`dsv41f-mlx-baseline-v2-20260913`。这是本地研究代码检查点，不是生产发布。
目标仍为完整专家Decode约10 TPS、2048输入Prefill约300 TPS、纯文本峰值65十进制GB。
当前完整专家路径未达到这两个速度目标；有损Burst应单独评价。

## 已完成

- 官方原始checkpoint与完整SSD专家仓库可用；CPU参考和逐层trace工具保留。
- 文本数值前向已迁移MLX/Metal：attention、router、专家、mHC、Engram处理、KV压缩、输出head。
  CPU仍负责tokenizer、文件读取/地址、缓存规划与必要同步，不能称为没有CPU参与。
- 原始MXFP4专家按需载入，复用GLM/Qwen native preadv直写统一内存。
- Main/L1=40、Hot/L0=8，动态L1默认开启；周期16步、最多4项/层晋升、衰减及迟滞。
- Engram embedding按需SSD读取，GPU解量化；没有全量驻留、Scope或预测L2。
- Prefill双缓冲32/64/96可选，64槽有较好实测；修正Prefill到Decode的完整Hot8交接。
- Decode Burst Top2/4、尾部策略，以及真正miss层回滚的Block2/4已经实现并比较。
- 独立Prefill Burst Top2/4已实现；保留全批必保专家并集及resident原尾部，不重新归一化。
- 专家调度复用与gate/up融合已试验，保留开关及负面结果。

## 默认值与后续建议基线

| 项目 | Tag中实际默认 | 后续实验建议 |
| --- | --- | --- |
| 原专家权重、完整Top6 | 是 | 保持 |
| 动态L1、Main40/Hot8 | 是 | 保持 |
| Prefill双缓冲 | 关闭，slots=0 | 完整路径以slots=64作为性能候选 |
| Prefill/Decode Burst | 均关闭 | 仅在明确有损实验中分别开启 |
| Block | 1，关闭跨层投机 | 保持，当前Block2/4端到端回退 |
| 尾部 | zero | 不自动改归一化或替补 |
| shared dispatch | 关闭 | 约0.8%～3.6%小收益，继续独立A/B |
| fused gate/up | 关闭 | 约7%～9%回退，当前不采用 |

## 关键实测

以下不同run的数字不可拼成同一次测量，也不等价于物理SSD冷读或统一steady gate。

| 配置 | 输入/Decode步数 | Prefill TPS | Decode TPS | 说明 |
| --- | --- | ---: | ---: | --- |
| 动态L1完整原路径 | 2048/128 | 103.58 | 7.35 | 全Top6 |
| 原Prefill，Decode Top2，Block1 | 2048/128 | 109.20 | 10.11 | 有损Decode |
| 原Prefill，Decode Top4，Block1 | 2048/128 | 96.66 | 9.08 | 有损Decode |
| 双缓冲64完整Top6，修正Hot交接 | 2048/32 | 116.19 | 6.25 | 峰值57.441GB |
| 双缓冲64，两阶段Top2 | 2048/32 | 136.79 | 8.75 | 峰值57.291GB，有损 |

64完整Top6多次Prefill约111～116 TPS；较同阶段104.54 TPS基线约+6%～11%。
共享dispatch约111.52→115.53/112.46 TPS；融合投影对照111.79，融合101.67～103.43。
32步和128步Decode包含不同的首步/维护摊销，机器状态也不同，不把波动单独归因于代码。

## 精度与验收边界

- 双缓冲完整Top6的长输入Prefill+32步logits逐值一致，逐层cache hit/miss计数也一致。
- 32/64/96分组和独立代码/中文样本有数值对照；shared dispatch与fusion的已测logits也一致。
- Burst与完整模型不是数值无损。代码Prefill Top4曾改变第一个预测token；中文短样本可能被
  resident全覆盖，不能作为通用质量证据。teacher forcing结果不等同自由生成全文一致。
- 相同Burst TopN的Block1/2/4在已测129步logits一致，但跨层投机有回滚额外计算和速度回退。
- 尾部补选/归一化没有统一精度赢家，原zero保留为默认；量化舍入差异不等同缓存漏专家。
- 未建立全驻留DS4.1F的实测TPS基线；CPU参考也不是所有MLX算子的逐位真值。
- 此版为单序列纯文本研究runner；没有生产会话、并发、视觉、多轮服务化验收。

## 下一步优先级

1. 消除Prefill最终Hot8交接重读：当前2048用例多约6.016GB读取，已计入总I/O。
2. 建立整模型Prefill分项profile，区分SSD等待、专家计算、attention/dense/Engram，避免继续只按kernel数量优化。
3. 评估更有效的批处理/原生调度；保持路由和量化位置，分别验证数值与65GB峰值。
4. 预测L2仍为设计阶段；未来与Block配合重新评估，当前不计入速度承诺。
5. CED/decoder bounded replay独立立项；不能将128-token回放混入完整40层数学等价验收。

## 恢复与复现

Tag包含独立MLX、CPU/混合参考、native loader构建源、分析脚本和DS4.1文档。
原始权重、约268.945GiB专家仓库、编译产物和大型trace留在本地artifacts，不进入Git。
构建loader见 `experiments/dsv41_reference/README.md`；模型运行依赖原checkpoint及对应完整仓库。
固定2048 fixture已纳入 `experiments/dsv41_analysis/fixtures/prefill2048.json`。

```sh
# 完整Top6性能候选；output必须是新目录
.venv/bin/python experiments/dsv41_mlx/run.py \
  --prompt-json experiments/dsv41_analysis/fixtures/prefill2048.json \
  --decode 32 --prefill-slots 64 --output artifacts/<fresh-output>
# 原默认对照：去掉 --prefill-slots 64
# 有损双阶段：额外加入 --prefill-top 2 --burst-top 2
```

`docs/checkpoints/dsv41f-mlx-baseline-v2-20260913.json` 保存当前实验源码SHA256、依赖版本、
关键原始manifest及其哈希和性能摘要。该文件记录base commit；最终提交由annotated Tag标识。
旧frozen-v1归档和所有旧benchmark目录保留。Tag不包含其他AI2Apps未提交修改，亦不自动推送远端。

相关细节：`docs/dsv41f-prefill-optimization-2026-09-13.md`、
`docs/dsv41f-burst-block-checkpoint-2026-09-13.md`、`docs/dsv41f-burst-tail-checkpoint-2026-09-13.md`、
`docs/dsv41f-expert-dispatch-2026-09-13.md`、`docs/dsv41f-fused-gate-up-2026-09-13.md`。
