# DS4.1F L2 预测器首批采样

状态：116条序列全部采集完成，20992条有效样本全部通过逐序列校验及完成后文件审计；rank128首版训练及独立测试已完成，见 [首次训练结果](dsv41f-l2-r128-training-2026-09-16.md)。尚无真实 L2 推理加速结论。

完成审计：训练12032行、验证4480行、测试4480行；supervision文件合计2,492,458,832 bytes（约2.49GB）。全部文件SHA-256与验证回执一致，checkpoint指纹一致，跨split的family和完全相同输入均无重叠。采样峰值58.682GB，未超过65GB预算。审计回执：`artifacts/dsv41-l2-v2-20260916/collection-audit.json`。模板相似性及真实多轮覆盖不足仍是下述限制，不能将分组审计视为已消除所有分布偏差。

Pilot：33-token 与2083-token输入各128步，共256条样本；全部生成 token/logits、SSD读取字节、逐层计数、晋升、bank fence与未插桩的原始路径一致。采样峰值分别55.254/57.443 GB。回执：`artifacts/dsv41-l2-v2-20260916/pilot-verified.json`。长输入有一处第六名精确同分，NumPy与MLX的排序选择不同；校验比较所选分数集合而不强制NumPy的同分ID，训练标签始终保留真实MLX输出。

## 已有数据与本次范围

旧目录 `artifacts/dsv41-l2-predictor-20260915` 有四条序列、512 条经 logits 对照的样本，随后暂停；不是完全没有采样代码。旧版只包含后35层，缺少缓存驻留信息。本次使用独立 v2 数据目录，不混用或覆盖旧数据。

代码：`experiments/dsv41_analysis/l2_predictor/v2/`。数据与状态：`artifacts/dsv41-l2-v2-20260916/`。

首批计划116条序列：训练64条、最多12032行；验证26条、最多4480行；测试26条、最多4480行。先保证每个 split 的10领域×中英文覆盖，再轮选短/长输入，主题 family 不跨 split。总上限20992行；遇到 EOS 提前结束，因此实际有效行数可能更少，不为凑数继续生成 EOS 后数据。

语料复用 Scope/L1 采样清单，含中英文、多领域、短输入及约2K的合成长输入。已知局限：共享通用指令模板，长上下文是合成材料，不包含真实服务的持久多轮缓存复用。首批是可学习性探索，不能据此宣称通用多轮能力；独立的多轮对话数据仍需补充。

## 样本定义

每个有效 Decode forward 对应一行：

- `hidden[5120]`：上一 forward 的最终归一化后、输出 head 前状态。
- `embedding[5120]`：本次实际输入 token 的原始词嵌入；两者均按 float32 保存，避免再次压缩丢失信息。
- `router_rank[40,384]`：本次真实选择使用的 scores + correction bias，float32。
- `top6[40,6]`、`previous_top6[40,6]`：当前与上一轮的专家集合，按专家 ID 升序；不是按分数排序。
- `resident[40,384]`：本轮执行前的缓存角色，0缺失/1 L1/2 L0，支持过滤已驻留专家及统计真实 miss。
- `position`：本次 token 的绝对输入位置。
- `alignment.json`：实际 token IDs、原输入 IDs、split、family_id；每行 token 是 manifest 的 generated_ids[:-1]，对应当前输入，而非当前新生成的输出。

Prefill 不作为训练标签行，但其最终 hidden 与最后位置路由用于第一行 Decode 的前态。全40层保留，未来预取起始层不由数据采集硬编码。

## 执行与验证

使用冻结的原始 legacy 无损 Top6、L0=8/L1=40、eviction_dual、Prefill64、SSD checkpoint。采样与缓存策略分离，不启用 Burst，不修改活动 Runtime。选择 legacy 是为了直接保留原有 Router/emit 路径；本次数据生成不代表新 packet/window 的性能验收。

只在冻结副本中插入采样：设备张量在 runner 原有 token 完成 `mx.eval` 中求值，CPU 数组转换在完成边界后执行；没有新增逐层 GPU→CPU 读回或 bank fence。每序列统一落盘。采集本身有构图/导出开销，不把其 TPS 当推理基准。

每条数据校验形状、有限值、原始分数对应 Top6、跨行前后路由对齐、位置连续性、驻留状态与实际 miss 计数一致。pilot 另与未插桩的当前原始路径比较全部 token/logits、逐层缓存计数、晋升与 bank fence。原始源码副本有 SHA-256 清单，每次启动验证；输出有内容哈希与逐序列验证回执。进程失败留下不完整目录，重启不会覆盖或自动当作成功。

执行命令：

```sh
.venv/bin/python experiments/dsv41_analysis/l2_predictor/v2/prepare.py
.venv/bin/python experiments/dsv41_analysis/l2_predictor/v2/collect.py --pilot
.venv/bin/python experiments/dsv41_analysis/l2_predictor/v2/collect.py
```

`prepare.py` 只用于首次建目录；不能对已有数据重新执行。批量采集以 pilot 验证成功回执为前置条件，训练/验证/测试文件分序列独立保存；训练阶段不得读取测试标签进行模型选择。

## 后续

采集完成先审计实际覆盖、EOS截断和分组，再训练 rank128 第一版；与上一轮路由、训练集固定频次等简单预测对照。核心指标是按每 token 8/16/32/48 的总预取预算过滤驻留项后的有效 miss 覆盖及误读字节。真实异步 L2 的暂存兑现、截止时间、误读竞争及端到端 TPS 仍需独立验收。
