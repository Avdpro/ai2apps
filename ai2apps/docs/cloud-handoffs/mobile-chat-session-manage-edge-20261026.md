# Cloud 交接：统一 Mobile Chat 会话管理入口被 Edge 404 拦截

日期：2026-10-26。需要 AI2Apps Cloud 项目实现、部署并验收。
本仓库只交付 Local 与文档，未修改或部署 Cloud 代码。

## 当前接收状态

Cloud 已回传生产部署完成，回执为 Cloud 项目
`docs/mobile-chat-session-manage-production-2026-10-26.md`，客户端手册为
`docs/mobile-chat-session-manage-client-handoff-2026-10-26.md`。
接收方已再次对实际 Dev Device 公网统一入口发出无凭据、不存在 Session 的 POST：
返回 `403 application/json {"detail":"Public route is not allowed"}`，不再是
Nginx HTML404。这证明 Edge 路径阻断已解除，不能作为已授权改名/删除成功证据。
真实手机临时会话的改名、取消删除、确认删除及列表重载仍待验收。
下文保留故障发现时的证据和原交接要求，不代表 Edge 仍未部署。

## 已确认的故障

手机显示 Apps · Agent，采用 unified Owner Mobile transport。
用户已确认删除，但收到 Request failed (HTTP 404)。Dev Local 已加载新 API 与
网关；列表、content、agent-runs GET 能进入 Local，manage POST 没有进入内部路由。

对同一个实际 Dev 公网 origin 做不携带 Cookie/密钥的诊断，使用不存在的 Session
`probe-not-a-session` 和空 JSON，不会删除或改名真实会话：

| POST 路径 | 实际响应 |
| --- | --- |
| `/v1/mobile/agent/chat/threads/probe-not-a-session/manage` | JSON 403，Invalid UUID，已进入 Local Agent 授权 |
| `/v1/mobile/owner-agent/chat/threads/probe-not-a-session/manage` | text/html 404，nginx/1.15.12 错误页，未到 Local |

Cloud 源码只读核对：`src/spaces/owner-mobile-edge.ts` 的
`OWNER_MOBILE_EDGE_RULES.POST` 未包含 `chat/threads/{id}/manage`。
`ownerMobileEdgeLocation()` 对不在白名单内的 Owner Agent 路径直接 `return 404`。
这与实测响应一致，不是 Session 不存在、Local 未重启或 iOS 对话框的问题。

## 请求的最小变更

在统一 Owner Mobile Edge 的 POST 精确规则中增加：

```text
chat/threads/[A-Za-z0-9_-]{1,256}/manage
```

公网完整路径为 `/v1/mobile/owner-agent/chat/threads/{thread_id}/manage`。
仅允许 POST，保留现有规范路径、方法、Host、Origin、租约与反向代理规则。
不要增加任意 `/chat/*`、`/v1/platform/*` 通配，不要开放 PATCH/DELETE，也不要
改变 iOS 原生签名器的 GET/POST/PUT 方法范围。

沿 Cloud 的标准流程更新规则生成器、生成的 Nginx map/location、测试与部署产物，
验证配置后重新加载 Edge。只改 TypeScript 文件而不部署生成配置不能完成修复。
如果已采用新的配置所有者/生成入口，应在该权威入口修改，不并行维护第二份规则。
Cloud 版本与契约记录由 Cloud 项目按其现行规则更新。

## Local 已有协议与守卫

Local 的 `web/owner_agent_gateway.py` 复用
`web/mobile_agent_gateway.business_target` 和原 actor/client-scope：

```json
{"action":"rename","expected_revision":7,"title":"新的名称"}
```

或：

```json
{"action":"delete","expected_revision":7}
```

Local `POST /v1/platform/chat/threads/{id}/manage` 严格拒绝未知字段、未知 action、
非正 revision、空白或超过160字符的改名、删除附带 title；再委托原 PATCH/DELETE
handler，保留归属检查、乐观版本及软删除语义。Edge 只转发，不解释或执行删除，
不保存消息正文、名称、Cookie 或签名。前端已改为页面内确认，不使用原生 confirm。

## 必须的回归与验收

1. 在 `test/owner-mobile-unified.test.ts` 等权威测试中验证 POST 精确路径允许。
   GET/PUT/PATCH/DELETE、尾斜杠、额外子路径、编码 ID/斜杠、双斜杠、其它平台路径
   继续拒绝；保留原有安全负例，不能改成前缀通配。
2. 验证生成的 Edge map 确实包含新规则，并部署到实际 Device 公网入口。
3. 不携带授权的上述 nonexistent-session 探测，应抵达 Local 的 JSON 授权拒绝
   （401/403），不再是 Nginx HTML 404；这只证明路径通，不证明操作已获授权。
4. 使用批准的测试连接和新建的可丢弃 Session，通过真实 unified Owner 手机路径：
   改名、取消删除（无请求）、确认删除、列表重载后不再出现；记录 HTTP 状态与
   Local 实际入站/内部 dispatch 证据，不记录凭据。
5. 跨 owner/不可访问线程拒绝；过期 revision 返回冲突；未授权/过期租约不能操作。
   不要在用户现有真实会话上做删除验收，也不要因为失败自动重发写请求。

完成条件：实际统一连接的管理 POST 到达 Local，并通过授权测试 Session 的端到端
操作验证。独立签名入口成功、Local 单测通过或配置生成成功均不能替代此条件。

## 其它入口漂移

同一白名单还可能落后于 Local 的其它新接口，例如 speech。请单独盘点并按明确需求
交接，不在本次修复里顺手全量开放；本次必要范围只有会话 manage POST。
