# AI2Apps Cloud FRP 设备认证需求 v1

状态：初始需求已由 Cloud 实现并完成契约修正，等待协调切换
目标版本：Remote Access v1
适用组件：AI2Apps Cloud API、Remote Device 存储、frps、FRP Auth Plugin、Edge Router

> 本文保留为需求与决策记录。实现时以 `ai2apps-cloud` 仓库的
> `docs/frp-device-auth-v1.md`、`docs/remote-access-client-integration-v1.md`
> 和 OpenAPI `1.12.0` 为权威契约。Cloud 已修正 FRP 0.62.1 的 run lease
> 时序和 stock HTTP Plugin 无法注入自定义认证 Header 的部署问题。

## 1. 背景

当前 Local 已经为每台 Remote Device 持有一把独立的 Connector Secret：

- Cloud 在设备注册或“轮换密钥”时签发；
- Local 仅存入 `SecretBackend`，不进入 SQLite、页面或日志；
- Cloud API 使用 `Authorization: Device <deviceId>.<connectorSecret>` 验证设备；
- 设备撤销、暂停、过期和密钥轮换都已有明确状态。

旧实现另外要求所有客户端持有一把部署级 `FRP bootstrap token`。它无法由普通
用户安全配置，一旦嵌入 App 就会变成所有安装共享的可提取长期秘密，也无法按设备
撤销。因此 v1 正式方案取消客户端全局 FRP Token，直接复用可轮换、可撤销的设备
Connector Secret，由 frps 的 HTTP Server Plugin 作为 fail-closed 认证边界。

FRP 官方 Server Plugin 支持 `Login`、`NewProxy`、`Ping` 和 `NewWorkConn`，并会把
全局 metadata 放入这些调用。参考：

- https://github.com/fatedier/frp/blob/dev/doc/server_plugin.md
- https://gofrp.org/en/docs/features/common/authentication/

## 2. 目标

1. 用户绑定 Remote Device 后，无需再配置 FRP Token。
2. 每台设备只能创建 Cloud 为它分配的 proxy/subdomain。
3. Connector Secret 轮换后，旧 Secret 立即不能创建新会话或工作连接。
4. 设备 revoked、suspended、expired 或失去 `remote.connect` 权益后，FRP 请求失败。
5. 任意 Cloud、Plugin、数据库或网络故障都必须 fail closed。
6. 日志、指标、错误和审计记录永远不包含 Connector Secret。

## 3. Local 已发送的 FRP 身份

`frpc-device.toml` 使用：

```toml
user = "<deviceId>"
auth.method = "token"
auth.additionalScopes = ["HeartBeats", "NewWorkConns"]

metadatas.deviceId = "<deviceId>"
metadatas.credentialVersion = "<positive integer>"
metadatas.connectorSecret = "<opaque secret>"
metadatas.authProtocol = "device-credential-v1"

[[proxies]]
name = "device-<deviceId>"
type = "http"
localIP = "127.0.0.1"
localPort = <当前已绑定的 AI2Apps Local 端口>
subdomain = "device-<32 lowercase hex>"
```

客户端不再设置 `auth.token`。frps 的内置空 Token 不是安全边界；安全边界必须是
下面定义的 HTTP Plugin。现有 TLS、固定服务端域名和固定 CA 指纹校验保持不变。

## 4. frps 配置要求

Cloud 部署必须在接受新版客户端前完成以下配置：

```toml
bindPort = 7000
auth.method = "token"
auth.additionalScopes = ["HeartBeats", "NewWorkConns"]
# 不配置部署级 auth.token。

[[httpPlugins]]
name = "ai2apps-device-auth"
addr = "http://127.0.0.1:<plugin-port>"
path = "/internal/frp/auth"
ops = ["Login", "NewProxy", "Ping", "NewWorkConn", "CloseProxy"]
```

要求：

- stock FRP 0.62.1 Plugin 不支持配置自定义 Authorization Header，因此正式链路为
  `frps -> 私有 frp-auth-proxy sidecar -> Internal Bearer -> Cloud`；
- sidecar 只能监听私有容器网络，Cloud 内部接口必须验证 sidecar 注入的服务凭据；
- Plugin 不可用、超时、返回非 2xx、响应无法解析时一律拒绝；
- 请求体上限 64 KiB，超时建议 2 秒；
- 不允许绕过 Plugin 的第二个公开 frps listener。

## 5. Plugin 校验规则

### 5.1 所有操作

Plugin 必须：

1. 只接受 `version=0.1.0` 以及白名单操作；
2. 要求 `authProtocol == "device-credential-v1"`，并提取
   `deviceId`、`credentialVersion`、`connectorSecret`；
3. 验证 `user == deviceId`；
4. 验证 Device ID 格式、正整数版本，以及满足
   `[A-Za-z0-9_-]{20,256}` 的 Secret；
5. 使用恒定时间比较/密码哈希验证 Secret，数据库不得保存明文；
6. 验证 Device 状态为 `active`，凭据未过期且版本完全一致；
7. 验证关联 Installation/Organization 有效且仍有 `remote.connect` 权益；
8. 成功返回 `{"reject":false,"unchange":true}`；
9. 任何不确定状态都返回通用拒绝，不向 frpc 暴露账户或策略细节。

### 5.2 Login

- `content.user` 必须等于 Device ID；
- `content.metas` 必须通过 5.1；
- 记录不含秘密的 login accepted/rejected 审计事件；
- FRP 0.62.1 在 Login Plugin 返回之后才分配 run ID，因此 Login 不创建
  authoritative run lease。

### 5.3 NewProxy

除 5.1 外必须精确验证：

- `proxy_name == "device-" + deviceId`；
- `proxy_type == "http"`；
- `subdomain` 等于 Cloud Device 记录中已分配的 subdomain；
- `custom_domains` 为空；
- 不接受客户端请求任意 remote port、域名或其他 proxy 类型；
- 同一 Device 不得创建第二个不同名称的 proxy。
- NewProxy 是第一个携带有效 run ID 的正常操作；它负责创建或接管
  `deviceId -> run_id` authoritative lease。最近 90 秒仍有心跳的其他 run 必须拒绝。

### 5.4 Ping / NewWorkConn

- 重复执行 5.1，确保撤销和轮换不只影响下一次进程启动；
- 校验 `run_id` 与 NewProxy 建立的当前 authoritative lease 完全一致；
- `NewWorkConn.content.run_id` 还必须与 `content.user.run_id` 完全一致；
- Secret 失效时立即拒绝，frps 应关闭对应 control/work connection。

### 5.5 CloseProxy

- 对 metadata 做同样的设备认证，但该操作主要用于状态收口；
- 仅当 Device ID 与 run ID 都匹配当前 accepted run 时，才把
  `proxyConnected` 更新为 false；
- 旧 run 的 CloseProxy 不得覆盖新 run 的在线状态。

## 6. Cloud 数据与现有 API

不新增面向浏览器的 Token API，也不把 FRP 凭据返回 Account 页面。

继续使用现有接口：

- `POST /v1/remote/devices`
- `POST /v1/remote/devices/{deviceId}/credentials/rotate`
- `POST /v1/remote/devices/{deviceId}/revoke`
- Device Authorization：`Authorization: Device <deviceId>.<connectorSecret>`

Cloud Device 记录至少需要：

- `id`、`status`、`credentialVersion`、`credentialExpiresAt`；
- Connector Secret 的安全哈希；
- `proxyName`、`subdomain`、`publicOrigin`；
- Installation、Organization、entitlement/access epoch 关联；
- 当前 accepted FRP `run_id` 和最后心跳时间（可独立存储）。

密钥轮换必须原子地：

1. 增加 `credentialVersion`；
2. 保存新 Secret 哈希；
3. 使旧 Secret 失效；
4. 关闭或标记旧 FRP run 失效；
5. 返回新 Connector Secret 一次，之后不可再次读取。

## 7. 状态投影

Account App 依赖 Cloud Device 的 `online` 与 `proxyConnected`：

- Login 接受：可更新 `online=true`；
- NewProxy 接受并由 frps 确认可用：`proxyConnected=true`；
- 心跳超时、CloseProxy、连接断开或认证拒绝：及时设为 false；
- 状态更新必须绑定 Device ID 与 run ID，旧连接不能覆盖新连接状态。

建议 90 秒无有效心跳即视为离线，具体值须大于客户端 30 秒 heartbeatInterval。

## 8. 错误与可观测性

Plugin 对 frps 的所有拒绝固定返回：

```json
{"reject":true,"reject_reason":"authorization denied"}
```

以下详细原因只允许进入无秘密的服务端安全审计和指标，例如：

- `device_auth_invalid`
- `device_inactive`
- `credential_version_mismatch`
- `credential_expired`
- `remote_entitlement_required`
- `proxy_policy_denied`
- `auth_backend_unavailable`

指标至少包括按 operation/reason 分类的 accepted/rejected、Plugin 延迟、Cloud/DB
错误、在线 run 数。日志禁止记录请求原文、Authorization、Connector Secret 或其可逆
派生值。

## 9. 部署顺序

项目尚未正式发布，不要求兼容已发布客户端，采用一次协调切换：

1. Cloud 已完成 Plugin、sidecar、run lease、数据查询、审计和自动化测试；
2. Cloud 已在隔离 frps 0.62.1 环境验证五类 operation 全部 fail closed；
3. 客户端完成 `device-credential-v1`、动态 Local 端口及到期保护；
4. 协调切换线上 frps：启用五类 Plugin callback 并删除共享 token；
5. 立即用新客户端完成注册、启动、手机访问、轮换、撤销和断线重连；
6. 删除部署 Secret 与流水线中所有旧 bootstrap token 材料。

## 10. 验收测试

Cloud/FRP 项目交付前必须自动验证：

1. 正确 Device + Secret 可 Login 并创建唯一合法 proxy；
2. 错误 Secret、错误版本、错误 Device ID 全部拒绝；
3. 合法 Secret 不能创建另一设备的 proxy/subdomain；
4. 非 http proxy、任意域名、任意 remote port 全部拒绝；
5. 轮换后旧 Secret 的 Ping/NewWorkConn 与新 Login 全部拒绝；
6. revoke/suspend/过期/权益移除后连接被关闭且不能重连；
7. Plugin/数据库/Cloud 超时或异常时 frps 不放行；
8. 日志与审计扫描确认不含测试 Secret；
9. 同一 Device 的旧 run 不能覆盖新 run 在线状态；
10. 真实公网 URL 完成手机配对和 Mobile Chat，Local 仍执行最终授权。

## 11. Cloud 项目交付物

- FRP Auth Plugin 源码和部署清单；
- frps 配置变更；
- 数据迁移（如需要 run/heartbeat 状态表）；
- 单元、集成和真实 frps E2E 测试；
- 运维指标、告警和不含秘密的审计说明；
- 测试环境地址及一个可撤销的测试 Device；
- Cloud commit、部署版本和协议版本 `device-credential-v1`。
