# Mobile FRP EOF / HTML 404：排查证据与 Cloud 修复需求

状态：已只读核查生产中转日志；Local 客户端容错已实现，Cloud 尚未修改或部署。

## 已确认的故障链

- Mobile 请求 ID：`4c8cf1bc-5c55-4ac7-8200-f70845f02de4`。
- 手机采样时间：`2026-10-18T18:00:24.155Z`，即北京时间 10 月 19 日 02:00:24。
- 逻辑请求：GET `/v1/platform/intelligence?view=channels`，诊断按隐私约定不保留查询串；实际网络请求为 POST `/v1/mobile/app-mounts/{mount}/bridge`。
- Mobile 记录外层 HTTP 404，`text/html; charset=utf-8`，489 字节，约 249 ms，无重定向。
- FRPS 同一设备域名在 `2026-10-18 18:00:24.085 UTC` 记录：`do http proxy request ... error: EOF`。
- Nginx remote-access 日志存在同一挂载桥接请求 `404 489`；相邻请求恢复为 `200 12229`。该日志目前没有时间戳，不能单独用它证明毫秒级关联。
- Desktop 没有该请求 ID 的业务入口 start/end。约 5 秒后的新请求正常进入 Local，响应 200、9129 字节、18 ms。挂载 ID 没有变化。
- 运行中 FRPS 镜像：`ai2apps-frps:0.62.1-dcf1c62e`。官方 v0.62.1 `pkg/util/vhost/http.go` ErrorHandler 对 timeout 返回 504，其余转发错误（包括 EOF 和 no-route）统一返回 404 HTML。
- 官方源码：https://github.com/fatedier/frp/blob/v0.62.1/pkg/util/vhost/http.go#L124-L134

因此直接故障是 FRPS 转发链提前关闭并伪装成 404；不是情报文章不存在，不是首屏数据过大，也不是这一次挂载被删除。EOF 由哪一侧连接/连接复用条件触发，当前证据仍不足。FRPS 的 60 秒 idle pool、Local HTTP keepalive、连接池与隧道回收应列为待验证假设，不能写成已证实根因。

17:56 UTC 附近另有 control-closed/no-route，邻近 Local 重启；它与 18:00 的 EOF 分开处理。服务器另有某 run_id 的 invalid NewWorkConn 告警，尚未证明属于本设备，不将其归因为本次故障。

## 已实现的 Local 容错

`mobile_app_gateway.js` 仅对**外层、非 JSON App 信封的 HTML 404**转换为客户端 502，错误码 `mobile_gateway_upstream_unavailable`，保留真实 relay_status=404 和原诊断记录。已有逻辑只对 GET 做一次延迟重试，重试沿用同一请求 ID、attempt=1。POST/PATCH/PUT/DELETE 不自动重放。

真实的 App 信封内业务 404、外层 JSON 404、401/403 均保持原状态。它是缓解和错误分类修正，不是隧道稳定性已被根治的声明。

## Cloud/Edge 项目实施要求

1. 区分真实 no-route、EOF/连接重置、连接超时等网关故障。EOF/reset 返回结构化 502/503，超时返回 504；真实路由缺失保留 404。不能将所有业务 404 一概改写。
2. 不在 Edge 对所有 bridge POST 添加自动重试。bridge 中可包含写操作；响应丢失时可能已经生效。除非已有明确的请求幂等合同和执行状态查询，不得重放不确定操作。
3. 增加安全的访问日志关联：UTC 时间、Edge 请求 ID、host、路径（不含查询串）、method、status、upstream_status/address、request/upstream 时间、传输错误分类。禁止 Cookie、授权头、桥接正文、连接密钥及用户内容入日志。当前 remote_safe 日志没有时间，需补齐。
4. 在隔离环境复现 FRPS HTTP 连接复用与 Local keepalive 边界；对单连接池空闲关闭、TCP reset、控制连接重连和 Local 重启分别做故障注入。核实具体 socket/连接来源后再调整池/超时或升级 FRP，不凭 EOF 本身确定修复参数。
5. 如需变更固定 FRP 0.62.1/校验合同，交付明确版本与兼容方案，不直接替换部署二进制。保留 Device Owner 认证、Origin、路由白名单、限额和权限校验。

## 验收

- 受控 EOF 不再被报告为文章不存在；只读请求至多重试一次后成功，或者显示可重试的网关错误。
- 写入请求在响应丢失时执行次数仍为 1，不自动重放；真实业务 404 和权限错误不触发传输重试。
- 日志能关联 Mobile → Edge → FRPS → Local，明确未到达/已到达/结果未知，缺失证据不得视为零耗时或未执行。
- 完成受控连接池/空闲边界复现与修复前后对照，再提供生产部署、健康及回滚回执。

按本仓库 Cloud 边界，本轮没有改 Cloud 代码、服务器配置或生产 FRPS。请交给 Cloud 项目实施服务端修复。

## Local 验证结果

三个 WebKit 传输/诊断测试通过：精确模拟外层 HTML404 → 客户端502 → 同请求ID attempt=1 → 成功；保留 relay404 原始证据；真实业务404只请求一次；PATCH 遇到同类错误只发送一次。Dev 实际返回的网关 JS 与 checkout SHA-256 一致。手机需重新进入/刷新 App frame；尚未观察到真机在修复后再次遇到该 EOF。该修正不要求 iOS 原生、Package 或 Local Python 重启。
