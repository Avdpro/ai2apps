# Owner Mobile Apps / Agent 统一授权 v1 对接要求

2026-10-22 更新：Cloud/Edge 已部署 OpenAPI 1.76.0。以下原始提案仅作历史背景；凡与最终合同不同，以 Cloud `docs/owner-mobile-unified-client-handoff-2026-10-22.md` 为准。客户端已按最终合同修订，实例 readiness 尚未开启。

## 最终合同接入记录

- 同时协商 `mobileAccessProtocol=owner-mobile-unified-v1` 和 `commitMode=exchange-v1`，缺任一字段不进入新模式。
- Desktop decision 仅返回 `awaiting_exchange`，显示“已确认，等待手机完成连接”。不赋权、不撤销、不 ACK。保留原始 expectedGeneration。
- Local 以 Device 凭证查询扫码 pairing，确认 prepared/active 后交换。独立的 `mobile_unified_generations` 持久表记录统一代次，不写旧 Agent generation。
- 每个 handoff/device/connection 组合先在实例 SecretBackend 持久化 Local 生成的 UUID `exchangeRequestId`，然后发送。浏览器不能指定 ID。存储失败时不发请求。只保存 handoff 哈希和 ID，不保存 bearer。
- 网络传输异常最多重试一次，完整 body 与 ID 不变。Local 重建后，同一 handoff 再提交仍读取原 ID；不会后台保存/重放 bearer，不重放聊天或业务任务。Cloud 60 秒回执恢复期限仍是硬限制。
- 只有已验证签名成员及租约绑定、协议/mode、active commitReceipt、device/session/connection/client/epoch 一致后才接受交换结果。拒绝降级。撤销只按已提交回执的精确 session ID 执行；旧 Agent 只消费独立 `legacyAgentGeneration`。
- 已提交回执可由 active pairing 查询补处理；revoked pairing 携带的历史回执不赋权。Cloud 重放必须标记 replayed，原会话绑定和绝对/闲置期限保持相同。
- 完整且合法的统一签名绑定允许 `mapping_revision=0`。退出持久重试屏障和恢复机制保持。

验证：84 项 Owner/统一/旧 Agent/Gateway Python 回归、7 项隔离 Chrome UI fixture、245 项 AaAT 边界门禁通过。最终细化后复跑39项协议测试及5项Desktop浏览器测试通过。真实 Cloud exchange、多客户端踢出、Desktop 重启及 iPhone Safari 尚未验收；此记录不代表公网开关或真机验收完成。


## 产品规则

本人登录并获准使用 Desktop 的 Mobile Apps，即可使用 Agent。网页和原生 App 规则相同，无单独 Agent 许可。匿名访客不包含在内。仍保留业务 Tool 所需确认、范围、资源归属和预算检查。

扫码登录 Desktop 确认框改为“断开其它客户端连接”，默认 false。false 允许同一 Desktop 多客户端共存；true 只在本次登录成功提交时撤销该 Desktop 其余 Mobile 客户端的 Apps、Agent、旧协议配对与恢复资格。不得撤销其它 Desktop 或账户全局登录。撤销不取消已提交后台任务，但旧客户端不可继续读取或操作任务。重新获得访问需用户明确重新登录授权，不能利用仍有效的账户 Cookie 静默恢复。

进程重启只使旧进程租约失效，保留长期客户端授权关系。续接重新验证 Cloud 登录、Owner/组织权限、设备绑定、客户端撤销代次，不自动重发业务请求。

## 协商和签名字段（客户端按此提案实现）

Local 开关 `AI2APPS_OWNER_MOBILE_UNIFIED_READY=1` 默认关闭。开启后 PUT `/v1/internal/spaces/owner-home/device` 增加 `mobileAccessProtocol: owner-mobile-unified-v1`；Cloud 仅在全部语义就绪时返回相同字段。旧服务不能收到未知能力字段（开关关闭不发送）。

Owner member assertion 和 lease JWT 保留现有 scope、audience、签名与全部身份检查，新增完整绑定组：

- `mobile_access_protocol`: `owner-mobile-unified-v1`
- `mobile_client_id`: 规范 UUID，代表浏览器配置/原生安装的逻辑客户端
- `mobile_client_epoch`: 正整数，此客户端当前授权代次

字段必须成组出现且合法；exchange/refresh 不得换绑定。缺少这组字段的旧 Owner lease 不具备统一 Agent 权限。Local readiness 关闭时同样拒绝。不要仅凭声明能力或客户端传参赋权。

`GET /v1/mobile/owner-home/status` 由 Local 从已验证租约投影 `agentAuthorized: true/false`；前端据此选择新通道，字段不授予权限。

## 扫码确认

沿用既有设备认证、Desktop 本机管理员确认、pairings 创建/查询通道。

Cloud 能力已确认时 Local 创建 pairing 请求增加 `mobileAccessProtocol`；创建和查询响应均须回传协议标记。旧响应不展示新复选框语义。

`POST /v1/internal/mobile-agent/pairings/{connectionId}/decision` 新请求：

```json
{"decision":"connect","expectedGeneration":12,"enforcerInstanceId":"UUID","mobileAccessProtocol":"owner-mobile-unified-v1","disconnectOtherClients":false}
```

拒绝仍使用既有 deny；旧 agent/chat 不改变语义。connect 默认同时允许 Apps/Agent。Cloud 校验扫码账号确为 Owner、pairing 未超时且代次正确。connect 是幂等事务：同一 pairing 同一参数重复请求返回同一结果，冲突参数拒绝。响应：

```json
{"status":"active","mobileAccessProtocol":"owner-mobile-unified-v1","generation":13,"disconnectOtherClients":false,"revokedSessionIds":[]}
```

若断开其它客户端，revokedSessionIds 必须完整列出此次撤销的该设备 Owner 会话，Local 收到后立即 drop 对应内存租约并隔离旧 Agent 租约。Cloud 同时撤销所有旧恢复资格及 legacy Agent 连接；任一新 Local 不能从 Cloud 恢复这些关系。成功回执丢失时重试同一事务获得相同撤销集合；此事务绝不能要求先撤销他人再去完成可能失败的新登录。

查询 pairing 若事务已成功，应返回同一 active 结果及撤销集合，供 Local 恢复丢失回执。设备重启不能清除统一客户端的长期授权。新模式不使用旧 Agent 单活 activeConnectionId 作授权源。

完成后用既有 Apps handoff 进入 /mobile/home；member exchange 返回带上述绑定的新 Owner 租约。网页账户入口同样签发统一租约，不限扫码。

## 精确 Edge 通道

新增 `/v1/mobile/owner-agent` 前缀，复用现有 Agent 的 business_target / asset 精确映射；不可放通任意 `/v1/platform`。

- GET models、agents、chat/state、chat/threads、chat/threads/{id}/content、chat/threads/{id}/agent-runs
- POST chat/threads、chat/threads/{id}/agent-runs
- GET agent-runs/{id} 及现有 `allowed_control` 允许的只读后缀
- POST/PUT 仅现有 `allowed_control` 的精确控制后缀
- GET assets/{run}/{viewIndex}/{itemIndex}、artifacts/{run}/{artifact}

以 `ai2apps/web/mobile_agent_gateway.py::business_target` 和 `mobile_agent_transport.py::allowed_control` 为精确清单来源，部署前导出逐方法路径测试，不用宽泛前缀替代。禁止 bootstrap/connections/challenge 等旧密钥接口映射到新前缀。

Local 由 PublicDeviceBoundary 验证安全 Cookie、Device Host 和写请求 Origin，验证签名的新租约字段后复用已有隔离 Agent router、所有权检查和结果适配。响应受租约生命周期保护。客户端不读取 Cookie、不保存 bearer；不复用 Local 管理会话。无需向普通网页暴露原生签名密钥。

## 撤销与故障一致性

撤销代次必须由 Cloud 持久保存。现存租约在 Local 收到撤销回执后立刻失效；Cloud 发起的撤销需现有通知/续租回执同步，最迟不超过租约有效期（当前 60 秒）。若要求跨节点零延迟，需 Cloud 提供可确认的撤销屏障，不能宣称单靠短租约实现瞬时撤销。断开后保留原页面缓存不表示继续拥有授权。

主动退出走现有持久 logout outbox；失败不能被自动续接抵消。Cloud 不可达时拒绝新权限。新登录失败不能误踢旧客户端。所有恢复只发认证/读取请求。

## 联调与验收

先部署 Cloud/Edge、确认协议与路由，再显式开启目标 Local 开关并重启；不得批量替用户开启。覆盖多客户端并存、勾选踢出 Apps/Agent/legacy、退出重试、撤销后不能自动恢复、Desktop 重启免扫码、旧租约拒绝、跨用户/设备/匿名拒绝、Origin/编码别名拒绝、重复事务、回执丢失、进行中任务不重发。真实 iPhone Safari、原生 iOS 和桌面浏览器验收必需。提供最终 OpenAPI、字段差异、生产回执后客户端再核对，未验收不能称已上线。

## Dev activation follow-up

2026-10-22: previous activation-disabled status is superseded. Readiness now defaults on, with AI2APPS_OWNER_MOBILE_UNIFIED_READY=0 as rollback. Fixed Dev Local restarted through Helper after zero executing tasks. Cloud confirmed protocol/mode negotiation; port50859 health and served JS verified. 80 regression tests passed. Existing phone must re-enter once to obtain a new signed grant; real phone/multi-client acceptance is still pending.
