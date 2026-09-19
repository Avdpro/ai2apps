# AI2Apps Cloud ModelScope Package Range 兼容与 Checkpoint 验证边界需求 v1

日期：2026-09-17
状态：交付 Cloud 项目实施
需求方：AI2Apps Local / Package Registry / Checkpoint Distribution Registry
目标实现仓库：AI2Apps Cloud 项目

> 2026-09-17 更正：本文件关于兼容来源“必须由不同账号激活”“双人审批”的要求错误地
> 收紧了 Cloud 既有管理员自审合同，已由
> `ai2apps-cloud-modelscope-range-activation-policy-correction-v1.md` 废止。管理员完成
> step-up 后应继续可以激活自己登记的来源，并写入既有自审审计事件。Range、piece、完整
> SHA-256、不可变 URL 和 validation receipt 的其余要求保持有效。

## 1. 最终结论

本次 Cloud 改动只需要解决 **Package 外部制品源** 的 ModelScope Range 兼容问题。

Checkpoint Distribution 不需要 Cloud 逐文件执行 Range 下载、piece hash 或完整 SHA-256
复验。Cloud 对 Checkpoint 的职责应限制为：

1. 验证 Publisher 签名和 Publisher/key 身份；
2. 验证 manifest 结构、文件大小、SHA-256、piece hashes 的格式和内部一致性；
3. 验证 Hugging Face / ModelScope source 使用不可变 revision，路径合法且 Provider 在 allowlist；
4. 保存并审核发布构建工具提交的 verification receipt；
5. 发布不可变 envelope 和签名 Checkpoint Index。

Checkpoint 文件的真实字节完整性由两层保证：

- 发布构建工具在上传完成后，对 HF/MS 两个不可变来源做匿名验证并生成收据；
- Local/Desktop 下载器按签名 manifest 的 size、piece hashes 和完整 SHA-256 验证实际下载内容。

ModelScope 的 `200 + Content-Range` 兼容在 Checkpoint 链路中属于 **Local/Desktop 下载器**
职责，不属于 Cloud Registry 的内容验证职责。

## 2. 三类资源的职责划分

| 资源 | Cloud 必须验证 | 字节完整性验证者 | Cloud 是否处理 `200 + Content-Range` |
| --- | --- | --- | --- |
| Package 外部 source，例如 Runtime `.ai2service` | source 可访问、Range 行为、size、piece hashes、完整 SHA-256 | Cloud 发布预检 + 客户端安装校验 | **是** |
| Checkpoint Distribution 外部文件 | 签名、manifest、不可变 source 声明和构建收据 | 发布构建工具 + Local/Desktop | **否** |
| Cloud 自己托管或代理的制品 | Cloud 自己保证存储与协议 | Cloud + 客户端 | 不适用；Cloud 必须标准返回 `206` |

本次不得把 Package source verifier 的完整下载规则套到 Checkpoint Registry，也不得因为
Checkpoint 使用 ModelScope 而让 Cloud 下载数十或数百 GB 模型文件。

## 3. 为什么 Package source 仍需要 Cloud 完整预检

Package Registry 当前会把通过审核的外部 source 标记为 `active`，并把它写入 Cloud 签名的
Repository Snapshot。按照现有合同，`active` 不只是“URL 存在”，而是表示 Cloud 已确认：

- URL 指向这个 Package 版本的精确制品；
- size 与 Release 声明一致；
- piece manifest 一致，可以断点续传和并行下载；
- 完整 SHA-256 一致；
- Range 能力足以支持当前安装器；
- source 可以作为 Cloud 源之外的正式安装来源。

Runtime Package 通常只有一个几百 MB 的 `.ai2service` 文件，这项验证只在注册或重新验证 source
时执行一次，成本可控。保留完整预检还能防止以下问题进入签名 Snapshot：

- URL 存在但指向错误版本；
- 上传未完成或文件被截断；
- Provider 元数据正确但实际下载字节错误；
- Range 请求返回整个文件，导致安装器并发下载放大流量；
- source 可访问但 piece manifest 不匹配。

Cloud 也可以从产品设计上把 `active` 降级为“仅确认存在”，但这会改变 Package Registry 既有
合同、审批语义和客户端对 active source 的预期，不建议为了本次 ModelScope 状态码问题进行这种
迁移。

## 4. 为什么 Checkpoint 不需要 Cloud 完整验证

Checkpoint 与 Package 的分发模型不同：

- 一个 Checkpoint 可能包含几十到几百个文件，总量达到数十或数百 GB；
- Cloud 不代理、不保存也不重新打包这些模型文件；
- Publisher 签名 manifest 已固定每个文件的路径、size、SHA-256 和 piece hashes；
- 发布构建工具已经位于上传和镜像流程中，适合执行双源完整校验；
- Local/Desktop 无论从 HF 还是 MS 下载，最终都必须按同一签名 manifest 校验；
- Cloud 再下载一次不会增加新的信任根，只会重复构建端和客户端已经完成的工作。

因此 Cloud 对 Checkpoint 的安全边界是“验证谁发布了什么不可变声明”，而不是“亲自重新下载
所有模型字节”。

当前 Cloud 不需要访问 Checkpoint source。路径拼错、revision 不存在或上传遗漏由发布构建工具
在提交前发现，并写入 verification receipt；Local/Desktop 下载时再次按签名 manifest 验证。

## 5. Package ModelScope 问题与复现

Runtime 1.7.0 的 ModelScope Git LFS 对象会正确执行单段 Range，却使用 HTTP `200` 而不是
标准 `206`：

```text
repository: ai2apps/desktop-releases
revision: 18751703b53671cb2db926f9f8ed508a70df15b0
path: ai2apps-runtime-omlx-1.7.0-production.ai2service
size: 373748488
sha256: b066700dcebec87012e93de01e6114db9f231b0a1c89642e97c50cd91a1ec3a7
```

匿名复现：

```bash
curl -sS -D - -o /dev/null \
  -H 'Range: bytes=0-4095' \
  -H 'Accept-Encoding: identity' \
  'https://modelscope.cn/models/ai2apps/desktop-releases/resolve/18751703b53671cb2db926f9f8ed508a70df15b0/ai2apps-runtime-omlx-1.7.0-production.ai2service'
```

当前响应：

```text
HTTP/1.1 200 OK
Content-Length: 4096
Accept-Ranges: bytes
Content-Range: bytes 0-4095/373748488
```

首段、中段和末段均已确认是本地正式制品的精确字节。相同 LFS OID 改名后重新提交仍保持该
行为。ModelScope 官方问题：<https://github.com/modelscope/modelscope_hub/issues/50>。

历史 Runtime 1.6.2 会跳转到 LFS CDN 并标准返回 `206`。同一 SSD Checkpoint 仓库中也观察到
一部分对象返回 `206`、另一部分对象返回 `200 + Content-Range`，说明该行为与具体 LFS 对象
交付映射有关，并非整个 Provider 或仓库的统一属性。

## 6. Cloud Package verifier 必须支持的严格兼容规则

设请求为：

```text
Range: bytes=S-E
T = Release 中声明的完整 artifact size
L = E - S + 1
```

### 6.1 可接受的状态

- HTTP `206`：标准单区间响应；
- HTTP `200`：仅允许进入受限 ModelScope 兼容路径；
- 其他状态：不得作为 Range 成功；
- `416` 可以用于诊断范围或 size 冲突，但不能计为成功。

HTTP `200` 不是单独的成功条件。它必须满足以下所有检查。

### 6.2 `Content-Range`

两种状态都必须有且只有一个：

```text
Content-Range: bytes S-E/T
```

要求：

- unit 精确为 `bytes`；
- start/end 精确等于请求的 `S/E`；
- total 精确等于 Release artifact size `T`；
- `0 <= S <= E < T`；
- 禁止 wildcard、未知 total、多段值、逗号拼接、重复 header、obs-fold；
- 禁止 `multipart/byteranges`。

`200` 若没有精确 `Content-Range`，必须立即拒绝。不能根据 `Content-Length` 猜测它可能是
切片，也不能继续下载来判断它是不是完整文件。

### 6.3 长度、编码与响应体

- 请求固定发送 `Accept-Encoding: identity`；
- `Content-Encoding` 只能缺失或为 `identity`；
- `Content-Length` 必须存在且精确等于 `L`；
- 实际 body 必须精确为 `L`；
- 流式读取设置 `L + 1` 硬上限：
  - 少于 `L`：`range_body_short`；
  - 读到第 `L + 1` 字节：立即中止并返回 `range_body_excess`；
- gzip、br、deflate、multipart 以及冲突的长度/传输编码必须拒绝；
- 不得把整个未知长度响应先下载到内存或磁盘后再判断。

### 6.4 适用来源

第一版 HTTP `200` 兼容只对同时满足以下条件的 Package source 开启：

- provider 明确为 ModelScope；
- URL host 在现有精确 allowlist 中；
- repository、40 位 immutable revision 和 path 已登记在 Release source；
- revision 不是 `main`、`master`、`latest`、`head` 或别名；
- URL 不含 userinfo、调用方凭据或临时签名；
- 每次重定向仍通过现有 scheme、host、端口、DNS、私网 IP 和次数限制；
- 最终响应通过本节所有检查。

不得把 `status in (200, 206)` 作为通用判断，也不得把该兼容开放给任意外部 source。

### 6.5 共同原语

建议 Package source verifier 使用一个严格单区间原语：

```text
validate_single_range(response, S, E, T, source):
    L = E - S + 1

    if response.status == 206:
        mode = "http-206"
    else if response.status == 200 and source is eligible_modelscope_package_source:
        mode = "http-200-content-range"
    else:
        reject range_status_unsupported

    require exactly_one_content_range == ("bytes", S, E, T)
    require content_length == L
    require content_encoding in {absent, "identity"}
    require content_type is not multipart/byteranges

    body = read_at_most(L + 1)
    require len(body) == L
    return body, mode
```

## 7. Package HEAD 与完整预检

现有 HEAD 回退流程保留：

1. source 先通过 URL、allowlist、immutable revision、DNS/SSRF 校验；
2. 发送现有 `HEAD`；
3. HEAD 有明确、合法 `Content-Length` 时，必须等于 Release size；
4. HEAD 明确长度不一致时立即 `size_mismatch`，不得通过 Range 掩盖；
5. HEAD 成功但缺少长度时，发送：

   ```http
   GET <immutable-source-url>
   Range: bytes=0-0
   Accept-Encoding: identity
   ```

6. 单字节响应可为标准 `206`，或符合第 6 节的 ModelScope 严格兼容 `200`；
7. 探针通过后继续现有首段、中段、末段、全部 piece SHA-256、完整 size 和完整 SHA-256
   预检；
8. 每个 piece response 都独立执行第 6 节判断，因为同一对象的交付路径可能变化；
9. 不发送 synthetic `If-Range`。

本文件仅在严格谓词成立时，替代
`ai2apps-cloud-modelscope-package-head-fallback-requirements-v1.md` 中“不接受 `200` 作为
Range 成功”的旧规则。旧文档其他安全、完整性、审批和激活要求继续有效。

## 8. Package validation receipt 与错误码

建议 Package 内部 validation receipt 增加以下可选字段：

```json
{
  "rangeTransportModes": ["http-200-content-range"],
  "rangeCompatibility": "modelscope-content-range-200",
  "rangeResponseCountByMode": {
    "http-206": 0,
    "http-200-content-range": 92
  },
  "observedOriginHosts": ["modelscope.cn"]
}
```

`rangeCompatibility` 可为：

- `standard`：只观察到 `206`；
- `modelscope-content-range-200`：只观察到严格兼容响应；
- `mixed`：两种模式都出现。

receipt 只记录规范化 host，不记录临时 redirect query、签名、Cookie 或 Authorization。

validation digest 应绑定 source identity、immutable revision、artifact size/SHA、piece manifest
digest、兼容策略版本和 receipt 摘要。规则版本或 source 变化后不能复用旧 validation 激活。

至少提供以下错误码：

| 错误码 | 含义 |
| --- | --- |
| `range_status_unsupported` | 状态不是允许的标准/兼容状态 |
| `range_source_not_eligible` | `200` source 不满足受限 ModelScope 条件 |
| `content_range_missing` | 缺少 `Content-Range` |
| `content_range_malformed` | 格式非法、重复、多段或 wildcard |
| `content_range_mismatch` | start/end 不匹配 |
| `range_total_mismatch` | total 与 Release size 不匹配 |
| `range_length_mismatch` | `Content-Length` 不匹配 |
| `range_body_short` | body 少于请求长度 |
| `range_body_excess` | body 超过请求长度并已中止 |
| `content_encoding_invalid` | 收到压缩或其他编码 |
| `range_multipart_rejected` | 收到 multipart/multi-range |

不要再把“正确切片但返回 `200`”误报为 `size_mismatch`。

## 9. Checkpoint Distribution 的 Cloud 最低验证

### 9.1 必须执行

Cloud 必须继续执行现有 Registry 信任和结构验证：

- Publisher Ed25519 签名；
- Publisher、key、namespace 和 key 状态；
- manifest digest 与签名正文；
- distribution ID、model ID、repo ID 和 HF commit；
- 文件路径安全、唯一；
- size、SHA-256、piece size、piece count、piece hashes 的格式和内部一致性；
- `estimatedSizeBytes` 与文件 size 总和一致；
- source provider 在 allowlist；
- HF/MS revision 不可变；
- redistribution、license、P2P 和审核政策；
- verification receipt 的 builder、文件数、piece 数、总大小和已验证 Provider 字段；
- submission、review、publication、yank/revoke、审计和签名 Index 状态机。

### 9.2 不新增 Cloud source 网络验证

本次保持当前生产行为：Cloud 接受并审核 Publisher 签名 envelope 和发布构建工具生成的 receipt，
不主动请求 HF/MS repository tree、file metadata、HEAD、Range 或文件 body。

如果未来产品需要 Cloud 持续监控外部 Checkpoint 是否仍然存在，应作为独立的异步健康监控需求
实施，不能混入 Registry 发布事务，也不能改变 Publisher 签名 envelope 的内容身份。

### 9.3 Cloud 明确不执行

Checkpoint Registry 不应：

- 对每个文件做 Range 能力探针；
- 下载每个 piece；
- 重算每个文件或整个模型的 SHA-256；
- 执行第二次完整 HF/MS 双源下载；
- 因为某个 Checkpoint 对象返回 `200 + Content-Range` 而拒绝 distribution；
- 把 Checkpoint source 标记为 Cloud 已验证 `rangeSupported=true`；
- 修改已发布的 Publisher 签名 envelope 来记录动态传输状态。

完整双源验证属于 `checkpoint-metadata-verified-v1` / `checkpoint-full-dual-download-v1` 发布构建
流程及其收据。Cloud 审核收据，但不重复构建机的字节工作。

### 9.4 未来可选健康监控（不属于本次需求）

Cloud 日后可以异步监控已发布 Checkpoint source 是否仍存在。该监控应：

- 只检查固定 revision/path 的存在性；
- 与 Publisher 签名 envelope 分离；
- 不因一次超时自动修改不可变 distribution；
- 持续失败时生成告警或管理员审计事件；
- 不向客户端宣称未经客户端实际验证的 Range 或内容能力。

## 10. Checkpoint `200 + Content-Range` 的正确处理位置

当前 Local 代码仍严格要求 `206`：

- Package 安装路径：`ai2apps/packages/registry.py`；
- Checkpoint 下载路径：`ai2apps/checkpoint_distribution.py`。

客户端后续应在两个路径中实现与第 6 节同等严格的单区间判断。对 Checkpoint 而言：

- source 来自已验证的 Publisher-signed manifest；
- URL 必须是固定 revision；
- `200` 仅对 ModelScope allowlist 启用；
- `Content-Range`、长度、identity 和 body 必须精确；
- 每个 piece 仍按 manifest hash 验证；
- 文件完成后仍验证完整 SHA-256；
- 普通 `200` 全文件响应必须在 piece 长度 `+1` 处中止。

这项客户端修改不属于本次 Cloud 实现，但 Package ModelScope source 的生产激活依赖包含该能力
的客户端版本。

## 11. Cloud 自动化测试

### 11.1 Package Range 兼容

1. `206` + 精确 Content-Range/length/body：通过；
2. 受限 ModelScope `200` + 精确 Content-Range/length/body：通过；
3. 非 ModelScope source 的同样 `200`：拒绝；
4. `200` 无 Content-Range：立即拒绝；
5. `200` 返回完整对象：读取到请求长度 `+1` 时中止并拒绝；
6. start、end、total 任一不一致：拒绝；
7. 缺失、重复、multi-range、wildcard 或非法 Content-Range：拒绝；
8. Content-Length 缺失或不匹配：拒绝；
9. body short/excess：拒绝；
10. gzip/br/deflate/multipart：拒绝；
11. 同一验证中合格 `206` 和严格兼容 `200` 混合：通过并记录 `mixed`；
12. verifier 不发送 `If-Range`；
13. piece hash 或完整 SHA 不匹配：拒绝；
14. GitHub、Runtime 1.6.2 ModelScope CDN 和 Cloud 自有 `206` 无回归；
15. 注册人与激活人相同仍拒绝。

### 11.2 Checkpoint 边界

1. Cloud 验证签名、manifest 和 receipt，但测试中不得触发文件 body 下载；
2. revision 为 branch/latest：拒绝；
3. ModelScope 文件即使实际 Range 状态为 `200`，只要签名/manifest 合法，Cloud
   不因此拒绝；
4. 已发布 envelope 和 Checkpoint Index 签名语义不变；
5. HTTP mock 断言 Cloud 没有对 Checkpoint 文件发送 Range 或下载 body；
6. HTTP mock 还应断言 Cloud 不请求 Checkpoint repository tree 或 file metadata。

### 11.3 网络安全

Package verifier 要覆盖：未允许 host、HTTP 降级、超限重定向、带凭据 URL、私网 IP、DNS
rebinding、跨 host 敏感 header、临时 URL 泄漏和超时。Checkpoint Registry 不发出网络请求，
只对 source URL/repository/revision/path 做结构和 allowlist 校验。

## 12. Runtime 1.7.0 生产复验

Cloud 部署后使用标准 Package source validation 重新验证：

```text
repository: ai2apps/desktop-releases
revision: 18751703b53671cb2db926f9f8ed508a70df15b0
path: ai2apps-runtime-omlx-1.7.0-production.ai2service
size: 373748488
sha256: b066700dcebec87012e93de01e6114db9f231b0a1c89642e97c50cd91a1ec3a7
```

验收：

- HEAD/单字节探针通过；
- 首段、中段、末段和全部 piece 通过；
- 完整 size/SHA-256 通过；
- `rangeSupported=true`；
- receipt 记录 `http-200-content-range`；
- validation digest 绑定新兼容策略版本；
- source 进入现有 `pending_approval`，不会自动激活。

同时回归标准 CDN-backed `206` 对象：

```text
repository: ai2apps/desktop-releases
revision: 97e28e20e9c420e50297d8891b2d1f4e2cb111d9
path: ai2apps-runtime-omlx-1.6.2-production.ai2service
size: 376086471
sha256: 040bdf2e5bc32fed203bbc695d5bd34ebd5e514a70a7b38dd8a97f0cdc28943a
```

七个 SSD Checkpoint 仓库不需要 Cloud 执行 source 存在性、Range 或重新下载验证；继续使用发布
构建工具已有的双源验证收据。

## 13. 上线顺序

1. Cloud 实现 Package source 的严格 `200 + Content-Range` 兼容；
2. Cloud 部署并重新验证 Runtime 1.7.0 ModelScope source；
3. source 保持 `pending_approval`，暂不对旧客户端激活；
4. Local/Desktop 在 Package 和 Checkpoint 下载器中实现相同严格兼容；
5. 完成真实 ModelScope 单源、断点恢复、并行 piece、完整 SHA 和 HF 回退验收；
6. 发布兼容客户端；
7. 再由不同于注册人的 reviewer/admin 激活 Runtime 1.7.0 ModelScope source；
8. 匿名回读 Repository Snapshot，验证签名和 source 状态。

Checkpoint Distribution envelope 无需重发。客户端升级后可以直接使用原有 immutable
ModelScope source；旧客户端继续回退 Hugging Face。

## 14. Cloud 交付物

Cloud 项目应提供：

1. Package strict single-range 实现提交；
2. 自动化测试命令与结果；
3. OpenAPI/镜像版本和部署时间；
4. Runtime 1.7.0 validation ID、receipt 摘要和状态；
5. Runtime 1.6.2、GitHub 和 Cloud `206` 回归证据；
6. Checkpoint 路径没有下载文件 body 的测试证据；
7. SSRF、响应体上限、重定向和日志脱敏测试；
8. 等待客户端版本后才能激活的 Package source 列表。

## 15. 验收标准

- 只有 Package 外部 source verifier 增加 ModelScope `200 + Content-Range` 兼容；
- 兼容 `200` 必须通过精确 Content-Range、length、identity、body 和完整 hash；
- 普通 `200`、全文件响应、多段、压缩、非 allowlist source 全部拒绝；
- Package 的 piece hash、完整 SHA、双人审批和签名 Snapshot 不降低；
- Checkpoint Cloud 路径只验证签名、结构、不可变 source 声明和构建收据；
- Cloud 不对 Checkpoint 执行 Range、piece 下载、完整 SHA 或双源重下载；
- Checkpoint 最终字节仍由发布构建工具和 Local/Desktop 两端校验；
- Runtime 1.7.0 真实 Package validation 通过；
- Runtime 1.6.2、GitHub 与 Cloud 标准 `206` 无回归；
- 兼容客户端发布前，Runtime 1.7.0 ModelScope Package source 不提前激活；
- 交付记录不包含 token、Cookie、临时 CDN 签名、浏览器 profile 或管理员凭据。
