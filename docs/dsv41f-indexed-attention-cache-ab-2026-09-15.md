# DS4.1F indexed attention与缓存容量对照（2026-09-15）

## 结论

SIMD直接索引KV attention微基准原型比原gather+MLX SDPA慢，未接入Model、没有默认开关。缓存Main40→48、Hot8不变则在512步Decode出现可测收益：8.25→8.79 TPS，尾128步8.71→9.29 TPS；513份完整logits逐值一致。额外约5.94GB footprint，总峰值63.22GB。仍保留Main40通用默认；Main48是已验证本例的纯文本长Decode选项，不自动推广到视觉/其他长度。

## Direct-index原型

`experiments/dsv41_mlx/indexed_attention.py`直接按indices读取KV，每query/head一个threadgroup；FP32 SIMD dot/softmax/value累加，支持负索引mask与sink，避免物化gather KV。不是张量单元/矩阵分块优化内核；减少中间数组不保证快于成熟SDPA。

最终复测每shape预热2次、计时7次中位数，H64/D512/K640，合成BF16输入：

| query数 | gather+SDPA ms | indexed ms | indexed相对耗时 |
|---|---:|---:|---:|
| 1 | 0.813 | 1.837 | 2.26× |
| 64 | 3.151 | 4.791 | 1.52× |
| 256 | 8.208 | 18.199 | 2.22× |

最大绝对差6.1e-5–1.22e-4、全部有限，未声称逐位一致或全模型精度通过。按速度门槛淘汰，不继续整模型集成；不能由这个朴素原型推导所有专用Metal attention都无效。首轮日志前的探索数值不是最终gate，最终kernel.log/kernel-results.json为准。

## Cache容量A/B

当前Main40默认、动态L1间隔16/最多4晋升、Hot8，完整Top6、Prefill专家双缓冲64、attention query分组64、Decode dispatch legacy、层末回调关闭。Main48仅复用已有参数，无新的缓存策略代码；官方SSD原权重不变。

2048-token同一科普fixture、128步Decode，顺序40/48/48/40，各独立进程：

| 配置 | 平均Decode TPS | 命中率 | miss | footprint峰值GB |
|---|---:|---:|---:|---:|
| Main40/Hot8 | 7.565 | 88.36% | 3577 | 57.299 |
| Main48/Hot8 | 7.677 | 92.11% | 2424 | 63.218 |

四次各129 logits、generated IDs完全一致。Main48 miss降低32.2%，但头两步更慢；原首轮Main40前两步约1.19/0.24秒，Main48约2.02/0.36秒，没有GPU时间线确认额外成本成因，不能直接称为JIT成本。短样本整体收益很小，后64步Main48两次9.09/9.07 TPS，Main40两次8.63/8.38 TPS。因此追加512步测试以摊薄启动影响。

2048输入、512步Decode，一组成对实测：

| 配置 | Prefill TPS | 整体Decode TPS | 尾128步TPS | 命中率 | miss | native expert I/O秒 | footprint峰值GB |
|---|---:|---:|---:|---:|---:|---:|---:|
| Main40/Hot8 | 109.82 | 8.254 | 8.711 | 88.83% | 13727 | 10.429 | 57.281 |
| Main48/Hot8 | 109.62 | 8.786 | 9.291 | 92.50% | 9218 | 7.710 | 63.218 |

两条路径各513完整logits逐值一致、max_abs=0、generated IDs一致、全部有限。整体Decode+6.45%，尾128步+6.66%，miss减少32.85%；Prefill基本不变。均低于65十进制GB采样预算，MLX原内存限制不变。没有改变通用默认，避免从单个纯文本样本推广到多模态/长上下文。

系统文件缓存允许，不是物理SSD冷读。测量期间本任务GLM上传进程临时暂停且已恢复。128步做反向双轮，512步仅一对；固定重复科普文本不是通用质量/多轮/长篇代码benchmark。

## Cache优化优先级的证据

128步Main40中miss最多的层（零基）为0/39/19/34，其次23/27/1/35等；前4贡献22.2%，前10贡献47.7%。并非只有前三层。Main40→48为每层加8槽，额外逻辑expert bank40×8×18,800,640=6,016,204,800 bytes；实际进程footprint增加约5.94GB，不与allocator/系统page cache混算。

512步Main40全命中layer-steps=11193/20480（54.7%）；Main48=13762/20480（67.2%）。92.5%的逐专家命中率仍然有32.8%的layer-steps需要miss处理。这支持继续验证按层动态预算和预测L2预取，但不能把提升后的hit率直接转换成TPS。

原生I/O计时包含native调用墙钟，读量是API逻辑读取，不是物理SSD；与GPU计算/调度并不完全独立。即使全命中，现有router `.item()`主机判断仍在。缓存是有实测增益的重点方向，但不是所有计算与同步成本的替代解释。

建议下一步：跨多个提示采集逐层路由与miss分布，评估在相同预算下的非均匀Main分配；再验证跨token预测L2与GPU计算重叠。不能拿未来实际routes做oracle预取并当成可部署收益。暂不采用固定全量层（此前用户已排除该方案）。

## 复现与证据

```sh
.venv/bin/python experiments/dsv41_mlx/run.py \
  --prompt-json experiments/dsv41_analysis/fixtures/prefill2048.json \
  --decode 512 --prefill-slots 64 --main-slots 48 \
  --output artifacts/<fresh-output>
```

`artifacts/dsv41-indexed-attention-20260915/`保留：kernel-results.json、cache-comparison.json、long-comparison.json、cache-layer-audit.json、全部manifest/logits、微基准及A/B脚本。原型py_compile通过，未改推理默认、未发布Runtime/Package。
