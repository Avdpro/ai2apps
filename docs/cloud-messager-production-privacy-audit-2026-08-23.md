# Cloud Messager 生产隐私审计任务（2026-08-23）

## 1. 目的与执行边界

请 Cloud 工程对 2026-08-23 的 Messager 生产联调执行一次只读隐私审计，确认
Local E2EE 消息的明文、Noise 载荷、Device Key 登记 proof、原始 challenge、私钥、
connector secret 和 compact peer assertion 没有进入 Cloud 数据库、应用日志、Nginx
日志、FRPS 日志、审计事件或指标标签。

本任务默认只允许：

- 只读数据库查询；
- 读取当前及保留期内的轮转日志；
- 读取实际生效配置、镜像/提交信息和指标定义；
- 在本地或隔离测试环境增加自动化隐私回归测试。

不要为了检查而在生产打印请求体、JWT、proof、challenge、Authorization、密文或
数据库完整行。不要把原始日志、正文、公钥字节或 token 回传给客户端工程。回传内容
只包含计数、字段名、状态、时间范围、配置/镜像哈希和必要的脱敏 ID。

如果任何检查非零或无法覆盖，应先标记 `FAIL` 或 `INCOMPLETE`，保留原始证据在生产
受控环境内，不要在聊天、提交或文档中粘贴敏感值。本任务不授权修改生产、清理日志、
删除数据、重启服务或重新部署。

## 2. 生产基线与联调范围

Cloud 基线：

- Cloud：`https://coder.ai2apps.com`
- OpenAPI：`1.19.0`
- Messager 功能提交：`28953f6`
- FRP 竞态修复：`6573e5f`，部署记录 `08488b7`
- 密文精确路由：`6fbc974`，部署记录 `9404136`
- Migration：`0030_puzzling_husk.sql`，生产 migration `31/31`
- 审计时间窗：`2026-08-23T03:00:00Z` 至 `2026-08-23T03:50:00Z`

参与主体：

| 角色 | User ID | Device ID |
| --- | --- | --- |
| A | `b8696bee-d730-46b6-848c-e41f1f96a0b4` | `3a4cce68-7458-4f2f-9b83-b1478c8c81b6` |
| B | `8ea38ac2-4beb-4a3d-bd9b-6a9fb994cddb` | `bfebb83e-fe54-4c13-9888-86cbba821f87` |

成功的 Local E2EE 客户端消息 ID：

- A → B：`2a17b9c3-5348-4d7b-960d-b43b7980e819`
- B → A：`d50b2e4a-f05d-428a-96d7-e53145064e52`
- B 轮换密钥后的 A → B：`c91ac0a6-bdfb-4ae2-a571-ac7b43e55022`

唯一的 Cloud offline 对照消息 ID：

- `a1552b79-7dc4-4b47-a770-4013301e859e`

## 3. Canary 与预期结果

以下三条是合成测试明文，不含用户秘密。它们在 Cloud 的所有存储、日志、审计和指标
中都必须为零匹配：

| Canary | SHA-256 |
| --- | --- |
| `Final Noise IK E2EE A→B · route 6fbc974 · 2026-08-23` | `dff0820c7d1728a3daa1a9ecc7f21b6eb83212e44458dd1aa21169df8ba0b678` |
| `Final Noise IK E2EE B→A · route 6fbc974 · 2026-08-23` | `a9eb35d91c90fe2bf90214185b70f72bc292bb143b52c6561d07cbc7a76a7ccd` |
| `Noise IK E2EE after B key rotation · 2026-08-23` | `8b5011f2b3d41e3a8481c2807467afcc4786ae7b569a6e65c6a6963717711772` |

Cloud offline 对照正文为：

`Cloud offline fallback after route 6fbc974 · 2026-08-23 11:22`

其 SHA-256 为
`cf1d5bafb8d87a98ed17a612ee1ba5f21eacea65e1a969dc29a1e8e263b07f48`。
该对照正文在 `system_messages` 中预期恰好一条，因为 v1 offline fallback 明确是 Cloud
可读存储；它不能被当作 E2EE 泄漏。它在应用/Nginx/FRPS 日志、审计和指标中仍应为零。

## 4. 数据库只读检查

### 4.1 Schema 最小化

先记录 Messager 表的列名，不要查询原始值：

```sql
select table_name, ordinal_position, column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name like 'messager_%'
order by table_name, ordinal_position;
```

通过条件：

- `messager_device_key_challenges` 只有 challenge ID、Device、`nonce_digest`、epoch 和
  生命周期字段，没有 challenge 明文或 proof；
- `messager_device_keys` 只有公钥、fingerprint、epoch、状态和生命周期字段，没有私钥；
- 不存在 assertion、JWT、Noise handshake、ciphertext、消息正文或会话密钥存储表/列。

### 4.2 Device Key 轮换状态

```sql
select device_id, key_epoch, device_access_epoch, status,
       octet_length(identity_signing_public_key) as identity_public_key_bytes,
       octet_length(static_dh_public_key) as static_dh_public_key_bytes,
       created_at, retired_at
from messager_device_keys
where device_id in (
  '3a4cce68-7458-4f2f-9b83-b1478c8c81b6',
  'bfebb83e-fe54-4c13-9888-86cbba821f87'
)
order by device_id, key_epoch;
```

通过条件：

- 每个 Device 至多一条 `active`；
- B 最新一条为 `active`，上一条为 `rotated`，两个 epoch 单调递增；
- 公钥均为 32 bytes；
- 不输出公钥字节或完整 fingerprint。

另执行：

```sql
select device_id,
       count(*) filter (where status = 'active') as active_count,
       count(*) filter (where status = 'rotated') as rotated_count,
       count(*) filter (where status = 'stale') as stale_count,
       count(*) filter (where status = 'revoked') as revoked_count
from messager_device_keys
where device_id in (
  '3a4cce68-7458-4f2f-9b83-b1478c8c81b6',
  'bfebb83e-fe54-4c13-9888-86cbba821f87'
)
group by device_id;
```

### 4.3 Audit 字段白名单与禁用字段

先只返回 event type、数量及 context key 名称：

```sql
select ae.event_type, count(distinct ae.id) as event_count,
       array_agg(distinct k.key order by k.key) as context_keys
from audit_events ae
cross join lateral jsonb_object_keys(ae.context) as k(key)
where ae.occurred_at >= '2026-08-23T03:00:00Z'
  and ae.occurred_at <  '2026-08-23T03:50:00Z'
  and (
    ae.event_type like 'messager.%'
    or ae.event_type like 'remote.frp.%'
    or ae.event_type like 'remote.proxy.%'
  )
group by ae.event_type
order by ae.event_type;
```

再检查禁用 key；只返回计数：

```sql
select count(*) as forbidden_audit_context_rows
from audit_events
where occurred_at >= '2026-08-23T03:00:00Z'
  and occurred_at <  '2026-08-23T03:50:00Z'
  and context::text ~* '"(assertion|compactJwt|proof|challenge|noiseMessage|ciphertext|body|messageBody|plaintext|privateKey|sessionKey|connectorSecret|authorization)"[[:space:]]*:';
```

通过条件：`forbidden_audit_context_rows = 0`。

当前代码允许的 Messager audit context 应限于：Device/User/Installation ID、key/access/
membership epoch、suite、fingerprint、handshake ID、过期时间、结果码以及 FRP 的脱敏
run/proxy/request 元数据。不得加入请求体、响应体、完整 assertion 或凭证。

### 4.4 E2EE 明文及 clientMessageId 不得进入 Cloud 消息表

以下查询只返回计数：

```sql
with e2ee_canary(value) as (values
  ('Final Noise IK E2EE A→B · route 6fbc974 · 2026-08-23'),
  ('Final Noise IK E2EE B→A · route 6fbc974 · 2026-08-23'),
  ('Noise IK E2EE after B key rotation · 2026-08-23')
)
select count(*) as e2ee_plaintext_rows
from system_messages sm
join e2ee_canary c on to_jsonb(sm)::text like '%' || c.value || '%';
```

```sql
with e2ee_client_id(value) as (values
  ('2a17b9c3-5348-4d7b-960d-b43b7980e819'),
  ('d50b2e4a-f05d-428a-96d7-e53145064e52'),
  ('c91ac0a6-bdfb-4ae2-a571-ac7b43e55022')
)
select count(*) as e2ee_client_id_rows
from system_messages sm
join e2ee_client_id c on to_jsonb(sm)::text like '%' || c.value || '%';
```

通过条件：两项均为 `0`。

离线对照检查：

```sql
select count(*) as offline_control_rows
from system_messages
where kind = 'user.offline_message'
  and sender_user_id = 'b8696bee-d730-46b6-848c-e41f1f96a0b4'
  and recipient_user_id = '8ea38ac2-4beb-4a3d-bd9b-6a9fb994cddb'
  and body = 'Cloud offline fallback after route 6fbc974 · 2026-08-23 11:22';
```

通过条件：`offline_control_rows = 1`。

### 4.5 全库结构审阅

检查生产实际 schema，而不只检查源码 migration：

```sql
select table_name, column_name
from information_schema.columns
where table_schema = 'public'
  and (
    column_name ~* '(assertion|proof|challenge|noise|ciphertext|plaintext|private.*key|session.*key)'
    or table_name ~* '(messager|message)'
  )
order by table_name, column_name;
```

逐项解释返回列的用途。`nonce_digest`、公钥、fingerprint、离线 `system_messages.body` 和
附件对象元数据是已知合同；任何用于保存 peer assertion、Noise 包、E2EE 正文或私钥的
新增列都直接判定失败。

## 5. 应用、Nginx、FRPS 与轮转日志

Cloud 工程先列出并回传本次实际检查的日志源名称，例如：

- 当前生产 Cloud 容器及保留的同版本/回滚容器；
- Nginx access/error 当前文件和轮转压缩文件；
- FRPS 当前日志、systemd journal 或容器日志；
- FRP auth plugin/sidecar 日志；
- 集中日志平台及其保留时间（如果存在）。

对 `2026-08-23T03:00:00Z`–`03:50:00Z` 执行精确 canary 搜索。命令需适配实际容器和
日志路径，但只能输出每个日志源的匹配计数，不输出命中行。例如可使用
`rg -F -c`、`zgrep -F -c` 或日志平台的 count-only 查询。

必须检查：

1. 三条 E2EE canary：每个日志源均为 0；
2. Cloud offline 对照正文：每个日志源均为 0；
3. 三个 E2EE clientMessageId：每个日志源均为 0；
4. JSON 字段名 `noiseMessage`、`ciphertext`、`assertion`、`proof`、`challenge`：不得伴随
   字段值写入；若仅有代码/启动文本，需说明来源；
5. `Authorization: Device ...`、connector secret、compact JWT 三段式 token：0；
6. 请求/响应 body dump、中间件 debug dump、反向代理 mirror、临时抓包或 APM body
   capture：均未启用。

注意：Nginx/FRPS 可以记录路径、方法、状态、字节数、Host、脱敏 Device/proxy ID 和
时延；这些属于必要路由元数据。不得记录 request body、Authorization、Cookie、完整
query secret 或响应 body。

## 6. 生效配置检查

### 6.1 Nginx

对生产 `nginx -T` 的输出执行只读检查并回传计数：

- 精确允许 `GET /v1/platform/health`；
- 精确允许 `POST /v1/messager/peer/v1/handshakes`；
- 精确允许 `POST /v1/messager/peer/v1/messages`；
- 同路径 GET 仍拒绝，其他 Local API 仍默认拒绝；
- 所有生效 `log_format` 不含 `$request_body`、`$http_authorization`、`$http_cookie`、
  `$upstream_http_set_cookie`；
- 未配置 `mirror`、body debug 或未审计的第三方流量复制。

不得把完整 `nginx -T` 回传；只回传上述断言结果、生效 include 的路径和 SHA-256。

### 6.2 Cloud/Fastify

确认生产镜像对应源码中：

- Fastify 默认请求日志没有序列化 request body；
- `RegistryError` 只返回固定错误码、消息和 request ID；
- 未处理错误日志不会序列化 `request.body`；
- Messager service 的 audit context 与第 4.3 节白名单一致；
- `no-store` 仍用于 challenge、Device Key 和 peer assertion 响应；
- logger serializer/redaction 未被生产环境覆盖成记录 headers/body。

### 6.3 FRPS/plugin/指标

确认：

- FRPS/plugin 不记录 HTTP body、Device Authorization 或 connector secret；
- FRPS Dashboard/usage collector 只采集连接、流量、Device/proxy 和时间元数据；
- 指标 label/name 中没有正文、JWT、proof、challenge、Noise/ciphertext、Authorization、
  Cookie 或任意高基数字段；
- 若没有独立指标系统，明确回传 `not configured`，不能写成“已检查通过”。

## 7. 自动化回归要求

请在 Cloud 工程增加或确认以下测试，测试使用合成 canary，不连接生产：

1. Device Key challenge/登记/幂等/轮换/失败路径的捕获日志中不包含 challenge、proof、
   公钥原文、Authorization 或 secret；
2. peer assertion 成功与拒绝路径的捕获日志和 audit 中不包含 compact JWT；
3. audit context 对 `messager.*` 使用显式字段白名单，并对禁用 key 做负向测试；
4. schema 合同测试证明 challenge 只有 digest、Device Key 只有公钥，无 assertion/
   Noise/E2EE message persistence；
5. Nginx 配置测试证明精确路由与默认拒绝，并拒绝含 request-body/header-secret 的
   `log_format`；
6. 真实 FRP 集成使用唯一明文 canary，经 E2EE 路由后，Cloud/FRPS/Nginx 捕获日志中
   canary 为零，仅 Local 收件端能恢复正文。

这些测试必须只断言敏感值“不出现”，失败输出也不能打印敏感值本身；建议只打印
canary SHA-256 和命中位置类别。

## 8. 最终通过标准

只有同时满足以下条件才能给出 `PASS`：

- 三条 E2EE canary 在 Cloud DB、audit、Cloud/Nginx/FRPS/plugin 日志和指标中均为 0；
- 三个 E2EE clientMessageId 在 `system_messages` 和 Cloud 日志中均为 0；
- offline 对照在 `system_messages` 中恰好 1 条，在日志/audit/指标中为 0；
- challenge 仅存 SHA-256 digest，proof、raw challenge 和 compact JWT 不落库；
- B 的旧 key 为 `rotated`、新 key 为 `active`，不存在两个 active key；
- audit 只含白名单元数据；
- Nginx/FRPS/Cloud 没有 body/header-secret capture；
- 覆盖了当前日志保留范围，无法访问的日志源均明确列为缺口；
- 自动化隐私回归测试通过。

## 9. Cloud 工程回传模板

请将结果写入 Cloud 工程的独立文档，并按以下格式回复：

```text
结论：PASS | FAIL | INCOMPLETE
检查时间：<UTC>
生产应用提交/镜像：<commit, image digest>
生效 Nginx include SHA-256：<sha256>
数据库：
- E2EE plaintext rows: 0
- E2EE clientMessageId rows: 0
- offline control rows: 1
- forbidden audit context rows: 0
- A active/rotated/stale/revoked counts: <counts>
- B active/rotated/stale/revoked counts: <counts>
日志：
- Cloud app: <覆盖时间，4 组 canary/ID/token 检查均为 0>
- Nginx access/error + rotations: <覆盖时间，均为 0>
- FRPS/plugin + rotations: <覆盖时间，均为 0>
- centralized/APM: <结果或 not configured>
配置：
- exact route/default deny: PASS | FAIL
- request body/secret header logging disabled: PASS | FAIL
- traffic mirror/body capture disabled: PASS | FAIL
自动化：<测试数/测试结果>
发现的问题：<仅写类别、计数、脱敏位置，不贴敏感原文>
Compatibility delta：无 | <说明>
生产变更：无（本任务只读）
结果文档：<Cloud repo absolute path>
```

如果发现泄漏，请另提修复方案和数据处置方案，等待批准后再执行；不要在本任务中直接
清理生产证据或轮换其他凭证。
