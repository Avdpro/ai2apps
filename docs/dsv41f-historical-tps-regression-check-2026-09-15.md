# DS4.1F 历史 TPS 回退核查（2026-09-15）

## 方法

历史锚点为重复科普输入 2048 tokens / Decode 128，Natural 完整 Top6，Main40/Hot8，Prefill64，legacy dispatch，关闭层回调。沿用同一 SSD checkpoint。Decode TPS 包含首个 Decode；另列排除前16个 Decode 的后112步吞吐，不能混作完整 TPS。所有新运行的129份 logits、输入和输出与历史逐字节一致。

历史源码未能完整恢复到9月14日同一哈希；独立旧源码使用 L1 shape 初期归档，早于本轮 L1 策略及晋升复用改动。运行使用当前相同 Python/MLX/native 二进制，不能据此排除更早的环境或代码变化。原归档路径：`artifacts/dsv41-l1-shape-20260915/source-snapshot/initial-experimental-source.tar.gz`。

| 版本 | 完整 Decode TPS | 首个 Decode 秒 | 后112步 TPS | 命中率 | Decode native IO 秒 | 峰值 GB |
|---|---:|---:|---:|---:|---:|---:|
| historical-legacy1 | 7.366 | 1.281 | 8.196 | 88.36% | 3.219 | 57.265 |
| historical-reread | 6.582 | 3.048 | 8.006 | 88.36% | 3.589 | 57.262 |
| current-baseline | 6.550 | 2.981 | 7.931 | 88.36% | 3.590 | 57.277 |
| current-new | 6.559 | 2.808 | 7.839 | 88.23% | 3.480 | 57.271 |
| pre-l1-rerun | 6.764 | 2.790 | 8.136 | 88.36% | 3.385 | 57.268 |
| current-new-repeat | 6.640 | 2.802 | 7.965 | 88.23% | 3.383 | 57.269 |
| pre-l1-repeat | 6.718 | 2.721 | 8.020 | 88.36% | 3.430 | 57.266 |

## 同机反序复测结论

优化前源码两次完整 TPS 为6.764/6.718，均值6.741；当前新 L1 为6.559/6.640，均值6.600，低约2.10%。后112步均值8.078→7.902，低约2.18%。这组高命中输入有小幅负收益迹象，不能称为普遍优化；两次样本不足以把全部差值确定归因于某一代码行。新策略命中率88.356%→88.226%，miss3577→3617，也没有缓存收益补偿维护开销。

与历史7.366相比，优化前源码同机复测的差距主要集中在首个Decode：首个Decode约2.72–2.79秒，历史1.28秒；后112步8.02–8.14，历史8.20。完整7.x尚未复现，不能以尾段8.x替代验收。

## 解释边界

- 最近不到5 TPS 的测试换成代码和中文记录分析任务，命中率约71%–73%；历史重复科普输入约88%。跨输入 TPS 不能作为代码回退比例。此前报告未同时呈现历史锚点，容易造成误解。
- 原样本在当前代码上仍未恢复历史完整7.36 TPS；旧源码同环境也慢，首个 Decode 时间明显增长。这里只定位时间发生在哪一段，未证明是编译、I/O、调度或后台负载中的哪一种原因。
- 不能把低命中样本约1.1%的收益推广为所有输入受益；新策略在本高命中样本并未提升命中率。
- 当前 baseline 仍为默认，新 eviction_dual 仍需显式启用；本次调查未改 Runtime 默认或部署。
- I/O 是 native请求计时，允许系统页缓存，并非物理SSD测量。系统曾观察到浏览器GPU及其他后台负载，没有主动结束用户进程；系统无已记录的 thermal warning。这些观察不能单独证明因果。

## 复现与证据

入口：`experiments/dsv41_analysis/l1_policy/check_historical_tps.py`。独立旧源码和反序复测采用同样的 `--prompt-json experiments/dsv41_analysis/fixtures/prefill2048.json --decode 128 --prefill-slots 64 --main-slots 40 --decode-dispatch legacy --logits-mode hash`，旧源码入口位于结果目录 `pre-l1-source/experiments/dsv41_mlx/run.py`；新策略额外 `--l1-policy eviction_dual`。

逐次 manifest、日志和比较 JSON：`artifacts/dsv41-historical-tps-check-20260915/`。
