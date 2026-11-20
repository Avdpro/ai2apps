# DeepSeek Cloud 生产缓存修复：Local 验收

日期：2026-11-08。对应 Cloud 发布 `deepseek-cache-20261108-v1`。

依据用户交付的 Cloud 客户端合同及生产回执执行，仅修改本地接收/统计；没有修改 Cloud、费率或历史账。使用 Dev 正常 Installation/actor/Device 身份，经当前托管路由 `cloud/ai2apps/deepseek/deepseek-v4-flash`。没有提交上游 user_id、读取 Cookie、导出凭据或调用 BYOK 替代托管路由。

## 真实生产请求

输入为约 1,916 Token 的稳定合成档案文本，要求仅答 OK，max_tokens=16。正常 requestId/幂等键各不相同，身份、模型与参数保持一致。JSON 四次后，SSE 使用相同输入序列，因此 SSE 的首项已经由 JSON 预热，不能称为独立冷测。

| 输入 | JSON 命中 / 输入 | SSE 命中 / 输入 |
|---|---:|---:|
| 基础输入首次 | 0 / 1,916 | 1,664 / 1,916（已预热） |
| 完全重复 | 1,664 / 1,916 | 1,664 / 1,916 |
| 仅尾部追加 | 1,664 / 1,919 | 1,664 / 1,919 |
| 头部新增 | 0 / 1,919 | 1,664 / 1,919（JSON 已预热该变体） |

重复基础输入命中约 86.85%。所有八次 `cacheObservation.integrity=valid`、`source=both`，hit+miss=input；原始 Cloud usage 与 Local cached_tokens/input 逐字段一致。SSE 四次还调用请求结果查询，均 completed，持久查询的 usage 与 SSE 终态完全一致。没有以固定命中率为门槛；结论是托管路由已证实能够跨不同请求 ID 命中，JSON/SSE 的结果一致。

JSON 基础冷/重复 requestId：

- `7859a636-7fd2-41a8-8efb-939d07223ffc`
- `adab3838-f61e-4306-8dc1-74432feb54da`

其余 ID 和数字回执见 [JSON 回执](acceptance/cloud-cache-production-20261108/json-receipts.json)、[SSE 与结果查询回执](acceptance/cloud-cache-production-20261108/sse-receipts.json)。只保存 usage、requestId 与状态，不保存凭据和输入正文。

## Local 对接

- Cloud Gateway 为 JSON 和 SSE 使用同一归一化入口，保留可选 `ai2apps.cache-observation.v1` 的白名单观测字段；未知诊断字段不透传。
- 有效、已上报并与总输入相符的 hit/miss 才投影 cached_tokens；明确零保留为零。未上报、冲突/非法观测不把兼容占位 0 当真实命中数。
- Agent 用量行保留 cache_observation，现有“未上报”和未知历史的处理继续生效。不回填旧运行、不按 Token 反算计费，不改变消息角色或顺序。

专项门禁选择 14 项通过；Gateway JSON/SSE 和用量对接测试最终选择 21 项通过、4 项未选。均为定向检查，未跑完整 App 回归。真实模型证据为上述生产八请求；Bot 中持久指标/UI 的端到端新任务不在此验收范围。

Local 已通过标准 Helper 空闲重载加载到 Dev（端口 58440），来源/健康/服务资源核验通过，App-Dev 未改动。最终代码对 JSON 原始收据重新归一化，完整保留 cacheObservation 且数值一致；SSE 的四个真实请求已使用新代码完成。收据见 [Local 验证](acceptance/cloud-cache-production-20261108/local-verification.json)。
