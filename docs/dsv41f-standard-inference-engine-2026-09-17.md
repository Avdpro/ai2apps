# DS4.1F 标准推理引擎冻结

日期：2026-09-17。状态：实验runner默认已冻结；Runtime与模型Package尚未构建或发布。

## 标准配置

- 无损Full Top6 Decode。
- 每层L1/Main固定40个逻辑槽，L0/Hot固定8个逻辑槽。
- L1策略为`eviction_dual`：短/长期频次在既有miss边界参与晋升，使用零复制槽角色交换，不增加GPU→CPU同步次数，不从SSD重读晋升专家。
- Decode执行器为`packet`：每层一次原生GPU→CPU路由确认；命中时专家ID保持在设备侧，miss packet才携带加载及L1维护元数据。
- `decode_dispatch=legacy`、`attention_chunk=64`。
- 不启用预测L2、跨层guarded/window、Burst、固定全驻留层或非均匀L1形状。
- 纯文本physical footprint继续以65GB为门禁。

`experiments/dsv41_mlx/run.py`现在默认`--inference-mode packet`。历史`--inference-mode auto`保留为兼容别名并明确解析成`packet`，manifest记录requested/selected及原因。`legacy`、`guarded`、`window`只能显式选择；其中后两者仍是研究路径。

## 选择理由

当前四段小预测模型即使扩大到103.03M参数，离线cap64全部miss覆盖也只有36.97%。把物理预读从64增加到72还会使受控重叠TPS从3.706降到3.540。跨层推进与L2尚未形成不退化的稳定在线组合，因此不进入标准引擎。

标准profile保留已经验收的缓存收益和准确性路径，避免为尚未兑现的预测覆盖增加SSD竞争、预测计算、回滚或额外通知。实验代码和权重继续保留，后续只有在无损正确性、逐层边界计数、65GB内存及成对TPS门禁全部通过后，才能改变该默认。

## 显式实验开关

- `--inference-mode legacy`：原始逐层执行对照。
- `--inference-mode guarded|window`：跨层研究，仅显式开启。
- `--burst-top 2|4`：有损Burst，仅显式开启。
- `--l1-policy baseline|dual_fast75|probation32_8`：L1策略对照。
- `--main-slots`、`--l1-shape`：容量实验。

未来生成Runtime与DS4.1F模型Package时，应把本文件的标准配置写入Package/Worker启动参数，并保留相同manifest字段；当前修改不冒充已发布Runtime。

## 默认入口验证

不传`--inference-mode`运行8-token严格`F_NOCACHE` smoke：manifest选择`packet`，L1全部40、L0全部8、`eviction_dual`和零复制晋升生效；8个Decode token恰好320次packet check，guarded/window为0，峰值52.459GB。

同输入显式`legacy`对照的generated IDs、全部9步logits SHA-256、cache统计、专家读取字节完全一致。验证回执：

- `artifacts/dsv41-standard-engine-default-smoke-20260917/verification.json`
- `artifacts/dsv41-standard-engine-default-smoke-20260917/parity.json`
