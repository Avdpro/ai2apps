# 冻结 v1 与逐层缓存检查

冻结目录：`artifacts/dsv41-frozen-mlx-v1-20260913`。归档含当前 MLX 与参考
源码、native loader、官方实现/config、专家 store 元数据和四组最终基准。
`freeze.json` 记录逐文件哈希、归档哈希、基础提交和依赖版本；已读回校验。
原始大权重和专家 payload 外置。未提交或改动共享工作区的其他修改。

## L1 / Scope

每层 L1/Main 40，L0/Hot 8。L1 根据本请求完整 Prefill 的路由计数选择
Top-40，平频按专家 ID，不足补 ID；Decode 期间不变。L0 使用 LRU。
未接入 Scope profile/分类/切换，未实现 Decode 晋升、滑动频次或分层容量。
各层容量相同。L1 是上下文预热，不是基于领域语料训练的 Scope。

## 逐层结果

独立诊断 wrapper：`experiments/dsv41_analysis/profile_frozen_cache.py`，
在 close 时导出已有 GPU 计数及捕获的路由。未修改冻结模型；逐文件哈希一致。
使用原始 2048 benchmark prompt、32 Decode，33 个输出 ID 与冻结基准一致。

| 层（从 0 编号） | L1 命中 | L0 命中 | 总命中 | Decode 不同专家数 | 相邻 token 平均共用专家数 / 6 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 68.23% | 0% | 68.23% | 91 | 0.35 |
| 1 | 73.96% | 0% | 73.96% | 73 | 1.39 |
| 2 | 84.90% | 1.56% | 86.46% | 60 | 2.35 |

前三层合计 76.22%，后 37 层 88.85%，全模型 87.90%。第 0/1 层明显
更分散、相邻 token 复用少；第 2 层已接近整体。低命中不只出现在前面：
19/39 层分别 75.52% / 75.00%。前三层占全部 misses 的 137/929 = 14.75%。

另用 26-token 天空问题固定生成 32 步：第 0/1/2 层总命中
31.77% / 52.08% / 66.67%；前三层平均 50.17%，后 37 层 63.09%。
该固定 benchmark 在 EOS 后仍继续执行，且输入不是聊天模板；只作为缓存
压力诊断，不代表正常会话质量或 EOS 前吞吐。2048 输入本身也有重复内容，
不能将它的较高覆盖率外推到真实多领域输入。

诊断输出：`artifacts/dsv41-frozen-layer-profile-20260913` 和
`artifacts/dsv41-frozen-layer-profile26-20260913`。每个目录含逐层 counters、
Main ID、Decode routes 和 provenance。此类抓取耗时不覆盖冻结性能成绩。

## 判断

本次支持优先研究前两层的分层策略，不能直接沿用 DS4 的“前三层”固定规则，
更不能把路由分散等同随机。当前官方 Gate 是学习权重与 correction bias
的 Top-K 选择，不是前三层特殊 hash router。

下一阶段建议先对逐层 miss 曲线做容量收益分析，再比较 Decode 动态晋升与
Scope bootstrap；保持 65 GB 预算，不先给每层统一扩容。Scope 是否有效需要
独立领域样本训练/验收，不能用同一轨迹构建 profile 又宣称通用命中率。
