# AI2Apps 条件式 Checkpoint 再分发契约需求 v1

日期：2026-08-27  
状态：Client 与 Cloud 已实现并通过测试；Fish S2 Pro 与 Ideogram 4 distribution 已发布

## 背景

Checkpoint Distribution v1 当前只允许：

- `redistributionPolicy: allowed`
- `redistributionPolicy: prohibited`
- `redistributionPolicy: unknown`

这三种状态无法准确表达“允许再分发，但接收方必须收到许可证、接受相同或更严格条款、
保留指定署名，且商业使用需要另行授权”的模型许可证。把这类 checkpoint 标成
`allowed` 会丢失法律条件；标成 `prohibited` 又与许可证明确授予的再分发权不符。

本次确认的两个阻塞项：

| Distribution | 使用限制 | 再分发条件 |
| --- | --- | --- |
| Fish Audio S2 Pro BF16 | 研究/非商业；商业使用需要 Fish Audio 书面许可 | 交付许可证、保留指定 Notice、产品界面或文档展示 “Built with Fish Audio” |
| Ideogram 4 FP8 | 仅非商业；其他用途需要 Ideogram 单独授权 | 下游条款不得更宽松、交付许可证、保留指定 Notice、修改文件需标记 |

两份许可证均明确允许满足条件后的再分发，因此需要正式扩展 Registry 契约，不应使用
宽松映射或发布侧例外。

## 契约扩展

### 1. 新增 policy

在 Checkpoint Distribution manifest v1 的 `license.redistributionPolicy` 中新增：

```json
"redistributionPolicy": "conditional"
```

已有三个值保持原语义和向后兼容。旧客户端遇到未知 policy 必须 fail closed，不得开始
下载或 P2P 分享。

### 2. 新增结构化条件

当 policy 为 `conditional` 时，`license.redistributionConditions` 必须存在：

```json
{
  "termsAcceptance": "required",
  "licenseDelivery": "required",
  "downstreamTerms": "same_or_more_restrictive",
  "commercialUse": "separate_license_required",
  "attribution": {
    "required": true,
    "noticeText": "Exact upstream-required attribution text",
    "noticeFile": "NOTICE",
    "productDisplay": "required"
  },
  "modifiedFilesNotice": "required"
}
```

字段规则：

- `termsAcceptance`: `required | not_required`；
- `licenseDelivery`: `required | not_required`；
- `downstreamTerms`: `same_or_more_restrictive | license_terms`；
- `commercialUse`: `allowed | prohibited | separate_license_required`；
- `attribution.noticeText` 必须逐字进入签名 manifest；
- `productDisplay`: `required | not_required`；
- `modifiedFilesNotice`: `required | not_required`。

### 3. 新增下载确认契约

当 policy 为 `conditional` 时，`license.downloadConsent` 也必须进入签名 manifest：

```json
{
  "required": true,
  "attestationText": "I confirm that I accepted the license terms or obtained the required separate license.",
  "acceptanceOptions": [
    "accepted_license_terms",
    "obtained_separate_license"
  ]
}
```

`acceptanceOptions` 只能使用以上两个值，并可按具体许可证只开放其中一个。客户端提交的
确认必须精确绑定：

```json
{
  "distributionId": "dist_...",
  "manifestDigest": "sha256:...",
  "termsHash": "sha256:...",
  "decision": "accepted_license_terms",
  "confirmed": true
}
```

任何 distribution、manifest 或条款 hash 不一致均视为未确认，不能沿用旧确认。

`termsUrl` 和 `termsHash` 继续必填，并绑定本次签名时采用的确切许可证文本。可选
`termsText` 用于在客户端内完整展示；若存在，其 SHA-256 必须等于 `termsHash`，大小上限
64 KiB。没有内嵌文本时，客户端必须展示固定 URL 和 hash，并要求用户先打开并阅读完整
条款。Cloud 不得把 URL 当前内容重新解释为签名内容，也不得修改 Publisher 提交的条件
或确认对象。

## Cloud 端要求

1. OpenAPI、数据库 JSON 校验和发布审核器接受 `conditional`、完整条件对象及
   `downloadConsent`；
2. `conditional` 缺字段、出现未知枚举、空署名/确认文本或非法 acceptance option 时拒绝
   submission；
3. Checkpoint Index 与单条 envelope 公网端点原样返回签名 JSON；
4. 审核界面明确展示使用限制、再分发条件、terms hash 和 Publisher；
5. `conditional` distribution 默认禁止 P2P 出传，直到 P2P 协议能够携带并验证接收方
   条款接受收据；
6. Cloud 不替 Publisher 判断用户是否具有商业许可证。若 Cloud API 接收用户确认，则必须
   保存并可审计绑定 account/installation、manifest digest、terms hash、decision 和时间的
   收据；当前本地 ACPF 收据由 Client 持久化；
7. 不允许服务端把 `conditional` 自动降级成 `allowed`。

建议 OpenAPI 从 `1.23.0` 升级到下一兼容小版本，并保持历史 Index v8 记录完全不变。

## Client / Local 端要求

Client 已实现以下统一门禁。门禁位于 `CheckpointAcquisitionService`，发生在 cache 命中、
本地导入、源探测、HTTP range 请求以及任何 checkpoint 字节读取之前，因此不能通过
Models App、ACPF、HF cache 或重试路径绕过。

下载前必须：

1. 校验签名 envelope、`termsHash` 和条件对象；
2. 展示许可证名称、固定条款链接、用途限制和完整署名要求；
3. 由用户选择“接受当前条款”或“已取得单独许可”，再勾选签名 manifest 中的明确声明；
4. 确认对象绑定 `distributionId + manifestDigest + termsHash + decision + confirmed`；ACPF
   另将 actor、installation 和 acceptedAt 写入 session operation 作为持久收据；
5. 把许可证文本或可离线验证的固定副本，以及规定的 `NOTICE`，随 checkpoint metadata
   落盘；
6. 未接受、收据失效或客户端不理解条件时 fail closed；
7. Package audit 和调用前用途门禁继续执行商业许可限制；仅接受下载条款不等于取得商业
   使用授权。

Models App 在创建下载 task 前返回结构化 409 challenge，展示许可后携带确认重试；ACPF 在
真正需要 checkpoint 时回到 `awaiting_confirmation`，确认后恢复 provisioning。两条路径
均不得在确认前读取 checkpoint 内容。

卸载 checkpoint 时可删除本地副本，但审计收据应按账户安全与隐私保留策略处理。

## Builder 与测试要求

- Builder 支持生成和解析 `conditional`，但不得自动推断条件；条件必须来自人工审计过的
  许可证映射；
- `redistributionPolicy=conditional` 时强制结构校验；其他 policy 不允许携带会造成歧义的
  条件对象；
- 增加 canonical JSON、签名、未知字段/枚举、旧客户端 fail-closed、manifest-bound 条款
  确认、确认发生前零 checkpoint I/O、ACPF 收据、P2P 禁止和许可证落盘测试；
- Cloud 发布测试应覆盖 submit、review、publish、签名 Index 以及无 Cookie 公网回读。

## 本批次恢复条件

Cloud 生产 OpenAPI `1.25.0` 已于 2026-08-27 部署上述契约，Client 目标测试亦已通过。
以下 distribution 已使用正式 Builder 生成签名 envelope，并完成提交、审核、发布和无 Cookie
公网回读：

- `dist_ai2apps_fish_s2_pro_bf16_eccd57bf_v1`
- `dist_ai2apps_ideogram4_fp8_bbee2ab2_v1`

恢复时沿用已固定的 HF/MS revision、文件清单和许可证 hash，重新使用正式 Builder 生成
envelope；不得手工修改当前失败的 envelope 或改用 `allowed`。
