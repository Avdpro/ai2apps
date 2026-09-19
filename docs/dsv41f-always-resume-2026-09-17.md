# 始终 GPU 停止/恢复模式：语义通过，性能未达标（2026-09-17）

用户明确要求不使用packet准入或回退：GPU连续推进，真正miss时停止，补齐当前层专家后从MoE恢复并继续连续推进。该模式已实现并完成正确性测试；**整40层模式性能尚不合格，不能宣称优化完成或替换生产默认**。

## 实现合同

隔离入口新增`resume`模式，固定使用原生prefix加GPU条件停止：首个Gate前及已确认安全的恢复MoE走普通Metal dispatch，但不存在CPU命中检查；Gate后所有算子均受GPU状态控制。miss时后续Attention、Router、MoE及KV写入不执行。CPU读取已有完成边界中的状态/维护元数据，加载专家，保留本层Attention、Router、权重和HC continuation，从MoE恢复；每次都重新进入同一多层控制器。

不再通过命中率准入，不进入native_tail，不调用Decode packet probe。显式packet仍作为测试参考存在。默认隔离resume入口/launcher使用40层链，因此没有人为的2/4层命中边界；2/4层仅作为分段性能消融，不冒充仅MISS/DONE返回。

GPU记录每层Router访问数，诊断开关额外记录Attention前入口及MoE完成数。在已有窗口结束处读取，不增加route等待。状态快照比较包含KV/shared、Engram hash、频次、年龄、ticks、cache counters及非张量元数据。诊断保存发生在计时段之外，GPU phase标记会增加少量诊断开销，所以另跑了无标记的整链计时。

## 整40层语义验收

同一9-token提示，固定原legacy token轨迹，严格F_NOCACHE、L0=8/L1=40、每层8个独立L2暂存槽。无损Top6。

| 用例 | token数 | 真正miss | 返回次数 | GPU层入口/Router/MoE各自执行次数 | packet检查/回退 |
|---|---:|---:|---:|---:|---:|
| 正常缓存整链 | 4 | 142 | 146 | 160 | 0 / 0 |
| 每层真实miss整链 | 2 | 80 | 82 | 80 | 0 / 0 |

返回次数严格等于miss数加token数：每token一次最终DONE。全部logits与原golden哈希一致；正常缓存所有保存状态逐字节一致，强制全miss的KV/shared/Engram状态与参考一致（缓存标签/年龄本来就因压力条件不同）。峰值约60.92GB，未越过65GB。

全命中同一token重放：每次40层模式只返回一次，零miss、零SSD读、零packet调用，输出精确一致。cache准备和恢复不计时，该结果不是生成TPS。

## 性能没有达标

整40层关闭GPU phase诊断与状态dump后，4token完整Decode只有 **0.580 TPS**。同输入轨迹的两次packet参考前4步分别3.327/3.314 TPS；这是短开发前缀对照，不是长context稳态。该数量级的退化不应归为普通波动。

原因有两个证据支持：

1. GPU虽未重复执行后缀，但CPU每次恢复仍重新构建并编码后缀。4token只有160个实际层，却构建2936个层图，GPU跳过2776个；全miss的2token构建1640个图，实际执行80个。带异步提交的build墙钟包含提交及可能背压，不能作为纯CPU profile，不过重复构图数量是确定的。
2. 当前仍逐算子套间接命令。全命中隔离中位耗时：packet83.17ms，真停止2层115.23ms、4层123.57ms、整40层129.43ms。没有miss也明显更慢，说明不能把全部问题归因回滚。此前81.6ms的4层数据来自无GPU条件停止的投机窗口，不能迁移到本模式。

2层分段的ABBA对照（全部Decode计时）为正常packet4.806→resume4.321 TPS（−10.08%），全miss1.990→1.891（−4.95%）。Burst Top2为7.733→6.257，Top4为5.949→5.108。这些分段方案也没有通过不退化门槛，而且含额外分段完成边界，不能作为整链目标的替代答案。

本轮还实现并测试了两项隔离后端CPU编码优化：ICB cache改为定长整数key，资源声明按encoder去重；条件执行与屏障保留。并将逐层异步提交应用于guarded构图。它们未解决上述根本问题，不宣称独立稳定收益。新ABI标识v3防止新旧桥接/后端误配，旧后端未替换。

## 其它正确性门禁

两个后端各完成18组开发case。2/4层逐字节状态检查通过，所有resume case的packet_checks、packet_tokens、native_tail_tokens均为0。无损组与原legacy logits一致；Burst组与同TopN的packet轨迹一致。state/rank64/Block6各8token无损检查通过，L2实际读取≤64/token，计数的提交+通知≤41/token。暂不据短case重新宣称70%覆盖或L2加速。未验收长上下文、视觉、生产Runtime/Package。

第一轮比较器不支持NumPy BF16，已改为按safetensors头与原始张量字节精确比较，并复用已完成模型case继续验收；错误日志保留。新后端构建环境缺少Metal header预处理工具，复用了旧构建中生成的JIT C++文本，已核对全部Metal kernel源文件及预处理脚本完全一致，并保存生成文件SHA；运行仍使用原wheel metallib，没有重新量化或改数学kernel。

## 运行入口与证据

```sh
.venv/bin/python experiments/dsv41_analysis/l2_predictor/resume_probe/launch_resume.py \
  --predictor none --output artifacts/my-always-resume \
  --prompt 'Explain why a database index speeds up queries.' \
  --decode 4 --prefill-slots 64 --logits-mode hash --expert-no-cache
```

默认40层、只MISS/DONE返回。`--segment-layers 2/4`为分段消融；不包含packet回退，但会有分段边界。`--predictor state/lookahead/block6`为L2实验选项。此入口需要本次隔离后端及bridge，未安装进venv或生产Runtime。

源码：`entry.py`、`guarded_model.py`、`native.cpp`、`packet_control.py`、`launch_resume.py`；后端优化可由`prepare_fast_backend.py`在原隔离MLX源码的副本上生成。新库位于`artifacts/dsv41-resume-fast-mlx-build/`，桥接位于`artifacts/dsv41-l2-fast-resume-native-build/`；构建配置、复用JIT文本哈希及日志在首轮产物目录。

首轮产物：`artifacts/dsv41-l2-always-resume-v1-20260917/`。优化后：`artifacts/dsv41-l2-always-resume-fast-v1-20260917/`，包含冻结源码、模块哈希、18组报告、allhit、full40-report、无诊断full40-timing及completion。completion明确标记`semantics_passed_performance_not_accepted`。

## 剩余工作

要满足性能目标，不能再用packet回退或缩成逐层窗口冒充完成。需要让续执行复用已经构建的后缀图/编码，按continuation绑定更新恢复所需数据；同时将条件调度从逐算子封装提升到可复用命令段。必须重新验证buffer生命周期、共享KV别名、一次性路由/频次维护、GPU停止范围与每层miss性能。该部分尚未实现，不能将研究方向写成已完成优化。
