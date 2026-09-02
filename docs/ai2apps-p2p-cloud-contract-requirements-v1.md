# AI2Apps P2P 客户端剩余 Cloud 合同需求 V1

状态：仅阻塞 Direct QUIC；Messager v2 Relay 数据面合同已冻结  
日期：2026-08-31

## 已完成合同

- `PeerSession.peer.relayOrigin`：仅在 Session 允许 `relay_https` 时返回，Local 逐字使用。
- Model Share Relay HTTPS：路径、Grant、Manifest、SSE 和结算承诺已有版本化合同。
- Messager v2：Device Key、Session、Grant、Candidate 和 Relay Admission 控制面已有合同。

## 必须补齐：Direct QUIC v1

Cloud/shared-contract 项目必须冻结并提供：

1. ALPN 的精确 ASCII 值与 QUIC 版本集合；
2. Noise IK Prologue 的逐字节编码，包含 Session ID、Grant JTI、Purpose ID 和双方 Key Epoch；
3. Frame Header 的字段、大小端、最大长度、AEAD Additional Data 和流关闭语义；
4. 双向 Grant 刷新、重连、网络切换和 0-RTT 禁用规则；
5. 至少一组跨语言有效 Fixture，以及篡改 Header、Static Key、Epoch、JTI 的无效 Fixture。

合同发布前 Local 不会发送或监听 Direct QUIC；Session 只请求 `relay_https`。

## 已冻结：Messager v2 Relay 数据面

Cloud 的 `docs/messager-peer-v2-data-plane.md`、四个闭合 JSON Schema 和
`fixtures/messager-peer-v2/wire-vectors.json` 已冻结：

1. 每条逻辑消息使用一次 Noise IK Connection 和一条 ACK；
2. handshake/message 两个 HTTP 请求分别刷新并消费一个 holder-bound Grant/JTI；
3. `clientMessageId` 跨新握手重试保持不变，接收端 exact replay 返回 `duplicate`；
4. 密文发出后任何不确定结果都落为 `result_unknown`，不得降级或上传 Cloud 明文；
5. v1 只允许在 v2 密文发出前用于迁移期回退；
6. v2 当前只承载 4,000 字符/16 KiB 内的文本，媒体和附件需要后续独立合同。

Local 已实现协议域隔离、Relay 入口、一次性 Connection、Grant 防重放、消息幂等和 Pending
Session 轮询；生产 Feature 仍默认关闭，须完成双 Local 互通验收后再开启受控窗口。

## Provider Pilot 配置

Provider 默认关闭。只有以下变量完整且 `AI2APPS_MODEL_SHARE_PROVIDER_ENABLED=1` 时，Local
才会登记 Model Share Key、发布 Offer、轮询 SoftOffer、接受 Session 并调用本地文本模型：

Pilot 可使用受审 Model Worker Package 声明的 `llm`，也可使用其 `vlm` 的纯文本
conversation 入口。后者仍只接受冻结的文本 Manifest；图片、附件、URL 和任意文件路径
不会进入 Provider Worker。HF cache 中未安装为受审 Package 的模型仍不可发布 Offer。

- `AI2APPS_MODEL_SHARE_RATE_CARD_ID`
- `AI2APPS_MODEL_SHARE_RATE_CARD_VERSION`
- `AI2APPS_MODEL_SHARE_MODEL_ID`
- `AI2APPS_MODEL_SHARE_MODEL_REVISION`
- `AI2APPS_MODEL_SHARE_RUNTIME`（默认 `omlx`）
- `AI2APPS_MODEL_SHARE_MAX_CONCURRENCY`（默认 `1`）
- `AI2APPS_MODEL_SHARE_ESTIMATED_TPS`（默认 `1`）

配置不完整、模型未就绪或 Revision 不一致时不发布可用算力；入口保持 fail closed。
状态通过 `GET /v1/platform/model-share/provider` 读取，Key 登记通过已认证的
`POST /v1/platform/model-share/peer/register` 执行。

## Buyer Local API

已认证桌面客户端通过 `POST /v1/platform/model-share/inference` 发起一次完整的 Buyer 流程。
Local 负责生成不可重放的 Request Manifest、签名 Commitment、等待 Cloud 匹配与资金 Hold、
建立 `model_share_v1` Peer Session、校验 Provider SSE Result Manifest，并只在校验通过后提交
Delivery Receipt。响应使用 `text/event-stream`，透传协议事件；流建立后的失败以 `error` 事件返回。

请求采用严格字段集合：`modelId`、`modelRevision`、`runtime`、`expectedRateCardVersion`、
`maximumAmountMinor`、`estimatedInputTokens`、`maximumOutputTokens`、`prompt`、`systemPrompt`、
`temperature`。未知或缺失字段、布尔型伪装的整数、非有限温度和超限文本均在任何云端交易前拒绝。
请求内容、Prompt、模型输出、Grant 和私钥不写入 Local 日志。
