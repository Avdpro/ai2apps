# 自定义通知 Cloud 接口需求

日期：2026-10-16。状态：需求提案，交 Cloud 项目评审、实现和部署；本文件不表示服务已支持。

基线：通知合同 1.2.0。复用现有 Device 生产者、Native 通知箱、APNs、偏好、授权、限流和持久重试链路。本仓库不修改 Cloud 代码。下面的新字段与能力名称为建议合同，需 Cloud 发布机器合同及客户端交接手册后接入。

## 1. 目标与范围

App / Mini-App 可以发送业务自行编写的标题、正文和点击目标，不必为每个业务场景预先在 Cloud 添加模板。标题和正文可来自业务代码、用户输入或 AI 整理；通知服务不额外调用模型改写或翻译。

系统继续统一负责：生产者身份及 App 发送权限、收件账户、用户预览隐私和静音、纯文本处理、长度限制、幂等、分组、有效期、重试、送达回执及点击目标校验。业务 App 不直接提交 APS 字典或 APNs token，不自己实现通知队列。

本次增加通用自定义事件，保留 intelligence.updated、task.completed 等现有事件。标准业务可以继续使用现有模板。Android 可复用平台无关合同，但本需求不包含 FCM 实现。

## 2. 建议的发送合同

沿用 `POST /api/v1/notifications/events`、现有 Device 身份和 `Idempotency-Key = event_id`。新增 `kind=app.custom`；该 kind 使用 `content`，不需要 `template` 或 `template_params`，也不接受两种展示方式混用。

协议示例仅用于说明字段，实际时间必须来自真实事件：

```json
{
  "schema_version": 1,
  "event_id": "custom-watch-update-run-123",
  "kind": "app.custom",
  "occurred_at": "2026-10-16T02:00:00Z",
  "expires_at": "2026-10-17T02:00:00Z",
  "content": {
    "title": "腕表 · 新增 6 篇情报",
    "body": "BA111OD 发布新表；Mido 更新机芯规格。本轮有一个来源未完成。"
  },
  "target": {
    "type": "app_route",
    "app_id": "ai2apps.intelligence",
    "route": "channel",
    "id": "opaque-channel-id"
  },
  "group_key": "channel-opaque-id",
  "metadata": {
    "run_id": "opaque-run-id",
    "system_task_id": "opaque-system-task-id"
  }
}
```

### 字段和边界

| 字段 | 需求 |
| --- | --- |
| content.title | 必填，自由纯文本；建议规范化后 1–160 Unicode code points。 |
| content.body | 必填，自由纯文本；建议规范化后 1–4,000 code points。通知箱保存完整合法内容，推送可以截短。 |
| content.locale | 可选，BCP 47 内容语言，仅描述文本本身；不覆盖接收设备语言或偏好。缺省保持原文。 |
| target | 必填，使用下文结构化目标；点击目标不是可执行命令。 |
| group_key | 可选，1–160 字符的不透明业务分组键；不能用于选择接收人或授权。缺省按来源 Device + App 分组。 |
| metadata | 仅允许已有或新合同明确列出的不透明追溯字段；本期建议 run_id / system_task_id，沿用 1.2.0 长度限制。不接受任意业务对象或正文副本。 |
| 事件标识、时间 | 沿用现有字符集、生命周期和上限。事件表示一次业务通知，event_id 在业务重试中稳定。 |

标题正文的“自由”指无需固定模板，不代表无限长或富文本。允许正常标点、换行、emoji 和类似 `A < B` 的字面文本；客户端必须以纯文本呈现，不能解析为 HTML、Markdown 链接或脚本。Cloud 统一处理非法 Unicode、控制/方向格式字符、换行与空白，保留 emoji 所需 ZWJ/ZWNJ；规范化后全空或超限返回明确校验错误。正文可保留合理段落换行，不能一律压成一行。

Cloud 为整个请求设置明确字节上限，建议 32 KiB；字符数与字节数分别校验。最终 APNs payload 不超过 4096 字节，计入完整 envelope、分组及 provider 字段，按 grapheme 边界截断正文、必要时再截标题，不拆坏 emoji。通知箱详情保留冻结的完整文本，推送实际文案另保留快照，便于准确追溯。

## 3. 点击目标：自由业务目标，统一路由边界

业务可以指向频道、文章、实体、任务、稿件、Mini-App 页面等，不能要求每新增一种资源就发布一套 Cloud 模板。建议新增以下两个通用 target 类型，并在机器合同中使用互斥分支、拒绝未知字段。

### App 内目标

`type=app_route`，字段为 `app_id`、`route`、`id`。app_id 使用稳定注册身份；route 为 App 声明的稳定路由键，建议 1–80 字符；id 为该路由下的资源标识，建议 1–256 字符。静态页面可约定固定 id，不传文件路径或任意脚本。

Cloud 校验语法、来源 Installation / Device / Owner、发送权限和 App 归属；Local/宿主负责确认请求来自实际有通知权限的 App，Mini-App 经宿主代理发送，不获得 Device credential。不得允许任意 Mini-App 冒充另一个 App 的 app_id。若当前 Cloud 的 Device 合同无法证明 App 注册关系，应明确记录校验责任在受信任宿主，不能声称 Cloud 已验证本地资源 ACL。

客户端/宿主通过注册路由表解析 route；由当前已鉴权会话加载资源并再次校验权限。新增 App 路由可随 App 的能力声明交付，Cloud 不维护逐业务跳转白名单。通知目标仅是定位提示，不是授权凭据。

点击前先使用当前 Native 账户读取通知 detail，然后定位 source_device_id 对应的 Desktop，再进入已授权 App 路由。设备离线、资源删除、账户不匹配、路由不支持时清楚提示；不能退到另一个账户、另一台 Desktop 或另一条资源来伪装成功。旧客户端可以保留并查看通知，不能把未知目标直接当 URL 打开。

### 网页目标

`type=https_url`，字段为 `app_id`、`url`，与 app_route 字段互斥。允许普通 HTTPS 网页，不要求每个域名都预建业务模板。建议 URL 最大 2,048 字符；拒绝 username/password、非法编码、控制字符以及 javascript/data/file/自定义脚本 scheme。凭据、一次性交接 token 不应写入通知 URL。

Cloud 只校验和存储目标，**不抓取 URL、预加载预览或跟随重定向**。点击时先鉴权取得 detail，再由客户端用系统浏览器打开外部网站；不得向它转发 Native Bearer、Device credential 或 Local 登录态。不把目标拼接成 JavaScript，不借通知触发 Local API、提交表单、执行 Shell 或自动操作。iOS 原生凭据始终只发给既有固定 Cloud 接口。

如果 Cloud 希望第一阶段仅实现 app_route，应在能力中明确不支持 https_url，客户端保留外链目标功能关闭；不能默默接收后丢弃点击行为。完整需求包含两类目标。

## 4. 系统统一的隐私与偏好

自定义文本不能绕过当前的 `preview_mode`、kind 静音、设备开关、账户开关或 iOS 系统预览控制。

| 当前预览模式 | 自定义通知锁屏表现 |
| --- | --- |
| generic | 使用系统本地化固定标题/正文，例如“AI2Apps / 有一条新通知，打开应用查看”。不显示自定义标题、正文、资源 ID、分组键或目标 URL。 |
| channel_only | 该设置现有含义为频道安全预览。自定义通知没有经系统定义的频道参数，默认同 generic；如可从可信 App 注册资料取得 App 名，允许仅显示该 App 名与固定提示。不能把自由标题当频道名。 |
| rich | 显示自定义标题、正文的推送快照；仍遵守系统隐藏预览设置。 |

本期不接受生产者自报 `safe_title` / `safe_body` 来获得 channel_only 展示，也不允许 `privacy=public`、`force_rich` 等字段绕过用户设置。将来要支持安全摘要，须另定义可验证语义和能力。

现有 generic、channel_only、rich 偏好均保持不变，不因合同升级自动改成 rich。新增 app.custom 应遵守现有 kind 缺省策略，不主动覆盖用户静音。iOS 修改偏好仍使用 GET 返回的 ETag + If-Match，保留未改动的 enabled/kinds/devices 等字段。

内容在入队时冻结；实际投递前仍按**当前**接收设备/账户权限、预览偏好和静音规则生成或选择可投递表现。入队后用户改成 generic 或关闭通知，重试不能继续发送此前已渲染的 rich 内容。保存最终推送快照用于审计，不以“冻结”为由绕过后来收紧的隐私设置。已送达的锁屏内容不能承诺追溯撤回。

通知箱在 Native 身份验证通过后可以展示完整冻结文本；锁屏模式不等同于通知箱内容删除。不同语言的系统固定文案按既有 binding.locale 策略选择，自定义文本不自动翻译。

## 5. 统一幂等、快照与分组

1. Local 在业务成功持久化后生成通知意图，将标题、正文、点击目标、group_key 和追溯引用冻结，再进入宿主持久 outbox。业务与通知库不在同一事务时，使用稳定业务事件 ID 对账关闭崩溃窗口。
2. Cloud 延续现有 event_id / Idempotency-Key 去重命名空间及身份边界。不能按标题或正文相同来去重：两次独立业务事件可能有相同文案。
3. 相同 event_id、相同规范化业务内容重试，返回原 notification_id，不新增 inbox 记录或重复安排投递。相同 ID 但标题、正文、目标、分组、元数据或其他冻结字段不同，返回现有 `409 NOTIFICATION_IDEMPOTENCY_CONFLICT`。保留既有时间/身份比较语义并在新机器合同中明确。
4. 网络超时、重启、凭据轮转等沿用原 outbox/身份恢复规则；不能生成新 ID 掩盖不确定结果，不能把新事件降级改写后用同 ID 重试。Cloud 202 只表示已入库或去重，不表示手机已收到。
5. group_key 仅用于展示分组，不是去重键。系统按 Device + App + group_key 派生稳定不可逆 thread-id；APS 不暴露原始业务分组键、资源 ID 或 URL。不同 Device / App 的相同分组键互不串组。
6. 沿用当前有效期、限流、持久重试退避、过期与清理策略。幂等记录保留至少覆盖既有最大有效期及重试窗口；过期重复请求不得导致重新推送。Provider 的模糊响应可能产生传输层重复，不能承诺端到端绝对 exactly-once；客户端继续按 notification_id 去重。

## 6. 能力协商与兼容

继续使用现有 producer-policy 与 Native capabilities。Cloud 发布新合同版本，不预设其最终版本号。建议显式公布 app.custom、content schema 版本、允许的 target 类型、字段长度/字节上限、预览行为和分组支持。例如：

```json
{
  "kind": "app.custom",
  "version": 1,
  "content_fields": ["title", "body", "locale"],
  "target_types": ["app_route", "https_url"],
  "privacy_policy": "system_preview_v1",
  "grouping": true
}
```

最终能力对象及精确匹配规则由 Cloud 机器合同确定；以上不是当前服务响应。Local 只在 enabled 和当前身份/epoch 校验通过、且声明所需能力时入队。未知能力时明确功能不可用，或在**首次入队前**选择已有且语义适用的标准事件；不能把任意内容塞进旧模板字段。已冻结事件原样重试，不补发历史通知。

上线顺序：Cloud 合同和兼容存储 → iOS 支持新 kind/target/展示 → Local 宿主生产入口与 App 权限代理。不得先让旧 iOS 收到它无法识别的新事件。Cloud 不需为每个 App 的自定义文案新增模板或逐业务部署。

## 7. 通知箱、回执与错误

沿用 inbox/list/detail/read/receipts。新事件 detail 返回冻结 content、target、group_key（仅鉴权后）、允许的 metadata，以及与最终推送一致的投递文案；可复用现有 display 或发布清晰的新字段，不让客户端自行猜测多语言和截断结果。列表返回足够的标题与正文摘要，避免逐条请求才能显示。

APNs 自定义 envelope 继续只传 version、notification_id、source_device_id、kind；自由正文、URL 和业务路由引用不另放到 envelope，rich 模式的可见 APS 文案除外。点击后通过鉴权 detail 取完整目标。received / opened / read 分开记录，成功打开后更新相应状态；客户端进入通知详情不等于目标业务页面已成功打开，两种行为要可区分。

沿用既有身份、权限、限流、幂等冲突和过期错误。新增字段校验/不支持的 target 应返回稳定机器错误码及字段路径，不回显完整敏感正文。未知 kind、content 与 template 混用、缺少目标、超限都不能静默接收或降级。日志/指标不得记录原始标题正文、目标 URL、token；按 event_id、notification_id 和错误类别排查。

## 8. Cloud 交付物与验收

Cloud 项目需要交付：更新后的 OpenAPI、独立事件 JSON Schema、producer-policy / Native capabilities 实际样例、错误码、隐私映射、幂等比较与保留语义、分组算法边界、回退规则，以及面向 Local/iOS 的客户端交接手册。部署回执区分模拟 provider 测试与真实设备证据。

验收至少覆盖：

- 同一接口接收不同 App 的自由标题/正文，无新增业务模板；正常中文、英文、换行、emoji 和字面尖括号纯文本呈现。
- 长度、字节数、非法 Unicode、无效 target / scheme、未知字段、未经授权的 App 发送被拒绝；APNs 完整 payload 不超限，通知箱保留完整合法正文。
- generic / channel_only 均不泄露自定义内容，rich 正确显示；入队后关闭通知或收紧预览偏好，重试执行新偏好。修改偏好保留现有静音和设备配置。
- 相同事件重试、重启、响应丢失仅产生一条 inbox 通知；改标题/正文/target/group_key 返回冲突；同文案不同事件可以分别通知；分组不引起去重。
- App route 能打开频道、文章和另一 App 的合法页面；外部 HTTPS 交系统浏览器；离线、删除、无权限、未知路由均不跨设备/账户回退，且不执行目标隐含的操作。
- 旧 1.2.0 标准事件与冻结 outbox 不变；旧客户端/旧 Cloud 能力不足时安全提示；现有 OAuth/PKCE/自动 handoff 和 Owner 隔离无回归。
- 真实 iPhone 验收锁屏、通知箱、点击正确目标以及 received/opened/read；202、provider accepted 和模拟推送不替代实际送达证据。

本阶段只交付需求文档。Cloud、Local、iOS 的新自定义事件接口实现、部署和真机验收由后续接入任务完成。
