# AI2Apps Local Knowledge 与 RAG 技术方案

Status: Architecture draft v0.6
Last updated: 2026-08-22
Related: [AI2Apps Platform Architecture](ai2apps-platform-architecture.md),
[Backend Development Plan](ai2apps-backend-development-plan.md),
[Documents](ai2apps-documents.md),
[Multi-user Gateway](ai2apps-multi-user-gateway.md),
[Authority and Secret Baseline](security-authority-baseline.md)

## 1. 决策摘要

AI2Apps 将新增第一类本地知识能力，由内置 `ai2apps.knowledge` App 和稳定的
`ai2apps.knowledge-service` Service 组成。

它不是单纯的向量数据库，也不是一个与 AI2Apps 平行运行的第三方 RAG 产品。系统的
权威数据是有所有者、可见范围、来源、时间和原始内容引用的 `KnowledgeItem`；解析块、
OCR、转写、caption、embedding 和向量索引全部是可失效、可重建的派生表示。

Release A 只向用户暴露两个知识范围：

- `private`：仅创建者本人可见，默认值；
- `installation`：当前 installation 内获准成员可见。

Release D 在 core 管理界面增加第三种 `federated` bucket；它不是普通保存目标，只接收经过
显式 preview/publish 的 revision，并按 Node allowlist 提供远端查询。

基础知识能力使用现有 Platform SQLite、FTS5、Documents、Workspace、Artifact、
ResourceHandle、Tool Gateway 和 Event Store，不要求额外模型即可启动。语义检索、
rerank、图片理解、音频转写和视频理解作为用户同意后安装的增强能力。

后端选型结论：

1. 不整体采用 RAGFlow、AnythingLLM、LlamaIndex、Haystack 或其他完整 RAG 框架；
2. AI2Apps 自己持有 Knowledge 领域模型、权限、摄取任务、检索编排和问答契约；
3. SQLite FTS5 是必选、零额外部署的 lexical backend；
4. LanceDB 是第一候选的可选 vector backend，但不得作为动态原生库加载进 Host；它必须
   在经过验证的 RAG Backend Service/Runtime Worker 中通过独立技术验证；
5. `sqlite-vec` 保留为小体量替代候选，但在 pre-v1、ANN 和 macOS extension 打包问题
   解决前不作为默认生产后端；
6. Vector backend 必须位于适配器后面，可删除、迁移或重建，不能成为权限或内容的
   source of truth；
7. “RAG Backend”拆分为 `LexicalIndexBackend`、`VectorIndexBackend`、
   `EmbeddingProvider`、`RetrievalStrategy` 和 `RerankerProvider`，避免数据库、模型和
   检索算法互相锁定；
8. backend 切换采用 generation、change log、dual-write、shadow query、原子激活和
   延迟回收，不要求停止 Knowledge App；
9. backend 迁移本质是从 AI2Apps 权威 Knowledge/Chunk 重建派生索引。只有当 chunker、
   parser 或 embedding contract 改变时，才需要重建对应派生表示；
10. 普通用户选择“基础/语义”等能力档位，具体 backend、模型和迁移由 core/owner/admin
    或高级设置管理，避免每位成员各自启动数据库进程；
11. Knowledge 支持可信 Source Facet、用户 Tag、App namespaced Tag 和 AI inferred Tag。
    Runtime 来源属性是不可伪造的结构化事实；AI Tag 只是带 producer、confidence 和
    evidence 的建议，不能直接提升为用户事实。
12. Knowledge Module 是 AI2Apps Package 体系的一等、不可执行类型，扩展名为
    `.ai2knowledge`；它复用统一的 digest、签名、发布者信任、Registry、安装、升级、
    rollback 和审计链路，并可通过 Discovery App 发现与安装。
13. Knowledge Module 内容按版本只读，用户批注、收藏、纠错和 Tag 保存为独立 Overlay；
    普通 ZIP 导入产生用户拥有的 KnowledgeItem，不自动获得“可验证、可升级知识包”身份。
14. 知识包只携带 backend-neutral 的内容、元数据、引用和 Eval，不以某种向量数据库私有
    索引作为权威。医疗、法律、金融等高风险模块必须经过额外 metadata、审核和时效门禁。
15. 普通成员可以向 installation shared space 提交公共知识，并管理自己的贡献，但不能
    安装、更新、rollback 或卸载 Knowledge Package；知识包生命周期操作只允许 core 用户。
16. core 删除 Member 时必须显式选择该成员 private Knowledge 的处理方式；revoke 立即阻断
    访问，系统不得因删除成员而采用未展示的隐式数据处置。
17. Knowledge 默认 installation 存储预算为 10 GiB，core 可查看 original、derived、module、
    private/shared 分项用量并调整预算；达到预算或物理低磁盘线时禁止增长型操作但保持读取、
    导出和删除可用。
18. Release A 冻结为 FTS 基础闭环，不等待 embedding、OCR、VLM 或 STT。
19. UI 中的“知识桶”由权威 `KnowledgeSpace` 表达。系统内置 private bucket 与 installation
    bucket；private bucket 的 `shareability=never` 是不可放宽的数据层不变量，不能直接分享
    给其他 Node。
20. 跨 Node 分享必须把选定内容显式发布到独立 federated bucket，并同时满足 BucketPolicy、
    NodeLink、上游持有的 NodeGrant 和 Federation Gateway policy；local shared 不自动变成
    node shared。
21. v1 跨节点知识采用 MCP/Service Federation 的 query-only 模式：数据所在 Node 执行权限
    过滤和检索，只返回有界 excerpt 与短期 citation handle，不共享 SQLite、blob store、FTS、
    embedding 或向量索引，也不做后台语料复制。
22. 联邦知识只允许单跳、allowlist Node、可立即撤销，并保留来源 Node/bucket/revision/trust
    provenance。远端结果在下游按外部不可信证据处理，不因来自已配对 Node 自动变成事实。
23. 用户体验上可以把 RAG 呈现为一个一键安装的完整能力套件；技术上必须拆成纯数据
    Knowledge Package、隔离的 RAG Backend `.ai2service`、可复用 Runtime Package 和独立
    model/checkpoint 依赖。签名或公证不能授予 Package 在 Host 内执行的权限。
24. 原生 Runtime payload 必须满足 Developer ID Application、Hardened Runtime、Apple
    notarization/staple、Gatekeeper 和 Team ID 校验；纯数据 `.ai2knowledge` 不走 Apple
    公证，但仍必须通过 AI2Apps Publisher/Repository 签名、digest 和内容风险审核。
25. Base App、Knowledge App 和 FTS5 必须在未安装 Runtime/模型/vector backend 时启动和
    工作。Core Local 不 import installable Package code；语义、OCR、STT、VLM 和原生解析器
    只能通过受管 Service/Worker 调用。
26. Knowledge App 是系统常驻入口，但增强能力不随 App 启动而安装。`knowledge.lexical_search`
    由 Core 永久提供；`knowledge.semantic_retrieval`、`knowledge.image_understanding`、
    `knowledge.audio_understanding` 和 `knowledge.reranking` 通过 ACPF 按操作 probe/ensure，
    复用 Discover、Package Manager、签名校验、重启恢复和健康验证。
27. 首个语义栈拆为 `ai2apps/runtime-knowledge-rag` 原生 RAG Runtime Provider、
    `ai2apps/service-knowledge-lancedb` Vector Service Package、独立 Embedding Provider/Model
    Package 与版本化 RetrievalProfile。LanceDB/Arrow/MLX text dependencies 只存在于隔离的
    专用 Knowledge RAG Runtime；Embedding Provider 复用该 Runtime，不加载进 Host，也不捆绑
    通用 oMLX 图像、音频或 VLM 依赖。

Runtime/Worker 分包和 ACPF 生命周期的实现契约见
[Knowledge RAG Runtime Package Contract](ai2apps-knowledge-rag-runtime-package-contract.md)。

## 2. 产品目标

### 2.1 用户能力

用户能够：

- 将网页链接、文件、图片、音频、视频、Chat 消息、Agent 结果和 Artifact 加入知识库；
- 添加时选择“仅自己”或“本机共享”；
- 使用自然语言按语义、来源、时间、类型和人物/主题找回内容；
- 查询“前几天看过的西瓜文章链接”或“前天吃了什么”；
- 从 Chat 中快速保存单条消息、选中消息、整个回合、附件或链接；
- 在 Knowledge App 中浏览 Library、Timeline、Shared、Inbox 和索引状态；
- 与自己的知识库 Chat，并打开每条回答对应的原始证据；
- 在 Discovery App 发现知识模块；获授权的 core 用户可以验证和安装法餐菜谱、家庭常见病、
  常用药等知识模块；
- 在 Knowledge App 查看已安装模块、版本、可信等级、更新状态和用户 Overlay；
- 撤回共享、删除内容、重试处理、重建索引和卸载增强模型。

### 2.2 平台目标

- 所有检索在候选召回前执行可信 principal 与知识空间过滤；
- Local 原始内容默认不发送 Cloud；
- 所有模型生成的派生事实保留来源、模型、版本和置信度；
- 索引损坏、模型替换或后端卸载不影响原始知识；
- Chat、Agent 和第三方 App 通过相同 Knowledge Service contract 使用知识；
- ingestion、indexing、retrieval 和 answer synthesis 可分别观测、取消和恢复；
- 基础模式不因增强后端未安装而失效；
- 同一权威知识集可以对多个 backend、embedding 和 retrieval strategy 做离线 Eval 或
  shadow 对比；
- 用户可以在明确资源、隐私和重建成本后切换 backend，并在保留期内回滚。
- 用户可以按来源、App、类型、时间和 Tag 组织知识；自动标签不掩盖其来源与不确定性。

### 2.3 第一版非目标

- 自动保存所有 Chat；
- 在用户不知情时建立完整浏览器历史；
- 跨 installation 同步私有知识；
- 节点联邦知识库或远程挂载上游知识空间；
- 自动将模型推断提升为无来源的永久事实；
- GraphRAG、复杂知识图谱推理或全自动实体合并；
- 视频逐帧理解和实时视频流索引；
- 由向量数据库自身承担用户、权限、计费或审计。
- 在知识包中执行安装脚本、Hook 或任意代码；需要运行能力时必须使用单独授权的
  `.ai2service`、`.ai2agent` 或 `.ai2app`。

## 3. 系统边界

```text
Chat / Knowledge App / Agent / third-party App
                       │
                       ▼
             Knowledge Service API
       principal · policy · ownership · audit
                       │
        ┌──────────────┼───────────────┐
        ▼              ▼               ▼
  Ingestion         Retrieval       Knowledge Ask
  coordinator       coordinator     context builder
        │              │               │
        ▼              ▼               ▼
 Documents/Web/   FTS5 + Vector     Model Runtime
 Media adapters   + Reranker        Service
        │              │
        └───────┬──────┘
                ▼
     Platform SQLite + content store
     authoritative metadata and assets
                │
                ▼
     optional rebuildable vector index
```

### 3.1 组件职责

`KnowledgeRepository`

- 持有 Space、Item、Asset、Representation、Job、SourceLink 和 revision；
- 在 Platform SQLite 事务中执行 ownership、visibility 和生命周期变更；
- 不调用模型或向量数据库。

`KnowledgeIngestionManager`

- 校验 URL、附件、Artifact、Chat message range 和 ResourceHandle；
- 创建不可变 source snapshot 或引用；
- 调度解析、OCR、转写、caption、chunk、embedding 和 index jobs；
- 幂等恢复 queued/running jobs。

`KnowledgeRetrievalService`

- 从可信 `RequestPrincipal` 计算允许的 `KnowledgeSpace`；
- 解析时间、类型、来源和范围过滤；
- 并行执行 lexical/vector retrieval；
- 使用 RRF 或等价确定性方法融合候选，再可选 rerank；
- 按 Item 聚合重复 chunk，返回有界、带来源证据。

`KnowledgeContextBuilder`

- 在 token budget 内选择证据；
- 保持时间、作者、URL、页码、图片、Chat message 等引用；
- 明确区分原文、结构化元数据和模型推断；
- 输出给 Knowledge Ask、Chat 或 Agent 的标准 context envelope。

`VectorIndexBackend`

- 只存 `representation_id`、embedding、必要 partition/filter 字段和 index metadata；
- 不存唯一一份正文；
- 支持按 model/dimension/index version 建立新 generation；
- 支持 shadow build、原子切换和整代删除。

## 4. 领域模型

### 4.1 KnowledgeSpace

```text
id
kind                    private | installation | federated
owner_user_id           private space 必填
installation_id         三种 space 均必填
display_name
shareability            never | local_only | node_allowlist
bucket_policy_json
status                  active | disabled | deleting
policy_json
revision
created_at / updated_at
```

每个 active member 首次使用时创建一个稳定的 private space。每个 installation 只有一个
内置 shared space。UI 将 Space 呈现为“知识桶”：private bucket 固定为 `never`，installation
bucket 固定为 `local_only`；二者都不能被更新为 `node_allowlist`。只有 core 显式创建的
federated bucket 可以选择远端 Node allowlist。把内容共享给其他 Node 必须产生一次明确的
publish/copy lineage，不能只修改原 private/local Item 的 ACL。未来的 App/Project space
通过新 kind 扩展，不在 v1 UI 中暴露。

### 4.2 KnowledgeItem

```text
id
space_id
owner_user_id
created_by_user_id
visibility              private | installation | federated
kind                    webpage | document | image | audio | video |
                        chat | artifact | note
title
user_note
source_time
event_time_start / event_time_end
event_time_basis        explicit | exif | source | extracted | inferred
event_time_confidence
language
status                  pending | ready | partial | failed | deleted
source_app_id
source_app_instance_id
source_session_id
source_run_id
metadata_json
revision
created_at / updated_at / deleted_at
```

`owner_user_id` 与 `created_by_user_id` 在第一版通常相同，但必须分开保存，以支持管理员
导入、系统迁移和未来受控代办。private ↔ installation visibility 变更是审计事件，不通过
复制 Item 实现；发布到 federated bucket 是安全例外，必须创建独立 published revision 和
lineage，不能修改源 Item 使其直接外发。

### 4.3 KnowledgeAsset

```text
id
item_id
role                    original | snapshot | thumbnail | keyframe |
                        transcript | derived
storage_kind            content_store | attachment | artifact |
                        resource_handle | inline
content_hash
media_type
filename
size_bytes
source_url
retrieved_at
locator_json
metadata_json
```

网页必须同时保存 canonical URL 和抓取时间。根据策略保存正文快照；登录态或禁止持久化的
网页只能保存允许的数据和明确的访问错误，不能绕过站点授权。

### 4.4 KnowledgeRepresentation

```text
id
item_id / asset_id
kind                    parsed_block | ocr | transcript | caption |
                        summary | entity | event | embedding_input
ordinal
text
location_json           page/slide/sheet/cell/timecode/message ids
producer                 parser/model/provider identifier
producer_version
confidence
content_hash
status
created_at
```

Representation 是派生数据。模型替换、解析器升级或权限撤回后可以失效和重建。

### 4.5 KnowledgeChunk 与索引 generation

```text
knowledge_chunks
  id, representation_id, item_id, space_id, ordinal, text,
  token_count, location_json, content_hash

knowledge_index_generations
  id, backend_instance_id, embedding_provider_id, model_id, model_digest,
  dimension, distance, chunker_version, representation_generation,
  status, source_watermark, created_at, activated_at, retired_at

knowledge_chunk_indexes
  generation_id, chunk_id, index_state, indexed_at, error_json

knowledge_change_log
  sequence, operation, chunk_id, item_id, tag_id, space_id, content_hash,
  authoritative_revision, created_at
```

FTS row 与 vector row 都通过稳定 `chunk_id` 回到 Platform SQLite。切换 embedding 模型时
建立新 generation，完成验证后原子激活；旧 generation 延迟回收。Change log 是跨存储
事务的增量真相：先提交权威 SQLite 变更，再由 active/building generation 幂等消费。

### 4.6 KnowledgeJob

```text
id
item_id
stage                   fetch | parse | analyze | tag | chunk | embed |
                        index | summarize | delete
status                  queued | running | waiting_dependency |
                        completed | failed | cancelled
attempt
dependency_key
progress_json
error_json
lease_owner / lease_expires_at
created_at / started_at / completed_at
```

Job 使用数据库 lease，启动时回收过期 running job。每个 stage 幂等，以输入 hash 与
producer version 作为 action key。

### 4.7 RetrievalBackend、Profile 与 Migration

```text
knowledge_backend_instances
  id, backend_kind, service_id, package_digest, runtime_mode,
  config_json, capabilities_json, status, health_json

knowledge_retrieval_profiles
  id, lexical_backend_id, vector_backend_id, embedding_provider_id,
  retrieval_strategy, reranker_provider_id, settings_json, status

knowledge_backend_migrations
  id, source_generation_id, target_generation_id, target_profile_id,
  status, snapshot_watermark, applied_watermark, validation_json,
  shadow_json, rollback_until, error_json, created_at, activated_at
```

`RetrievalProfile` 是一次可复现的检索配置，而不是只有数据库名称。它固定 lexical/vector
backend、embedding contract、fusion strategy、reranker 和有界参数。Search/Ask Event
记录 profile/generation ID，使结果可以回放和比较。

Migration 状态机：

```text
planned -> building -> catching_up -> validating -> shadowing
        -> ready -> active -> retired
                     └------> failed
```

`active` 切换必须是 Platform SQLite 中的一次原子指针更新。旧 generation 在
`rollback_until` 前只读保留；rollback 只切换指针并追平 change log，不重新解释知识。

### 4.8 Source Facet 与 KnowledgeTag

来源、类型、时间等可信属性使用结构化 Facet；用户分类和模型建议使用 Tag。二者在 UI
中可以统一展示，但权限和可信度不能混为一谈。

```text
knowledge_source_facets
  item_id
  facet_key              source.kind | source.app | source.session |
                         source.agent | content.kind | source.domain
  value
  authority              runtime
  source_object_id
  created_at

knowledge_tags
  id
  namespace              user | app:<app-id> | inferred
  normalized_key
  display_name
  owner_user_id
  installation_id
  visibility             private | installation | federated
  aliases_json
  status
  created_at / updated_at

knowledge_item_tags
  item_id
  tag_id
  assignment_source      user | app | model | rule
  status                 active | suggested | rejected
  confidence
  producer
  producer_version
  evidence_representation_id
  created_at / updated_at
```

规则：

- Source Facet 只能由 Runtime 根据可信 AppInstance、Session、Run、Attachment、Artifact
  和 URL 解析结果生成，客户端不能自报或覆盖；
- `user` Tag 可由所有者创建、编辑、合并、删除和设置别名；
- `app:<app-id>` Tag 只能由对应的已验证 App 建议或写入，不能使用 `system`、`user` 或
  其他 App namespace；
- `inferred` Tag 必须记录模型/provider digest、confidence 和 evidence；
- 用户确认 inferred Tag 时保留原推断记录，并新增 user-confirmed assignment，不能改写
  历史使模型建议看起来像用户事实；
- 用户拒绝的模型 Tag 保存 bounded rejection，避免同一 producer/version 反复建议；
- Tag 与 assignment 继承 Item 的读取边界。private Item 的 Tag 不进入 shared catalog、
  自动补全、统计或模型提示；
- shared Tag 的创建者和来源可见，普通成员不能修改他人的 shared user Tag；
- 敏感属性 Tag（健康、宗教、政治、性取向、精确位置等）默认禁止自动生成，必须由单独
  policy 和用户同意开启。

推荐确定性 Facet：

```text
source.kind             chat | app | upload | webpage | artifact
source.app              stable App package ID
source.session          internal Session ID, UI 显示安全标题
source.agent            stable Agent key when applicable
source.domain           normalized webpage host
content.kind            webpage | document | image | audio | video | message
content.media_type      normalized MIME type
```

Facet ID 和内部对象 ID 默认不直接进入模型上下文；Context Builder 输出经过权限校验的
显示名称和可打开 citation。

### 4.9 Knowledge Module 与用户 Overlay

`KnowledgeModule` 是可发布、可验证、可升级的知识集合；`ModuleVersion` 对应一个不可变
`.ai2knowledge` Package digest。模块安装后创建独立的 module space/generation，不把上游
内容复制成无法追踪版本的普通用户 Item。

```text
knowledge_modules
  id                       stable package/module ID
  publisher_id
  trust_tier               community | verified_publisher | reviewed | system | restricted
  installed_scope          private | installation
  installed_by
  active_version_id
  status                   installing | active | updating | degraded | disabled | uninstalling
  policy_json
  created_at / updated_at

knowledge_module_versions
  id
  module_id
  version
  package_digest
  manifest_digest
  signature_json
  license_expression
  source_registry
  content_generation
  installed_at
  activated_at
  retired_at

knowledge_module_items
  module_version_id
  stable_item_key
  knowledge_item_id
  content_digest
  upstream_revision

knowledge_item_overlays
  id
  module_id
  stable_item_key
  owner_user_id
  kind                     note | favorite | correction | user_tag | hidden
  payload_json
  revision
  created_at / updated_at
```

模块 Item 对普通用户只读。Overlay 通过 `module_id + stable_item_key` 绑定稳定上游对象，
不直接修改 module generation；升级时把仍存在的 key 重新挂载，把消失或冲突的 key 放入
待处理队列。卸载时用户可以选择保留 Overlay，供以后重装或导出。

#### 4.9.1 `.ai2knowledge` Package contract

知识包是统一 AI2Apps Package Contract 中不可执行的 `knowledge` 类型。外层根 manifest、
精确文件索引、digest 和签名采用标准 Package Trust；knowledge-specific 内容声明由
`entrypoints[].path` 指向。建议结构：

```text
french-recipes-1.0.0.ai2knowledge
├── ai2apps.json
├── LICENSE
├── NOTICE
└── knowledge/
    ├── manifest.json
    ├── content/
    ├── assets/
    ├── schemas/          optional structured content schemas
    └── evals/            optional retrieval/answer evaluation cases
```

根 `ai2apps.json` 至少声明 `package.type=knowledge`、slash namespace package ID、版本、
兼容性、license、attribution、`knowledge` entrypoint、空 permissions 和精确 `files`。示例：

```json
{
  "schemaVersion": "ai2apps.package-manifest.v1",
  "package": {
    "id": "example/french-recipes",
    "type": "knowledge",
    "version": "1.0.0",
    "displayName": "French Recipes"
  },
  "entrypoints": [
    {"name": "knowledge", "kind": "knowledge", "path": "knowledge/manifest.json"}
  ],
  "permissions": [],
  "dependencies": [],
  "files": []
}
```

Publisher signature 和 Repository snapshot 是 archive 外部的 detached trust material，不在
ZIP 内设置可被内容冒充的 `signature/` 目录。v1 沿用通用 Package 的 1 GiB/10,000 files
上限；更大语料拆成多个有稳定依赖关系的 shard，而不是放宽单包解压攻击面。

Package validator 必须复用 AI2Apps Package Trust 的 canonical digest、exact file coverage、
Ed25519 publisher signature、兼容性和 immutable store 语义，并额外拒绝：

- manifest/file index 未覆盖的文件、重复路径、绝对路径、`..`、symlink 和特殊设备；
- archive bomb、超限文件数、单文件/总展开体积超限和不匹配的 media type；
- executable、安装脚本、动态 Hook、宏和要求安装时访问任意网络的内容；
- 缺失许可证、来源或内容 digest 的 release；
- 使用保留的 module ID、冒充其他 publisher 或签名覆盖不完整。

需要解析器或运行时扩展的模块只能声明对独立 `.ai2service` capability 的依赖。Discovery
必须把该依赖和新增权限作为单独安装/授权步骤展示，知识包本身不能获得执行能力。

Package 信任分层如下：所有 Package 先验证 AI2Apps Publisher/Repository signature 和完整
digest；Knowledge Package 再做 license/provenance/risk 审核；只有带原生可执行 payload 的
Runtime/Service 才增加 Developer ID、notarization/staple 和 Gatekeeper；所有可执行 Package
无论是否已公证，都必须保持 Worker 隔离且不能 import 进 Host。

#### 4.9.2 普通 ZIP 导入与知识包安装

两条入口必须在产品和 API 上分开：

| 输入 | 结果 | 信任与生命周期 |
| --- | --- | --- |
| 用户拖入普通 ZIP/目录 | 解包后生成该用户拥有的普通 KnowledgeItem | 非签名导入；可编辑/删除；无 Registry 更新与版本关系 |
| 安装 `.ai2knowledge` | 创建只读 ModuleVersion 和 module generation | 验证 publisher/digest/license；可升级、rollback、禁用、卸载 |

不得因为 ZIP 中碰巧存在 `knowledge.yaml` 就自动提升为可信 Package；只有显式 Package 安装
入口和完整验证链路可以创建 KnowledgeModule。

#### 4.9.3 Discovery、安装范围与更新

Registry release descriptor 增加 `packageType=knowledge`。Discovery App 提供 Knowledge
分类、搜索、版本说明、可信等级、语言、大小、许可证、来源、风险域、适用地区、审核日期、
预估原始/派生存储和依赖能力。安装前用户必须确认：

- 安装到本人 private scope，还是 installation shared scope；
- 需要的磁盘、解析、embedding/OCR/VLM 资源和是否允许自动下载；
- 更新策略：手动、自动兼容更新或仅安全更新；
- restricted 模块的风险提示、适用范围和额外 policy。

所有成员可以浏览 Discovery 中的 Knowledge Module，但普通成员不能安装、更新、rollback
或卸载任何知识包。安装入口只对 core 用户开放；core 可以安装到自己的 private scope 或
installation shared scope，但不能写入其他成员的 private space。安装流程为 verify → stage →
ingest → index → validate → atomic activate。旧 ModuleVersion 在 rollback deadline 前只读
保留；任一步失败继续使用旧版本。更新不得改变安装范围或扩大 capability，除非重新授权。

Knowledge App 增加 `Modules` 页面，展示 Installed、Updates、Disabled、Degraded、Overlay
conflicts，并可以跳转 Discovery。Discovery 负责获取与 Package Trust，Knowledge App 负责
内容浏览、Chat、索引状态和 Overlay；二者不重复持有安装 authority。

#### 4.9.4 Backend independence 与模块标签

知识包携带原文、结构化内容、稳定 item key、来源、publisher/module Tag、可选 chunk hint 和
Eval；安装后由 active RetrievalProfile 产生 Chunk、embedding 和派生索引。v1 不接收包内
预计算向量，以避免 embedding model/digest、dimension、normalization、distance metric 和
chunker 不一致。未来若支持，也只能作为经过完整 contract 匹配后可丢弃的加速缓存。

Runtime 为模块 Item 写入不可伪造 Facet：

```text
source.kind              knowledge_module
source.module            stable module ID
source.module_version    semantic version + package digest
source.publisher         verified publisher ID
content.category         manifest category
risk.domain              general | health | legal | financial | other
```

包内主题标签使用 `module:<module-id>` namespace，不得写入 `user`、`system`、其他 App 或
`inferred` namespace。用户 Overlay Tag 仍属于用户，并在模块升级后保留。

#### 4.9.5 高风险知识模块

健康、药品、法律和金融模块不是因“已签名”就自动可信。除通用字段外必须声明：

- `intended_use`、`jurisdictions`、适用人群和明确的非适用范围；
- 每条关键内容的来源 citation、来源日期和 upstream revision；
- reviewer 身份/机构、reviewed_at、review_due_at 和 review method；
- contraindication、emergency、dosage 等结构化风险分类（适用时）；
- 免责声明、紧急情况转介规则和内容过期策略。

restricted 模块默认不得自动安装到 shared scope。超过 `review_due_at` 或来源被撤回时，
系统标记 stale/degraded、降低或阻止 Ask 使用，并在引用处显示明确警告；不得把模块内容
包装成个体诊断、处方或无引用的确定性建议。

## 5. 权限与多用户隔离

### 5.1 读取规则

一个 principal 只能读取：

```text
item.owner_user_id == principal.actor_user_id
OR
(
item.visibility == installation
AND item.space.installation_id == principal.installation_id
AND membership is active
AND organization/App policy permits Knowledge access
)
OR
(
item.visibility == federated
AND principal is a local installation member
AND item.space.bucket_policy permits local read
)
```

过滤必须在 FTS/vector 查询阶段执行，而不是先做全库 Top-K 后再过滤。所有返回 ID 必须
再次通过 authoritative SQLite ownership join 校验，防止 stale vector rows 泄露。远端
Node 不进入这条普通 principal 读取路径，只能走 5.4 的 Federation Gateway contract。

### 5.2 写入和治理

- 添加默认写入 private space；
- member 及以上角色可显式向 shared space 提交公共知识；child/guest 默认不能提交；
- 用户可修改、删除或撤回自己创建的 Item；
- 普通成员不能修改或删除他人 shared Item；
- 默认只有 core 可隐藏、隔离或删除他人的 shared Item；未来可通过显式 delegation 授予
  owner/admin，但角色名称本身不隐式获得该权限；
- core 删除 Member 时，API/UI 必须分别要求选择 private Knowledge 和 shared contribution
  的处置方式；member revoke 立即阻止其 private space 访问；
- private 处置至少支持 `delete_now`、`retain_locked(until)` 和
  `member_export_window(until)`。导出窗口只授权原成员下载，core 不能借此读取 private 内容；
- shared contribution 至少支持 `retain_with_author`、`transfer_to_core` 和 `delete`；
- 删除 Member 的请求没有显式处置参数时 fail closed，不采用默认删除或默认永久保留。

### 5.3 Tool 与 Agent 权限

新增 capability vocabulary：

```text
knowledge.read.private
knowledge.write.private
knowledge.read.shared
knowledge.write.shared
knowledge.manage.shared
knowledge.use.semantic
knowledge.use.cloud_processing
knowledge.tags.write.private
knowledge.tags.write.shared
knowledge.tags.manage.shared
knowledge.modules.install
knowledge.modules.manage
knowledge.storage.manage
knowledge.federation.publish
knowledge.federation.manage
```

Agent 不因能读取当前 Chat Session 而自动获得 private knowledge。Knowledge search Tool
必须接收由 Tool Gateway 派生的 `ToolCallContext`，不能接受模型自报 actor、space 或
installation。

Tag 写入同样从 ToolCallContext 派生 actor。App 只能写自己的 namespace；模型只能创建
`inferred/suggested` assignment；只有用户操作或显式规则可以产生 user/active Tag。

### 5.4 Knowledge Bucket 与跨 Node 联邦

`KnowledgeSpace` 同时是检索 ACL 和分享边界，UI 使用更容易理解的“知识桶”。系统不提供
“把个人桶打开给远端”的开关，避免配置错误把既有个人历史整体暴露出去。

| Bucket | 本机可见范围 | 跨 Node | 创建/治理 |
| --- | --- | --- | --- |
| private | 当前 Member | 永不允许 | Runtime 自动创建；本人治理内容 |
| installation | 当前 installation 成员 | 不允许 | Member 可贡献本人内容；core 治理公共内容 |
| federated | 本机按 policy 可见 | 仅 allowlist Node | core 创建、发布、撤回和授权 |

```text
knowledge_publications
  id
  federated_space_id
  source_item_id / source_revision
  published_item_id / published_revision
  published_by / published_at
  content_digest
  status                   staging | active | retracted
  retracted_at / reason

knowledge_federation_exports
  id
  federated_space_id
  node_grant_id
  remote_installation_id
  capability_set
  quota_json
  status                   active | suspended | revoked
  expires_at / grant_epoch / revoked_at
```

Member 可以向 local shared bucket 提交知识，但不能把 Item 发布到 federated bucket，也不能
创建或修改 NodeGrant。core 发布时必须看到内容清单、来源、Tag、Package license、预计返回
字段、目标 Node、有效期和 quota；批量发布需要 preview，不能用“分享整个本地知识库”的
模糊操作。

发布到 federated bucket 推荐生成独立、不可变的 published revision，并保留
`source_item_id/source_revision/published_by/published_at` lineage。源 Item 后续修改、删除或
撤回共享不会静默改写已发布版本；UI 提示 core 选择 update/retract。删除或发现敏感内容时
可执行紧急 retract，使 active remote query 立即不可见，再异步清理派生索引。

#### 5.4.1 NodeGrant 与 BucketPolicy

联邦知识调用的有效权限是以下交集：

```text
downstream member permission
∩ downstream route policy
∩ authenticated NodeLink
∩ upstream NodeGrant
∩ federated BucketPolicy
∩ per-item visibility/license/risk policy
```

NodeGrant 的权威副本保存在提供知识的 Node，至少绑定：

```text
origin_installation_id
serving_installation_id
allowed_capabilities       knowledge.remote.search@1 / knowledge.remote.get@1
allowed_bucket_ids
query/result/bytes/concurrency quotas
allowed_content_kinds
excerpt/citation limits
expires_at / grant_epoch / revoked_at
```

下游请求中的 actor、role、bucket ID、Tag 和 scope 都不能扩大 NodeGrant。private 和
installation bucket 不进入 exported descriptor discovery，即使请求伪造其 ID 也返回 404。
grant revoke/epoch rotation 必须在 active retrieval 前校验，并使未完成请求与短期 citation
handle 按契约失效。

#### 5.4.2 MCP/Service contract

Knowledge Federation 复用现有 NodeLink、NodeGrant、RemoteServiceBinding 和 Federation
Gateway。MCP 是受控 Tool/Service contract，不是让对端连接数据库或任意本机 MCP server。
提供知识的 Node 只导出：

```text
service: ai2apps.knowledge-federation
capabilities:
  knowledge.remote.search@1
  knowledge.remote.get@1

tools:
  knowledge.remote.search
  knowledge.remote.get_citation
```

第一版为 query-only：下游发送 query、明确 bucket selector、时间/类型过滤和有界 Top-K；
上游执行 lexical/vector retrieval、ACL recheck、redaction 和 result shaping，返回 excerpt、
source title、publisher、event/source time、content digest、published revision、serving Node 和
短期签名 citation handle。不得返回 embedding、内部路径、原始 blob key、private Tag、内部
Session ID、完整未请求文档或 backend-specific score/debug state。

`get_citation` 只能读取 search 已授权结果对应的有界证据，handle 绑定 NodeGrant、origin
Node、bucket、item revision、expiry 和 audience，不能枚举或转授。下游若要长期保存远端
内容，必须由用户显式执行“导入本地”，创建带远端 provenance 的新 Item；这不是透明 cache。

第一版只允许一跳。上游收到联邦知识请求后不得再次调用第三个 Node；`route_path` 包含重复
installation 或 `hop_count > 1` 时拒绝。超时、取消、disconnect 和 idempotent retry 沿单次
MCP/Service request 传播。

#### 5.4.3 隐私、信任与内容安全

远程检索会把 query 和过滤条件发送给另一台 Local 服务器，因此 Knowledge App/Chat 必须
标明 serving Node；首次使用某 Node 或敏感 bucket 时需要明确授权。服务端审计记录
request/Node/bucket/latency/result count，不默认保存 query 和 excerpt 明文。

下游将远端 excerpt 标记为 `external_node_evidence`，保留 Node、bucket、published revision、
publisher/module 和 retrieval time。它参与 RRF/rerank 时使用独立 source trust 权重，并在
回答中显示远端 citation；网页或文档中的 prompt injection 不因 Node 已配对而获得 Tool、
系统提示或写入本地 Knowledge 的权限。

`.ai2knowledge` 模块只有在 manifest/license 明确允许 remote serving/redistribution，且
BucketPolicy 与 NodeGrant 都允许时才能发布到 federated bucket。健康、法律、金融等
restricted 内容还要满足远端 jurisdiction、review_due 和用途 policy；安装知识包不等于
自动获得跨节点再分发权。

## 6. 摄取管线

### 6.1 通用流程

```text
authorize source
  -> create Item and original Asset
  -> persist immutable provenance
  -> enqueue format-specific processing
  -> create Representations
  -> chunk
  -> FTS index
  -> optional embedding/vector index
  -> deterministic source facets
  -> optional summary/entities/events/inferred tags
  -> publish item.ready or item.partial
```

基础 lexical 处理完成即可进入 `ready`。增强 stage 失败时 Item 为 `partial`，用户仍能
打开原件和使用已有索引。

### 6.2 网页

- 验证 `http`/`https`，拒绝 file、localhost、link-local、metadata service 和内网 SSRF；
- 使用现有 managed browser/readability 能力，但以独立 Service context 执行；
- 保存用户提交 URL、最终 URL、canonical URL、标题、正文、抓取时间和响应元数据；
- 登录态抓取必须显示信任边界，并禁止将 Cookie 或 token 写入知识记录；
- 支持仅保存链接、保存可读正文和保存授权快照三种结果状态；
- 定期刷新必须是显式 source subscription，v1 不默认刷新。

### 6.3 文件与 Office/PDF

- 复用 Attachments、content-addressed blob 和 Documents parser；
- 不复制 parser runtime；
- Representation 保留页码、slide、sheet、cell range、section；
- scanned PDF 在 OCR backend 未安装时进入 `waiting_dependency`，而非失败或静默空文档。

### 6.4 图片

- 基础模式保存原图、EXIF、拍摄时间、尺寸、文件名和用户说明；
- 可选 OCR 和 VLM caption；
- caption、对象和食物识别均保存 producer 与 confidence；
- “前天吃什么”首先按 event/source time 过滤图片，再检索用户说明、OCR 和 caption；
- 回答使用“可能”表达低置信度推断，并链接原图。

### 6.5 音频和视频

- 音频可选调用本地 STT Service，Representation 保留 timecode；
- 视频 v1.1 提取容器元数据、音轨和有界关键帧，不逐帧处理；
- 关键帧数量、分辨率、时长和总计算量有硬限制；
- 原视频始终是证据，transcript/caption 是派生表示。

### 6.6 Chat、Agent 与 Artifact

Chat 保存入口支持：

- 单条 Message；
- 选中 Message range；
- 一个 user/assistant turn；
- Attachment；
- Agent final output；
- Artifact 或网页链接。

Knowledge Item 保存 message IDs、Session ID、AppInstance、Run ID 和显示快照。默认不保存
隐藏 system prompt、Tool secret、内部 reasoning 或未授权的 Tool output。

Chat 来源自动生成 `source.kind:chat`、`source.app:ai2apps.general-chat`、可信 Session、
Agent 和 content kind Facet。第三方 App 来源自动使用其稳定 package ID。App 可以附带
自己 namespace 下的 Tag 建议，但不能写 Runtime Facet 或伪造其他 App 来源。

### 6.7 自动 Facet 与 Tag 管线

自动化分两层：

1. 无模型确定性层：来源 App/Session/Agent、内容类型、MIME、URL domain、显式时间、
   parser location；随 Item 创建或解析事务写入；
2. 可选模型层：主题、实体、事件、对象、食物等 inferred Tag；异步执行，不阻塞 Item
   进入 ready，并遵守 semantic/multimodal dependency 与隐私 policy。

模型 Tag 的 prompt 只接收当前 Item 获准的 bounded Representation，不得读取其他 private
Item 来“补全”标签。模型升级后以新 producer version 生成新 assignment generation；旧
建议在验证和用户确认迁移前不被静默覆盖。

## 7. 检索与回答

### 7.1 Query contract

```json
{
  "query": "前几天我找的那个关于西瓜的文章链接",
  "spaces": ["private", "installation"],
  "kinds": ["webpage"],
  "facets": {"source.app": ["ai2apps.general-chat"]},
  "tags": ["西瓜", "稍后阅读"],
  "time": {"relative": "last_7_days", "field": "ingested_at"},
  "remote": {"mode": "off", "bindings": []},
  "limit": 20,
  "answer": false
}
```

客户端只能表达想搜索的逻辑范围；服务端根据 principal 缩小为实际 space IDs。Remote
默认 `off`，只有用户选中的 RemoteServiceBinding 才参与；本地 private Tag、内部 Space ID
和未选择的过滤条件不得被自动加入远端 query。

### 7.2 Query understanding

优先使用确定性规则抽取：

- 相对时间与时区；
- “看过/找过/保存”对应 ingested/source interaction time；
- “吃了/去了/做了”对应 event time；
- 网页、图片、文件、Chat 等 kind；
- URL、标题、作者和 App source。
- 用户 Tag、可信 Source Facet 和 inferred Tag；inferred Tag 只能作为带 confidence 的 query
  expansion/boost，不能单独成为事实证据。

模型 query rewrite 是可选增强，输出结构化 filter 与多条 lexical/semantic query，不得
扩大权限或自行取消用户指定范围。

### 7.3 Hybrid retrieval

第一版算法：

1. authoritative filters：space、installation、status、kind、time；
2. exact Facet/Tag filters；
3. SQLite FTS5/BM25 lexical Top-N；
4. 可选 vector Top-N；
5. Reciprocal Rank Fusion；
6. trusted Facet、user-confirmed Tag 和 inferred Tag 的分级 boost；
7. Item-level diversity，避免同一长文占满结果；
8. 可选 local reranker；
9. authoritative recheck；
10. context budget selection。

启用 remote bindings 时，每个远端 Node 独立执行上述检索并返回有界结果；下游在本地执行
source-aware fusion。远端失败不改变本地结果，也不能静默转向第三个 Node。local 与每个
remote source 的 Top-K、latency、trust weight 和 citation coverage 分开记录。

默认权重顺序是用户显式 filter > Source Facet > user-confirmed Tag > App Tag > inferred Tag。
Tag boost 的具体参数属于版本化 RetrievalProfile，必须可在 Eval 中复现。

所有阶段记录匿名化 metrics，但不记录完整 query 或正文，除非用户启用诊断。

### 7.4 Citation envelope

每条证据至少包含：

```text
item_id
title
kind
owner/display attribution
source_url or openable local resource
source/event/ingested time
location: page/slide/sheet/timecode/message IDs
quoted excerpt or media thumbnail reference
representation kind, producer and confidence
retrieval score breakdown
optional remote provenance: serving_node, bucket_id, published_revision,
  grant_epoch, retrieved_at, citation_expiry
```

Knowledge Ask 的最终回答必须引用 evidence IDs。无足够证据时返回“不确定/没有找到”，
不能把模型常识伪装成本地记忆。

## 8. Knowledge App 与 Chat 联动

### 8.1 内置 App

新增 `ai2apps.knowledge`，`singleton/user`，默认需要：

```yaml
access:
  capabilities:
    - app.knowledge.use
```

主要页面：

- Ask：选择“我的知识/本机共享”、类型与时间后对话；
- Timeline：按 event/source/ingested time 浏览；
- Library：网页、文档、图片、音频、视频、Chat、Artifact；
- Shared：本机共享内容和治理状态；
- Inbox：pending、partial、waiting dependency、failed；
- Sources：原始来源与处理历史；
- Tags：用户 Tag、别名、合并、来源、建议确认/拒绝和 shared governance；
- Buckets：private、Local Shared、Federated bucket 的边界、published revisions 与状态；
- Shared Nodes：已配对 Node、获准 bucket、有效期、quota、最近调用和 revoke；
- Settings：增强模型、磁盘、自动保存、自动 Tag、敏感 Tag、Cloud 处理和重建索引。

Knowledge Chat 是该 App 的 App-owned ConversationSession。检索结果以标准 Message
parts、ResourceHandle 和 citations 呈现，不建立第二套消息系统。

### 8.2 Chat 集成

Chat 使用 Knowledge Service，不直接写数据库。UI 提供“加入知识库”，保存面板包括：

```text
title          generated but editable
scope          private(default) | installation
selection      message | turn | selected range | attachment | link
note           optional explicit context
tags           user input + App/AI suggestions with visible source
```

第一版仅手工保存。后续自动记忆模式为 `off | ask | rules`，默认 `off`。模型只能建议保存，
不能自行将 private 内容升级为 shared。

P0 接线采用两级 Knowledge Context：`consumer_app_id` 保存 App 默认 buckets，
`consumer_app_id + session_id` 保存 Conversation/Workflow 覆盖。会话记录一旦存在，即使其
bucket 列表为空也表示显式禁用，不回退到 App 默认。Chat 与 General Agent 在调用模型前通过
Knowledge Context Search 获取有界 evidence，将其作为非可信证据而非指令注入，并把稳定
item/revision citation metadata 保存到最终消息；向量索引尚未 catch-up 或 Runtime 失败时，
同一调用透明使用 FTS5，而不是阻塞对话。

保存面板将“来自 Chat/某 App、Session、Agent、文件类型”等显示为只读 Source Facet；用户
可以编辑 user Tag；App/AI 建议以独立样式显示并可逐个接受或删除。不得把模型建议渲染为
已经确认的用户分类。

## 9. 初始化、依赖与资源策略

### 9.1 默认基础模式

Knowledge App 可直接打开，使用：

- Platform SQLite schema；
- FTS5；
- 已有 Documents parser；
- URL、文本、文件和 media metadata；
- lexical/time/source search。

不自动下载模型，不要求 Docker，不启动额外常驻服务器。

### 9.2 增强能力部署

Knowledge 打开时只通过 ACPF 静默 `probeCapability()`，不得下载。用户首次明确启用语义
检索，或 Chat/Workflow 对当前操作请求 semantic/OCR/STT/VLM/rerank 时，才展示 ACPF
Capability Choice Sheet 与 Setup Sheet。建议 capability 拆分为：

```text
knowledge.lexical_search        Core 内置，始终 ready
knowledge.semantic_retrieval    LanceDB RAG Runtime + Embedding Provider/Model
knowledge.image_understanding   OCR/VLM Package
knowledge.audio_understanding   STT Package
knowledge.reranking             可选 Reranker Package
```

`knowledge.semantic_retrieval` 的推荐组件栈为：

```text
Knowledge App / Chat action
  -> ACPF probe/ensure
  -> ai2apps/runtime-knowledge-rag (.ai2service Runtime Provider)
  -> ai2apps/service-knowledge-lancedb (thin Vector Worker)
  -> ai2apps/model-multilingual-e5-small (thin Embedding Provider)
       -> reuse the exact Knowledge RAG Runtime generation
       -> pinned multilingual-e5-small-mlx checkpoint (384 dimensions)
  -> health verify + background shadow generation
  -> activate RetrievalProfile(FTS5 + LanceDB + RRF)
```

Setup Sheet 展示安装清单：

- 组件和模型名称、publisher、digest；
- 下载量和预计磁盘占用；
- 是否复用已安装模型；
- 本地或 Cloud 处理边界；
- 首次索引预计时间；
- 取消、恢复、卸载和数据保留行为。

用户同意后通过 ACPF 调用现有 signed Service/Model Provider package 流安装，不通过
Knowledge ingestion code 执行任意 `pip install`。ACPF Session 只保存 capability、profile、
Package 操作和 opaque resume token，不保存查询、文档或附件正文。未安装时 Job 进入
`waiting_dependency`，基础功能保持可用；卸载增强栈只删除可重建索引，不删除 Knowledge。

### 9.3 资源调度

- embedding/rerank 使用隔离的 Model Service 与其声明的 native Runtime，不在 Core 直接 import MLX；
- indexing 使用低优先级、有界 batch，并响应内存压力与前台生成；
- 大批量导入可暂停、恢复和限速；
- 默认 installation Knowledge 存储预算为 10 GiB，由 core 在 Settings 调整；统计实际占用的
  original、derived、module、staging，以及各 private/shared space 分项；
- 预算用量达到 80%/90% 时分别提示 warning/critical；达到 100% 时拒绝新增 ingest、Package
  install/update 和其他增长型写入，并暂停会增加磁盘的派生 Job；
- 物理低磁盘保护独立于逻辑预算：volume 可用空间低于 `max(5 GiB, 10%)` 时进入 critical，
  即使逻辑预算尚未用满也执行相同限制；阈值可由 core 调整但不能关闭安全下限；
- critical 状态仍允许 search/read、export、删除、撤回共享、卸载模块和调整配额；不得自动
  删除原始 Item、ModuleVersion 或 Overlay；
- 自动回收仅限已验证无引用的 staging/temp、超过 rollback deadline 的 retired generation
  和其他明确可重建的非 active cache，并产生审计 Event；
- core 在 Knowledge Settings 查看当前/历史用量、最大贡献者、增长趋势、Job 占用和可回收
  估算，可按 space/module 清理或调整预算；普通成员只能查看自己的用量；
- 每用户和 shared space 仍可设置可选子配额、Item、并发 Job 与每日处理额度，子配额之和
  不要求等于 installation 总预算；
- 原始文件、派生媒体、text index 和 vector index 分项显示占用。

## 10. 开源后端选型

### 10.1 评估原则

- 能否嵌入本地 App，避免 Docker 和独立管理员；
- Apple Silicon/macOS 与 Linux arm64/x86_64 打包；
- metadata/partition filter 是否在 ANN 前生效；
- 增量 upsert/delete、crash recovery、备份和 schema migration；
- 多模态向量和大于十万 chunk 的性能；
- Python 3.11–3.13 和打包体积；
- 许可证与离线分发；
- 是否可以完全置于 AI2Apps Adapter 后面。

### 10.2 候选结论

| 候选 | 优点 | 主要问题 | 决策 |
| --- | --- | --- | --- |
| LanceDB OSS | Embedded、Apache-2.0、Rust、面向本地/多模态、支持向量与检索索引 | 增加独立存储目录和 Python/Arrow 二进制；与 Platform SQLite 非同一事务 | macOS arm64 MVP spike 已通过，作为首个可选 vector backend |
| sqlite-vec | 极小、C/SQLite、MIT/Apache-2.0、支持 metadata/partition、易备份 | 官方标记 pre-v1；ANN 仍在演进；macOS Python extension 与签名需专项验证 | 备选与实验 backend |
| Chroma | Persistent embedded/client-server、metadata filtering、生态成熟 | 依赖和内部存储较重；重复一部分文档/collection 管理；JS 仍需 server | 不作为默认，可通过 External Service 支持 |
| Qdrant | 过滤、ANN、运维能力成熟 | 完整部署通常需要独立进程/容器；不符合零部署默认路径 | 大型/企业 External backend |
| RAGFlow | 完整解析与 RAG 产品能力 | 官方自托管要求 Docker，资源与系统依赖重；重复 AI2Apps 产品面 | 不嵌入 |
| AnythingLLM | 本地产品完整、默认使用 LanceDB、MIT | 自带 UI、用户、Workspace、Agent 和模型编排，和 AI2Apps 重叠 | 只作产品参考，不作为 backend |
| LlamaIndex/Haystack | 丰富 connectors、pipeline 和 RAG 组件 | 会引入第二套 orchestration/Document/Agent 抽象，长期升级面大 | 可参考或隔离复用单个 connector，不作核心 |

### 10.3 可替换 Retrieval Stack

采用权威 Knowledge 与可替换 Retrieval Stack 分层：

```text
AI2Apps Knowledge Authority                 never replaceable
  Platform SQLite + content store
  Item / Asset / Representation / Chunk / ACL / change log

Replaceable Retrieval Stack
  LexicalIndexBackend
    └── SQLiteFTS5Backend                    always installed
  VectorIndexBackend
    ├── LanceDBBackend                       first candidate
    ├── SqliteVecBackend                     experimental/fallback
    └── ExternalVectorBackend                future enterprise integration
  EmbeddingProvider                          separate from vector database
  RetrievalStrategy                          fts/vector/hybrid/time-aware
  RerankerProvider                           optional
```

核心 protocol：

```text
LexicalIndexBackend
  create_generation / upsert / delete / search / validate / drop / health

VectorIndexBackend
  create_generation / upsert / delete / search / count / validate /
  activate / drop / health

EmbeddingProvider
  descriptor / embed / dimension / distance / normalization / health

RetrievalStrategy
  plan / retrieve / fuse / diversify / explain

RerankerProvider
  descriptor / rerank / health
```

Backend manifest 至少声明：runtime mode、package digest、vector types、distance、最大维度、
metadata/partition filter、incremental delete、exact/ANN、generation/shadow 支持、网络与
磁盘权限。AI2Apps 不接受只提供“上传文档并 Chat”的黑盒 backend 作为正式索引实现。

LanceDB spike 必须通过以下门槛后才能成为默认增强 backend：

- macOS arm64、Linux arm64/x86_64、Python 3.11–3.13 wheel/DMG 安装；
- 无网络冷启动和可预测的二进制体积；
- 10k/100k/1M chunk build、upsert、delete、filtered Top-K 和 restart 测试；
- private/shared partition 无越权候选；
- crash 后 index generation 可重建；
- embedding 模型切换 shadow generation；
- Apache-2.0 attribution 和供应链 digest 纳入 package trust。

若 spike 不通过，v1 仍可只发布 FTS5，并继续评估固定版本 `sqlite-vec`。Knowledge API、
App 和数据模型不因 backend 选择变化。

### 10.4 Backend 与知识迁移

只更换 vector database 时不迁移知识，而是迁移派生索引：

```text
freeze authoritative snapshot watermark
  -> create target generation
  -> backfill authoritative active Chunks
  -> dual-write/consume Knowledge change log
  -> catch up to current watermark
  -> validate count/hash/filter/delete invariants
  -> run offline Eval and optional shadow queries
  -> atomically switch active RetrievalProfile/generation
  -> retain source generation for bounded rollback
  -> retire and delete after rollback window
```

迁移类型：

| 变化 | 处理 |
| --- | --- |
| 仅更换 vector backend | 复用 Chunk 和兼容 embedding，重写目标索引 |
| 更换 backend 与 embedding 模型 | 新建 embedding/index generation，重新 embedding |
| embedding dimension/distance/normalization 改变 | 禁止混用，必须完整新 generation |
| chunker 改变 | 重建 Chunk、FTS 和 vector generation |
| parser/OCR/VLM 改变 | 重建受影响 Representation 及所有下游派生物 |
| External backend 返回本地 | 从 AI2Apps Authority 重建，不依赖外部导出正文 |

可选将 embedding BLOB 作为 AI2Apps 管理的派生缓存保留，使同一 embedding contract 下
更换数据库时避免重复推理。缓存同样按 generation/model digest 管理，可安全删除。

Migration 验证至少包括：

- active Item、Chunk、space 和 tombstone 数量；
- 随机与分层 content hash；
- private/shared partition 与两个用户的 adversarial query；
- delete、shared retract、member revoke 和 stale row；
- target/source shadow Recall@K、nDCG、latency、RSS 和 disk amplification；
- source 故障、target 故障、进程重启和原子 rollback。

迁移期间 Search 只读取一个 active generation。Shadow query 可以读取 target 进行内部
比较，但结果不能返回用户、进入回答或扩大内容日志采样。

### 10.5 用户选择与部署策略

普通用户看到能力档位：

```text
基础模式          FTS5，无额外安装
语义模式          系统推荐的 vector backend + embedding
高级/外部模式     管理员选择具体 backend/profile
```

backend 是 installation 级基础设施，不能由每个普通成员分别启动不同数据库进程。成员
可以选择自己的 private space 是否参与 semantic indexing，以及是否允许本地/Cloud 增强
模型处理；core/owner/admin 管理具体 backend、配额和迁移。

切换 UI 必须展示：目标 backend/profile、需要安装的 signed package、下载和磁盘占用、
是否重新 embedding、是否涉及 Cloud、预计时间、迁移/验证进度、旧 backend 保留期和
rollback 操作。默认只提供系统推荐选项，实验 backend 放在 Advanced 中并明确风险。

### 10.6 参考资料

- [LanceDB OSS FAQ](https://docs.lancedb.com/faq/faq-oss)
- [LanceDB repository and SDKs](https://github.com/lancedb/lancedb)
- [sqlite-vec repository](https://github.com/asg017/sqlite-vec)
- [sqlite-vec Python integration](https://alexgarcia.xyz/sqlite-vec/python.html)
- [Chroma persistent client](https://github.com/chroma-core/docs/blob/main/docs/usage-guide.md)
- [Qdrant local quickstart](https://qdrant.tech/documentation/quick-start/)
- [Haystack component/pipeline architecture](https://docs.haystack.deepset.ai/)
- [RAGFlow self-hosting requirements](https://github.com/infiniflow/ragflow)
- [AnythingLLM Docker and LanceDB defaults](https://github.com/Mintplex-Labs/anything-llm/blob/master/docker/HOW_TO_USE_DOCKER.md)

## 11. Service、Tool 与 API 契约

稳定 Service：

```text
service: ai2apps.knowledge-service
capabilities:
  knowledge.ingest@1
  knowledge.search@1
  knowledge.ask@1
  knowledge.manage@1
```

首批 Tools：

```text
knowledge.add_url
knowledge.add_attachment
knowledge.add_chat_selection
knowledge.add_artifact
knowledge.search
knowledge.get
knowledge.update
knowledge.delete
knowledge.share
knowledge.status
knowledge.reindex
knowledge.tags.list
knowledge.tags.assign
knowledge.tags.remove
knowledge.tags.confirm
knowledge.tags.reject
knowledge.tags.merge
knowledge.modules.list
knowledge.modules.get
knowledge.modules.overlay
knowledge.federation.list_buckets
knowledge.federation.publish
knowledge.federation.retract
knowledge.federation.search_remote
knowledge.federation.get_citation
```

建议平台 API：

```text
GET    /v1/platform/knowledge/spaces
GET    /v1/platform/knowledge/items
POST   /v1/platform/knowledge/items
GET    /v1/platform/knowledge/items/{id}
PATCH  /v1/platform/knowledge/items/{id}
DELETE /v1/platform/knowledge/items/{id}
POST   /v1/platform/knowledge/items/{id}/share
POST   /v1/platform/knowledge/items/{id}/retry
POST   /v1/platform/knowledge/search
POST   /v1/platform/knowledge/ask
GET    /v1/platform/knowledge/jobs/{id}
POST   /v1/platform/knowledge/jobs/{id}/cancel
GET    /v1/platform/knowledge/settings
PUT    /v1/platform/knowledge/settings
POST   /v1/platform/knowledge/indexes/rebuild
GET    /v1/platform/knowledge/tags
POST   /v1/platform/knowledge/tags
PATCH  /v1/platform/knowledge/tags/{id}
POST   /v1/platform/knowledge/tags/{id}/merge
POST   /v1/platform/knowledge/items/{id}/tags
DELETE /v1/platform/knowledge/items/{id}/tags/{tag_id}
POST   /v1/platform/knowledge/items/{id}/tag-suggestions/{tag_id}/confirm
POST   /v1/platform/knowledge/items/{id}/tag-suggestions/{tag_id}/reject
GET    /v1/platform/knowledge/backends
POST   /v1/platform/knowledge/backends/install
GET    /v1/platform/knowledge/retrieval-profiles
POST   /v1/platform/knowledge/backend-migrations
GET    /v1/platform/knowledge/backend-migrations/{id}
POST   /v1/platform/knowledge/backend-migrations/{id}/cancel
POST   /v1/platform/knowledge/backend-migrations/{id}/activate
POST   /v1/platform/knowledge/backend-migrations/{id}/rollback
GET    /v1/platform/knowledge/modules
GET    /v1/platform/knowledge/modules/{id}
POST   /v1/platform/knowledge/modules/install
POST   /v1/platform/knowledge/modules/{id}/update
POST   /v1/platform/knowledge/modules/{id}/rollback
POST   /v1/platform/knowledge/modules/{id}/disable
DELETE /v1/platform/knowledge/modules/{id}
GET    /v1/platform/knowledge/modules/{id}/overlays
POST   /v1/platform/knowledge/modules/{id}/overlays
GET    /v1/platform/knowledge/storage
PUT    /v1/platform/knowledge/storage/budget
POST   /v1/platform/knowledge/storage/reclaim
POST   /v1/platform/knowledge/spaces/federated
POST   /v1/platform/knowledge/spaces/{id}/publish
POST   /v1/platform/knowledge/spaces/{id}/retract
GET    /v1/platform/knowledge/federation/exports
POST   /v1/platform/knowledge/federation/exports
PATCH  /v1/platform/knowledge/federation/exports/{id}
DELETE /v1/platform/knowledge/federation/exports/{id}
```

所有按 ID 读取的越权结果返回 404。Search/Ask 不接受任意 owner ID；shared scope 由服务端
映射。mutation 使用 idempotency key 和 revision/ETag 防止重复导入或静默覆盖。模块安装
API 只接受已验证的 staged Package/Registry release handle，不接受客户端自报 publisher、
digest 或 trust tier；Registry 下载与本地 archive 安装都必须经过同一个 validator。普通
成员的 storage 响应只返回自己的用量；budget/reclaim mutation 和所有 module lifecycle
mutation 都要求 core principal，不能仅凭普通 Package 管理 capability 调用。federated
space、publish/retract 和 export binding mutation 同样要求 core principal 与 reauth；对端
只通过 Federation Gateway/MCP Service contract 查询，不能调用这些平台 API。

## 12. Event、审计与可观测性

语义 Event：

```text
knowledge.item.created
knowledge.item.visibility.changed
knowledge.item.ready / partial / failed / deleted
knowledge.tag.created / updated / merged / deleted
knowledge.item.tag.assigned / removed / suggested / confirmed / rejected
knowledge.module.installing / installed / updated / rolled_back / disabled /
  uninstalled / degraded
knowledge.module.overlay.created / updated / conflicted / deleted
knowledge.storage.warning / critical / budget_changed / reclaimed
knowledge.federation.bucket.created / item.published / item.retracted
knowledge.federation.export.created / updated / revoked
knowledge.federation.search.completed / citation.opened / denied
knowledge.job.started / progress / completed / failed / cancelled
knowledge.index.generation.created / activated / retired
knowledge.backend.migration.started / progress / validated / activated /
  rolled_back / failed
knowledge.retrieval.shadow.compared
knowledge.search.completed
knowledge.ask.completed
knowledge.dependency.required / installed / removed
```

默认 metrics：

- Items/assets/chunks/jobs by kind and status；
- ingest latency、parse/OCR/STT/embed/index latency；
- FTS/vector/rerank candidate count 和 latency；
- Recall/Eval 数据集上的 retrieval metrics；
- index bytes、original bytes、derived bytes；
- permission denial、stale index rejection 和 dependency wait；
- answer citation coverage、no-evidence rate。
- Source Facet/Tag usage、suggestion acceptance/rejection、duplicate/alias merge 和自动 Tag
  latency；metrics 不包含 private Tag 明文。
- module install/update/rollback latency、package bytes、expanded bytes、item count、Overlay
  conflict 和 stale/restricted status；metrics 不包含 private Overlay 正文。
- federation requests/latency/errors/result bytes by origin/serving Node and bucket、NodeGrant
  denial/revoke/quota、remote citation expiry 和 prompt-injection rejection；不包含 query、
  excerpt、private bucket 名称或 Tag 明文。

日志和审计默认不记录完整 query、正文、图片、转写、embedding 或 answer。调试采样必须由
用户显式启用，限定 space、时间和保留期。

## 13. 备份、删除与恢复

- Platform SQLite 与 content store 是备份权威；
- vector index 可以排除在基础备份之外并在恢复后重建；
- backup 必须包含 active RetrievalProfile、generation descriptor 和 change-log watermark，
  但无需包含 backend 私有索引格式；
- Item 删除先产生 tombstone、撤销索引可见性，再异步清理独占资产和派生数据；
- shared Item 撤回必须立即从其他用户检索路径消失；
- content-addressed blob 只有引用计数归零后才能清理；
- index backend 不可用时自动降级 FTS，不静默返回跨 generation 混合结果；
- migration 失败不激活新 schema/index generation；
- backend 卸载前必须确认没有 active generation；强制卸载先原子降级 FTS profile，再
  清理可重建索引。
- backup 包含 federated bucket、publication lineage/revision 和 export policy，但不包含
  NodeLink credential；恢复后 export 默认 suspended，重新验证 NodeGrant/epoch 后才能服务；
- 下游不把 remote query result 当作备份或透明 cache；显式导入的远端内容作为新的本地 Item
  备份，并保留 serving Node、bucket、published revision 和 content digest provenance。

## 14. 质量与安全验收

最小验收集必须包括：

- 两个成员的 private 内容互不可见；
- shared 内容可见，但普通成员不能修改他人贡献；
- member 可以提交、修改和撤回自己的 shared contribution；默认只有 core 能治理他人贡献；
- private → shared → private 变更立即影响 FTS/vector/Ask；
- stale vector row 不能绕过 SQLite authoritative recheck；
- 网页 URL、PDF 页码、图片原图、音频 timecode 和 Chat message citation 可打开；
- “前几天的西瓜文章”和“前天吃了什么”在固定数据集上可复现；
- embedding/reranker/VLM 未安装时基础模式正常，安装需明确同意；
- ingestion crash/restart 不重复 Item、Asset 或计费模型调用；
- 删除、成员 revoke、installation access epoch 变更后不再召回；
- Cloud processing 未授权时任何原始内容不离开 Local；
- 无证据时 Knowledge Ask 不生成伪造的本地记忆；
- LanceDB → sqlite-vec/FTS-only 及反向迁移不改变 Item、Asset、owner、visibility、来源
  或 citation identity；
- migration backfill、catch-up、shadow、activate 和 rollback 任一阶段崩溃后均可恢复；
- 用户选择的 RetrievalProfile 能固定 backend/model/strategy 版本并复现实验结果；
- Chat/App Source Facet 不能由请求体伪造；App 不能越过自己的 Tag namespace；
- private Tag 不出现在其他用户的搜索、自动补全、统计、shared catalog 或模型 prompt；
- AI inferred Tag 保留 producer/confidence/evidence，拒绝后不被同版本反复建议；
- 仅凭 inferred Tag 不生成“用户吃过/去过/拥有”等事实回答；
- Tag rename/merge/delete、Item share/retract 和 backend migration 后检索结果一致；
- `.ai2knowledge` 拒绝 path traversal、symlink、archive bomb、未索引文件、digest/signature
  不匹配、可执行内容和 publisher spoof；
- 普通成员不能安装、更新、rollback 或卸载任何 private/installation Knowledge Module；
- core 安装 private module 时不能把内容写入其他成员的 private space；
- core 删除 Member 时必须显式选择 private/shared 处置；revoke 后 core 无法读取 private，
  member export window 只产生面向原成员的窄化、限时下载授权；
- 10 GiB 默认预算、80%/90%/100% gate 和物理 reserve 边界可复现；critical 时读取、导出、
  删除仍可用，且原件、active ModuleVersion 和 Overlay 不被自动删除；
- private/installation bucket 不出现在远端 descriptor、search、citation、Tag/count/statistics、
  error detail 或 timing side-channel；伪造 bucket ID 始终 fail closed；
- 只有 core 可以创建 federated bucket、publish/retract 和绑定 NodeGrant；Member 的 local
  shared contribution 不因存在 NodeLink 自动外发；
- remote search/get 同时受 NodeLink、NodeGrant、BucketPolicy、Item/license/risk policy 和
  grant epoch 约束，revoke/retract 后立即不再召回；
- 联邦请求只允许一跳，不传输 embedding/index/blob path，短期 citation 不能 replay、换
  audience 或越 grant 枚举；
- 远端不可用时本地 Search/Ask 保持工作，恶意 remote excerpt 不触发 Tool、不读取系统提示、
  不自动写入本地 Knowledge；
- 模块 update/rollback 不改变稳定 citation identity，用户 Overlay 保留且冲突可见；
- 普通 ZIP 导入不会获得 verified publisher/trust tier 或进入 Registry 更新链；
- restricted 模块缺少 jurisdiction、citation、review/review_due metadata 时拒绝安装，过期后
  不作为无警告的可靠 Ask 证据；
- 模块在 FTS-only 与 semantic backend 之间迁移不改变 Package digest、ModuleVersion、
  Overlay 或上游 provenance。
