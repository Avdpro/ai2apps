# Cloud 工作需求：模型 Package 过时机制（兼容现有客户端）

日期：2026-09-28（Asia/Shanghai）

状态：交付 Cloud 实现的需求与建议契约；不是已部署接口说明。

范围：Cloud 数据、后台管理、公共生命周期接口、兼容测试与部署回执。客户端 ACPF/Discover 另行实现。

## 1. 目标与不可破坏的边界

管理员可将整个模型 Package 标为“已过时”，或恢复正常。后续新客户端：

- ACPF 隐藏过时模型，不作为新安装或自动推荐的候选。
- Discover 仍显示，带“已过时”标记、原因和可选替代模型。
- 已安装模型、已保存工作流、正在运行的任务继续可用。
- 允许用户从 Discover 明确选择安装过时模型；此机制不是安全禁用机制。

**本次 Cloud 部署必须允许当前已发布客户端继续搜索、推荐、安装、更新和使用模型。不得要求同步升级客户端。**

旧客户端暂时不显示过时标记、仍可通过 ACPF 安装过时模型，是预期的向后兼容行为。不能在 Cloud 静默改变旧请求结果来强制启用新规则。

第一版按稳定 `packageId` 生效，覆盖其所有已发布和未来版本。新版本发布不自动清除标记；恢复正常必须有显式管理操作。暂不实现按 release、checkpoint、modelId 的局部覆盖，也不涉及 Cloud 托管推理模型目录。

## 2. 已确认的客户端兼容风险

核对代码：

- `ai2apps/packages/contract_v1.py::verify_repository_snapshot`：对 envelope、signature、payload 使用 `_exact_keys`。现有 payload 只接受 `domain/version/generatedAt/expiresAt/releases`。
- `ai2apps/packages/registry.py::_release` 与 `_dependency_release`：安装依赖 release 的 `status == published`。
- `RegistryPackageManager.trusted_snapshot`：校验固定 repository key 指纹、Ed25519 签名、有效期、单调 metadata version。
- ACPF 当前还有本地 Profile 候选；Cloud 单独完成本功能不会让旧 ACPF 自动隐藏模型。

因此禁止：

1. 给现有 `/v1/registry/metadata/latest` envelope、payload 或 signature 增加字段或改 schema/domain。本需求进一步要求旧 release 记录也保持原状，生命周期完全独立。
2. 把 release.status 改成 `deprecated`，或通过 yank/revoke/删除快照条目实现过时。
3. 修改已经签名发布的 manifest、artifact、envelope、文件摘要或 Publisher 签名。
4. 仅因为过时而拒绝原 artifact、envelope、下载授权、依赖解析、安装或升级请求。
5. 新增所有客户端必须提供的 header、参数或鉴权步骤。
6. 将生命周期服务故障传播为原 Registry 搜索、推荐、下载接口的故障。

## 3. 数据模型

建议新增独立 Package 生命周期记录，不复用 release 发布状态列。

公共投影：

```json
{
  "packageId": "ai2apps/model-example",
  "state": "deprecated",
  "reason": "已有更新模型，建议新安装使用替代版本。",
  "replacementPackageId": "ai2apps/model-example-next",
  "revision": 3,
  "updatedAt": "2026-09-28T01:00:00Z"
}
```

约束：

- `state` 仅 `active`、`deprecated`，已有 Package 逻辑默认 active；不强制给历史表逐条回填。
- `reason` 为纯文本：deprecated 必填，去空白后 1–1000 字符；active 时公共原因置 null。
- `replacementPackageId` 可为 null；非 null 时必须是存在、公开、具有已发布版本且 active 的模型 Package，不得为自身。
- 按正式模型分类/Service 元数据判断模型 Package，兼容已有正式旧包分类，不依赖名称前缀猜测，不允许将普通 Runtime 当模型标记。
- 第一版替代项仅作为建议，不自动替换依赖、迁移模型或修改用户默认模型。
- 不允许形成替代关系环；若被推荐的替代 Package 后来要过时，管理操作须提示并在同一事务处理引用，不能留下“推荐安装已过时替代包”的关系。
- `revision` 按 Package 单调增加，用于并发控制；新建的未标记记录可表示 revision 0。
- 已标记后恢复 active 的记录必须保留并同步，不能通过删除记录表达恢复，避免客户端永久缓存 deprecated。
- 操作者、权限验证、内部备注及 before/after 审计属于管理数据，不能出现在公共投影。

## 4. 后台管理

在现有后台 Package 管理的模型详情/列表中增加：

- 状态：正常 / 已过时；列表可按此状态筛选。
- “标记过时”：输入原因，可选推荐替代 Package，提交前说明不停止已安装模型。
- “恢复正常”：确认恢复推荐资格；要求内部操作理由。
- 显示最后更新时间、操作者和变更历史（仅有权限的后台用户）。

写接口沿用现有管理员路由体系、管理员授权、二次验证及 Cookie/CSRF 防护。不要新增低权限 Publisher 写入口。具体后台 URL 由 Cloud 团队按现有规范确定，并在回执中提供。

建议逻辑请求：`state/reason/replacementPackageId/expectedRevision/auditReason`；拒绝并发旧 revision，返回 409，避免相互覆盖。支持项目已有的幂等机制，相同重试不产生重复状态变更。每次有效变更记录目标、操作者、时间、前后值、请求关联 ID；事务失败不得留下半完成状态。

## 5. 公共接口：旁路新增，不改变旧接口默认行为

### 5.1 新增签名生命周期快照（建议契约）

建议 `GET /v1/registry/package-lifecycle/latest`，认证要求不高于现有公共 Registry 元数据。此 URL 和以下 schema 是本需求提案，Cloud 如需调整，应在客户端实现前返回最终契约。

独立 envelope：

```json
{
  "schemaVersion": "ai2apps.package-lifecycle-envelope.v1",
  "payload": {
    "domain": "ai2apps.package-lifecycle.v1",
    "version": 12,
    "generatedAt": "2026-09-28T01:00:00Z",
    "expiresAt": "2026-09-29T01:00:00Z",
    "records": []
  },
  "signature": {
    "keyId": "<existing-repository-key-fingerprint>",
    "algorithm": "Ed25519",
    "value": "<base64url-signature>"
  }
}
```

- `records` 是所有曾有管理变更的公开模型 Package 的完整状态集，每条使用第 3 节公共投影；包含已恢复 active 的记录。同一快照不重复 packageId。
- 从未标记且不存在记录的 Package 逻辑默认 active；客户端无有效快照时应区分“未知”与已验证 active，不把网络失败解释为 deprecated。
- 此 `version` 是独立、持久化、全局单调递增的生命周期快照版本，不与旧 repository metadataVersion 混用；同一版本不得返回不同 payload。
- 建议复用现有受信任 repository signing key，但采用独立签名域，不能复用旧快照签名域。
- 签名输入提案：UTF-8 字节 `AI2APPS-PACKAGE-LIFECYCLE-V1\n` 后连接 `JCS(payload)`；signature.value 使用无 padding 的 base64url。Cloud 必须提供最终固定字节规则和测试向量供客户端联调。
- 不能通过降低验签强度、关闭指纹固定或允许版本回退实现兼容。
- 生命周期写入与快照发布采用原子事务或可靠 outbox：后台区分“已保存/已传播”，失败可重试，禁止显示成功却永久不发布。
- 状态变化后主动失效缓存；提供 ETag/304，建议最长公开缓存 60 秒，目标两分钟内可见。定期续签更新 expiresAt 时也增加版本。
- 不携带账户、安装、操作者或其他私密信息；不新增 Set-Cookie。可缓存完整快照，避免每个模型独立请求。

### 5.2 可选目录投影与过滤

旧客户端不传任何新参数时，以下接口响应结构、状态枚举、可见集合、推荐资格和排序规则保持原有语义，不因 deprecated 改变：

```text
GET /v1/registry/search
GET /v1/registry/recommendations
GET /v1/registry/packages/{namespace}/{name}/catalog
GET /v1/registry/packages/{namespace}/{name}
```

为新客户端显式增加可选参数（建议名称）：

- `includeLifecycle=true`：仅在公开 Package 投影上增加 `lifecycle` 对象，内容与签名快照一致；绝不写入 signed manifest 或旧 snapshot。
- 列表端点可选 `lifecycleState=active|deprecated|all`；省略为 all，保持旧行为。传入才启用过滤，过滤后计算分页和 total。
- 只传 includeLifecycle 不隐式过滤或降权。详情没有过滤含义，过时 Package 仍返回 200。
- 缓存 key 必须区分新参数，禁止将 opt-in 响应误缓存给旧请求。
- 新客户端可只依赖独立快照完成筛选；生命周期不得成为旧接口运行的前置依赖。

生命周期不得绕过原有可见性、授权、审核或撤销控制。deprecated 并不使原本不可见的 Package 公开。

## 6. 客户端职责与分阶段上线

Cloud 阶段只实现管理与契约，不宣称 ACPF 已隐藏或 Discover 已展示。

后续客户端负责：

- 验签、按 repository 身份隔离缓存、版本防回退；加载本地数据不能等待联网。
- ACPF 新候选、自动选型、手工 profileId、组合方案及确认安装统一应用过时策略。
- 已使用旧模型的工作流继续运行；不后台替换或卸载。已有任务不被追溯中止。
- Discover 标记与安装提醒、替代建议、中英文文案。
- 离线时使用最后已验证缓存并标识时效；过期生命周期提示不等于旧安装授权或签名失效豁免。没有缓存时不阻断已安装模型运行。

独立生命周期接口的 404/503/超时不应导致旧或新客户端的本地模型调用失败。新客户端在确认新安装时如何处理未知状态由客户端策略定义，但 Cloud 不得修改旧下载链路来强制执行。

## 7. 必须通过的验收

### 向后兼容门禁（发布阻断级）

使用当前已发布客户端/其未修改的验签与安装代码，不能仅用 Cloud 自己的新测试替代：

1. 标记前后，旧 snapshot schema 与字段集合不变；旧代码验签成功，release.status 仍为 published。
2. 未携带新参数的搜索、推荐、详情仍可发现同一过时 Package，原字段与类型保持不变。
3. 可安装、重新安装、更新、作为依赖解析该 Package；envelope、artifact 内容及摘要不变；原镜像、授权、断点下载流程不受影响。
4. 旧 ACPF 仍能按原方案安装，已安装模型继续使用。不得把“旧客户端看不懂标记”当作失败。
5. 新生命周期服务不可用/数据库新记录缺失/管理功能关闭时，旧 Registry API 不新增 5xx 或显著等待。
6. 不仅覆盖模型包，还回归 Runtime 与普通 App Package 的旧搜索、发布和安装。

### 新功能门禁

- active → deprecated → active 的完整流程；版本发布不重置标记。
- 非管理员、过期管理员验证、CSRF、普通 Publisher 写入被拒绝；公开接口不泄漏审计信息。
- 不存在/非模型/自引用/循环/已过时替代项被拒绝；并发 revision 冲突为 409。
- 新快照验签正确、域隔离、ETag/304、全量恢复状态、版本单调，坏签名测试不通过。
- opt-in 搜索/推荐过滤、计数、分页正确；详情可见；缓存不串用。
- 状态管理与签名发布失败恢复、重复请求、缓存传播均有测试。
- 同时保留原 yank/revoke 门禁，不因为 deprecated 可安装而放行被撤销的制品。

## 8. 迁移、回滚与交付回执

- 采用可增量部署的独立表/可选数据结构；默认行为不依赖记录存在。首次部署不自动标记任何真实 Package。
- 先部署后端与公共契约，再开放管理员入口；客户端之后上线。无需同步发布。
- 回滚管理 UI 或接口代码时保留生命周期记录、审计和已发布版本计数，不删除数据，不回退已签发快照版本。
- 可独立关闭新管理入口/投影，旧接口继续工作。撤销某次标记应发布更高版本的 active 状态，而不是回放旧快照。

请 Cloud 交付：

1. 最终 OpenAPI、后台入口、权限规则及与本提案的差异。
2. 状态数据样例、新快照样例、验签测试向量和准确签名字节规则（不含私钥）。
3. migrations、回滚操作、缓存策略与传播时限。
4. 当前旧客户端验签/搜索/推荐/安装回归证据，以及新增用例结果。
5. 部署环境、版本/提交、健康检查与新旧 API 探测结果；未验证项必须列明。

**禁止只回复“新增 API 已完成”就认为可发布；旧客户端兼容门禁全部通过后才可交付生产。**
