# DS4.1F attention/indexer分项与分组实验（2026-09-14）

## 结论

新增可复现Prefill/Decode嵌套同步诊断，定位到本组2048输入Indexer很小、稀疏attention/SDPA更值得研究。完成query分组64/128/256的六次完整模型A/B。256分组Prefill平均仅约+1.3%，Decode没有提升；保留64默认，128/256作为显式实验选项。未声称已完成融合Metal attention内核。

## 分项诊断

诊断使用2048输入+16步Decode，显式同步破坏正常重叠，计时不是正常吞吐；包含子调用的inclusive时间不能相加。

| 操作 | Prefill秒 | 16步Decode累计秒 |
|---|---:|---:|
| attention | 5.9358 | 2.0986 |
| sparse | 3.6163 | 0.4114 |
| sparse_gather | 0.3505 | 0.1041 |
| sparse_sdpa | 2.7654 | 0.1402 |
| index | 0.1215 | 0.1809 |
| index_scores | 0.0576 | 0.0260 |
| index_topk | 0.0055 | 0.0247 |

Prefill forward约20.74秒，attention约5.94秒，其中sparse3.62秒，SDPA2.77秒；每层32组，共1280次SDPA。index_scores+index_topk合计约0.063秒，不支持在此长度优先优化TopK。Decode attention平均约131ms/步，SDPA约8.8ms/步，说明其余投影、压缩和外围操作也应重视；该同步诊断包括启动摊销，不能直接与正常7TPS运行相减来算潜在收益。

抽取index_scores/index_topk、sparse_gather/sparse_sdpa边界，64默认保持原算式。同步profile的17份完整logits与原参考逐值一致。新入口`experiments/dsv41_analysis/profile_attention.py`；本次实际诊断脚本保留在artifacts中。

## 正常异步路径A/B

同一2048-token fixture +128步Decode，完整Top6、Main40/Hot8、动态L1、Prefill专家双缓冲64、逐层回调关闭、Decode dispatch legacy；仅attention query分组不同。系统文件缓存允许，不声明物理SSD冷读。每次独立进程，GLM上传测量期间暂停、finally已恢复。

| query分组 | Prefill两轮TPS | 平均Prefill | 平均Decode | footprint峰值GB |
|---|---|---:|---:|---:|
| 64 | 110.40 / 111.00 | 110.70 | 7.442 | 57.266 |
| 128 | 107.66 / 98.82 | 103.24 | 7.366 | 57.267 |
| 256 | 112.80 / 111.45 | 112.12 | 7.440 | 57.254 |

每次129份完整logits与修改前legacy参考逐值一致，生成IDs及cache计数一致，全部有限；峰值低于65GB。调整分组不改变Decode的单query计算，因此Decode微小差别只作为噪声观察，不计作优化收益。

## 边界检查

另以真实Metal SDPA检查query长度1/65/129/257、因果mask与sink。8组全部有限，7组逐位一致；129-query使用256分组最大绝对差4.768e-7。这是很小的浮点数值差异，不是漏专家或更低位量化；但不能声称任意长度严格逐位一致。没有据此提高数值容差或改变默认。保留64默认的主要理由是吞吐收益太小且仅一个输入长度；不是把该微小误差视为严重精度问题。

## 代码与复现

- `run.py --attention-chunk {64,128,256}`，默认64，manifest记录attention_chunk。
- `model.py`参数校验、评分/TopK边界及分组传递。
- `kernels.py`保留原运算，分离诊断边界并允许query分组。
- `profile_attention.py`分别记录Prefill/Decode inclusive/exclusive时间。

```sh
.venv/bin/python experiments/dsv41_analysis/profile_attention.py \
  --prompt-json experiments/dsv41_analysis/fixtures/prefill2048.json \
  --decode 16 --prefill-slots 64 --output artifacts/<fresh-profile>
.venv/bin/python experiments/dsv41_mlx/run.py \
  --prompt-json experiments/dsv41_analysis/fixtures/prefill2048.json \
  --decode 128 --prefill-slots 64 --attention-chunk 256 \
  --output artifacts/<fresh-benchmark>
```

原始profile、六次完整logits与性能收据、comparison.json、sparse-edge-results.json、命令脚本在`artifacts/dsv41-attention-ab-20260914/`。源码py_compile通过。仅实验入口/诊断改动，不是Runtime/Package发布。

后续若继续应评估直接索引KV的原生attention kernel，减少KV物化与SDPA外围操作；本轮没有实现，不能承诺其提升。当前结果不支持继续盲目增加query分组或把Indexer当主要瓶颈。
