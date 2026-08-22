# AI2Apps Local Knowledge 与 RAG 开发计划

Status: Implementation in progress v0.6
Last updated: 2026-08-22
Architecture source: [Local Knowledge and RAG Architecture](ai2apps-local-knowledge-rag-architecture.md)

## 1. 实施原则

开发按小型垂直切片进行。每个阶段都必须保持 AI2Apps 可启动、现有 Chat/Agent/Document
行为兼容，并为新增 schema、ownership、Job recovery 和索引后端提供自动化测试。

优先级顺序：

1. 权威对象、权限和来源；
2. 无模型可用的基础摄取与 FTS；
3. Knowledge App 和 Chat 手工保存闭环；
4. 可选 semantic backend；
5. 多模态与时间事件；
6. 自动记忆和更复杂检索。

向量不是第一个里程碑。任何阶段都不得将 private 内容发送 Cloud，除非已有显式、用途
绑定的授权和清晰 UI。

所有检索实现必须位于可替换 protocol 后面。AI2Apps Authority、Chunk ID、ACL、来源和
change log 不随 backend 改变；backend、embedding、retrieval strategy 和 reranker 可以
独立验证、组合、迁移和回滚。

Source Facet、用户 Tag、App namespaced Tag 和 AI inferred Tag 是核心数据契约，不作为
后期 UI 附件。可信来源由 Runtime 写入；模型建议必须携带 confidence、producer 和 evidence。

Knowledge Module 作为 AI2Apps Package 体系的不可执行 `knowledge` kind 实现。Package
Trust、Registry、Discovery、安装/升级/rollback 使用统一基础设施；模块正文和用户 Overlay
分离，索引始终是可以在不同 retrieval backend 上重建的派生数据。

知识桶使用 `KnowledgeSpace` 作为权威边界。private 固定不可跨 Node 分享，installation
shared 固定为本机范围；跨 Node 只允许 core 显式发布到 federated bucket，并复用 NodeLink、
NodeGrant、Federation Gateway 和 MCP/Service contract 做单跳、query-only 检索。

RAG 增强能力不作为 Host 内嵌库交付。Vector backend、OCR/STT/VLM 和其他带原生代码的
组件通过隔离 `.ai2service`/Worker 运行，并声明对独立 Runtime Package 和模型包的依赖；
Runtime 原生 payload 必须经过 Developer ID 签名、Apple 公证/staple 与 Gatekeeper 验证。
纯数据 `.ai2knowledge` 不需要 Apple 公证，但必须通过 AI2Apps Package Trust，并拒绝任何
可执行 payload。缺少或不兼容 Runtime 时必须保持 FTS-only 可用。

## 2. 前置工作

### 开工决策门

以下决定会影响 K1 schema、权限或不可逆的数据语义，正式编码前需要由项目 owner 接受并
记录为 ADR。表中给出推荐基线；若无反对，应以推荐值冻结，避免实现阶段反复等待选择。

| 决策 | 推荐基线 | 状态 |
| --- | --- | --- |
| Release A 边界 | private/shared、Note/URL/PDF/现有 Document/Chat selection、FTS、Knowledge App/Ask；不含 embedding/OCR/STT/VLM/自动记忆 | **已接受** |
| 数据 authority | Platform SQLite + content-addressed store 是唯一权威；FTS/vector/thumbnail/embedding 全部可重建 | 文档已定 |
| 默认可见性 | 所有新增内容默认 private；shared 必须显式选择，自动流程不得升级 scope | 文档已定 |
| shared 治理 | member 可提交并管理自己的 shared contribution；默认只有 core 治理他人内容；普通成员不能安装知识包 | 贡献/安装规则已接受；core-only 治理为推荐默认 |
| private 生命周期 | core 删除 Member 时必须显式选择 `delete_now`、`retain_locked(until)` 或 `member_export_window(until)`；revoke 立即阻断访问，core 不获得 private 读取权 | 选择处置原则已接受；具体枚举为推荐 contract |
| 存储与配额 | installation 默认 10 GiB；core 可看分项用量并管理；80%/90% 告警，100% 或物理可用空间低于 `max(5 GiB, 10%)` 时阻止增长型操作 | 10 GiB/core 管理已接受；低磁盘线为推荐默认 |
| Cloud 边界 | 默认只允许 Local parser/model；任何正文/图片/音视频外发都需要用途绑定的显式授权 | 文档已定 |
| ID/citation 稳定性 | 沿用 Platform ID/时间规范；Item 和 module stable item key 不因 rechunk、reindex、backend migration 改变 | 文档已定 |
| Package MVP 时序 | `.ai2knowledge` 在 Knowledge Core 之后作为独立 Release B；不阻塞 K1–K5，但其 schema 扩展点在 K1 预留 | **已接受** |
| 高风险模块 | v1 Package contract 支持 risk metadata，但官方健康/药品模块发布必须等审核、时效和 stale policy gate 完成 | 待 owner 接受 |
| 首个 semantic backend | 只做隔离 Service/Runtime 形态的 LanceDB spike；不通过则 Release A 保持 FTS-only，不延期 Knowledge Core | 文档已定 |
| Runtime 安全边界 | Core Local 不 import installable Package code；原生 Runtime 需 Developer ID、公证/staple、Gatekeeper，执行仍须 Worker 隔离 | **已接受** |
| 语音发布隔离 | RAG 先旁路开发独立 Core/测试，不注册 Router/System App、不改语音发布依赖；语音版本发布后再 feature-gated 接入 | **已接受** |
| 目标平台 | 首先保证 macOS arm64 本地发行，同时 schema/API 不绑定平台；Release B 前验证 Linux arm64/x86_64 | 待 owner 接受 |
| 知识桶与 Node 分享 | private=`never`、installation=`local_only`、仅 federated bucket 可按 Node allowlist 导出；Member 不能发布，core 管理 | 分桶/MCP 需求已接受；不可直接分享个人桶为推荐安全不变量 |
| 联邦数据模式 | v1 只做 MCP query-only、短期 citation、无后台复制、无索引/embedding 传输、单跳 | 推荐基线，待与 Node Federation contract 一起冻结 |

开工前还必须产出四个短文档/fixture，而不是只作口头约定：

1. Knowledge threat model 与角色/动作权限矩阵，包括 member shared contribution、core module
   install 和 Member 删除处置；
2. Release A API/Tool contract、错误码和两个用户的 golden fixtures；
3. content/derived/module 存储布局、配额、备份和删除状态机 ADR；
4. 中文为主的最小 retrieval/citation Eval 集及测量命令。

以下选择不是 K1–K5 的开工 blocker，可按阶段冻结：embedding 模型与维度、LanceDB 最终
采用与否、reranker、OCR/VLM/STT 型号、包内预计算向量、外部 Qdrant/Chroma、自动记忆、
订阅和跨节点语料复制。query-only Federation 的 schema/policy 扩展点必须在 K1 冻结，但
完整 K11 不阻塞 Knowledge Core。不得为了提前选定这些组件而推迟 K1–K5。

### K0：契约冻结与安全补线

目标：在新增 Knowledge API 前，冻结 principal、scope 和管理面授权边界。

工作项：

- 定义 `app.knowledge.use` 与 `knowledge.*` capability vocabulary；
- 固化 member 可提交 shared、只能治理自己的贡献、普通成员不能安装知识包，以及 core
  默认治理他人 shared contribution 的权限矩阵；
- 为当前 Capability、Package、Browser、Remote 管理 Router 接入可信 principal 和
  `app.system.manage`，避免新 Knowledge App 建立在不完整多用户边界上；
- Member 删除 API/UI 要求 core 显式选择 private 的 delete/locked retention/member export
  window 和 shared contribution 的 retain/transfer/delete；不得把 private 导出给 core；
- 定义 Knowledge API error、404-on-IDOR、idempotency 和 revision/ETag contract；
- 建立威胁模型：IDOR、stale vector row、SSRF、prompt injection、恶意文档、EXIF 泄露、
  shared poisoning、Cloud 数据外发、deletion lag、private bucket export、伪造 Node/bucket、
  transitive federation、remote query leakage 和恶意远端 excerpt；
- 与 Node Federation 冻结 Knowledge remote capability、NodeGrant bucket allowlist、grant epoch、
  单跳 route、短期 citation handle、query/result/bytes quota 和 revoke contract；
- 保存已经接受的 Release A、shared 治理、private 生命周期和 10 GiB/低磁盘策略 ADR，并
  继续确认 Package 时序和目标平台基线；
- 冻结第一版 golden Eval/fixture，后续 backend 只能在同一数据集上比较。

验收：所有非管理员角色无法操作 installation-wide 管理 API；两个用户的 Knowledge
权限矩阵形成 contract tests；架构决策无未定义的 payer/actor/owner 来源。

## 3. 核心实现阶段

### K1：Knowledge schema 与 Repository

目标：建立不依赖 embedding 的权威 Knowledge 对象。

建议模块：

```text
ai2apps/knowledge/
  models.py
  repository.py
  policy.py
  provenance.py
  __init__.py
ai2apps/api/knowledge.py
```

工作项：

- 增加 KnowledgeSpace、Item、Asset、Representation、Chunk、Job、IndexGeneration、
  BackendInstance、RetrievalProfile、ChangeLog、BackendMigration、SourceFacet、Tag 和
  ItemTag schema；
- KnowledgeSpace 增加 private/installation/federated kind 与 immutable shareability invariant；
  增加 published revision、source lineage、FederationExport 和 bucket policy schema；
- 增加按 installation、space 和 storage class 汇总的 storage ledger；默认 installation
  budget 为 10 GiB，content-addressed blob 按实际物理占用只计一次；
- 每个 active user 延迟创建 private space；installation 创建 shared space；
- 实现 create/get/list/update/delete/share 与 tombstone；
- 实现 owner、created-by、visibility、installation 和 source lineage；
- 复用 content-addressed attachment/document blob；
- 增加 repository-level ownership，API 不能绕过；
- 增加 Event 和 audit payload，正文不进入日志；
- 每次 Chunk create/update/delete/share/revoke 在同一 SQLite 事务写入单调 change log；
- active RetrievalProfile/generation 使用原子指针，不在 backend 私有状态中决定；
- 实现 user/app/inferred namespace、normalized key、alias、suggested/confirmed/rejected、
  producer/confidence/evidence；
- Runtime Facet 与请求 payload 分离，Repository 拒绝客户端写入可信来源 namespace；
- 实现 migration、rollback fixture 和数据库重启测试。

验收：private/shared CRUD、分页、过滤、revision conflict、IDOR、撤回共享、成员 revoke、
blob 引用计数、tombstone、Tag namespace、private Tag 隔离和 alias/merge 测试全部通过。

实施状态（2026-08-22）：已建立不接入 App 启动路径的 `ai2apps.knowledge` 独立数据库纵切，
实现 private/installation 内置 Space、不变量、文本 Item、可信 Source Facet、user Tag、FTS5、
SQL 层 principal 过滤、revision 软删除和双用户/双 Installation contract tests。Platform DB
migration、API、App 注册、文件/blob、Job 与完整 Tag lifecycle 留待语音版本发布后的接线阶段。

### K2：基础 ingestion、FTS 与 Job recovery

目标：无需下载模型即可保存并检索 URL、文本、文件和现有文档。

建议模块：

```text
ai2apps/knowledge/ingestion.py
ai2apps/knowledge/jobs.py
ai2apps/knowledge/chunking.py
ai2apps/knowledge/lexical.py
ai2apps/knowledge/sources/
  url.py
  document.py
  chat.py
  artifact.py
```

工作项：

- 创建数据库 lease 驱动的 durable KnowledgeJob dispatcher；
- 实现 content/input hash 幂等和启动恢复；
- 复用 Documents parser，将 DocumentBlock 映射为 Representation/Chunk；
- 增加 note、plain text、Attachment、Artifact ingest；
- 增加 URL fetch 的 SSRF 防护、readability、canonical URL 和本地正文快照；
- 建立 FTS5 表、trigger/repository 同步和按 space/time/kind 过滤；
- 根据可信 source object 自动生成 App、Session、Agent、content kind、MIME、URL domain
  等确定性 Source Facet；
- 实现 lexical search、citation envelope 和原件打开链接；
- 实现 80%/90%/100% budget gate 和物理 `max(5 GiB, 10%)` reserve gate；critical 时保持
  read/search/export/delete 可用，拒绝 ingest 并暂停增长型 Job；
- 自动清理只覆盖无引用 staging/temp、过期 retired generation 和明确可重建的非 active
  cache，不自动删除 Item、active ModuleVersion 或 Overlay；
- 失败以 partial/waiting dependency 呈现，不阻断已有结果。

验收：无 embedding 模型、无网络和增强依赖缺失时 Knowledge App backend 仍可保存本地
内容并按可信 Source Facet 搜索；进程在每个 stage 中断后重启不会重复 Item 或 Asset。

### K3：Knowledge Service、Tools 与平台 API

目标：让 Chat、Agent、Knowledge App 和未来第三方 App 通过统一 contract 使用知识。

工作项：

- 注册 `ai2apps.knowledge-service` embedded Service；
- 实现 `knowledge.add_*`、search/get/update/delete/share/status Tools；
- 实现 Tag list/create/assign/remove/confirm/reject/merge Tools；
- ToolCallContext 派生 actor/installation/Session，不接受 payload 自报身份；
- 实现 `/v1/platform/knowledge/*` API；
- Search API 服务端解析 logical scopes 为实际 Space IDs；
- 允许 member 向 shared space 创建并治理自己的 contribution；治理他人 Item 需要 core
  authority，不能由客户端 owner 字段或普通角色绕过；
- 支持 idempotency key、cancel、retry、Job progress 和 replayable Event；
- 加入 Tool schema、effect、capability、action preview 和 audit；
- 增加 API/OpenAPI contract tests；
- Search 支持 Facet/Tag exact filter，并对 user/App/inferred Tag 使用不同可信等级；

验收：同一 ingestion/search 操作从 REST、Tool Gateway 和 Agent 调用得到相同权限与结果；
普通成员不能通过 Tool 参数访问其他 private space。

### K4：Knowledge App 基础闭环

目标：交付可独立使用的内置知识库 App。

工作项：

- 在 system App manifest 注册 `ai2apps.knowledge` singleton/user；
- 增加 Library、Timeline、Shared、Inbox、Sources、Settings；
- 预留 Buckets 与 Shared Nodes 页面；Release A 只显示 private/Local Shared，federated 操作
  在 K11 contract ready 前 feature-gated；
- 支持拖入/选择文件、粘贴 URL、文本 Note 和范围选择；
- 展示 parse/index progress、partial、dependency required 和 retry；
- 展示原始来源、时间、作者、scope、派生表示和磁盘占用；
- 普通成员显示自己的空间用量；core Settings 显示默认 10 GiB 预算、original/derived/module/
  staging、private/shared 分项、增长趋势、最大贡献者和可回收估算，并允许调整预算；
- 增加 Tag 浏览、过滤、自动补全、别名、合并、来源和建议确认/拒绝；
- Source Facet 只读显示，不能伪装为可编辑用户 Tag；
- 实现 share/retract/delete 二次确认；
- 增加移动端最小 Library/Search，复杂设置可暂留桌面；
- 完成角色可见性、Shell mount、CSP 和窄屏测试。

验收：新用户打开 App 不需要安装额外依赖；能够加入 URL/PDF/图片原件/Note，随后按
关键词、时间、类型、来源和 Tag 找回并打开证据；private Tag 不进入其他成员补全结果。

### K5：Chat 保存与 Knowledge Ask

目标：建立 Chat ↔ Knowledge 双向闭环。

工作项：

- Chat message/turn/selection/attachment/link/Artifact 菜单增加“加入知识库”；
- 保存面板提供 title、private/shared、selection 和 note；
- 保存面板显示只读 Chat/App/Session/Agent Source Facet，并允许输入 user Tag；
- App/AI Tag 建议独立展示，可接受或删除，不默认伪装为用户确认；
- 禁止保存 system prompt、hidden reasoning、Secret 和无权 Tool output；
- Knowledge App 建立 App-owned Ask Session；
- 实现 token-aware KnowledgeContextBuilder 和 citation Message parts；
- answer synthesis 使用现有 Model Runtime Service；
- 无证据或低置信度时返回明确不确定性；
- 将 evidence 打开动作映射回 webpage/file/image/Chat Session/Artifact。

验收：Chat 内容能手工保存并在 Knowledge Ask 找回；回答引用可打开；可信 Chat/App
Facet 不能伪造；用户 Tag 和建议来源显示正确；未保存的 private Chat 不会因使用
Knowledge Ask 被自动持久化。

### K5M：可信 Knowledge Module 与 Discovery 安装

目标：让知识集合成为可从 Registry/Discovery 获取、验证、安装、升级和 rollback 的
系统 Package，同时不允许知识包执行代码或绑定某个 RAG backend。

建议模块：

```text
ai2apps/knowledge/modules/
  contract.py
  archive.py
  repository.py
  installer.py
  overlays.py
  risk_policy.py
```

工作项：

- 为统一 Package contract 增加 `knowledge` kind、`.ai2knowledge` extension 和
  `application/vnd.ai2apps.knowledge+zip` media type；
- 定义 `knowledge.yaml`、`files.json`、stable item key、provenance、license、risk 和
  compatibility schema；
- 复用 canonical digest、exact file coverage、Ed25519 publisher signature、immutable
  package store、Registry release 和 Package audit；
- 实现 bounded archive validator，拒绝 path traversal、symlink、archive bomb、特殊设备、
  executable/macro、未声明文件、digest 不匹配和 publisher spoof；
- 扩展 Public Registry descriptor/download/install 支持 `packageType=knowledge`；
- 在 Discovery App 增加 Knowledge 分类、release detail、trust/risk/license/size/dependency
  展示和 private/installation 安装确认；
- 实现 verify → stage → ingest → index → validate → atomic activate，保留旧 generation
  至 rollback deadline；
- 创建 Module、ModuleVersion、ModuleItem 和 Overlay schema，模块内容只读，用户 note、
  favorite、correction、Tag 和 hidden state 独立保存；
- 更新时用 `module_id + stable_item_key` 重挂 Overlay，显示 orphan/conflict，不静默丢弃；
- Knowledge App 增加 Modules/Installed/Updates/Degraded/Overlay conflicts，并能跳转 Discovery；
- 普通 ZIP/目录继续走用户导入路径，不因存在 manifest 自动获得 Package trust；
- 模块写入可信 publisher/module/version/category/risk Source Facet 和 namespaced Tag；
- active RetrievalProfile 为模块重建索引；v1 禁止把预计算向量作为 Package 权威；
- restricted 模块执行 jurisdiction、intended_use、citation、reviewer、reviewed/review_due 和
  stale policy 校验，缺失时 fail closed；
- 所有 Knowledge Package 安装/更新/rollback/卸载均接入 core-only
  `knowledge.modules.manage`、reauth 和 action preview；普通成员只能浏览 Discovery，不能
  安装 private 或 installation module；
- core 可安装到自己的 private scope 或 installation shared scope，不能写入其他成员的
  private space；

验收：签名模块可从本地 archive 和 Registry release 经同一验证器安装；篡改、恶意 ZIP、
越权 shared 安装和不完整 restricted metadata 均 fail closed；升级/rollback 后 citation 与
Overlay 稳定；卸载后用户可选择保留 Overlay；模块可在 FTS-only 和 semantic profile 间
重建而不改变 Package/Module identity。

## 4. 开源后端验证与语义检索

### K6A：LanceDB 技术 Spike

目标：验证 LanceDB 是否适合作为可选、可重建、进程隔离的 vector backend Service。本阶段
不把它写入正式 schema authority，不默认安装，也不允许其原生模块加载进 Core Local。

产物：

```text
scripts/bench_knowledge_vector_backend.py
artifacts/knowledge-backend-spike/<platform>/<run>.json
docs/ai2apps-knowledge-vector-backend-evaluation.md
```

验证矩阵：

- macOS arm64；Linux arm64/x86_64；Python 3.11–3.13；
- editable checkout、wheel、独立 `.ai2service`、Runtime Package 与 macOS inner DMG；
- offline startup、cold import time、installed bytes、RSS；
- 10k、100k、1M chunks；384/768/1024 dimensions；
- build、incremental upsert、delete、filtered Top-K、restart；
- private/shared partition 与 adversarial stale rows；
- concurrent reads plus background indexing；
- crash during generation build；
- full rebuild and shadow generation activation。

通过门槛：

- 所有目标平台可由签名的可选 Service/Runtime Package 安装，无 Docker；
- macOS 原生 payload 通过 Developer ID、Hardened Runtime、notarization/staple、安装前后
  `codesign`/Gatekeeper/Team ID 验证，并在干净 consumer Mac 上通过 release smoke；
- Backend 只通过稳定 Service RPC 访问，Core Local 无 LanceDB/sqlite-vec import；
- private/shared filtered retrieval 零越权；
- 100k filtered Top-20 的 p95 满足交互搜索目标，目标先设为 150 ms CPU-only，实测后冻结；
- background build 不导致前台模型服务显著失速或内存 gate 失败；
- 删除/撤回在 API 返回成功前从 active generation 不可见；
- index 目录删除后可从 SQLite/content store 完整重建；
- 许可证、NOTICE、SBOM、digest 与升级/rollback 满足 Package Trust。

若不通过：仅发布 FTS5 v1，同时启动 K6B 对 `sqlite-vec` 的相同验证，不为赶进度改变
Knowledge API。

### K6B：VectorIndexBackend 与 semantic capability

目标：在 spike 通过后接入可选 semantic search。

工作项：

- 定义 `LexicalIndexBackend`、`VectorIndexBackend`、`EmbeddingProvider`、
  `RetrievalStrategy`、`RerankerProvider` protocol 和 capability descriptor；
- 实现 generation create/upsert/delete/search/activate/drop/health；
- 通过 Model Runtime Service 批量 embedding，保存 model digest/dimension；
- 增加用户同意的安装、下载、取消、恢复和卸载 UI；
- 增加 semantic feature state：disabled/installing/indexing/ready/degraded；
- Runtime 缺失、不兼容、签名失败或 Worker 不可用时 fail closed 到 FTS-only；
- FTS/vector 并行召回和 RRF；
- 将 backend、embedding、strategy、reranker 和有界参数固化为版本化 RetrievalProfile；
- authoritative SQLite recheck；
- embedding 模型切换 shadow generation；
- backend 不可用自动降级 lexical，并在 UI 明示。

验收：未安装、安装中、ready、损坏、卸载五种状态均不破坏基础 Knowledge；混合检索
在固定 Eval 集上显著优于 FTS-only，且无 ownership regression。

### K6C：Backend migration、shadow 与用户选择

目标：实现不同 backend/profile 之间的无停机重建、对比、切换和回滚。

建议模块：

```text
ai2apps/knowledge/backends/
  protocol.py
  fts5.py
  lancedb.py
  sqlite_vec.py
ai2apps/knowledge/migrations.py
ai2apps/knowledge/profiles.py
```

工作项：

- 实现 BackendInstance、RetrievalProfile 和 BackendMigration Repository；
- 从 snapshot watermark 建立 target generation；
- 全量 backfill authoritative Chunk；
- building/active generation 幂等消费 Knowledge change log；
- catching-up 达到 current watermark 后冻结 validation snapshot；
- 校验 count、hash、partition、tombstone、delete、share/revoke；
- 支持 shadow query：source/target 同时检索，但 target 结果不进入用户回答；
- 保存 Recall、nDCG、latency、RSS、disk 等匿名比较；
- 原子切换 active RetrievalProfile/generation；
- 保留旧 generation 至 rollback deadline，并支持追平后回滚；
- restart 后从 migration 状态和 watermark 恢复；
- 增加 backend install/uninstall、migration progress、activate/rollback API；
- 普通 UI 提供基础/语义模式，高级设置提供具体 backend/profile。

迁移矩阵：

```text
FTS-only -> LanceDB hybrid -> FTS-only
LanceDB -> sqlite-vec -> LanceDB
same backend, new embedding model/dimension
same backend/model, new retrieval strategy/reranker
new chunker/representation generation
local backend <-> External backend test double
```

验收：所有迁移不修改 KnowledgeItem、Asset、owner、visibility、provenance 和 citation ID；
backfill/catch-up/validation/shadow/activation/rollback 任一点 crash 均可恢复；两个用户和
private/shared 对抗测试零泄露；迁移失败继续使用原 active generation。

### K6D：Reranker 与检索评测

目标：把“能搜索”提升为可度量的检索质量。

工作项：

- 复用 oMLX reranker Service adapter；
- 建立中文/英文、多语言、时间、网页、文档、图片 caption 和 Chat 数据集；
- 指标包含 Recall@K、MRR、nDCG、citation precision、no-answer accuracy；
- 对 lexical、vector、hybrid、hybrid+rerank 做消融；
- 记录 latency、memory、model bytes 和能耗代理指标；
- Query rewrite 必须独立评估，不与权限过滤耦合。

验收：发布配置与模型版本固定，并保留可复现实验命令和 artifacts。

## 5. 多模态与时间记忆

### K7：图片、OCR 与事件时间

目标：支持“前天吃了什么”等基于个人图片和时间的找回。

工作项：

- 提取 EXIF/source/ingested time，标准化到 installation timezone；
- 基础图片 metadata 与 thumbnail；
- 可选 OCR/VLM capability 安装；
- 保存 caption/entity/event representation 的 producer/version/confidence；
- 生成 topic/entity/event/object/food 等 inferred Tag，保存 producer/version/confidence 和
  evidence representation；
- 默认阻止健康、宗教、政治、性取向、精确位置等敏感属性自动 Tag；
- 用户修正或确认 inferred Tag 时新增 user-confirmed assignment，不覆盖模型历史；
- deterministic time parser 和 event/source/ingested field selection；
- Timeline 支持推断标记和用户纠正；
- 用户纠正生成 explicit representation，不覆盖模型原始输出；
- 图片回答引用原图并按 confidence 使用“可能”等措辞。

验收：固定照片集上的日期过滤、食物描述、用户修正、卸载 VLM 后既有来源可用；private
图片和 EXIF 不泄露给其他成员。

### K8：音频与有界视频

目标：支持音频转写和有限的视频内容找回。

工作项：

- local STT dependency 与 timecoded transcript；
- 视频 metadata、音轨抽取、时长/大小 gate；
- 有界关键帧抽取和可选 caption；
- timecode citation 和原媒体播放入口；
- indexing pause/resume、前台推理让路和磁盘配额；
- 明确不支持或需要用户确认的超大视频策略。

验收：处理可取消、重启恢复、资源有界；检索结果能跳转到音视频 timecode；未同意
Cloud processing 时媒体不外发。

## 6. 后续阶段

### K9：自动记忆规则

第一版之后再实现：

```text
off     default, never save automatically
ask     Agent may suggest, user confirms every save
rules   explicit App/source/kind rules with preview and revoke
```

自动规则必须可查看命中历史、暂停和批量撤回。任何规则都不能自动将 private 升级为
shared，也不能保存 hidden reasoning、Secret 或越权 Tool output。

### K10：可选 Source subscriptions

- 用户显式订阅网页或目录更新；
- source-level ETag/hash/version；
- 删除、改名和更新策略；
- 有界刷新频率与网络权限；
- 不在 v1 默认监控浏览器历史或整个文件系统。

### K11：基于 MCP 的 Knowledge Federation

目标：在 NodeLink/NodeGrant/Federation Gateway 稳定后，让一个 Node 查询另一个 Node 显式
发布的 federated bucket，同时保证 private/local bucket 永远不可远程发现或访问。

建议模块：

```text
ai2apps/knowledge/federation/
  policy.py
  publications.py
  service.py
  citations.py
  client.py
```

工作项：

- 实现 private=`never`、installation=`local_only`、federated=`node_allowlist` 数据库约束，
  不提供把前两者原地升级为 federated 的 API；
- core 创建 federated bucket，通过 preview 把选定 Item revision 发布为独立 immutable
  publication，保存 source lineage；Member 不能 publish 或配置远端；
- 发布模块内容前检查 `.ai2knowledge` license 的 remote serving/redistribution 和 risk policy；
- 扩展 NodeGrant：allowed bucket、remote search/get capability、query/result/bytes/concurrency
  quota、expiry、grant epoch 和 revoke；
- 注册 `ai2apps.knowledge-federation` MCP/Service，只导出
  `knowledge.remote.search@1` 与 `knowledge.remote.get@1`；
- Federation Gateway discovery 只返回已授权 federated bucket 的安全 descriptor，不返回
  private/local bucket 名称、Tag、Item count 或内部 ID；
- 上游执行 retrieval、authoritative bucket/Item recheck、redaction 和 bounded result shaping；
- 返回 serving Node、bucket、published revision、content digest、trust、retrieval time 和
  短期 audience-bound citation handle，不返回 embedding、blob path 或 backend debug state；
- 下游 Knowledge Search/Ask 支持显式选择 RemoteServiceBinding，默认 remote=off；远端 query
  发送前显示目标 Node，不自动附加本地 private Tag/Space ID；
- 下游执行 source-aware fusion，把远端 excerpt 标记为 external/untrusted evidence，保持可见
  citation，并隔离 prompt injection；
- 实现 route_path/hop_count 单跳约束以及 timeout/cancel/disconnect/idempotent retry；
- revoke、grant epoch 或 publication retract 立即阻止新召回并使短期 handle 失效；
- 远端结果不自动写入本地 Knowledge；“导入本地”必须是用户显式动作并保存远端 provenance；
- Knowledge App 增加 Buckets、Shared Nodes、publication update/retract、grant/quota/usage/audit。

验收：两个 Node 配对后，下游只能发现并查询 NodeGrant allowlist 中的 federated bucket；
private/installation bucket 在 descriptor、search、citation、错误、metrics 和 timing 对抗测试中
均不泄露；Member 无法发布；revoke/retract 立即生效；远端不可用不影响本地结果；请求不能
第二跳；恶意 excerpt 不能触发 Tool 或写入本地；全程不传输 embedding 或 backend index。

以下仍为后续研究，不包含在 K11：后台语料复制、encrypted sync、双向冲突合并、跨 Node
统一 organization corpus、远程 embedding 和多跳检索。

## 7. 横向测试计划

### 7.1 权限矩阵

至少覆盖：

```text
core / owner / admin
developer / member / child / guest
revoked member
legacy installation API key
two installations with same Cloud account
upstream/downstream core and member
revoked/expired/quota-exhausted NodeGrant
```

对每个角色验证 private read/write、shared read/write/manage、Search、Ask、Job、Source、
Settings、dependency install、Discovery browse、core-only module install/manage 和 storage
budget manage。member 必须能创建/撤回自己的 shared contribution，但不能治理他人内容或
安装任何 Knowledge Package。
跨 Node 验证 Discovery descriptor、remote search/get、publish/retract、NodeGrant manage 和
citation；只有 core 可以创建 federated bucket 和 publication，远端 Member 权限不能扩大
上游 NodeGrant。

### 7.2 数据与恢复

- schema migrate/rollback fixture；
- Job 每个 stage 的 crash recovery；
- duplicate request/idempotency；
- content hash dedupe 与引用计数；
- tombstone、shared retract、member revoke；
- core 删除 Member 时 private delete/locked retention/member export window 和 shared
  retain/transfer/delete 的完整矩阵；请求缺失处置参数时 fail closed；
- 10 GiB budget 的 80%/90%/100% 边界、物理 reserve、重启后计数、dedupe 计费和 core
  调整；critical 时 read/export/delete 可用且不自动删除权威数据；
- stale FTS/vector rows；
- index generation shadow build/activate/retire；
- change-log watermark、dual-write、catch-up 和重复消费；
- LanceDB/sqlite-vec/FTS-only profile 双向迁移；
- migration 每个状态的 crash recovery、cancel、activate 和 rollback；
- active backend 被卸载或损坏时原子降级 FTS；
- backup without vector index and full rebuild；
- ModuleVersion generation 的 stage/activate/rollback crash recovery；
- module upgrade 中 stable item key、citation 和 Overlay 重挂/orphan/conflict；
- 卸载保留 Overlay 后重新安装；
- federated publication stage/activate/retract、source revision update、重启恢复和 lineage；
- NodeGrant revoke/epoch rotation、citation expiry、quota exhaustion 和 RemoteServiceBinding
  reconnect；
- disk full、corrupt asset、parser crash、backend unavailable。

### 7.3 安全

- SSRF：localhost、link-local、redirect、DNS rebinding 和超大响应；
- malicious PDF/Office/archive/media；
- `.ai2knowledge` path traversal、symlink、special file、archive bomb、duplicate path、未索引
  文件、digest/signature mismatch、publisher spoof 和 executable/macro；
- prompt injection in webpage/document；
- citation URL/path escaping；
- EXIF/location disclosure；
- shared corpus poisoning；
- Tool payload actor/space spoof；
- Source Facet forged by client or third-party App；
- App writing another App/system/user Tag namespace；
- private Tag leaking through autocomplete、statistics、shared catalog or model prompt；
- inferred sensitive-attribute Tag without explicit policy；
- 普通 ZIP 冒充 verified Knowledge Package；
- restricted module 缺失 jurisdiction/citation/reviewer/review_due 或安装后过期；
- member 越权 private/installation module install/update/rollback/uninstall；
- core 通过 Member 删除/导出流程读取 private Knowledge；
- private/installation bucket 通过 ID spoof、descriptor enumeration、Tag/count/statistics、错误
  差异、stale index 或 forged publication 被远端发现；
- forged NodeLink/NodeGrant/actor/bucket/grant epoch、过期 citation、replay 和 audience swap；
- hop loop、second-hop forwarding、oversized query/result、remote quota bypass；
- malicious remote excerpt prompt injection、citation URL/path escaping 和自动写入本地知识；
- Knowledge Package license/risk policy 不允许时仍被 remote serving；
- Cloud processing without grant；
- logs/events contain prompt/body/token/embedding scans。

### 7.4 质量与性能

- multilingual retrieval；
- time-relative query with timezone/DST；
- exact URL/title lookup；
- semantic paraphrase；
- exact Source Facet/User Tag filtering and inferred Tag weighted boost；
- inferred Tag suggestion acceptance/rejection and producer-version refresh；
- Tag alias/rename/merge/delete consistency across FTS/vector backends；
- module install/update/rollback 后的 retrieval、citation、Facet/Tag 和 Overlay consistency；
- identical module corpus across FTS/vector backend generations；
- restricted/stale module citation warning and Ask refusal policy；
- local-only、remote-only、local+multiple remote 的 source-aware fusion、citation precision 和
  remote unavailable degradation；
- federation Top-K/result bytes/latency、cancel、revoke propagation、quota 和一跳 route；
- long-document diversity；
- multimodal caption/OCR；
- no-answer and conflicting evidence；
- backend/profile shadow comparison and reproducibility；
- cold/warm latency、indexing throughput、RSS、disk amplification；
- foreground generation under background indexing。

## 8. 发布策略

### Release A：Knowledge Core

包含 K0–K5：private/shared、URL/file/document/note、FTS、可信 Source Facet、用户/App
Tag、Knowledge App、Chat 手工保存和带 citation 的 Ask。不要求 embedding。

发布门槛：权限、恢复、SSRF、删除和 citation 测试通过；新用户零额外部署可用。

### Release B：Trusted Knowledge Modules

包含 K5M：`.ai2knowledge` contract、Package Trust、Registry/Discovery 安装、private/shared
范围、只读 ModuleVersion、Overlay、升级、rollback、卸载和高风险 metadata gate。不要求
semantic backend，所有模块必须可用 FTS 建索引。

发布门槛：archive/signature/license、角色权限、恶意包、atomic activate、升级/rollback、
Overlay 稳定、普通 ZIP 隔离和 restricted/stale policy 测试通过。

### Release C：Semantic Search

包含通过验证的 K6 backend、用户同意安装、embedding generation、hybrid search、
可选 reranker、RetrievalProfile、backend migration、shadow comparison 和 rollback。

发布门槛：backend evaluation、跨平台 packaging、retrieval Eval、双向迁移、权限隔离、
crash recovery、rollback 和 FTS 降级测试通过。

### Release D：Federated Knowledge

包含 K11：federated bucket、core publication、NodeGrant bucket allowlist、MCP query-only
search/get、短期 citation、source-aware fusion、revoke/retract 和 Shared Nodes UI。不包含后台
同步、embedding/index 传输或多跳。

发布门槛：Node Federation 基础 contract 稳定；两 Node 权限/隐私/循环/撤销/配额/恶意证据
测试通过；private 与 Local Shared bucket 在任何远端接口上不可发现。

### Release E：Personal Multimodal Memory

包含 K7 和 K8：图片/EXIF/OCR/VLM、带置信度的 inferred Tag、音频、有限视频、Timeline
与事件时间。

发布门槛：多模态隐私、资源 gate、时间 Eval 和引用原媒体通过。

### Release F：Controlled Memory Automation

包含 K9/K10 的显式规则和 source subscriptions。默认仍为 off。

## 9. 完成定义

Local Knowledge v1 完成需同时满足：

- 每位成员有隔离 private space，installation 有受控 shared space；
- URL、文件、文档、图片原件、Chat selection 和 Artifact 可入库；
- 无增强模型时可通过 FTS、时间、类型和来源检索；
- Knowledge App 可管理、搜索并 Chat；
- Chat 可手工保存内容并选择 private/shared；
- Chat/App 来源生成不可伪造的 Source Facet；用户可创建、编辑、合并和检索 Tag；
- App 只能写自己的 namespace；AI inferred Tag 有 producer/confidence/evidence，且可确认、
  拒绝和重新生成；
- private Tag 不泄露到其他用户或 shared catalog，敏感 Tag 默认不自动生成；
- `.ai2knowledge` 可通过统一 Package Trust 和 Discovery 安装到 private/shared 范围，模块
  正文只读且无执行能力；
- 模块可升级、rollback、禁用和卸载，用户 Overlay 与稳定 citation identity 不丢失；
- 普通 ZIP 导入与可信知识包安装严格分离，高风险模块有来源、审核、时效和 stale gate；
- private bucket 永久不可跨 Node 分享，Local Shared 不自动导出；只有 core 可把显式 revision
  发布到 federated bucket；
- Node 间知识通过 NodeGrant + MCP query-only Service 检索，默认 remote=off、只允许一跳、
  不传输 embedding/index，revoke/retract 立即生效；
- 远端证据保留 serving Node/bucket/revision/trust citation，不自动写入本地 Knowledge；
- 每条 Ask 结论包含可打开 citation，低证据时不伪造记忆；
- ingestion/indexing 可观察、取消、恢复和重建；
- semantic backend 是可选依赖，安装需用户同意，卸载不丢原始知识；
- backend、embedding、retrieval strategy 和 reranker 是独立可替换的版本化组件；
- 管理员可在至少 FTS-only 与一个 semantic backend 之间无停机迁移、shadow 比较并回滚；
- backend 迁移只重建派生索引，不改变 KnowledgeItem、权限、来源和 citation identity；
- member revoke、撤回共享和删除对所有 active index 立即生效；
- 权限、安全、恢复、质量、资源和跨平台 release gate 有可复现实验记录。
