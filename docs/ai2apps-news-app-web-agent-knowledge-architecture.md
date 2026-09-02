# AI2Apps《新闻》App：基于 Web Agent 与 Knowledge 的技术方案

状态：实施方案 v0.2  
日期：2026-08-29  
产品依据：`ai2apps-news-app-draft.md`  
技术依赖：`ai2apps-publishable-adaptive-web-agent-architecture.md`、
`ai2apps-local-knowledge-rag-architecture.md`、`agent-task-runtime.md`

## 1. 决策摘要

《新闻》App 是 AI2Apps 面向个人的信息采集、事件组织和简报消费 App。它不自行实现
网站爬取器，也不直接持有 WebDriver BiDi 凭据：

- **Web Agent** 负责访问来源、处理允许处理的页面阻碍、提取列表和正文、增量比较；
- **Knowledge** 负责保存获得授权的原始内容、派生表示、Embedding、检索、引用与 Bucket；
- **News Core** 负责来源配置、去重、事件聚类、Claim、时间线、相关性、重要性、简报和通知；
- **AgentRun/Scheduler** 负责每日计划、幂等运行、恢复和用户接管；
- **News App UI** 负责 Today、Sources、Events、Topics、Briefings 和 Settings。

```text
News source configuration
          |
          v
Scheduler / durable AgentRun
          |
          v
System Agent Broker -> Local Compiled Agent IR -> AceFox BiDi / allowed HTTP
          |
          v
ArticleFeedResult / WebDocument + provenance
          |
     +----+------------------+
     |                       |
     v                       v
Knowledge ingest        News normalization
and retrieval           dedupe / event / claim
     |                       |
     +-----------+-----------+
                 v
         personal ranking
                 v
 Today / Event / Topic / Briefing / Notification
```

## 2. 产品边界

### 2.1 News App 负责

- 用户兴趣、排除项、主题、消息源和通知规则；
- 来源与 Web Agent Provider 的绑定状态；
- 文章记录、跨来源重复关系和事件时间线；
- 事实、来源说法、传闻和 AI 推断的分层；
- 个性化相关性、重要性和新颖性；
- 每日简报、事件卡和专题；
- 对来源、Knowledge Item 和 Agent Run 的追溯。

### 2.2 Web Agent 负责

- `web.article_feed`：获取当前列表与新增条目；
- `web.read_document`：提取允许访问的正文和元数据；
- `web.page_access`：处理 Cookie/低风险 Blocker及用户接管；
- 站点专用分页、无限滚动、搜索或 API/RSS Adapter；
- Pipeline 校验、drift 检测和本地修复；
- provenance、checkpoint 和结构化失败。

### 2.3 Knowledge 负责

- 原始网页、文本、图片和附件的权威 `KnowledgeItem/Asset/Representation`；
- Bucket、ACL、来源、digest、时间和删除治理；
- FTS5、语义索引、混合检索和引用 Envelope；
- News App、Chat 和其他 App 的受授权检索；
- 可重建的派生表示，不承担新闻事件业务状态。

### 2.4 非目标

- 不绕过付费墙、CAPTCHA、登录授权或服务条款。
- 不把搜索摘要作为事实证据。
- 不把所有采集正文默认永久保存或公开分享。
- 不用一篇 LLM 摘要替代来源、Claim 和事件模型。
- MVP 不承诺覆盖所有社交平台、视频直播和封闭 API。

## 3. 领域模型

### 3.1 NewsProfile

每个 actor 的新闻主编配置：

```text
id, actor_id, name, locale, timezone
interest_prompt, exclusion_prompt
daily_item_limit, briefing_schedule
default_knowledge_context_id
notification_policy_json
created_at, updated_at
```

兴趣说明是可查看、可编辑的显式配置，不是不可解释的隐式画像。

### 3.2 NewsSource

描述一个规范化来源，而不是某次抓取：

```text
id, profile_id, name
source_url, normalized_origin, source_kind
topic_ids, priority, enabled
collection_schedule, locale
rights_policy, retention_policy
created_at, updated_at
```

`source_kind`：`web_agent | rss | authorized_api | user_link | connected_account`。

### 3.3 SourceBinding

记录来源解析到哪个 capability Provider：

```text
source_id
capability = web.article_feed
package_id, package_version, pipeline_id, pipeline_generation
grant_id, profile_binding
resolver_status, last_validated_at
health_status, last_error_code
```

用户可以使用自动解析结果，也可以固定 Provider/version。升级或 local patch 不改变 Source ID。

### 3.4 CollectionRun

引用持久化 `AgentRun`，保存新闻领域结果：

```text
id, source_id, agent_run_id, schedule_slot
provider identity, checkpoint_before, checkpoint_after
started_at, completed_at, status
item_count, new_count, updated_count
validation_status, error_class
```

同一 `source + schedule_slot` 使用幂等键。

### 3.5 NewsItem

新闻数据库中的轻量文章记录：

```text
id, source_id, canonical_url, source_item_id
title, author, published_at, discovered_at, updated_at
language, media_kind, rights_policy
content_fingerprint
knowledge_item_id nullable
agent_run_id, provenance_json
status
```

NewsItem 不复制 Knowledge 中的完整权威正文。需要保存正文时写入 Knowledge，并保存
`knowledge_item_id`。

### 3.6 StoryOccurrence 与 NewsEvent

`StoryOccurrence` 表示某来源的一次报道；`NewsEvent` 表示多个来源共同描述的现实事件。

```text
NewsEvent:
id, profile_id, domain, canonical_title
summary, status, first_seen_at, last_updated_at
importance, relevance, novelty, confidence
topic_ids, entity_ids

StoryOccurrence:
event_id, news_item_id
relationship = primary | follow_up | commentary | duplicate | correction
stance, evidence_weight, linked_at
```

新报道优先更新已有事件，而不是总是创建新事件。

### 3.7 Claim

Claim 是可追溯的原子说法：

```text
id, event_id, normalized_claim
claim_type = fact | source_statement | report | rumor | ai_inference
verification_status = confirmed | corroborated | disputed | unverified | retracted
first_seen_at, last_checked_at
```

ClaimEvidence 指向 NewsItem/Knowledge citation，并记录来源、原文片段位置、发布时间和
提取时间。AI 生成的结论不能没有 Evidence 或明确标记为 inference。

### 3.8 Topic、Briefing 与 Feedback

- `Topic`：AI 科技、NBA、球队、公司或用户自定义专题；
- `Briefing`：某个时间窗口内按模板生成的不可变版本；
- `Feedback`：重要、不重要、已知道、以后少看、来源不可信、事实有误。

Feedback 更新显式偏好和排序特征，不改写历史 Evidence。

## 4. Knowledge 设计

### 4.1 Bucket 与 Context

News App 创建 `consumer_app_id=ai2apps.news` 的 Knowledge Context。建议默认提供：

- `News Inbox`：近期自动采集、待治理内容；
- `News Archive`：用户确认长期保留的内容；
- 主题 Bucket：用户可选，例如 `AI Technology`、`NBA`；
- 外部共享内容只有用户显式发布后才能进入允许的 federated bucket。

所有 Bucket 遵守 Knowledge 原有 private、installation、local shared 和 federated 边界。
News App 不创建绕过 ACL 的隐藏索引。

### 4.2 摄取策略

每个来源可配置：

1. `metadata_only`：仅保存标题、URL、时间和摘要；
2. `on_demand`：打开或进入事件时读取正文；
3. `new_items`：仅为新增 Item读取正文；
4. `important_only`：先分类，达到阈值才读取和入库；
5. `full_authorized`：对有明确授权的来源保存完整内容。

默认优先 `new_items` 或 `important_only`，减少带宽、存储和版权风险。

### 4.3 KnowledgeItem provenance

写入 Knowledge 时至少记录：

```json
{
  "source": {
    "kind": "webpage",
    "url": "https://...",
    "domain": "example.com",
    "collected_at": "..."
  },
  "collector": {
    "consumer_app_id": "ai2apps.news",
    "agent_run_id": "arun_...",
    "package_id": "...",
    "package_version": "...",
    "pipeline_id": "...",
    "pipeline_generation": 4,
    "extraction_method": "site_pipeline"
  },
  "rights": {
    "policy": "limited_quote_and_link",
    "retention": "30d"
  }
}
```

相同 canonical URL 和内容 digest 应幂等更新 representation/revision，不重复创建无关 Item。

### 4.4 删除与保留

- 来源关闭不自动删除用户明确归档的 KnowledgeItem；
- 自动 Inbox 内容按 retention policy清理；
- 删除 NewsItem 时，如果 KnowledgeItem 被其他 Bucket/事件引用，不能级联误删；
- 来源撤回或更正产生状态/新 revision，不静默改写已生成简报；
- 用户可查看每个 Bucket 的自动采集来源和占用空间。

## 5. 来源接入与 Discovery

用户添加 URL 后：

```text
normalize source
→ resolve web.article_feed locally
→ if missing, query Discovery
→ show matching Agent Sources, Publisher and requested permissions
→ install selected Pack and verify signed Agent Source
→ compile locally, minimize capabilities and authorize
→ first-run site binding + calibration
→ bind SourceBinding
→ enable schedule
```

Discovery 中的 Agent Source 是权威发布物。Publisher 可以附带预编译 IR、Selector 或
Extractor Hint，但 News 不得直接执行；Agent Broker 必须在本机重新编译或逐项验证，生成
Local Compiled IR 后才能绑定来源。

若没有 Pack，可以从用户描述和 URL Zero-shot 生成本地 Agent Source。生成结果仍需经过
本地编译、最小权限检查、首次站点绑定、Validator 和 calibration 后才能启用每日任务。
后续如果 Discovery 出现官方/Publisher Pack，系统可以比较 Source、权限和健康度并建议迁移，
但不能无提示替换本地健康 IR。

来源状态：

```text
pending_provider -> compiling -> binding -> calibrating -> active
active -> degraded -> needs_login / needs_user / drifted
drifted -> repairing -> active / disabled
```

## 6. 每日采集流程

```text
1. Scheduler creates idempotent CollectionRun
2. Broker invokes web.article_feed with previous checkpoint
3. Web Agent opens/reuses page and runs PageAccessAgent
4. Local Compiled IR extracts, validates and diffs items
5. News Core upserts NewsItem metadata
6. Policy selects which new/updated items require web.read_document
7. WebDocument is ingested into configured Knowledge bucket
8. Classification and embedding match interests/topics
9. Deduplication links near-identical reports
10. Event linker creates or updates NewsEvent
11. Claim extraction and source corroboration update Evidence
12. Ranking computes relevance, importance and novelty
13. Briefing/notification policy emits user-facing results
14. Checkpoint commits only after source collection validation
```

正文读取失败不应回滚已经验证的列表 checkpoint，但必须把 Item 标记为 `content_pending` 并
单独重试。事件和通知不得把未读取的标题推断当成已确认事实。

## 7. Agent 调用示例

列表请求：

```json
{
  "capability": "web.article_feed",
  "target": {"url": "https://example.com/news"},
  "options": {
    "only_new": true,
    "limit": 100,
    "checkpoint": "opaque"
  },
  "context": {
    "consumer_app_id": "ai2apps.news",
    "source_id": "nsrc_..."
  }
}
```

正文请求：

```json
{
  "capability": "web.read_document",
  "target": {"url": "https://example.com/news/article"},
  "options": {
    "readability": "preferred",
    "rendered_html_fallback": true,
    "screenshot": "when_required"
  },
  "context": {
    "consumer_app_id": "ai2apps.news",
    "news_item_id": "nitem_..."
  }
}
```

News 只接受通过 Broker 返回的 Schema Envelope，不信任 Pack 自报的 actor、Package identity、
权限、校验状态或 provenance。

## 8. 去重、事件与事实处理

### 8.1 三层去重

1. 精确层：canonical URL、站点 Item ID、内容 digest；
2. 近重复层：标题/摘要 Embedding、实体、时间窗口；
3. 事件层：不同来源是否描述同一现实事件。

近重复只用于候选召回，最终事件合并应考虑时间、实体、动作、地点和来源。一次错误合并必须
可拆分并保留审计。

### 8.2 事件更新

新 Item 到来后：

- 检索相关 Knowledge 和近期 Event；
- 产生候选事件；
- 判断 duplicate、follow-up、commentary、correction；
- 提取新的 Claim；
- 与已有 Evidence 比较；
- 更新事件时间线、确认状态和下一观察节点；
- 仅当信息改变用户已有判断时提升 novelty。

### 8.3 来源与 Claim 权重

来源权重按领域和 Claim 类型计算，而不是一个全局“可信分”。官方赛程适合确认比赛时间，
但不一定适合评价球员；公司公告适合确认发布内容，但不是独立产品评价。

高风险或争议结论可以要求两个独立来源。来源转载同一原始报道不能被计算为两个独立证据。

## 9. 个性化与模型策略

### 9.1 分级模型优先级

- Web Agent 健康 Pipeline优先走确定性路径，但允许按 Pack策略调用少量轻量模型；
- exact dedupe、checkpoint 和规则过滤：确定性；
- Embedding召回、主题匹配、近重复、局部语义校验和简单分类：本地或低成本轻量模型优先；
- 高级模型用于首次 Web Agent编译、复杂漂移修复、事件判断、Claim、跨来源比较、解释和简报；
- Broker按任务难度、置信度、隐私策略、延迟和预算升级模型等级，不能把高级模型固定在每次
  来源轮询的热路径上。

### 9.2 排序信号

```text
score = relevance + importance + novelty + source_quality
        + corroboration + urgency - duplication - known_background
```

所有信号应可解释。UI 至少能回答“为什么推荐”“哪些来源支持”“这是事实还是推断”。

### 9.3 成本预算

NewsProfile 可设置每日：

- 最大来源运行数；
- 最大正文读取数；
- 最大模型 Token/Cloud费用；
- 最大通知数；
- 最大保留正文和图片空间。

预算不足时优先保留来源采集与 metadata，延迟低优先级正文和总结，不破坏 checkpoint。

## 10. 调度、恢复与用户接管

- 使用 actor timezone 计算 schedule slot；
- 同一 Source 默认串行，多个 Source 按全局浏览器并发限制调度；
- `AgentRun` 持久化步骤与 action key，Local 重启后恢复；
- 网络错误退避重试，结构漂移交给 Web Agent repair；
- 登录/条款/CAPTCHA进入 `waiting_input` 并在 Sources 页面提示；
- 用户在绑定 AceFox Profile完成操作后恢复同一 Run；
- 临时页面完成后关闭，不抢占用户当前浏览窗口；
- 错过的每日任务在启动后按策略补跑，不能无限追赶旧窗口。

## 11. App UI 与 Mini-Entry

### 11.1 Today

- 必须知道、可能影响、趋势、待证实、可忽略；
- 有限列表，不做无限流；
- 每条显示来源数量、更新时间、确认状态和推荐原因。

### 11.2 Sources

- 添加 URL/RSS/API/连接账号；
- 展示 Web Agent Pack、版本、权限、最近成功和健康状态；
- Test now、重新登录、Repair、切换 Provider、暂停和删除；
- 配置正文策略、Knowledge Bucket、频率和保留时间。

### 11.3 Events

- 当前结论、Claim/Evidence、时间线和来源；
- 区分事实、说法、传闻、争议和 AI 推断；
- 支持拆分/合并事件和查看历史版本。

### 11.4 Topics 与 Briefings

- 自然语言兴趣、来源规则、重要性和通知；
- 早报、晚报、周报与用户模板；
- 专题可持续更新，分享前执行内容和权限检查。

### 11.5 News Mini-Entry

News 可提供 Mini-Entry：

- 将当前网页添加为 Source；
- 将当前文章保存到 Topic/Knowledge Bucket；
- 查看当前页面是否属于已跟踪 Event；
- 对当前页面与已有来源进行对比；
- 显示当前站点使用的 Web Agent Pack 和健康状态。

Mini-Entry 通过 Agent Broker 和 Knowledge Context 工作，不自行连接原始 BiDi credential。

## 12. API 与事件草案

```text
POST /v1/platform/news/profiles
GET  /v1/platform/news/profiles/{id}
POST /v1/platform/news/sources
POST /v1/platform/news/sources/{id}/test
POST /v1/platform/news/sources/{id}/collect
POST /v1/platform/news/sources/{id}/pause
GET  /v1/platform/news/collection-runs/{id}
GET  /v1/platform/news/items
GET  /v1/platform/news/events
GET  /v1/platform/news/events/{id}
POST /v1/platform/news/events/{id}/feedback
POST /v1/platform/news/briefings
GET  /v1/platform/news/briefings/{id}
```

主要事件：

```text
news.source.created/provider_resolved/degraded/needs_attention
news.collection.started/completed/failed
news.item.discovered/updated/content_ingested
news.event.created/updated/merged/split
news.claim.added/corroborated/disputed/retracted
news.briefing.created
news.notification.emitted
```

事件 payload 默认只传 ID、状态和有界统计；正文从 Knowledge 按 ACL 查询。

## 13. 权限、隐私与版权

- 用户明确授权 News App 调用来源能力和写入指定 Knowledge Bucket；
- Web Agent Pack 只获得声明网站和本次 Run 的最小浏览器权限；
- Discovery Agent Source、Publisher Hint 和页面内容都是不可信编译输入；只有通过本地 Policy
  Engine 的 IR 可以执行；
- 账号登录使用用户绑定 Profile，凭据不进入 Agent、模型或日志；
- 具有法律约束力的条款同意、CAPTCHA和身份验证要求用户接管；
- 付费墙只记录 `access_restricted`，不隐藏或读取受限正文；
- 遵守 robots、来源条款、API限制和用户授权，不能以技术可读替代内容权利；
- 默认以有限引用、事实提取和原文链接呈现；
- 自动采集的个人兴趣、浏览来源、截图和正文不进入匿名健康遥测；
- 分享 Briefing/Topic 前检查 Knowledge visibility、来源权利和敏感信息。

## 14. 失败处理

| 故障 | News 行为 |
| --- | --- |
| 网络/站点错误 | 退避重试，保留旧 checkpoint |
| Agent 缺失 | 查询 Discovery Agent Source，或创建 Zero-shot 本地 Source |
| Source 编译失败 | 不绑定来源；显示歧义、权限或 Schema 错误并允许修订 |
| 首次站点绑定失败 | 保留 Source，进入 degraded/needs_user，不启用定时任务 |
| Pipeline drift | 来源标记 degraded，启动 repair，不发送空更新 |
| 登录失效 | `needs_login`，通知用户接管 |
| 条款/CAPTCHA | `needs_user`，不自动同意/规避 |
| 付费墙 | `access_restricted`，只保留允许的 metadata |
| 正文读取失败 | Item为 `content_pending`，列表 checkpoint可提交 |
| Knowledge Runtime缺失 | SQLite/FTS5可用；语义任务降级或排队 |
| 模型/预算不可用 | 保留采集数据，延迟事件分析和简报 |
| 错误事件合并 | 支持拆分并重算派生摘要，不改写来源 Item |

## 15. 分阶段开发计划

### P0：AI 科技来源采集 MVP

- 建立 NewsProfile、NewsSource、SourceBinding、CollectionRun 和 NewsItem。
- 接入 Agent Broker 的 `web.article_feed`、`web.read_document`。
- 支持 Discovery Agent Source 安装或 Zero-shot 本地 Source。
- 接入本地 Source Compiler、权限审计、首次站点绑定和 Compiled IR 缓存。
- 建立 `News Inbox` Knowledge Context/Bucket 摄取。
- 实现定时采集、checkpoint、exact dedupe 和来源健康 UI。
- Today 展示新增文章，提供来源、时间、Agent版本和 Knowledge 链接。

首批来源选择公开且结构稳定的 AI 官方 Blog、研究机构和开发者媒体；避免 MVP依赖封闭社交
平台。

验收：至少 5 个来源连续运行 7 天；Discovery Hint 不被直接执行；第二次健康运行不调用高级
编译模型，允许按预算使用轻量模型；无重复通知；空结果不覆盖 checkpoint；任一 Item 可回溯
Agent Source digest、Local IR generation、Agent Run 和 Knowledge provenance。

### P1：事件与个性化

- 实现 Embedding近重复、实体、Event候选和 StoryOccurrence。
- 实现 Claim/Evidence、confirmed/disputed/unverified 分层。
- 实现自然语言兴趣、排除规则、相关性/新颖性排序。
- 生成有限每日 Briefing并支持反馈。
- Chat通过 News Knowledge Context进行带引用问答。

验收：同一事件多来源报道能聚合；来源仍可单独查看；重要结论有 Evidence；反馈改变后续排序。

### P2：NBA领域与领域模板

- 增加 NBA官方、球队和媒体 Web Agent Pack/RSS/API Adapter。
- 增加比赛、球队、球员、伤病、交易和赛程实体 Schema。
- 提供 NBA重要性规则和 Briefing模板。
- 验证同一平台跨 AI 科技和体育领域的 capability复用。

验收：赛果、伤病、交易和评论不被错误混为同一类型；官方数据与媒体观点明确分层。

### P3：专题、分享与生态

- 长期 Topic、下一观察节点和动态事件页；
- 早报/晚报/周报、音频和分享卡；
- 用户可发布主编模板，但不携带个人来源凭据或私有 Knowledge；
- 第三方 App 可在授权后消费 News Event capability；
- 完善来源权利、保留、删除和存储治理。

## 16. 测试与验收矩阵

- 公开静态站、SPA、RSS、登录站和 API来源；
- Web Agent Pack安装、升级、local patch、drift和回滚；
- 多语言标题、时区、错误发布时间和 canonical URL；
- exact/near duplicate、转载链、事件合并与拆分；
- correction、retraction、传闻和来源冲突；
- Knowledge ACL、Bucket切换、删除、降级和索引重建；
- Scheduler重启、重复 slot、预算耗尽和部分失败；
- 登录接管、条款、CAPTCHA和付费墙边界；
- 分享时的私有来源、受限正文和敏感数据检查；
- Prompt injection、恶意 Pack输出和伪造 provenance。

## 17. 成功指标

- 来源采集成功率和 drift恢复时间；
- Web Agent Tier 0命中率、轻量模型调用率、高级模型升级率与每来源模型成本；
- 新文章检测 precision/recall和重复压缩率；
- 事件合并准确率及用户拆分/纠正率；
- 重要事件遗漏率和通知有用率；
- Claim可追溯比例和来源回读成功率；
- Briefing阅读、反馈和节省时间；
- Knowledge存储、索引和自动保留成本。

## 18. 首个端到端示范

建议以“AI 科技每日简报”作为首个闭环：

```text
5-10 个公开来源
→ Discovery Agent Source 或本地 Source
→ 本地编译、站点绑定和 Provider 激活
→ 每日 article_feed 增量采集
→ 重要新增 read_document
→ News Inbox Knowledge摄取
→ 去重与事件聚类
→ 10 条以内个人简报
→ 每条可查看原文、Knowledge引用和 Agent provenance
```

Fratello 可以继续作为 Web Agent机制测试 Pack，但 News App产品 MVP应优先选 AI 科技来源，
与现有用户和 Knowledge能力更一致；NBA在事件模型稳定后作为第二个领域验证。
