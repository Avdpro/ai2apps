# Bot Task Context 与 DeepSeek Cache 核查（2026-11-08）

本轮区分输入长度、缓存用量、Cloud Points，不把命中缓存等同于减少逻辑输入 Tokens。所有线上探针只请求短文字，没有执行业务 Tool、绘图或重跑用户任务；凭据未写入脚本或收据。真实任务上下文只在本机离线分析。

## 实测结论

Dev 的 BYOK `cloud/deepseek/deepseek-flash` 与此前 App-Dev 使用的托管 `cloud/ai2apps/deepseek/deepseek-v4-flash` 是不同调用链，不能混为一谈。

Dev 历史 794 次有报告调用：768 次命中，输入 18,981,318 Tokens，命中 10,612,736，按输入加权命中率 55.91%。原生 `prompt_cache_hit_tokens` 和 `prompt_tokens_details.cached_tokens` 在这些记录中没有不一致。另有两次无用量报告，不补零。本轮审计为当时数据库快照，不代表全部产品实例或未来命中率。

使用 Dev 已配置 Key 直连供应商，冷请求 1,916 输入/0 命中；相同请求第二次 1,916/1,664；尾部追加 1,923/1,664；头部插入变动内容 1,934/0；相同头部再次发送 1,934/1,792；流式同请求 1,934/1,792。原生和 OpenAI 风格缓存字段完全一致。

通过标准 Dev Installation Cloud 调用链，对同一合成输入连续三次调用：Cloud 原始返回均为 `inputTokens=1916, cachedInputTokens=0, cacheUsageReported=true, cacheUsageSource=upstream-reported`。本地转换保持相同数值。此证据将问题边界定位在托管 Cloud 及其供应商链路，不足以单独判定是上游真实未命中、模型路由不同，还是 Cloud 字段提取有误。详见独立 Cloud 变更核查要求。

## 本地改进

通用 Agent 每步仍向 owner 获取当前作用域的发现数据。模型投影仅忽略宿主顶层 `observed_at` 的刷新差异，保留数据原始业务时间字段：

- 首个发现快照保留在 Run 的原位置；内容未变不重写时间戳。
- 发现数据、版本、可见性或可用状态真实变化，追加新的不可信数据快照；最新快照取代旧覆盖范围。
- 变化为无可用发现数据时，追加空快照，不能继续声称旧范围仍然有效。
- 变化历史在后续请求中回放到原位置，恢复来自当前 Run 的持久模型请求，不设跨用户/跨 Run 全局缓存。
- 当前权限、Tool 目录可见性、Provider 版本及精确参数契约检查不变；快照不是授权。
- 新投影的发现数据、可信声明和参数契约去除 JSON 分隔空格，字符串值、schema、字段与约束不删减。旧可信审阅消息仍保持原字节回放。

该修改不自动归纳/删除用户历史，不丢弃旧任务产物，不缓存 Tool 执行结果，也不依据业务身份做分支。

## 合成数据线上 A/B

相同的 100 条合成目录数据，分属两个任意 Provider、每个 50 条，遵守单 owner 8 KiB/整体 16 KiB 边界，仅第二步观察时间变化：旧投影两次各 2,817 输入、0 命中；新投影两次各 2,442 输入，第二次命中 2,304（94.35%）。该夹具输入减少 13.31%；两次合计未缓存输入由 5,634 降为 2,580，减少 54.21%。最初单 Provider 100 条的探针仅为投影原语校准，超过单 owner 大小边界，不作为真实发现夹具的验收数据；原始收据保留为 synthetic-context-ab-initial.json。此为真实 DeepSeek API、合成 Context，不是用户 Bot 任务 E2E，也不能外推全部 Task 节省相同比例。探针短输出，耗时不用于宣称性能提升。

真实 Dev 一条任务的 11 个请求仅压紧可信声明字符串，离线字符体积减少 5,885 / 1,178,781（0.50%）；这不是 Tokens 实测。大幅减量仍需单独设计历史工具回执摘要、契约引用和按需发现，不能把本轮缓存前缀修复宣称为已经兑现此前估算的 40%–60% 总 Tokens 降幅。

## 验证与收据

- 50 项定向测试通过：跨任意 Provider 快照、时钟变化、真实更新、撤回、恢复及显式/懒加载目录，原生缓存统计、精确契约与权限边界。
- 完整 AaAT 门禁：1,301 passed / 2 failed，1183.93 秒。两项与此前门禁相同：`test_multibot_review_background_intersection_and_durable_aggregate` 后台协作未完成，以及 `test_installed_first_party_provider_fields_have_owner_translations` Gallery summary 映射类型不符；不标为全绿，不改动门禁或业务规则绕过。
- 原始用量、请求 ID 与离线聚合保存在 `acceptance/deepseek-cache-context-20261108/`，不含密钥或用户 Prompt。
- DeepSeek 参考：<https://api-docs.deepseek.com/guides/kv_cache/>、<https://api-docs.deepseek.com/api/create-chat-completion/>。

## 后续减量计划与验收门槛

1. 本轮：完成原始 usage 对照、发现快照稳定、JSON 紧凑投影；保留源记录和当前授权检查。已激活 Dev，不重启 App-Dev。
2. 契约去重：设计模型 Context 中完整 schema 的单一当前投影；旧工具回执只引用可读取的原始 step/版本，不能把不可信工具内容提升成可信声明。必须覆盖任意 Provider、版本变更、模型选择变更、恢复及撤权，先做同任务轨迹离线体积对照，再用合成业务 E2E 验证调用轮数没有增加。
3. 任务续接：保留目标、用户约束、实际产物、未解决问题和执行凭据；旧能力发现及冗余进度回执按可追溯摘要投影。用户事实、素材来源、失败/不确定执行不能因压缩丢失或被自动重放。需要独立设计与验证，不在本轮低风险修复中提前删除历史。
4. 托管 Cloud：按独立核查要求确认真实路由、raw usage 与归一化。未经证据不修改本地统计来伪造命中，不根据本轮 BYOK 比率修正旧 Cloud 数据。

每阶段分别报告逻辑输入、输出、实际命中/未命中、未知报告数、模型调用次数、真实结算、任务结果正确性；首次调用与续步分列。缓存命中率不能靠填充无用上下文提高，命中增加也不能掩盖输入膨胀。
