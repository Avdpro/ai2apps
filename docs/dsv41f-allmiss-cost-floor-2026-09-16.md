# DS4.1F 每层 miss 的成本下限验收

2026-09-16。对照使用旧的逐层路径（block1），它在 miss 后继续当前 MoE，本来就不重算 attention。

## 当前进度标记与待验收项

2026-09-16 对话确认：本轮已完成低命中时的 window 准入和首次 miss 退出，以及人为全 miss 的成本对照；**尚未在本轮最新修改后重跑历史约 7 TPS 的正常缓存用例**。不能用下表的全 miss 成绩宣称正常负载回归已经通过。

| 条件 | 本轮全 miss 压测 | 历史正常缓存锚点（本轮修改前） |
|---|---|---|
| 输入 | Rust 内存缓存设计问题，32 tokens | 重复的天空颜色解释问题，2048 tokens |
| Decode | 32 tokens | 128 tokens |
| 缓存行为 | 每层强制清除专家标签，再走原 loader | 正常使用缓存，不强制失效 |
| 无损 Top6 完整 TPS，旧/新 | 3.190 / 3.214 | 7.045 / 7.168 |
| 配置 | L0=8、L1=40、eviction_dual、Prefill64 | L0=8、L1=40、eviction_dual、Prefill64 |

这两组是不同输入长度、Decode 长度及缓存条件的单用例性能实验，不是可直接比较的同一测试集。历史锚点数据在 `artifacts/dsv41-tps-anchor-20260916/natural-legacy/manifest.json` 及同目录的对照结果，说明见 [历史锚点报告](dsv41f-tps-anchor-recheck-2026-09-16.md)。

下一步待执行：用历史相同 prompt、2048 输入 / 128 Decode、正常缓存和无损 Top6，对最新代码的 legacy / auto 做配对回归；核对 logits、实际缓存命中与 SSD 读取、同步/fence 次数、内存峰值，并分别报告完整 TPS、首 Decode 与尾段 TPS。必要时重复交错运行判断波动，不能以尾段 TPS 代替完整值。

默认 auto 仍为 packet；window 为显式实验模式。尚未完成任意命中率突变下逐 token 严格等价的成本保证，也未发布 Runtime 或 Package。本次仅记录进度，没有新增性能测量。

## 改动

明确请求 `window` 时，控制器冷启动先用原生 packet；上一 token 必需专家 miss 层数不超过2时，下一 token 才允许跨层。进入窗口后首次 miss 即修复当前 MoE，并将本 token 后续层交给 packet。低命中时不会反复组建失败窗口，也不创建跨层状态快照。这是运行时观测策略，不读取测试开关来选择执行路径。

`DSV41_WINDOW_FORCE=1` 仅用于固定窗口研究和复现早期数据，绕过准入与首次miss退出，不享有本次成本下限验收。默认 auto 仍为 packet。

## 实验

32-token 短输入、32步 Decode，Main40/Hot8、eviction_dual、Prefill64。每层 MoE 前清除专家标签，走原 SSD loader 重新加载实际必需专家。没有替换权重或输出，没有清空 OS 文件缓存，因此不声称所有文件读取都来自物理 SSD。

新 Burst 明确选择 window/block4，并开启异步选项；结果由实际 miss 历史决定是否跨层。Top2 按旧→新→新→旧顺序；Top4、自然Top6分别做旧/新配对。自然Top6测试的是原默认auto路径。

| 模式 | 旧版完整 TPS | 新版完整 TPS |
|---|---:|---:|
| Top2 A | 4.549 | 4.782 |
| Top2 B | 4.419 | 4.701 |
| Top4 | 3.834 | 4.013 |
| 自然 Top6 | 3.190 | 3.214 |

各组33份 logits 哈希、逐层统计、SSD读取字节、晋升完全一致。每个新版有1280个实际miss边界、0个跨层构图、0个window token；bank fence均1360次（包括Prefill），没有新增维护fence。Top2全流程专家读取84,226,867,200字节，Top4为132,356,505,600，自然Top6为180,486,144,000；各自旧/新完全一致。采样峰值约55.2GB。

结论：本次连续全miss负载未观察到性能下降。自然Top6的微小差别视为性能等价，不宣称其稳定提速。这里不把不同TopN的速度互相比较。

## 从窗口状态突然转为连续miss

另外把控制器初始准入状态设为“上一token命中良好”，随后仍强制每层真实miss。第一个窗口在第0层miss后立即退回packet；其余31个token不再跨层。共1280次提交、1280次miss，attention重放为0，SSD/fence/logits与旧Top2相同；总吞吐4.580 TPS，后24步5.415 TPS。

必须保留的边界：第一个窗口确实构建了4层，存在一次推测/快照成本。该次首Decode为1.230秒，旧Top2两轮首Decode约1.020秒与1.111秒；不能据此声称每个瞬时token都绝无额外成本。本次32步总吞吐没有下降。真正无须准入、任意突变下逐层等价的GPU停止控制器仍未完成。

数据：`artifacts/dsv41-allmiss-floor-20260916/results.json`、`transition-verification.json`。脚本：`experiments/dsv41_analysis/miss_resume/benchmark_allmiss_floor.py`，转换诊断：`allmiss_transition.py`。
