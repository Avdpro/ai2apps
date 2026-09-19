# DS4.1F 按需逐层诊断回调（2026-09-14）

当前实验runner默认不再执行层末`mx.eval`/预算检查/进度打印；新增`--layer-progress`恢复旧诊断行为。`--trace`仍保存中间张量并启用逐层诊断。修改不涉及Router miss判断、读取IDs/ages、缓存覆写安全栅栏、每步结果求值及预算检查；physical footprint继续20ms采样、65十进制GB预算、MLX内存限制不变。旧`probe_sync.py --keep-layer-eval`已转接新开关。

## A/B

同一2048-token fixture、128步Decode、完整Top6、Main40/Hot8、动态L1、Prefill双缓冲64；顺序on1/off1/off2/on2，各独立进程。系统文件缓存允许，未声称物理SSD冷读；测量期间临时暂停GLM双源上传，结束后已自动恢复。

| 配置 | Prefill TPS平均 | Decode TPS平均 | physical footprint峰值GB | MLX峰值GB |
|---|---:|---:|---:|---:|
| 旧行为：逐层回调开启 | 108.21 | 6.96 | 57.232 | 51.691 |
| 新默认：逐层回调关闭 | 110.24 | 7.20 | 57.292 | 52.395 |

Decode提升3.43%，Prefill提升1.88%。两次关闭的Decode7.13/7.26 TPS，两次开启6.94/6.98 TPS；只有两轮，不能保证通用提升，也不能复述旧单组+9%为当前收益。延迟求值增加MLX临时峰值约0.705GB；进程footprint峰值仅增加约0.059GB，均低于65GB。

四次运行每次129份完整logits均与on1逐值一致且有限，input/generated IDs、cache counters、动态L1 promotion记录完全一致。缓存命中路径没有改变。比较脚本与comparison.json保存在`artifacts/dsv41-layer-progress-ab-20260914`。源码py_compile通过。

## 用法

```sh
# 新默认性能路径
.venv/bin/python experiments/dsv41_mlx/run.py \
  --prompt-json experiments/dsv41_analysis/fixtures/prefill2048.json \
  --decode 128 --prefill-slots 64 --output artifacts/<fresh-output>
# 需要恢复逐层检查/进度时，追加 --layer-progress
# 需要完整中间张量诊断时，追加 --trace
```

只修改实验入口/兼容诊断脚本和说明；不是正式Runtime/Package发布。运行manifest新增layer_progress与trace_enabled以避免混淆计时口径。
