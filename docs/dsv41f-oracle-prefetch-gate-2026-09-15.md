# Oracle 前台优先预取收益门槛（2026-09-15）

当前默认全Top6、L1每层40/L0每层8、eviction_dual、Prefill64。先记录真实逐token各层读请求和目标槽位，然后重放完全相同的token与实际Router：预取从第5层开始，最多领先当前MoE层8层，每批2/4条专家记录。单一I/O仲裁器保证有前台请求时不提交新后台批次；在途小批不能抢占，前台最多等待该批结束。前台只读取未完成部分，不重复读取。

这是理想路由及目标槽位oracle，不是可部署的预测L2。利用已经完成上一token的正常边界，直接预写未来真实miss的目标槽位，省去L2暂存/搬运。仅在未来地址已被参考轨迹证明不会覆盖本层需要的驻留专家时成立，严禁把猜测地址用于此路径。所有oracle写入仍需等实际层的miss路径确认ID和槽位；不绕过Router，不取消原有GPU栅栏。

## 实测

短32输入/128Decode：baseline→batch2→batch4→baseline；长2083输入/512Decode：baseline→batch4→batch2→baseline。每种oracle各一次、基线前后夹持；规模有限，不宣称统计显著或跨任务普遍收益。

| 用例 | 配置 | 完整TPS | 尾段TPS | 后台专家/token | 就绪miss层比例 | 峰值GB |
|---|---|---:|---:|---:|---:|---:|
| coding-en-train-18 | baseline1 | 4.676 | 5.077 | 0.00 | — | 55.215 |
| coding-en-train-18 | oracle2 | 6.071 | 6.792 | 53.79 | 85.90% | 55.245 |
| coding-en-train-18 | oracle4 | 5.993 | 6.757 | 53.79 | 85.94% | 55.220 |
| coding-en-train-18 | baseline2 | 4.581 | 5.034 | 0.00 | — | 55.210 |
| long-math_logic-zh-test | baseline1 | 4.952 | 5.214 | 0.00 | — | 57.333 |
| long-math_logic-zh-test | oracle4 | 6.390 | 6.784 | 53.57 | 85.90% | 57.341 |
| long-math_logic-zh-test | oracle2 | 6.383 | 6.814 | 53.55 | 85.85% | 57.357 |
| long-math_logic-zh-test | baseline2 | 4.938 | 5.218 | 0.00 | — | 57.321 |

coding-en-train-18 oracle2 相对前后baseline均值 4.628 TPS：+31.17%。

coding-en-train-18 oracle4 相对前后baseline均值 4.628 TPS：+29.50%。

long-math_logic-zh-test oracle4 相对前后baseline均值 4.945 TPS：+29.22%。

long-math_logic-zh-test oracle2 相对前后baseline均值 4.945 TPS：+29.08%。

完整TPS包含首个Decode，尾段排除前16步。所有输入/生成tokens/logits、缓存命中/替换轨迹、专家目的槽位、总请求字节及bank GPU fence次数精确一致。后台小批切分会增加native函数调用次数；这不是增加GPU fence。原cache_stats仍按L0/L1逻辑缺失计数，不把prefetched-ready误标成L1命中。后台读取即使移到前台之前，计入总字节；不能用原adaptive逐层IO差分统计解释后台耗时。

## 范围与限制

- 后台完成的专家/token不等于全部在截止时间前完成；另列ready miss层比例。到层时仍在途的当前批需要等待，foreground_service_s包含该等待和剩余读取。
- 地址oracle比真实L2更理想：真实预测器不能安全覆写猜测槽位，必须暂存并在真实路由验证后使用；预测误差、缓存兑现和调度开销尚未包含。
- 整个token的可用重叠窗口不等于先前12ms的纯专家kernel隔离窗口；不能把10专家/token当硬件上限。
- 系统页缓存沿用原推理设置，不改F_NOCACHE策略，不增加随机无用读取；结果是本机当前文件缓存条件下的净收益。
- 正式L2训练仍未启动，先评估oracle净收益及预算敏感性；无活动Runtime/Package修改。

证据：`artifacts/dsv41-oracle-prefetch-20260915/`。执行：`experiments/dsv41_analysis/oracle_prefetch/benchmark.py`；独立调度器：`entry.py`；报告：`report.py`。

## 有效预读预算门槛

短代码同一128步轨迹，在上述长测后追加8→16→32预算，各一次。仅限制真实有效预读数量，尚未注入错误预测或浪费读取；以先前同批短测夹持baseline均值作参照，非每组重新夹持，因此小差异仍需谨慎。

| 最大有效专家/token | 实际后台专家/token | TPS | 相对短测baseline均值 |
|---|---:|---:|---:|
| 8 | 8.00 | 4.689 | +1.32% |
| 16 | 16.00 | 4.912 | +6.13% |
| 32 | 31.29 | 5.249 | +13.41% |

8个约+1.32%，未超出可疑波动范围；16个约+6.12%，32个（实际31.29）约+13.41%。无限预算约53.8个，对应约30%。这给出有效覆盖量的初步门槛：只有个位数有效预读，不支持投入复杂预测器；若能及时提供约30个以上有效预读，存在值得继续验证的空间。该结论不包含预测误差及额外带宽损耗。

## 当前决定

确认前台优先的oracle预取有明显端到端收益，但不把它当作真实预测L2已成功。保持整批补采/训练暂停；下一道门槛是安全独立暂存、真实路由确认后兑现预取的成本，以及无效预测读取下的收益保留。当前同步路径的oracle也只有约6.0–6.4TPS，不能承诺仅训练预测器便达到10TPS。

本轮共11个完整模型进程，所有输入/token/logits/缓存轨迹/总读取量/原GPU栅栏核对一致，峰值≤57.357GB；native请求小批拆分允许增加调用次数。未修改活动Runtime、缓存默认或发布Package。预算入口`budget.py`，结果`budget-results.json`、`budget-verification.json`。
