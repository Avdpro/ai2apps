# AI2Apps 系统级 Peer Transport 技术与开发方案 V1

状态：C0/C1 Local 基座实施中（2026-08-31）

日期：2026-08-27

主实现仓库：`omlx-moe-cache`

相关文档：

- [Account 与 Messager 开发方案](ai2apps-account-messager-development-plan-v1.md)
- [P2P 模型分发与模型推理能力分享规划](ai2apps-p2p-model-distribution-capability-sharing-plan-v1.md)
- [Messager Local E2EE Cloud 合同](messager-local-e2ee-cloud-contract-v1.md)
- [Cloud Peer Session Broker 变更需求](cloud-system-peer-session-broker-requirements-v1.md)

## 1. 结论与优先级

> 2026-08-31 合同校准：Cloud `p2p-model-share-client-integration-v1` 是当前实现权威。
> Direct QUIC 的字节级 ALPN/Noise/Frame 合同尚未冻结，Peer Session 也尚未投影通用
> Relay Origin。因此当前实现只落地协议身份、Broker、Grant、Session/Replay、Model Share
> HTTP/SSE 语义和受控 Relay Adapter；不得按本文早期设想自行实现 Direct QUIC，也不得从
> Device 公网资料猜测 Relay Origin。Messager v1 在 v2 数据合同冻结前继续作为生产基线。

AI2Apps 应建设由 Local Runtime 持有的系统级 `PeerTransportCore`。Messager、Model Share 和
Checkpoint 分别作为独立应用协议接入，共享 Device 身份、连接探测、安全会话、多路流、分块、
背压和恢复，但不共享业务授权、密钥域、历史、存储或结算。

对 Messager 和 Model Share，传输路径必须对 App 和业务调用方透明。App 始终调用同一个 Local
API；`PeerTransportCore` 自动执行 `Direct P2P → FRP C/S`，不能因为打洞失败就向业务报错，
也不能要求用户重新提交消息或模型请求。只有目标 Device/Provider 经 Direct 和 FRP 都不可达，
且 Model Share 无法重新撮合其他 Provider 时，模型调用才返回不可用；Messager 则进入现有
Cloud Offline 消息机制。

Transport 切换也不能改变已确认的模型价格、结算资产、优先级或 Provider 收入算法。FRP 成本
应计入平台统一 Rate Card/平台费和容量规划，不能在 Direct 失败后临时弹出另一份报价。

| 优先级 | 能力 | 首个交付结果 |
| --- | --- | --- |
| P0 | Messager 信息/文件 | 现有 E2EE 文本不回归；单文件分块、恢复、确认；随后开放多附件 |
| P0 | P2P 模型推理 | 固定模型、审核节点、文本输入、流式文本输出、Points-only Pilot |
| P2 | P2P Checkpoint | 先保留 Source Adapter；MS/HF 双源稳定且达到门槛后再启用 |

实施顺序必须是：冻结现有 Messager 基线 → 抽取 Core → Messager 文件 → Direct QUIC →
Model Share 文本 Pilot → 媒体和长任务 → Checkpoint P2P Pilot。不要并行复制三套传输实现。

## 2. 当前基础与缺口

现有代码和生产验收已经具备：

- Cloud Device、Installation、User、好友关系和短期 Peer Assertion 绑定；
- Ed25519 身份 key、X25519 static key、Noise IK、Key Rotation 和 Replay Protection；
- HTTPS/FRP 精确 Device Origin；
- E2EE 文本、加密 ACK、本地账本、幂等和 `result_unknown`；
- 正文发送前的 Cloud Offline fallback；
- 生产双向消息、离线回退、密钥轮换和隐私审计记录。

当前还不是系统级 P2P：

- `MessagerPeerService` 混合授权、连接、加密、HTTP 和业务落库；
- 每条文本建立一次 Noise 会话，只传一个应用帧；
- 实际路径是 HTTPS + FRP，不支持 LAN、IPv6 或 UDP 打洞直连；
- 没有 Stream、Chunk、背压、暂停、恢复、持久 Transfer 或大对象临时目录；
- 图片仍走 Cloud Offline，任意文件不支持；
- Model Worker 和 Checkpoint Downloader 没有共用 Peer Data Plane；
- Local Messager 文件目前仍是工作区未跟踪/未提交基线，干净 checkout 不能完整重建。

## 3. 范围与非目标

V1 支持两个 AI2Apps Local Device 之间的认证连接、FRP 兼容路径、Direct QUIC、短消息、多路流、
分块对象、恢复和取消；承载 Messager 内容、Model Share 推理和未来 Checkpoint Piece。

V1 明确不做：

- 分享 MCP、Agent、Service、Tool、Terminal、Secret、浏览器控制或任意进程；
- 让网页持有 Peer Device 私钥或直接作为公共 Peer；
- 用 System Message 传 Candidate、高频进度或正文；
- 把 Direct/FRP 路径选择暴露成 App 必须处理的业务分支；
- 公共 DHT、匿名网络、任意文件做种和无许可 Checkpoint 分发；
- Gas/Cash；首个 Model Share Pilot 只使用 Points。

## 4. 总体架构

```text
MessagerService       ModelSharingService       CheckpointAcquisitionService
        |                     |                              |
        +---------- Application Protocol Adapters ----------+
                              |
                      PeerTransportCore
      +-----------------------+-----------------------+
      |                       |                       |
PeerIdentity            SecureSession          ObjectTransfer
GrantVerifier           ProtocolMux            ResumeStore
ReplayStore             FlowControl            QuotaManager
      |                       |                       |
      +--------------- Transport Adapter ------------+
                  |                         |
        DirectQuicTransport          RelayHttpsTransport
        LAN/IPv6/STUN/UDP             现有 FRP 兼容路径
                  \                         /
                   PeerSessionBroker / Cloud
       Presence、Candidate、短期 Grant、System Message、策略
```

Cloud 是控制面。Local 是私钥、明文、文件、模型执行和资源准入的最终权威。

## 5. Core 模块

### 5.1 `PeerIdentity`

- 管理 Device Ed25519 身份签名根；
- 为每个应用协议登记和轮换独立 X25519 static key；
- 验证 Cloud Assertion/Grant，并绑定 User、Device、Installation、Access Epoch、Key Epoch；
- 私钥只进入命名隔离的 SecretBackend。

协议域冻结为：

```text
ai2apps/messager-peer/v2
ai2apps/model-share-peer/v1
ai2apps/checkpoint-peer/v1
```

现有 `ai2apps-messager-peer-v1` 在迁移期保留。新协议不得复用 v1 Audience、Noise Prologue、
HKDF Context 或 X25519 key。可以共享 Ed25519 Device 身份根。

### 5.2 `PeerSessionBrokerClient`

- 创建带 TTL 的 `PeerSessionIntent`；
- 获取 purpose-bound `MessageGrant`、`JobGrant` 或 `DownloadGrant`；
- 交换 LAN、IPv6、Server Reflexive 和受控端口映射 Candidate；
- 报告粗粒度路径结果，不上传正文或 Candidate 到普通审计；
- 订阅 Presence 和低频 System Message。

Candidate 和 QUIC token 必须进入短时 Broker，不能进入普通 System Inbox。

### 5.3 `ConnectivityManager`

按并行竞速选择第一条通过认证 Probe 的路径：

1. 同一主机 loopback/Unix-domain fast path；
2. LAN 私有地址；
3. Global IPv6；
4. STUN Server Reflexive Candidate + 同步 UDP 打洞；
5. 用户允许时的 PCP/NAT-PMP/UPnP 受控映射；
6. 按业务策略使用 HTTPS/FRP Relay；
7. 换候选 Peer 或明确失败。

系统只记录路径类型、粗网络分类、耗时和错误码，不记录长期 IP 或 Candidate 全文。打洞成功率
必须来自真实指标，不能写死产品承诺。

### 5.4 Transport Adapter

`DirectQuicTransport` 作为原生 Local-to-Local 数据面：

- 两端都是受控 Local Runtime，不需要浏览器 WebRTC 媒体栈；
- QUIC 提供多路流、流控、取消和连接迁移；
- QUIC TLS 之外仍使用 Noise/Grant 绑定业务身份；
- 0-RTT 默认关闭，直到所有非幂等 Frame 都有重放防护；
- 移动端需要时可增加 WebRTC Adapter，不改变应用协议。

`RelayHttpsTransport` 封装现有 HTTPS/FRP：

- 第一阶段保持生产文本链路；
- Edge 只开放精确、版本化 Endpoint；
- Messager 和 Model Share 在 Direct 失败后自动回退，不要求 App 或用户重试；
- Model 文本、媒体和结果都必须保持同一应用协议语义；FRP 的流量配额、带宽和成本由系统策略
  管理，不能表现为“P2P 建连失败”；
- Checkpoint 继续禁止 Relay，并回退 MS/HF Source；
- UI 和指标必须明确标识 `direct` 与 `relay`。

### 5.5 `SecureSession` 与 `ProtocolMux`

每个 Session 必须冻结：

```text
session_id
protocol_id / protocol_version
initiator / recipient device
grant_id / grant_jti
access_epoch / key_epoch
expires_at
max_streams / max_bytes
```

公共 Frame Header：

```json
{
  "version": 1,
  "protocol": "ai2apps.messager/v2",
  "sessionId": "...",
  "streamId": 3,
  "sequence": 17,
  "type": "object.chunk",
  "flags": ["ack_required"],
  "payloadLength": 262144
}
```

Header 必须进入 AEAD Additional Data。未知协议/Frame、乱序越界、超限、Nonce 重用、过期 Grant
或用途不匹配一律 fail closed。

### 5.6 `ObjectTransfer`

Messager 文件、模型输入媒体、结果 Artifact 和 Checkpoint Piece 复用一个对象引擎：

```text
ObjectOffer -> ObjectAccept/Reject -> Chunk Stream
            -> Verify -> Commit -> ObjectAck
```

Manifest 至少包含 `objectId/purpose/name/mediaType/size/chunkSize/sha256/chunk hashes/expiresAt`。

要求：

- Manifest 先于正文，并受 Session 和业务 Grant 认证；
- Chunk 使用固定索引、Hash、AEAD 和有界乱序窗口；
- 写入随机名临时文件，完整 Hash 验证后原子 Commit；
- 恢复交换缺失 Chunk Bitmap，不重传已验证块；
- 业务 ACK 前保留源对象，Commit 后才进入历史或 Worker；
- 支持暂停、取消、超时、磁盘不足、配额拒绝和进程恢复；
- 文件名只作显示，不能决定落盘路径；
- 禁止自动执行、解压、加载动态库或打开高风险文件；
- Chunk 默认 256 KiB，基准测试范围为 64 KiB–1 MiB。

新增持久表建议：

```text
peer_sessions
peer_transfers
peer_transfer_chunks
peer_replay_tokens
peer_transport_observations
```

这些表只保存恢复所需的身份、状态、大小、Hash、路径引用和时间，不保存 Session Key、消息正文、
Prompt 或模型输出。各应用仍持有自己的业务历史。

## 6. 应用协议

### 6.1 Messager Protocol V2（P0）

Frame：

```text
message.text / message.ack
attachment.offer / attachment.accept / attachment.reject
object.chunk / object.resume / object.commit / object.ack
transfer.cancel
result.query / result.status
```

规则：

- 只有 Cloud 权威确认的好友可获得 Messager Grant；
- 文本保留当前 `clientMessageId` 幂等语义；
- 协议支持多对象，首个 UI 只开放单附件；
- 图片、音频、视频和普通文件复用 ObjectTransfer；
- 小文件也不以 Base64 嵌入消息 JSON；
- 大文件必须由接收方显式接受；
- 正文提交后 Relay 失败不能静默转 Cloud Offline；
- 目标离线时不向用户报传输错误：文本进入现有 Cloud Offline；文件保存为 `waiting_peer_online`，
  Cloud Offline 只投递 `attachment.offer` 元数据，源文件继续由发送方 Local 保管，双方上线后以
  原 `clientMessageId/objectId` 自动恢复；
- V1 不把任意文件明文自动上传 Cloud。若以后需要发送方离线后仍可下载文件，应单独设计
  Client-side E2EE Cloud Object Spool、保留期和配额；
- 用户可控制自动下载、目录、计费网络、带宽和磁盘配额。

建议默认上限：文本 4,000 字符/16 KiB，图片 25 MiB，音频 100 MiB，视频和普通文件 1 GiB，
单会话并发对象 2。限制由服务端 Policy 执行，网页不能绕过。

### 6.2 Model Share Protocol V1（P0）

Model Share 只允许固定 Schema 的模型推理，不允许 Tool/Agent/Service 调用。

```text
控制流：job.open / accept / reject / queued / started / progress / cancel
        job.complete / failed / usage.receipt
数据流：prompt.json / input.object.* / output.delta / output.object.*
```

首个 Pilot：

- 审核节点和两到三个固定 `modelId + revision`；
- 文本 Prompt 和流式文本输出；
- 窄化 OpenAI-compatible Chat Completion 字段；
- 一个 Winner、一个 JobGrant、一个 Currency Hold；
- Points-only、系统统一 Rate Card、Provider 不可改价；
- 本机优先，`WorkerResourceManager` 最终准入；
- Direct 优先，失败后由 Core 透明切换到 FRP C/S；
- 请求方断开后取消 Streaming Job，不恢复已生成 Token。

需求方 Local 把 `output.delta` 投影回本地 SSE。Provider Core 完成认证和解密后，只把 Contract
允许的字段交给 `ModelInvocationService/WorkerJobScheduler`；Worker 不接触 Peer 私钥。

第二阶段才增加图片、语音、视频、Durable Job 和结果 Artifact。System Message 只发送低频
里程碑，输入输出继续走 Peer Data Plane。

### 6.3 Checkpoint Protocol V1（P2）

Checkpoint 不复用 Messager 文件业务协议，只复用 Chunk Engine：

- 只传 Registry 签名 Manifest 中的不可变 Revision/Piece；
- 许可必须允许再分发；
- Piece Hash 和最终 Hash 双重验证；
- Peer 是 Source Adapter，MS/HF 可补充不同 Piece；
- 不进入 Messager 历史或普通文件目录；
- 不使用 FRP/Cloud Data Relay；
- 激活门槛前保持关闭，不阻塞 MS/HF 双源。

本阶段只冻结 Adapter：

```text
discover(manifest, missing_pieces)
open_peer_source(peer, grant)
read_piece(piece_index, range)
submit_receipt(piece_index, hash, bytes)
close()
```

## 7. 降级策略

| 业务 | Direct | FRP Relay | Cloud Offline | 无连接时 |
| --- | --- | --- | --- | --- |
| Messager 文本 | 首选 | 自动回退 | 目标离线时使用 | 进入 Offline Message，不因打洞失败报错 |
| Messager 文件 | 首选 | 自动回退 | 投递 Offline Offer | 保持 `waiting_peer_online`，双方上线后自动恢复 |
| Model 文本 | 首选 | 自动回退 | 禁止 | 重新撮合；无可达 Provider 才报错 |
| Model 大媒体/长任务 | 首选 | 自动回退 | 禁止 | 重新撮合；无可达 Provider 才报错 |
| Checkpoint | 必需 | 禁止 | 不适用 | 使用 MS/HF Source |

Direct→FRP 切换对业务透明，但只能发生在正文未提交或协议证明可恢复的 Chunk 边界。结果未知
时不能重新创建 Message、Job 或 Transfer；应以原 ID 查询状态并继续。目标离线和网络路径失败
是两个不同状态，只有前者进入模型不可用或 Messager Offline 语义。

## 8. Cloud 控制面

Cloud 需要通用协议级 Device Key、`PeerSessionIntent`、Candidate Broker、purpose-bound Grant、
Presence、Model Contract/Lease/Points Hold、System Message、Feature Flag 和 Kill Switch。

详细要求见 [Cloud Peer Session Broker 变更需求](cloud-system-peer-session-broker-requirements-v1.md)。
Cloud 代码由 Cloud 项目实施，本仓库不直接修改 Cloud 服务。

## 9. 开发阶段与 Exit Gate

### Phase 0：基线冻结

- 整理并提交现有 Messager、Router、Migration、UI、Fixture 和测试；
- 增加真实 `omlx.server` Router 装配测试；
- 固定 v1 文本、fallback、`result_unknown` 和 Key Rotation；
- 建立 `peer_transport_core/messager_peer_v2/model_share_peer_v1` Feature Flag。

Exit：干净 checkout 可构建；生产文本语义不变；安全与幂等测试通过。

### Phase 1：抽取 Core，保持 Relay

- 抽出 Identity、GrantVerifier、SecureSession 和 Transport Adapter；
- `RelayHttpsTransport` 复现现有链路；
- 实现版本协商、Frame Codec、Mux、限额和 Replay Store；
- Messager v1/v2 双栈；加入 FakeTransport 双节点测试。

Exit：v2 文本双 Local 成功；关闭 v2 后 v1 可用；Cloud/FRP 无正文。

### Phase 2：Messager ObjectTransfer

- Manifest、Chunk、Hash、临时文件、原子 Commit、ACK 和 Resume Bitmap；
- 单附件 UI，再开放多附件；
- 接收确认、配额、带宽、暂停、取消和失败 UX；
- 大文件、断线、崩溃、磁盘不足和恶意文件名测试。

Exit：1 GiB 文件中断和 Local 重启后可恢复；Hash 错误不落盘；重复 Chunk 不重复计入；Cloud
数据库/日志无正文或密文。

### Phase 3：Direct QUIC

- Candidate 收集、STUN、并行 Probe 和 Broker Client；
- QUIC Listener/Connector、Stream、Flow Control、Keepalive 和路径观测；
- Messager 和 Model Share 均 Direct 优先，失败后透明切换 FRP；
- 覆盖对称 NAT、UDP 禁止、IPv6、双层 NAT、网络切换和休眠恢复。

Exit：LAN/IPv6/可打洞网络不经过 FRP；路径可解释；Direct 失败自动使用 FRP 且不双发；App
接口、Message ID、Job ID 和流式语义不随 Transport 改变。

### Phase 4：Model Share 文本 Pilot

- Offer/Request/Contract/Lease/Grant Local 投影；
- 接入 Worker Scheduler/Resource Manager；
- Prompt、SSE Delta、Cancel、Usage Receipt；
- 固定模型、审核节点、Points-only、系统 Rate Card；
- Top-K SoftOffer 只允许唯一 CommitLease Winner。

Exit：一任务只执行/结算一次；取消和断线释放剩余 Hold；MCP/Agent/Service 在 Schema 和授权
两层被拒绝；Prompt/输出不进入 Cloud/Currency/Audit。

### Phase 5：媒体与 Durable Job

- ObjectTransfer 传图片、语音、视频和结果 Artifact；
- 阶段状态、离线执行、完成通知、Result Grant；
- Artifact 保留、恢复、取消点和阶段计费。

### Phase 6：Checkpoint P2P Pilot

仅在 MS/HF 双源稳定、并发下载证明有收益、许可清单完成、Direct/ObjectTransfer 经规模验证、
Receipt/反作弊具备后进入。

## 10. 测试与隐私门槛

Core：Frame 篡改/截断/重复/乱序/超限、错误 Audience、协议串用、Key Rotation、Epoch 变化、
Nonce 重用、断线、崩溃、重启、磁盘满、网络切换和敏感日志扫描。

Messager：Unicode、同 ID 重试、ACK 丢失、1 GiB 恢复、拒收/取消、解除好友/拉黑、Primary Device
切换，以及 Direct→Relay→Offline 不双发。

Model：模型/Revision/模态/结算硬过滤、唯一 Winner、资源拒绝、排队/取消/断线、SSE 顺序、Receipt
分歧、幂等结算和禁止 Capability 负向测试。

Checkpoint：许可、签名、Revision、Piece/最终 Hash、Peer/MS/HF 混合、坏 Peer 和刷量测试。

允许记录协议版本、路径类型、连接耗时、Bytes/Chunks/Streams 计数、粗错误码和状态；禁止记录
消息、Prompt、输出、文件 bytes/name、私钥/Session Key、完整 Grant、Candidate/IP 和密文 Payload。

## 11. 人力与粗排期

建议最小团队：一名 Peer/Core 工程师、一名 Messager/产品工程师、一名 Model Runtime 工程师，
Cloud 工程师并行完成 Broker/Grant/Edge；安全与测试评审按里程碑介入。

| 阶段 | 建议工期 | 可并行工作 |
| --- | ---: | --- |
| Phase 0 基线 | 1 周 | Cloud 合同评审 |
| Phase 1 Core/Relay | 2 周 | Broker Schema/OpenAPI |
| Phase 2 Messager 文件 | 2–3 周 | Candidate/QUIC 原型 |
| Phase 3 Direct QUIC | 3–4 周 | Model Contract/Offer/Lease |
| Phase 4 Model 文本 Pilot | 3–4 周 | Messager 多附件稳定化 |
| Phase 5 媒体/Durable | 3–5 周 | 依据产品范围拆分 |
| Phase 6 Checkpoint | 门槛触发 | 不排入近期关键路径 |

在 Cloud 工作按时并行的前提下，Messager 单文件首版约 5–6 周，Direct + Model 文本 Pilot 的
关键路径约 11–14 周。这是工程规划区间，不是发布日期承诺；Phase Exit Gate 未通过时不以日期
强行推进下一阶段。

## 12. 推荐代码布局

```text
ai2apps/peer/
  identity.py  grants.py  broker.py  session.py  framing.py  mux.py
  connectivity.py  repository.py
  transports/base.py  transports/relay_https.py  transports/direct_quic.py
  transfer/manifest.py  transfer/sender.py  transfer/receiver.py  transfer/resume.py

ai2apps/messager/protocol_v2.py
ai2apps/model_sharing/protocol.py
ai2apps/model_sharing/requester.py
ai2apps/model_sharing/provider.py
ai2apps/model_sharing/receipts.py
ai2apps/checkpoints/peer_source.py
```

`ai2apps/peer` 不得导入 Messager Repository、Currency、Model Worker 或 Checkpoint Registry；依赖
方向只能由应用协议指向 Core。

## 13. 第一批任务

1. 提交当前 Messager P2P 基线；
2. 补真实 Server Router 装配测试；
3. 定义 `PeerTransport/SecureSession/ApplicationProtocol/ObjectStore` 接口；
4. 用 `RelayHttpsTransport` 搬迁现有文本；
5. 加入协议域分离和 v1/v2 协商；
6. 完成 Manifest、Chunk Store、Resume Bitmap 和原子 Commit；
7. 交付 Messager 单文件 P2P；
8. 实现 PeerSessionBroker 合同和 Local Client；
9. 加入 Direct QUIC；
10. 固定模型/审核节点交付 Model Share 文本 Pilot；
11. 收集连接成功率、吞吐、失败和 Relay 成本；
12. 最后决定 Checkpoint P2P 是否进入 Pilot。
